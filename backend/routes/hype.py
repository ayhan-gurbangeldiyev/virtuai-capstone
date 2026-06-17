"""Hype Crew user-facing API.

Endpoints for the TypeHype frontend to manage Hype Crew auto-drafts:

  GET    /hype/drafts/auto                — list pending auto-drafts for current user
  POST   /hype/drafts/{draft_id}/approve  — approve (keep Postiz schedule)
  POST   /hype/drafts/{draft_id}/reject   — reject (cancel Postiz, log feedback to memory)
  POST   /hype/drafts/{draft_id}/edit     — edit content + log diff to memory
  GET    /hype/config/{account_id}        — get hype_account_config
  PATCH  /hype/config/{account_id}        — update hype_account_config

Auth: standard `require_auth` + account_id ownership check.
Memory: every approve/reject/edit writes to hype_memory for the learning loop.
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal, NamedTuple
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from pydantic import BaseModel, Field

from middleware.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hype", tags=["hype"])


def get_supabase():
    from server import supabase
    return supabase


# ─── Models ────────────────────────────────────────────────────────────────


class RejectRequest(BaseModel):
    category: Literal[
        # Current descriptive set — these are what the UI sends today.
        "too_long",
        "too_short",
        "tone_too_harsh",
        "tone_too_soft",
        "tone_too_corporate",
        "sounds_like_ai",
        "misread_trend",
        "shallow_insight",
        "weak_hook",
        "inaccurate",
        "already_posted",
        "off_voice",
        "other",
        # Legacy values still accepted so old clients / replays don't error.
        "tone_off",
        "wrong_topic",
        "low_quality",
        "off_brand",
    ] = "other"
    feedback: Optional[str] = Field(None, max_length=2000)
    # Phase 28 Fix 3 — image/text feedback split
    # text  → only the wording is bad (image is fine); Strategist learns from this
    # image → only the visual is bad (text is fine); Visual Director learns
    # both  → both are bad; both subsystems learn
    rejection_target: Literal["text", "image", "both"] = "both"
    image_rejection_reason: Optional[Literal[
        "deformed_hand",     # extra/melted fingers, floating nails
        "fake_logo",         # fake Apple/Nvidia logo on laptop
        "off_brand",         # doesn't fit Cansu's visual identity
        "aesthetic_poor",    # composition / lighting / colors weak
        "ai_obvious",        # too synthetic, plastic skin, uncanny
        "wrong_scene",       # scene type mismatch (e.g. crowded café when prompt said home office)
        "identity_drift",    # face doesn't look like Cansu
        "other",
    ]] = None


# ─────────────────────────────────────────────────────────────────────
# Phase 43.C — Video reject (Reject path 3: text / image / video)
# ─────────────────────────────────────────────────────────────────────
# Mirrors RejectRequest but with video-specific reasons. Distinct
# endpoint instead of overloading /reject because the worker dispatch
# is different (HeyGen split-screen pipeline vs Wiro nano-banana),
# and approve-state semantics are different (video_regen_pending
# blocks approve until the queue worker writes regen_done).
class RejectVideoRequest(BaseModel):
    feedback: Optional[str] = Field(None, max_length=2000)
    video_rejection_reason: Optional[Literal[
        "off_voice",          # MiniMax voice doesn't sound like Cansu
        "lipsync_drift",      # mouth movement off vs audio
        "uncanny_motion",     # HeyGen Avatar V motion stutter / weird gestures
        "wrong_look",         # photar look mismatch — wardrobe / setting wrong
        "subtitle_mismatch",  # burn-in captions wrong text or position
        "image_overlay_off",  # split-screen top half visual mismatch
        "audio_quality",      # MP3 artifacts, distortion, wrong volume
        "ai_obvious",         # too synthetic / uncanny valley
        "other",
    ]] = None
    # Worker overrides — let the user steer the regen directly. Same
    # shape as RegenImageRequest so the worker can read both via the
    # video_params JSONB column. Empty = worker picks fresh randomly.
    override_look_id: Optional[str] = Field(None, max_length=128)
    override_voice_id: Optional[str] = Field(None, max_length=128)
    override_script_text: Optional[str] = Field(None, max_length=2000)


class EditRequest(BaseModel):
    edited_content: str = Field(..., min_length=1, max_length=4000)
    feedback: Optional[str] = Field(None, max_length=2000)
    # Phase 43.A — multi-field edit capture. JSON patch shape so caller
    # can edit text + scene + composition simultaneously in one request.
    # All keys are optional; the worker / approve flow reads whichever
    # are present. Backward-compatible with single-field text edits
    # (clients that only set `edited_content` keep working).
    edit_fields: Optional[dict] = Field(
        default=None,
        description=(
            "Optional JSON patch: any of "
            "{text_content, scene_description, composition_type, voice_mode}"
        ),
    )


class ApproveRequest(BaseModel):
    """Phase 43.A — optional edit_token race-condition guard.

    When the client edits a draft, it receives back an `edit_token`.
    Sending that token on the next /approve call ensures no other
    edit landed between read and approve. Empty token = no check
    (backward-compatible with all current callers).
    """
    edit_token: Optional[str] = Field(default=None, max_length=64)


class ConfigUpdate(BaseModel):
    identity_card: Optional[str] = None
    voice_description: Optional[str] = None
    topics_focus: Optional[list[str]] = None
    forbidden_topics: Optional[list[str]] = None
    watch_accounts: Optional[list[str]] = None
    reactive_enabled: Optional[bool] = None
    reactive_triggers: Optional[list[str]] = None
    follower_goal: Optional[int] = None
    posting_cadence: Optional[str] = None
    daily_post_quota: Optional[int] = Field(None, ge=0, le=20)
    auto_publish_enabled: Optional[bool] = None
    dry_run_mode: Optional[bool] = None
    active_style_profile_id: Optional[str] = None  # Phase 17.2: user-selected style for Hype Crew
    # Tier 3 — daily $ cap for the hourly Hype Crew runs (covers TrendScout +
    # Strategist + Writer + Compliance LLM + Wiro image gen). The video
    # pipeline has its own separate cap on personas.daily_video_budget_usd.
    daily_cost_cap_usd: Optional[float] = Field(None, ge=0, le=20)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _verify_account_ownership(account_id: str, user_id: str) -> dict:
    """Phase 28.M — Verify caller can access this account: either as owner
    OR as an accepted workspace collaborator. Returns the connected_accounts row."""
    from services.access_control import accessible_owner_ids
    sb = get_supabase()
    result = (
        sb.table("connected_accounts")
        .select("id, user_id, platform, username, postiz_integration_id")
        .eq("id", account_id)
        .in_("user_id", accessible_owner_ids(user_id))
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="account not found or unauthorized")
    return result.data[0]


def _verify_draft_ownership(draft_id: str, user_id: str) -> dict:
    """Phase 28.M — Verify caller can access this draft via workspace membership."""
    from services.access_control import accessible_owner_ids
    sb = get_supabase()
    result = (
        sb.table("daily_drafts")
        .select("*")
        .eq("id", draft_id)
        .in_("user_id", accessible_owner_ids(user_id))
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="draft not found or unauthorized")
    return result.data[0]


def _save_memory(
    account_id: str,
    memory_type: str,
    content: str,
    metadata: Optional[dict] = None,
    importance: float = 0.7,
    scope_tag: Optional[str] = None,
):
    """Insert hype_memory row. Mirrors hype_crew/tools/memory_tools.py
    save_memory_entry — including Phase 43.B.3's `scope_tag` auto-derivation.

    `scope_tag` controls visibility to the Strategist / Writer / Visual
    Director:
      · 'draft_only'  (default for editor_diffs) → hidden from agent ctx
      · 'trend_type'  → visible to that content_type cluster only
      · 'global'      → persona-wide (default for everything else)

    Without this auto-set, downstream filters in
    hype_crew/tools/memory_tools.py:_is_scope_visible would silently
    treat every row as 'global' (legacy fallback), defeating Critic's
    overfitting protection on editor_diffs.
    """
    sb = get_supabase()

    # Derive the default scope_tag from memory_type unless the caller
    # forced one. editor_diffs default to 'draft_only' (Critic's fix);
    # every other memory_type defaults to 'global'.
    effective_tag = scope_tag
    if effective_tag is None:
        effective_tag = "draft_only" if memory_type == "editor_diffs" else "global"

    # Merge into metadata. We preserve any existing 'scope_tag' the caller
    # provided in metadata so Phase 43.B-era callers that set it directly
    # (memory_tools-style) still win.
    md = dict(metadata or {})
    md.setdefault("scope_tag", effective_tag)

    sb.table("hype_memory").insert({
        "account_id": account_id,
        "memory_type": memory_type,
        "scope": f"/account/{account_id}/{memory_type.replace('_', '-')}",
        "content": content,
        "metadata": md,
        "importance_score": importance,
    }).execute()


# 2026-06-07 (Part 3) — quality-signal classification thresholds.
# The thresholds are intentionally coarse-grained; they exist so
# /control's "approve-on-quality rate" stops being silently 0. The
# operator can override per-row later via PATCH (UI work TBD).
_QUALITY_REJECTION_CATEGORIES = {
    "sounds_like_ai",
    "shallow_insight",
    "off_voice",
    "ton_steril_ai_kelime",
    "yapi_sorunu_ozet_yorum",
    "tone_too_corporate",
    "haber_yanlis_aktarim",
}


def _classify_quality(
    action: str,
    rejection_category: Optional[str],
    original_content: Optional[str],
    edited_content: Optional[str],
) -> tuple[Optional[int], Optional[str]]:
    """Return (edit_distance_chars, operator_quality_verdict).

    Rules (operator can override later via PATCH):
      - rejected with a quality-class category → ('discarded_quality')
      - approved with no edits OR equal content → ('publishable_as_is')
      - approved with low edit distance (<= 40 chars OR <= 15% of len)
        → ('needed_minor_edit')
      - approved with higher edit distance → ('needed_major_edit')
      - any non-quality reject (manually_cancelled, other) → None
        (leave the column NULL so the rate computation ignores it).
    """
    if action == "rejected" and rejection_category in _QUALITY_REJECTION_CATEGORIES:
        return (None, "discarded_quality")
    if action != "approved":
        return (None, None)

    orig = original_content or ""
    edit = (edited_content if edited_content is not None else orig) or ""
    if orig == edit:
        return (0, "publishable_as_is")

    # difflib's SequenceMatcher gives a coarse char-level distance suitable
    # for our threshold purpose. We don't need cryptographic precision.
    try:
        import difflib as _difflib  # stdlib
        sm = _difflib.SequenceMatcher(a=orig, b=edit, autojunk=False)
        # ratio() returns similarity 0..1; convert to edit-distance-ish
        # by (1 - ratio) * max(len). This is monotonic with Levenshtein
        # but cheaper.
        dist = int(round((1.0 - sm.ratio()) * max(len(orig), len(edit), 1)))
    except Exception:
        dist = abs(len(orig) - len(edit))

    denom = max(len(orig), 1)
    pct = dist / denom
    if dist <= 40 or pct <= 0.15:
        return (dist, "needed_minor_edit")
    return (dist, "needed_major_edit")


def _log_feedback(
    *,
    run_id: Optional[str],
    account_id: str,
    user_id: str,
    action: str,
    draft_id: Optional[str] = None,                   # Phase 28.H: per-draft attribution
    rejection_category: Optional[str] = None,
    free_text: Optional[str] = None,
    original_content: Optional[str] = None,
    edited_content: Optional[str] = None,
    content_diff: Optional[dict] = None,
    rejection_target: Optional[str] = None,           # Phase 28: 'text'|'image'|'both'
    image_rejection_reason: Optional[str] = None,     # Phase 28: deformed_hand|fake_logo|...
):
    sb = get_supabase()
    # Part 3 (2026-06-07) — compute quality signal at write time so the
    # rolling view v_cansu_quality_acceptance can answer Berkay's question
    # ("is Cansu writing GOOD editorial?") without re-scanning content.
    edit_distance_chars, operator_quality_verdict = _classify_quality(
        action=action,
        rejection_category=rejection_category,
        original_content=original_content,
        edited_content=edited_content,
    )
    sb.table("hype_feedback").insert({
        "run_id": run_id,
        "draft_id": draft_id,
        "account_id": account_id,
        "user_id": user_id,
        "action": action,
        "rejection_category": rejection_category,
        "free_text_feedback": free_text,
        "original_content": original_content,
        "edited_content": edited_content,
        "content_diff": content_diff,
        "rejection_target": rejection_target,
        "image_rejection_reason": image_rejection_reason,
        "edit_distance_chars": edit_distance_chars,
        "operator_quality_verdict": operator_quality_verdict,
    }).execute()


def _cancel_postiz(postiz_post_id: Optional[str]) -> bool:
    """Best-effort Postiz cancel (DRY_RUN_ ids skipped)."""
    if not postiz_post_id or postiz_post_id.startswith(("DRY_RUN_", "ERROR_", "UNKNOWN_")):
        return False
    try:
        import os, httpx
        api_key = os.environ.get("POSTIZ_API_KEY", "")
        if not api_key:
            return False
        base = os.environ.get("POSTIZ_BASE_URL", "https://api.postiz.com/public/v1").rstrip("/")
        with httpx.Client(timeout=15.0) as client:
            r = client.delete(f"{base}/posts/{postiz_post_id}", headers={"Authorization": api_key})
            return r.status_code in (200, 204)
    except Exception as e:
        logger.warning(f"Postiz cancel failed for {postiz_post_id}: {e}")
        return False


def _arm_publish_verifier(post_ids: list[str], scheduled_at_dt) -> None:
    """Auto-arm a per-platform publish verifier ~5-10 min after the scheduled
    publish time. Spawns a one-shot systemd-run transient service that runs
    `hype_crew/scripts/verify_publish.py` and updates the DB on per-platform
    failure (via the script's own DB write path).

    Audit 6 Haz 2026 follow-up: replaces the manual one-off systemd-run.
    Every successful schedule path now arms its own verifier so "scheduled"
    reliably becomes "verified published" without the 6 h reconciler blind
    spot.

    Best-effort: failure here must NEVER fail the approve route.
    """
    if not post_ids:
        return
    try:
        ids_csv = ",".join(p for p in post_ids if isinstance(p, str)
                            and not p.startswith(("DRY_RUN_", "ERROR_", "UNKNOWN_")))
        if not ids_csv:
            return
        # Wait until scheduled_at + 5 min (so Postiz has had time to publish)
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        fire_at = scheduled_at_dt + _td(minutes=5)
        # systemd-run accepts --on-calendar with a Calendar event spec
        fire_at_str = fire_at.astimezone(_tz.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        unit_name = f"verify-publish-{_dt.now(_tz.utc).strftime('%H%M%S')}-{ids_csv[:8]}"
        import subprocess
        subprocess.Popen(
            [
                "systemd-run",
                "--on-calendar", fire_at_str,
                "--unit", unit_name,
                "/opt/hype-crew/venv/bin/python",
                "/opt/hype-crew/scripts/verify_publish.py",
                "--post-ids", ids_csv,
                "--max-minutes", "12",
                "--poll-sec", "20",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        logger.info(
            f"[verify-arm] systemd-run unit={unit_name} fires at "
            f"{fire_at_str} for {len(post_ids)} post_id(s)"
        )
    except Exception as e:
        logger.warning(f"[verify-arm] failed (non-fatal, won't block approve): {e!r}")


# SEV-1 follow-up P0 (2026-06-07) — video integrity check helper.
# Returns (is_defective, reason). Reads the render-time verdict written
# by the video pipeline / regen worker. Default policy:
#   video_integrity_ok IS NULL    → soft-pass (legacy / not yet probed)
#   video_integrity_ok IS FALSE   → refuse (truncated / malformed)
#   video_integrity_ok IS TRUE    → pass
def _video_integrity_defective(draft: dict) -> tuple[bool, Optional[str]]:
    if not draft.get("video_url"):
        return (False, None)
    ok = draft.get("video_integrity_ok")
    if ok is False:
        return (True, draft.get("video_integrity_reason") or "video_integrity_ok=false")
    return (False, None)


# SEV-1 P0 fix (2026-06-07) — video↔content binding helper.
# Returns (is_stale, reason). Single source of truth used by approve_draft
# and approve_thread so the rule stays identical on both paths.
def _video_out_of_sync(draft: dict) -> tuple[bool, Optional[str]]:
    """Returns (True, reason) when the draft has a video that does NOT
    match its current content. Returns (False, None) otherwise. Two
    independent signals:
      1. video_stale flag (set by edit_draft when content's sha changes
         after a render).
      2. live recomputation of sha256(content) vs stored video_content_sha
         (catches the case where someone updated content via raw SQL,
         bypassing edit_draft).
    """
    if not draft.get("video_url"):
        return (False, None)
    if draft.get("video_stale"):
        return (True, "video_stale flag set")
    stored = draft.get("video_content_sha")
    if stored is None:
        # Pre-binding render — we can't verify. Soft-pass: log + allow.
        # The binding column was added 2026-06-07; older videos won't
        # carry it. New ones do.
        return (False, None)
    import hashlib as _hl
    live = _hl.sha256((draft.get("content") or "").encode("utf-8")).hexdigest()
    if live != stored:
        return (
            True,
            f"content sha changed since render "
            f"(rendered={stored[:12]}…, current={live[:12]}…)",
        )
    return (False, None)


def _diff_words(original: str, edited: str) -> dict:
    """Cheap word-level diff (added/removed sets). For semantic learning."""
    import re
    orig_words = set(re.findall(r"\b\w+\b", (original or "").lower()))
    new_words = set(re.findall(r"\b\w+\b", (edited or "").lower()))
    return {
        "added": sorted(new_words - orig_words),
        "removed": sorted(orig_words - new_words),
        "original_length": len(original or ""),
        "edited_length": len(edited or ""),
    }


# ─── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/drafts/auto")
async def list_auto_drafts(
    account_id: Optional[str] = Query(None),
    status: str = Query("pending"),
    platform: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(require_auth),
):
    """List Hype Crew auto-generated drafts for the current user.

    Default: drafts awaiting user review (status='pending', source='hype_auto').
    Filter by account_id to scope to a single connected account.
    Phase 20: ``platform`` filter (twitter|linkedin|devto|instagram|youtube) +
    response carries ``content_thread_id`` so the UI can group multi-platform
    variants of the same trend.
    """
    from services.access_control import accessible_owner_ids
    sb = get_supabase()
    q = (
        sb.table("daily_drafts")
        .select(
            "id, user_id, account_id, trend_id, content, platform, status, source, "
            "trend_topic, insight, hype_run_id, scheduled_at, postiz_post_id, "
            "created_at, image_url, image_asset_id, persona_id, content_thread_id, "
            # Phase 35.2 — video fields (NULL for image-only drafts)
            "video_url, video_thumbnail_url, video_duration_sec, "
            "heygen_video_id, youtube_video_id, "
            # Phase 43.B.5 — composite confidence (sample-weighted 30d reject rate)
            # Phase 25.B/C — content_type + voice_mode surfaced for UI grouping
            "confidence_score, content_type, voice_mode"
        )
        .in_("user_id", accessible_owner_ids(user.id))  # Phase 28.M
        .eq("source", "hype_auto")
        # 2026-06-10 — soft-delete edilen draftlar (reaper yetimleri,
        # temizlik kayıtları) listelenmez; UI eski yarım setleri
        # göstermeye devam ediyordu.
        .is_("deleted_at", "null")
        # Pending tab is dominated by pending_review rows (scheduled_at=NULL).
        # Ordering by scheduled_at ASC NULLS LAST pushes pending_review to the
        # tail and silently truncates them at limit=200 — exactly the rows the
        # user needs to act on. Sort by created_at DESC so the freshest review
        # items always surface first.
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status and status != "all":
        # Phase 28.C — 'pending' tab now also surfaces 'pending_review' drafts
        # (those waiting for user approval before Postiz schedule fires).
        if status == "pending":
            q = q.in_("status", ["pending", "pending_review"])
        # Phase 28.R-Lite-V2 — approved tab unifies modern 'approved' (set by
        # /approve endpoint Phase 28.C onward) and legacy 'auto_approved'
        # (older rows). Without this, approve tab was empty even after
        # approving drafts, and users could not find them to cancel.
        elif status in ("approved", "auto_approved"):
            q = q.in_("status", ["approved", "auto_approved"])
        # Rejected tab same unification.
        elif status in ("rejected", "auto_rejected"):
            q = q.in_("status", ["rejected", "auto_rejected"])
        else:
            q = q.eq("status", status)
    if account_id:
        _verify_account_ownership(account_id, user.id)
        q = q.eq("account_id", account_id)
    if platform and platform != "all":
        q = q.eq("platform", platform)
    result = q.execute()
    drafts = result.data or []

    # Phase 17.3 — enrich with source metadata (single batch JOIN on trends)
    trend_ids = [d["trend_id"] for d in drafts if d.get("trend_id")]
    if trend_ids:
        trends_rows = (
            sb.table("trends")
            .select("id, url, source_name, source_type, raw_content")
            .in_("id", trend_ids)
            .execute()
        )
        trends_map = {t["id"]: t for t in (trends_rows.data or [])}
        for d in drafts:
            t = trends_map.get(d.get("trend_id"))
            if t:
                snippet = (t.get("raw_content") or "")
                d["source_meta"] = {
                    "url": t.get("url"),
                    "name": t.get("source_name"),
                    "type": t.get("source_type"),
                    "snippet": snippet[:300] + ("…" if len(snippet) > 300 else ""),
                }

    # Phase 21 — enrich with persona_assets compliance scores when an image is linked
    asset_ids = [d["image_asset_id"] for d in drafts if d.get("image_asset_id")]
    if asset_ids:
        asset_rows = (
            sb.table("persona_assets")
            .select(
                "id, clip_persona_similarity, aesthetic_score, ocr_flagged, "
                "llm_judge_verdict, llm_judge_reasoning, compliance_passed, "
                "provider_model_slug, generation_cost_usd, status"
            )
            .in_("id", asset_ids)
            .execute()
        )
        assets_map = {a["id"]: a for a in (asset_rows.data or [])}
        for d in drafts:
            a = assets_map.get(d.get("image_asset_id"))
            if a:
                d["image_meta"] = {
                    "asset_id": a["id"],
                    "model": a.get("provider_model_slug"),
                    "clip_similarity": a.get("clip_persona_similarity"),
                    "aesthetic_score": a.get("aesthetic_score"),
                    "ocr_flagged": a.get("ocr_flagged"),
                    "llm_verdict": a.get("llm_judge_verdict"),
                    "llm_reasoning": a.get("llm_judge_reasoning"),
                    "compliance_passed": a.get("compliance_passed"),
                    "cost_usd": float(a.get("generation_cost_usd") or 0),
                    "status": a.get("status"),
                }

    # Phase 28.H — per-draft feedback timeline (who approved/rejected/edited)
    draft_ids = [d["id"] for d in drafts]
    if draft_ids:
        fb_rows = (
            sb.table("hype_feedback")
            .select(
                "draft_id, user_id, action, rejection_category, rejection_target, "
                "image_rejection_reason, free_text_feedback, created_at"
            )
            .in_("draft_id", draft_ids)
            .order("created_at", desc=False)
            .execute()
        )
        fb_data = fb_rows.data or []
        # Resolve user_id → email via Supabase Auth Admin API (PostgREST does
        # NOT expose the `auth` schema — Phase 28.H regression fixed here).
        user_ids = {r["user_id"] for r in fb_data if r.get("user_id")}
        user_email_map: dict[str, str] = {}
        if user_ids:
            try:
                page = sb.auth.admin.list_users()
                items = page if isinstance(page, list) else getattr(page, "users", []) or []
                for u in items:
                    uid = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
                    if uid in user_ids:
                        email = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
                        user_email_map[uid] = email or ""
            except Exception as e:
                logger.warning(f"[hype/list] auth.admin.list_users() failed: {e}")
        fb_by_draft: dict[str, list] = {}
        for r in fb_data:
            d_id = r.get("draft_id")
            if not d_id:
                continue
            fb_by_draft.setdefault(d_id, []).append({
                "user_id": r.get("user_id"),
                "user_email": user_email_map.get(r.get("user_id") or "", ""),
                "action": r.get("action"),
                "rejection_category": r.get("rejection_category"),
                "rejection_target": r.get("rejection_target"),
                "image_rejection_reason": r.get("image_rejection_reason"),
                "free_text_feedback": r.get("free_text_feedback"),
                "created_at": r.get("created_at"),
            })
        for d in drafts:
            d["feedback_events"] = fb_by_draft.get(d["id"], [])

    # Phase 28.P — attach iteration chain so frontend Stacked Chat UI can
    # hydrate v1..vN history without an extra round trip per draft.
    if draft_ids:
        it_rows = (
            sb.table("draft_iterations")
            .select("draft_id, version, content, status, rejection_category, "
                    "rejection_feedback, image_rejection_reason, rejection_target, "
                    "rejected_by, rejected_at, approved_at, tokens_used, cost_usd, "
                    "created_at")
            .in_("draft_id", draft_ids)
            .order("version", desc=False)
            .execute()
        )
        it_by_draft: dict[str, list] = {}
        for r in (it_rows.data or []):
            it_by_draft.setdefault(r["draft_id"], []).append({
                "version": r.get("version"),
                "content": r.get("content"),
                "status": r.get("status"),
                "rejection_category": r.get("rejection_category"),
                "rejection_feedback": r.get("rejection_feedback"),
                "image_rejection_reason": r.get("image_rejection_reason"),
                "rejection_target": r.get("rejection_target"),
                "rejected_by": r.get("rejected_by"),
                "rejected_at": r.get("rejected_at"),
                "approved_at": r.get("approved_at"),
                "tokens_used": r.get("tokens_used"),
                "cost_usd": r.get("cost_usd"),
                "created_at": r.get("created_at"),
            })
        for d in drafts:
            d["iterations"] = it_by_draft.get(d["id"], [])

    return {"items": drafts, "count": len(drafts)}


@router.post("/drafts/{draft_id}/cancel-approval")
async def cancel_approval(draft_id: str, user=Depends(require_auth)):
    """Phase 28.R-Lite-V2 — Cancel a previously-approved draft.

    Use case: user clicked Onayla by mistake. The draft is now status='approved'
    with a Postiz scheduled post (typically +2h). They want it gone.

    Flow:
      - If scheduled_at is still in the future → Postiz cancel + flip status to
        'auto_rejected'. The post never publishes.
      - If scheduled_at already passed (post is live) → cannot recall from
        social platforms. Return 409 with guidance to delete manually.

    Side effects:
      - Postiz DELETE /posts/{postiz_post_id} (best-effort)
      - daily_drafts.status = 'auto_rejected'
      - hype_feedback: action='rejected' with category='manually_cancelled'
      - hype_memory.rejected_drafts: NO write (text was approved-quality;
        we don't want to teach the Strategist this angle was bad)
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    current_status = draft.get("status")
    if current_status not in ("approved", "auto_approved", "published", "auto_scheduled"):
        raise HTTPException(
            400,
            f"draft is not in an approved state (current: {current_status}) — "
            "use /reject for pending drafts",
        )

    # Window check: if scheduled_at is in the past, the post likely already
    # published on the social platform. We can't recall it from here.
    scheduled_at_str = draft.get("scheduled_at")
    if scheduled_at_str:
        try:
            scheduled_dt = datetime.fromisoformat(scheduled_at_str.replace("Z", "+00:00"))
            if scheduled_dt < datetime.now(timezone.utc):
                # Past-window: still try Postiz cancel as best-effort (some
                # providers allow recall up to publish time), but if the post
                # is live we surface the limit to the user.
                pid = draft.get("postiz_post_id")
                cancelled = False
                if pid and not pid.startswith(("DRY_RUN_", "PENDING_")):
                    cancelled = _cancel_postiz(pid)
                if not cancelled:
                    raise HTTPException(
                        409,
                        f"already_published: scheduled_at={scheduled_at_str} is in the past. "
                        "Postiz could not cancel — the post is live on the platform. "
                        "Delete it manually from the social account.",
                    )
        except (ValueError, TypeError):
            # Bad timestamp — fall through to normal cancel path
            pass

    # Normal future-window cancel: kill Postiz schedule, flip status.
    pid = draft.get("postiz_post_id")
    if pid and not pid.startswith(("DRY_RUN_", "PENDING_")):
        _cancel_postiz(pid)

    sb.table("daily_drafts").update({
        "status": "auto_rejected",
        "postiz_post_id": None,
    }).eq("id", draft_id).execute()

    # Log to hype_feedback so it counts in the rejected-this-week stat.
    # Do NOT write to hype_memory.rejected_drafts: the user actually
    # liked the content (they approved it); they just changed their mind.
    # Teaching Strategist this angle was bad would poison future selection.
    _log_feedback(
        run_id=draft.get("hype_run_id"),
        draft_id=draft_id,
        account_id=draft["account_id"],
        user_id=user.id,
        action="rejected",
        rejection_category="manually_cancelled",
        free_text="Onaylanan draft kullanıcı tarafından iptal edildi",
        original_content=draft["content"],
        rejection_target="text",
        image_rejection_reason=None,
    )

    return {
        "status": "cancelled",
        "draft_id": draft_id,
        "postiz_cancelled": bool(pid and not pid.startswith(("DRY_RUN_", "PENDING_"))),
    }



# ─────────────────────────────────────────────────────────────────────────
# 2026-06-10 (Berkay: "otonom çalışırken sağlıklı çalışması lazım") —
# Gate-block otomatik onarım döngüsü. HARD_BLOCK artık çıkmaz sokak değil:
# ihlaller (tier0 eksik entity'ler + tier1 desteksiz iddialar) yazara geri
# verilir, draft AYNI voice sistemiyle (tools.cansu_voice: directive +
# platform lugatı + sanitize) BİR kez yeniden yazılır ve yeniden gate'lenir.
# PASS → içerik DB'de güncellenir (video'lu draft'ta video_content_sha yeni
# metne damgalanır, pin-kaldırma kararıyla tutarlı) ve approve kaldığı
# yerden devam eder. Hâlâ blok → mevcut 409 davranışı (operatör görür).
_GATE_REWRITE_CT = {
    "twitter": "tweet", "x": "tweet", "linkedin": "linkedin",
    "instagram": "instagram", "devto": "blog", "youtube": "youtube",
}
_GATE_REWRITE_UZUNLUK = {
    "twitter": "punch", "x": "punch", "linkedin": "spark",
    "instagram": "punch", "devto": "storm", "youtube": "spark",
}
_GATE_REWRITE_VOICE = {
    "twitter": "first_person_witty", "x": "first_person_witty",
    "instagram": "first_person_witty", "linkedin": "hybrid",
    "devto": "hybrid", "youtube": "hybrid",
}


def _inject_hype_crew_path() -> None:
    import sys as _sys_hc
    for _hp in ("/opt/hype-crew", "../hype_crew", "../../hype_crew"):
        if _hp not in _sys_hc.path:
            _sys_hc.path.insert(0, _hp)


async def _gate_block_auto_rewrite(sb, draft: dict, source_raw: str, outcome, *, path: str):
    """HARD_BLOCK onarımı: ihlal-geri-beslemeli tek rewrite + re-gate.

    Returns (new_content, pass_outcome) ya da None (onarım tutmadı —
    çağıran mevcut 409/atomik-iptal davranışına düşer).
    """
    import os as _os
    try:
        _inject_hype_crew_path()
        from tools.cansu_voice import (
            build_cansu_directive, _lugat_for_platform, sanitize_draft,
        )
        from tools.guarded_postiz import assert_publishable as _ap_rewrite

        v = getattr(outcome, "raw_verdict", None)
        t0 = (v.tier0_entities_missing if v else []) or []
        t1 = (v.tier1_ungrounded_claims if v else []) or []
        feedback = []
        if t0:
            feedback.append(
                "Kaynakta geçmeyen unsurlar (KALDIR ya da kaynaktaki "
                "haliyle değiştir): " + ", ".join(str(x) for x in t0[:6])
            )
        for claim in t1[:4]:
            feedback.append(
                f"Desteksiz iddia (kaldır ya da kaynaktaki olguyla değiştir): {claim}"
            )
        if not feedback:
            feedback.append(str(getattr(outcome, "reasoning", "") or "gate blokladı"))

        plat = (draft.get("platform") or "twitter").lower()
        context = "\n".join([
            build_cansu_directive(),
            _lugat_for_platform(plat),
            f"Trend konusu: {draft.get('trend_topic') or ''}",
            "## KAYNAK METİN (tüm iddialar buna bağlı olmalı — kaynak dışı "
            "bir entity / sayı / ürün / olay / sebep YAZMA)\n"
            + (source_raw or "(yok)"),
            "## GATE DÜZELTMESİ (zorunlu)\n"
            "Önceki taslak fact-check gate'ine takıldı. İhlaller:\n- "
            + "\n- ".join(feedback)
            + "\nTaslağı bu ihlaller OLMADAN, yalnızca kaynaktaki "
            "olgularla yeniden yaz.",
        ])

        cron_secret = _os.environ.get("CRON_SECRET") or ""
        if not cron_secret:
            logger.warning("[gate-rewrite] CRON_SECRET yok — onarım atlandı")
            return None

        import httpx as _httpx
        body = {
            "account_id": draft.get("account_id"),
            "etki": "konustursun", "karakter": "haberci", "yapi": "dogal",
            "uzunluk": _GATE_REWRITE_UZUNLUK.get(plat, "punch"),
            "additional_context": context,
            "is_ultra": False, "language": "tr",
            "content_type": _GATE_REWRITE_CT.get(plat, "tweet"),
            "voice_mode": _GATE_REWRITE_VOICE.get(plat),
            "model_override": _os.environ.get("HYPE_WRITER_MODEL")
                or "anthropic/claude-sonnet-4.6",
            "clean_source_input": True,
        }
        async with _httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                "http://127.0.0.1:8000/api/internal/generate-tweet",
                headers={"X-Cron-Secret": cron_secret},
                json=body,
            )
            r.raise_for_status()
            new_content = sanitize_draft(
                (r.json().get("content") or "").strip(), plat,
            )
        if not new_content:
            return None

        new_outcome = await _ap_rewrite(
            draft_text=new_content,
            source_raw_content=source_raw,
            path=f"{path}_auto_rewrite",
            draft_id=draft["id"],
        )
        if new_outcome.verdict != "PASS":
            logger.warning(
                f"[gate-rewrite] draft={draft['id'][:8]} onarım da bloklandı: "
                f"{new_outcome.reasoning!r}"
            )
            return None

        payload = {"content": new_content}
        if draft.get("video_url"):
            import hashlib as _hl_gr
            payload["video_content_sha"] = _hl_gr.sha256(
                new_content.encode("utf-8")
            ).hexdigest()
            payload["video_stale"] = False
        sb.table("daily_drafts").update(payload).eq("id", draft["id"]).execute()
        logger.info(
            f"[gate-rewrite] draft={draft['id'][:8]} ({plat}) otomatik "
            f"onarıldı ve PASS (path={path})"
        )
        return (new_content, new_outcome)
    except Exception as e:
        logger.warning(f"[gate-rewrite] onarım hatası (fallback: blok): {e!r}")
        return None


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    body: Optional[ApproveRequest] = None,
    delay_minutes: int = Query(
        120, ge=1, le=240,
        description="Schedule offset in minutes from now. Default 120 (2h). "
                    "Set lower (e.g. 5) for a fast publish-time verification.",
    ),
    user=Depends(require_auth),
):
    """Approve an auto-draft.

    Phase 28.C — when the draft is in `pending_review` (Hype Crew has NOT yet
    scheduled it on Postiz), THIS endpoint is what triggers the Postiz schedule
    call. Without this endpoint being hit the post never leaves our DB, never
    reaches Postiz, and never publishes.

    Phase 43.A (Berkay 2 Jun 2026) — optional `edit_token` body field. If the
    caller edited the draft and passes the token they received from /edit,
    the approve handler compares it against the current `daily_drafts.edit_token`.
    Mismatch → 409 (someone else edited between your read and approve). When
    the schema migration hasn't run yet, edit_token is empty/absent on the
    row and the check silently passes — backward-compatible.

    For legacy drafts that were scheduled at generation time (auto_publish_enabled
    was true), the schedule stays active and we just mark them approved.
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    # Phase 43.A — race-condition guard. Only checks when:
    #   (a) the client provided an edit_token AND
    #   (b) the draft row actually has an edit_token column populated.
    # If either condition is missing we skip silently (no regression for
    # legacy callers and no false 409s before the migration runs).
    client_token = (body.edit_token if body else None) or None
    draft_token = draft.get("edit_token")
    if client_token and draft_token and client_token != draft_token:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "edit_token_mismatch",
                "message": (
                    "This draft was edited again after your last edit. "
                    "Reload the draft and re-apply your changes."
                ),
            },
        )

    # Phase 43.B — state machine guard. Approve is legal only from these
    # states; everything else means there's pending async work (regen) or
    # the draft was already shipped. Returns 409 with structured detail so
    # the client can show the right message.
    #   draft / pending_review / edited / regen_done → approve OK
    #   regen_pending → wait (regen worker still running)
    #   regen_failed  → tell user to retry regen or revert to last version
    #   approved / scheduled / published / cancelled → idempotent no-op or refuse
    APPROVE_OK_STATES = {None, "", "draft", "pending", "pending_review", "edited", "regen_done"}
    APPROVE_WAIT_STATES = {"regen_pending"}
    APPROVE_BLOCKED_STATES = {"regen_failed"}
    current_status = (draft.get("status") or "").lower()
    # Phase 43.C — video regen lives on a separate boolean column
    # (video_regen_pending) so image and video regens can in theory
    # coexist on the same draft. Either side being pending → 409.
    video_pending = bool(draft.get("video_regen_pending"))
    if video_pending:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "video_regen_in_progress",
                "status": current_status,
                "message": "Video yeniden üretiliyor. Tamamlanması bekleniyor (~3-5 dk).",
            },
        )
    # SEV-1 follow-up P0 (2026-06-07) — refuse defective videos
    # (truncated / malformed / audio≠video). The render-time integrity
    # check writes video_integrity_ok=false; this guard refuses approve
    # so a defective render can never reach Postiz.
    is_defective, defect_reason = _video_integrity_defective(draft)
    if is_defective:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "video_truncated",
                "status": current_status,
                "message": (
                    "Bu draft'ın videosu eksik / kesik üretilmiş "
                    f"(actual={draft.get('video_duration_s')}s vs "
                    f"expected={draft.get('expected_duration_s')}s). "
                    "Yayına alınmadan önce videoyu yeniden üret."
                ),
                "reason": defect_reason,
                "actual_duration_s": draft.get("video_duration_s"),
                "expected_duration_s": draft.get("expected_duration_s"),
                "remediation": (
                    "Call POST /api/hype/drafts/{id}/regen-video to "
                    "trigger a full re-render against the current content."
                ),
            },
        )

    # SEV-1 P0 fix (2026-06-07) — refuse video drafts whose video was
    # rendered against a previous content version. The handler that put
    # us here (edit_draft) sets video_stale=true; the helper also
    # recomputes the sha live to catch raw-SQL edits.
    is_stale, stale_reason = _video_out_of_sync(draft)
    if is_stale:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "video_out_of_sync",
                "status": current_status,
                "message": (
                    "Bu draft'ın videosu, metnin DAHA ESKİ bir sürümüne "
                    "göre üretilmiş. Mevcut metinle eşleşmiyor. Yayına "
                    "alınmadan önce videoyu yeniden üret (re-render)."
                ),
                "reason": stale_reason,
                "remediation": (
                    "Call POST /api/hype/drafts/{id}/regen-video to trigger "
                    "a re-render against the current content; on completion "
                    "the draft becomes approvable."
                ),
            },
        )
    if current_status in APPROVE_WAIT_STATES:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "regen_in_progress",
                "status": current_status,
                "message": "Image/video regen is still running. Wait for it to complete before approving.",
            },
        )
    if current_status in APPROVE_BLOCKED_STATES:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "regen_failed",
                "status": current_status,
                "message": "Last regen failed. Trigger another regen or revert to the previous version.",
            },
        )
    if current_status and current_status not in APPROVE_OK_STATES:
        # Unknown state — log a warning but allow (forward-compat with new states)
        logger.warning(
            f"[hype/approve] draft {draft_id[:8]} has unrecognized status={current_status!r}; "
            f"allowing approve but check Phase 43 state machine"
        )

    postiz_post_id = draft.get("postiz_post_id")
    needs_schedule = draft.get("status") == "pending_review" or not postiz_post_id

    # Phase 1 (Berkay 6 Haz 2026 fabrication audit) — fail-CLOSED gate.
    # Routes through the single choke-point assert_publishable() which
    # returns a signed verdict token. ERROR is no longer silently passed
    # through; a gate exception → HTTP 503 + draft holds pending_review.
    # The signed token is later required by GuardedPostizClient — a code
    # path that publishes without going through this gate would fail at
    # the wrapper.
    # ── Shadow-mode: capture the human approve decision ────────────────
    # Stamps the latest shadow_/shadow_backfill verdict row for this
    # draft with human_decision='approve'. Best-effort; never fails the
    # approve flow. The publish-time gate below is unchanged.
    try:
        import sys as _sys_hs
        for _hp in ("/opt/hype-crew", "../hype_crew", "../../hype_crew"):
            if _hp not in _sys_hs.path:
                _sys_hs.path.insert(0, _hp)
        from tools.guarded_postiz import record_human_decision as _record_human
        _record_human(
            draft_id, "approve",
            reason=(getattr(body, "reason", None) if body else None) or "",
            decided_by=str(user.id),
        )
    except Exception as _he:
        logger.warning(f"[hype/approve] shadow-human capture failed (non-fatal): {_he!r}")

    gate_outcome = None
    if needs_schedule and draft.get("content"):
        trend_row = (
            sb.table("trends")
            .select("raw_content, url, source_tweets, full_source_text")
            .eq("id", draft.get("trend_id"))
            .limit(1)
            .execute()
            .data
        )
        source_raw = ""
        if isinstance(trend_row, list) and trend_row:
            # 2026-06-10: kaynak birleşimi yazarla SİMETRİK tek tanıma indi
            # (tools.cansu_voice.assemble_source_text: fst + raw_content +
            # tweet text'leri). 2026-06-09 hotfix'i yalnız fst'yi tercih
            # ediyordu ama fst bazı trendlerde tweet'leri içermiyor (Apple
            # Siri "Apple Intelligence" vakası: yazar union gördü, gate fst
            # gördü → deterministik false block).
            _inject_hype_crew_path()
            from tools.cansu_voice import assemble_source_text as _asrc
            source_raw = _asrc(trend_row[0] or {})
        import sys as _sys_fg
        for _hype_path in ("/opt/hype-crew", "../hype_crew", "../../hype_crew"):
            if _hype_path not in _sys_fg.path:
                _sys_fg.path.insert(0, _hype_path)
        from tools.guarded_postiz import assert_publishable as _assert_publishable
        gate_outcome = await _assert_publishable(
            draft_text=draft["content"],
            source_raw_content=source_raw,
            path="manual_approve",
            draft_id=draft_id,
        )
        logger.info(
            f"[hype/approve] gate draft={draft_id[:8]} "
            f"verdict={gate_outcome.verdict} elapsed_ms={gate_outcome.elapsed_ms} "
            f"reasoning={gate_outcome.reasoning!r}"
        )
        if gate_outcome.verdict == "HARD_BLOCK":
            # 2026-06-10 — otonom onarım: blok çıkmaz sokak değil; ihlal
            # geri-beslemeli tek rewrite + re-gate. PASS → approve devam.
            _repaired = await _gate_block_auto_rewrite(
                sb, draft, source_raw, gate_outcome, path="manual_approve",
            )
            if _repaired:
                draft["content"], gate_outcome = _repaired
        if gate_outcome.verdict == "HARD_BLOCK":
            v = gate_outcome.raw_verdict
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "faithfulness_block",
                    "message": (
                        "Bu draft kaynak metnine bağlı kalmıyor. "
                        "Otomatik onarım da gate'i geçemedi; "
                        "pending_review olarak kaldı."
                    ),
                    "tier0_entities_missing": v.tier0_entities_missing if v else [],
                    "tier1_pass_ratio": v.tier1_claim_pass_ratio if v else None,
                    "tier1_ungrounded_claims": v.tier1_ungrounded_claims if v else [],
                    "tier2_verdict": v.tier2_verdict if v else None,
                    "tier2_ungrounded_angles": v.tier2_ungrounded_angles if v else [],
                    "reasoning": gate_outcome.reasoning,
                },
            )
        if gate_outcome.verdict == "ERROR":
            # FAIL-CLOSED. The previous fall-through-and-continue path
            # (line 752 prior PR) was the silent-publish bug. Now an
            # ERROR → 503 + draft stays pending_review. Never publish
            # on ERROR.
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "gate_unavailable",
                    "message": (
                        "Faithfulness gate çalışamadı; güvenli tarafta "
                        "kalıyoruz. Draft pending_review olarak duruyor — "
                        "az sonra tekrar deneyin veya manuel inceleyin."
                    ),
                    "reasoning": gate_outcome.reasoning,
                },
            )

    scheduled_at_iso = draft.get("scheduled_at")
    if needs_schedule:
        # Phase 28.C — fire Postiz schedule now. We re-import the Hype Crew
        # PostizClient (installed under /opt/hype-crew on Hetzner; reachable
        # here too because contentfactory backend and hype_crew live on the
        # same box). On local dev the import may fail; in that case we just
        # mark approved without scheduling and log.
        try:
            import sys
            for hype_path in ("/opt/hype-crew", "../hype_crew", "../../hype_crew"):
                if hype_path not in sys.path:
                    sys.path.insert(0, hype_path)
            from tools.postiz_client import PlatformPost  # type: ignore
            # Phase 1: every publish path uses the guarded wrapper. The
            # base PostizClient is never constructed directly in publish
            # call sites.
            from tools.guarded_postiz import (  # type: ignore
                GuardedPostizClient as PostizClient,
                GuardedPublishRefused,
            )
        except Exception as e:
            logger.warning(f"[hype/approve] PostizClient import failed: {e}")
            PostizClient = None  # type: ignore[assignment]
            PlatformPost = None  # type: ignore[assignment]
            GuardedPublishRefused = Exception  # type: ignore[assignment]

        if PostizClient is not None and PlatformPost is not None:
            # Resolve integration_id for the draft's account
            ca_row = (
                sb.table("connected_accounts")
                .select("id, platform, postiz_integration_id, user_id")
                .eq("id", draft["account_id"])
                .limit(1)
                .execute()
            )
            ca = (ca_row.data or [{}])[0]
            # 2026-06-10 — platform/integration mismatch koruması
            # (approve_thread'dekiyle aynı; ayrıntı oradaki notta).
            _plat_d = (draft.get("platform") or "").lower()
            _acc_plat = (ca.get("postiz_provider") or ca.get("platform") or "").lower()
            if _plat_d and _acc_plat and _plat_d != _acc_plat:
                _fix = (
                    sb.table("connected_accounts")
                    .select("id, platform, postiz_integration_id, postiz_provider, user_id")
                    .eq("user_id", draft["user_id"])
                    .or_(f"platform.eq.{_plat_d},postiz_provider.eq.{_plat_d}")
                    .not_.is_("postiz_integration_id", "null")
                    .limit(1)
                    .execute()
                )
                if _fix.data:
                    ca = _fix.data[0]
                    logger.warning(
                        f"[hype/approve] draft {draft_id[:8]} platform={_plat_d} "
                        f"account mismatch (account was {_acc_plat}) — re-resolved "
                        f"to integration {ca.get('postiz_integration_id')}"
                    )
            integration_id = ca.get("postiz_integration_id")
            if not integration_id:
                raise HTTPException(400, f"no postiz_integration_id for account {draft['account_id']}")

            # Default 2h delay; query param `delay_minutes` can override
            # (1-240). Lets the operator run a quick publish-time verification.
            scheduled_at_dt = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
            scheduled_at_iso = scheduled_at_dt.isoformat()

            # Build media: prefer video_url over image_url. Berkay 6 Haz
            # 2026 — video drafts have video_url + video_thumbnail_url;
            # without this branch the video never attached to the Postiz
            # post (the approve path used to be image-only and the YT/IG
            # Reels variants would have shipped as text-only or 400'd).
            # is_video=True drives per-platform settings (IG → "reel",
            # YT → video media reference, LinkedIn → native video).
            media = None
            is_video = False
            pc = PostizClient()
            # ── FAIL-CLOSED VIDEO UPLOAD (audit fix, 6 Haz 2026) ────────
            # If the draft HAS a video_url, a failed upload must abort
            # the approve — NEVER schedule a media-less text-only post
            # on LinkedIn / Twitter. YouTube / Instagram already error
            # at publish on missing media; LinkedIn / Twitter would
            # happily ship the text and silently lose the video. The
            # gate caught the entity grounding; the new abort here
            # catches the media-loss silent-degradation seam.
            if draft.get("video_url"):
                try:
                    media_obj = pc.upload_from_url(draft["video_url"])
                    if not media_obj or not media_obj.get("id"):
                        raise RuntimeError(
                            f"upload_from_url returned no id: {media_obj!r}"
                        )
                    media = [media_obj]
                    is_video = True
                except Exception as e:
                    logger.error(
                        f"[hype/approve] VIDEO UPLOAD FAILED for draft "
                        f"{draft_id} (fail-closed): {e!r}"
                    )
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "error": "media_upload_failed",
                            "message": (
                                "Video upload to Postiz failed. Draft stays "
                                "pending_review; we never silently post text-only."
                            ),
                            "draft_id": draft_id,
                            "video_url": draft.get("video_url"),
                            "underlying_error": f"{type(e).__name__}: {str(e)[:300]}",
                        },
                    )
            elif draft.get("image_url"):
                try:
                    media_obj = pc.upload_image_url(draft["image_url"])
                    if not media_obj or not media_obj.get("id"):
                        raise RuntimeError("image upload returned no id")
                    media = [media_obj]
                except Exception as e:
                    logger.error(
                        f"[hype/approve] IMAGE UPLOAD FAILED for draft "
                        f"{draft_id} (fail-closed): {e!r}"
                    )
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "error": "media_upload_failed",
                            "message": (
                                "Image upload to Postiz failed. Draft stays "
                                "pending_review; we never silently post media-less."
                            ),
                            "draft_id": draft_id,
                            "image_url": draft.get("image_url"),
                            "underlying_error": f"{type(e).__name__}: {str(e)[:300]}",
                        },
                    )

            pp = PlatformPost(
                integration_id=integration_id,
                provider=draft.get("platform") or "twitter",
                content=draft["content"],
                title=draft.get("trend_topic"),  # devto/medium use title
                media=media,
                is_video=is_video,
            )
            try:
                pc = PostizClient()
                if gate_outcome is None or gate_outcome.verdict != "PASS":
                    # Defense in depth: we already raised on HARD_BLOCK
                    # and ERROR above, so getting here without a PASS
                    # outcome is a logic bug. Refuse.
                    raise HTTPException(
                        500,
                        f"approve reached schedule without PASS gate outcome "
                        f"(verdict={gate_outcome.verdict if gate_outcome else None})",
                    )
                # SEV-1 guard (2026-06-07) — open the operator-UI publish
                # context so GuardedPostizClient knows this call originated
                # from a real require_auth-protected handler, not a script.
                # 2026-06-08 fix: was 'from hype_crew.tools.guarded_postiz...'
                # which doesn't resolve on prod (hype_crew lives at
                # /opt/hype-crew/, not as a package under contentfactory).
                # sys.path was already injected above at line 1024-1036.
                from tools.guarded_postiz import operator_publish_context
                with operator_publish_context():
                    resp = pc.schedule_posts(
                        [pp], scheduled_at_dt, gate_outcomes=[gate_outcome],
                    )
                # Extract returned post_id. Postiz returns `postId`
                # in the per-post array element; `id` is the legacy
                # field on older Postiz versions. Try both. Without
                # this, postiz_post_id stayed NULL → the UI kept the
                # draft in "Bekleyen" forever even though Postiz had
                # actually scheduled it (Berkay 6 Haz 2026 audit).
                new_post_id = None
                if isinstance(resp, list) and resp and isinstance(resp[0], dict):
                    new_post_id = (
                        resp[0].get("postId")
                        or resp[0].get("id")
                    )
                elif isinstance(resp, dict):
                    new_post_id = (
                        resp.get("postId") or resp.get("id")
                        or (resp.get("posts", [{}])[0].get("postId")
                             or resp.get("posts", [{}])[0].get("id")
                             if resp.get("posts") else None)
                    )
                if new_post_id:
                    postiz_post_id = new_post_id
                    # Audit follow-up — auto-arm the per-platform publish
                    # verifier ~5 min after the scheduled time. Kills the
                    # 6 h reconciler blind spot on this draft.
                    _arm_publish_verifier([new_post_id], scheduled_at_dt)
                else:
                    logger.warning(f"[hype/approve] Postiz response had no postId; resp={str(resp)[:200]}")
            except Exception as e:
                logger.exception(f"[hype/approve] Postiz schedule call failed: {e}")
                raise HTTPException(502, f"Postiz schedule failed: {type(e).__name__}: {str(e)[:200]}")

    # Phase 28.P — if this draft has iteration history, mark the final pending
    # iteration as approved + pull its content into daily_drafts.content.
    iter_chain_q = (
        sb.table("draft_iterations")
        .select("id, version, content, status, rejection_category, rejection_feedback")
        .eq("draft_id", draft_id)
        .order("version", desc=False)
        .execute()
    )
    iter_chain = iter_chain_q.data or []
    final_iteration_version = 1
    final_content = draft["content"]
    if iter_chain:
        # Final iteration = highest-version row (should be 'pending')
        final_row = iter_chain[-1]
        final_iteration_version = final_row["version"]
        final_content = final_row.get("content") or draft["content"]
        if final_row.get("status") == "pending":
            sb.table("draft_iterations").update({
                "status": "approved",
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", final_row["id"]).execute()

    # Persist approval — postiz_post_id set if newly scheduled, scheduled_at too
    update_payload = {"status": "approved"}
    if final_content != draft["content"]:
        update_payload["content"] = final_content
    if postiz_post_id and postiz_post_id != draft.get("postiz_post_id"):
        update_payload["postiz_post_id"] = postiz_post_id
    if scheduled_at_iso and scheduled_at_iso != draft.get("scheduled_at"):
        update_payload["scheduled_at"] = scheduled_at_iso
    sb.table("daily_drafts").update(update_payload).eq("id", draft_id).execute()

    # Phase 43.D — Passive approval signal capture.
    # When the user approves a draft WITHOUT touching it (no edits, no
    # iterations), record the WINNING combination of generative knobs
    # (content_type / voice_mode / scene / composition / hook) as an
    # implicit positive signal. Strategist reads this and biases
    # toward the same combos on future trends — it's the inverse of
    # the reject signal we already capture.
    #
    # `is_passive=True` lets downstream filters tell "user clicked
    # Approve on first sight" from "user iterated 3 times then
    # approved" — different confidence levels.
    is_passive = (
        final_iteration_version == 1
        and not (draft.get("edit_fields") or draft.get("edit_token"))
    )

    # Pull implicit-preference signals straight from the draft row. They
    # were filled at draft-creation time by Strategist + Visual Director
    # (Phase 25.B + 42.A). Missing fields are simply omitted.
    implicit_pref: dict = {
        "content_type": draft.get("content_type"),
        "voice_mode": draft.get("voice_mode"),
        "platform": draft.get("platform"),
    }
    # Visual signals — readable from persona_assets via image_asset_id
    if draft.get("image_asset_id"):
        try:
            asset_row = (
                sb.table("persona_assets")
                .select("generation_metadata, scene_type, composition_type")
                .eq("id", draft["image_asset_id"])
                .limit(1)
                .execute()
            )
            if asset_row.data:
                ar = asset_row.data[0]
                gm = ar.get("generation_metadata") or {}
                if isinstance(gm, dict):
                    implicit_pref["scene_type"] = (
                        ar.get("scene_type")
                        or gm.get("scene_type")
                    )
                    implicit_pref["composition_type"] = (
                        ar.get("composition_type")
                        or gm.get("composition_type")
                    )
                    if gm.get("hook_type"):
                        implicit_pref["hook_type"] = gm["hook_type"]
        except Exception as e:
            logger.warning(f"approve: implicit_pref asset read failed: {e}")
    # Drop empties so the JSONB stays compact
    implicit_pref = {k: v for k, v in implicit_pref.items() if v}

    _save_memory(
        account_id=draft["account_id"],
        memory_type="approved_drafts",
        content=final_content,
        metadata={
            "trend_id": draft.get("trend_id"),
            "trend_topic": draft.get("trend_topic"),
            "postiz_post_id": postiz_post_id,
            "scheduled_at": scheduled_at_iso,
            "iteration_count": final_iteration_version,
            # Phase 43.D — implicit positive preference
            "is_passive": is_passive,
            "implicit_preferences": implicit_pref or None,
        },
        importance=0.85 if is_passive else 0.8,
    )

    # Phase 28.R-Lite-V2 — bug fix: log feedback action so it appears in stats.
    # Previously approve_draft only wrote to hype_memory; the StatsRow counter
    # queries hype_feedback and was therefore stuck at 0 approved, making
    # users feel their reviews didn't count.
    _log_feedback(
        run_id=draft.get("hype_run_id"),
        draft_id=draft_id,
        account_id=draft["account_id"],
        user_id=user.id,
        action="approved",
        rejection_category=None,
        free_text=None,
        # Part 3 (2026-06-07) — pass BOTH original + edited so the quality
        # classifier can compute edit_distance and tag the row with the
        # operator_quality_verdict (publishable_as_is / needed_minor_edit
        # / needed_major_edit). Without edited_content, every approve
        # would default to publishable_as_is.
        original_content=draft["content"],
        edited_content=final_content,
        rejection_target=None,
        image_rejection_reason=None,
    )

    # Phase 28.P — if approval came after refinement, record the pattern so
    # Strategist learns which feedback themes lead to acceptance for future trends.
    if final_iteration_version > 1 and iter_chain:
        rejection_chain = []
        for r in iter_chain:
            if r.get("status") == "rejected":
                rejection_chain.append({
                    "version": r.get("version"),
                    "category": r.get("rejection_category"),
                    "feedback": r.get("rejection_feedback"),
                })
        pattern_summary = (
            f"Trend '{draft.get('trend_topic') or '?'}' için {final_iteration_version} "
            f"iterasyon sonunda onaylandı.\n"
            f"Reddedilen denemeler: " +
            "; ".join(
                f"v{c['version']}: {c.get('category') or 'other'}"
                + (f" ({(c.get('feedback') or '')[:80]})" if c.get('feedback') else "")
                for c in rejection_chain
            )
            + f"\nFinal kabul edilen versiyon: v{final_iteration_version}"
        )
        _save_memory(
            account_id=draft["account_id"],
            memory_type="refinement_pattern",
            content=pattern_summary,
            metadata={
                "trend_id": draft.get("trend_id"),
                "trend_topic": draft.get("trend_topic"),
                "iteration_count": final_iteration_version,
                "rejection_chain": rejection_chain,
                "platform": draft.get("platform"),
            },
            importance=0.85,
        )

    _log_feedback(
        run_id=draft.get("hype_run_id"),
        draft_id=draft_id,
        account_id=draft["account_id"],
        user_id=user.id,
        action="approved",
        original_content=final_content,
    )
    return {
        "status": "approved",
        "draft_id": draft_id,
        "postiz_post_id": postiz_post_id,
        "scheduled_at": scheduled_at_iso,
    }


@router.post("/threads/{content_thread_id}/approve")
async def approve_thread(
    content_thread_id: str,
    delay_minutes: int = Query(
        120, ge=1, le=240,
        description="Schedule offset in minutes from now. Default 120 (2h). "
                    "Set to 5 for a fast publish-time verification test.",
    ),
    user=Depends(require_auth),
):
    """2026-06-10 — concurrency kilidi (çift-submit koruması).

    Approve ~60-90sn sürebiliyor (gate + arbiter + olası rewrite); UI
    timeout/yeniden tıklama ikinci bir isteği paralel sokunca AYNI thread
    Postiz'e İKİ KEZ schedule edildi (96d1157f vakası: 03:02:57 + 03:03:28
    setleri — yetim set elle silindi). Çözüm: content_threads.status
    üzerinden atomik claim ('approving'); ikinci istek 409 alır. Hata
    durumunda status eski değerine döner; başarıda inner zaten 'approved'
    yazar.
    """
    sb = get_supabase()
    th_rows = (
        sb.table("content_threads")
        .select("status")
        .eq("id", content_thread_id)
        .limit(1)
        .execute()
    ).data or []
    prev_status = th_rows[0].get("status") if th_rows else None
    if prev_status in ("approving", "approved"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "approve_in_progress_or_done",
                "message": (
                    "Bu thread için onay zaten çalışıyor ya da tamamlandı. "
                    "Sayfayı yenileyip durumu kontrol edin."
                ),
                "thread_status": prev_status,
            },
        )
    if prev_status is not None:
        claim = (
            sb.table("content_threads")
            .update({"status": "approving"})
            .eq("id", content_thread_id)
            .eq("status", prev_status)
            .execute()
        ).data or []
        if not claim:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "approve_in_progress_or_done",
                    "message": (
                        "Onay isteği başka bir istekle yarıştı; thread şu an "
                        "işleniyor. Sayfayı yenileyin."
                    ),
                },
            )
    try:
        return await _approve_thread_inner(content_thread_id, delay_minutes, user)
    except Exception:
        if prev_status is not None:
            try:
                (
                    sb.table("content_threads")
                    .update({"status": prev_status})
                    .eq("id", content_thread_id)
                    .eq("status", "approving")
                    .execute()
                )
            except Exception:
                pass
        raise


async def _approve_thread_inner(content_thread_id: str, delay_minutes: int, user):
    """Phase 40 (Berkay 1 Haz 2026) — Tek tıkla thread'i 5 platforma birden
    Postiz'e schedule eder.

    Akış:
      1. Thread'deki pending_review draft'larını bul (workspace-scoped)
      2. Her draft için PlatformPost objesi kur — varsa video Postiz'e
         upload-from-url ile aktar (Reels/Shorts/LinkedIn için), yoksa image
      3. Tek `schedule_posts(platform_posts, +2h)` call → multi-platform array
      4. Her satır için status='approved' + postiz_post_id + scheduled_at update
      5. Her satır için hype_feedback (action='approved') ve hype_memory
         (approved_drafts) yaz

    Hata davranışı: Postiz call exception fırlatırsa hiçbir row update edilmez
    (atomik). Postiz başarılı olur ama bazı satırlarda postiz_post_id eksik
    döner → uyarı log'la, kalan satırları yine de approved işaretle.
    """
    sb = get_supabase()

    # 1. Fetch thread drafts — workspace-scoped via accessible_owner_ids
    try:
        from services.access_control import accessible_owner_ids
        accessible = accessible_owner_ids(user.id)
    except Exception:
        accessible = [user.id]

    rows_res = (
        sb.table("daily_drafts")
        .select(
            # IMPORTANT: trend_id is required for the faithfulness gate to
            # load source_raw_content. Without it the gate ERRORs with
            # "no_source_raw_content" → HTTP 503 — that was the 2026-06-06
            # 3-Meta-AI-videos block (drafts da99c25a / d0013b89 / a7b3234b).
            "id, account_id, user_id, platform, content, trend_id, "
            "trend_topic, image_url, video_url, hype_run_id, "
            "status, postiz_post_id"
        )
        .eq("content_thread_id", content_thread_id)
        .in_("user_id", accessible)
        .in_("status", ["pending", "pending_review"])
        .execute()
    )
    drafts = rows_res.data or []
    if not drafts:
        raise HTTPException(404, "Thread not found, already approved, or access denied")

    logger.info(
        f"[hype/approve_thread] {content_thread_id[:8]} — {len(drafts)} drafts "
        f"platforms={[d.get('platform') for d in drafts]}"
    )

    # SEV-1 follow-up P0 (2026-06-07) — per-draft integrity refusal.
    # Atomic on threads: ONE truncated video → whole thread refused.
    for _d in drafts:
        _is_def, _def_reason = _video_integrity_defective(_d)
        if _is_def:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "video_truncated",
                    "draft_id": _d["id"],
                    "platform": _d.get("platform"),
                    "message": (
                        f"Bu thread'in {_d.get('platform')} videosu eksik "
                        f"üretilmiş (actual={_d.get('video_duration_s')}s "
                        f"vs expected={_d.get('expected_duration_s')}s)."
                    ),
                    "reason": _def_reason,
                    "remediation": (
                        "Re-render the affected platform's video and "
                        "retry the thread approve."
                    ),
                },
            )

    # SEV-1 P0 fix (2026-06-07) — per-draft video-stale check. The
    # thread is atomic: if ANY video draft is out of sync, refuse the
    # whole thread. Same rule as approve_draft; uses the shared helper.
    for _d in drafts:
        _is_stale, _stale_reason = _video_out_of_sync(_d)
        if _is_stale:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "video_out_of_sync",
                    "draft_id": _d["id"],
                    "platform": _d.get("platform"),
                    "message": (
                        f"Bu thread'in {_d.get('platform')} videosu, metnin "
                        f"DAHA ESKİ bir sürümüne göre üretilmiş. Yayına "
                        f"alınmadan önce videoyu yeniden üret."
                    ),
                    "reason": _stale_reason,
                    "remediation": (
                        "Re-render the video for this draft and retry the "
                        "thread approve."
                    ),
                },
            )

    # Phase 1 — use the guarded wrapper. Every post in this thread is
    # individually gated below.
    try:
        import sys
        for hype_path in ("/opt/hype-crew", "../hype_crew", "../../hype_crew"):
            if hype_path not in sys.path:
                sys.path.insert(0, hype_path)
        from tools.postiz_client import PlatformPost  # type: ignore
        from tools.guarded_postiz import (  # type: ignore
            GuardedPostizClient,
            assert_publishable as _assert_publishable_thread,
        )
    except Exception as e:
        logger.exception(f"[hype/approve_thread] PostizClient import failed: {e}")
        raise HTTPException(503, f"Postiz client unavailable: {type(e).__name__}")

    pc = GuardedPostizClient()

    # 3. Build PlatformPost list — resolve integrations + upload media per draft
    platform_posts: list = []
    draft_by_post_idx: list[dict] = []  # parallel list to map response back

    for d in drafts:
        # Integration lookup
        ca_row = (
            sb.table("connected_accounts")
            .select("id, postiz_integration_id, platform, postiz_provider")
            .eq("id", d["account_id"])
            .limit(1)
            .execute()
        )
        ca = (ca_row.data or [{}])[0]
        # 2026-06-10 — platform/integration mismatch koruması. Bazı draftlar
        # (Apple Siri youtube vakası) primary hesabın account_id'siyle
        # yazılmış: youtube post'u X integration'ına gitti → Postiz 400
        # (who_can_reply_post, X DTO'su) → thread atomik düştü. Draft'ın
        # platformu account'ın provider'ıyla uyuşmuyorsa doğru hesabı
        # (user_id + platform) ile yeniden çöz; bulunamazsa draft atlanır.
        _plat_d = (d.get("platform") or "").lower()
        _acc_plat = (ca.get("postiz_provider") or ca.get("platform") or "").lower()
        if _plat_d and _acc_plat and _plat_d != _acc_plat:
            _fix = (
                sb.table("connected_accounts")
                .select("id, postiz_integration_id, platform, postiz_provider")
                .eq("user_id", d["user_id"])
                .or_(f"platform.eq.{_plat_d},postiz_provider.eq.{_plat_d}")
                .not_.is_("postiz_integration_id", "null")
                .limit(1)
                .execute()
            )
            if _fix.data:
                ca = _fix.data[0]
                logger.warning(
                    f"[approve_thread] draft {d['id'][:8]} platform={_plat_d} "
                    f"account mismatch (account was {_acc_plat}) — re-resolved "
                    f"to integration {ca.get('postiz_integration_id')}"
                )
            else:
                logger.warning(
                    f"[approve_thread] draft {d['id'][:8]} platform={_plat_d} "
                    f"mismatch ve {_plat_d} için integration yok; skipping"
                )
                continue
        integration_id = ca.get("postiz_integration_id")
        if not integration_id:
            logger.warning(
                f"[approve_thread] draft {d['id'][:8]} platform={d.get('platform')} "
                f"has no postiz_integration_id; skipping"
            )
            continue

        provider = (d.get("platform") or "twitter").lower()
        media_obj = None
        is_video = False

        # ── FAIL-CLOSED VIDEO UPLOAD (Berkay 6 Haz 2026 audit) ──────────
        # If a draft HAS a video_url but upload_from_url fails, NEVER
        # fall through to text-only. A video draft becoming a text-only
        # post on LinkedIn/Twitter is the silent-degradation failure
        # the audit flagged. YouTube/Instagram error on missing media
        # but those errors land later; LinkedIn/X would ship text-only.
        # The fix: abort THIS draft (skip), leave it pending_review, and
        # surface the upload error in the thread's response so the
        # operator sees what broke.
        upload_failures: list[dict] = locals().get("upload_failures", [])
        if d.get("video_url"):
            try:
                media_obj = pc.upload_from_url(d["video_url"])
                if not media_obj or not media_obj.get("id"):
                    raise RuntimeError(
                        f"Postiz upload_from_url returned no media id: {media_obj!r}"
                    )
                is_video = True
                logger.info(
                    f"[approve_thread] {d['id'][:8]} {provider}: video uploaded → {media_obj.get('id')}"
                )
            except Exception as e:
                logger.error(
                    f"[approve_thread] {d['id'][:8]} {provider}: VIDEO UPLOAD FAILED "
                    f"(fail-closed; draft skipped, stays pending_review): {e!r}"
                )
                upload_failures.append({
                    "draft_id": d["id"], "platform": provider,
                    "error": f"video_upload_failed: {type(e).__name__}: {str(e)[:240]}",
                    "video_url": d.get("video_url"),
                })
                continue
        elif d.get("image_url"):
            try:
                media_obj = pc.upload_image_url(d["image_url"])
                if not media_obj or not media_obj.get("id"):
                    raise RuntimeError("image upload returned no id")
            except Exception as e:
                logger.error(
                    f"[approve_thread] {d['id'][:8]} {provider}: IMAGE UPLOAD FAILED "
                    f"(fail-closed; draft skipped): {e!r}"
                )
                upload_failures.append({
                    "draft_id": d["id"], "platform": provider,
                    "error": f"image_upload_failed: {type(e).__name__}: {str(e)[:240]}",
                    "image_url": d.get("image_url"),
                })
                continue

        media = [media_obj] if media_obj else None

        # YouTube needs video — skip if no video and Postiz would 400 anyway
        if provider == "youtube" and not is_video:
            logger.warning(
                f"[approve_thread] {d['id'][:8]} youtube with no video — skipping (Postiz YT requires MP4)"
            )
            continue

        pp = PlatformPost(
            integration_id=integration_id,
            provider=provider,
            content=d["content"],
            title=d.get("trend_topic"),
            media=media,
            is_video=is_video,
        )
        platform_posts.append(pp)
        draft_by_post_idx.append(d)

    if not platform_posts:
        raise HTTPException(
            400,
            {
                "error": "no_postable_drafts",
                "message": "No drafts could be scheduled (missing integrations, "
                            "YouTube without video, or media-upload failures).",
                "upload_failures": locals().get("upload_failures", []),
            },
        )

    # 4. Phase 1 — gate every post in the thread individually, then a
    # single multi-platform Postiz call. ERROR or HARD_BLOCK on ANY draft
    # holds the entire thread.
    scheduled_at_dt = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    scheduled_at_iso = scheduled_at_dt.isoformat()

    gate_outcomes_thread = []
    for pp, d in zip(platform_posts, draft_by_post_idx):
        trend_row_t = (
            sb.table("trends")
            .select("raw_content, source_tweets, full_source_text")
            .eq("id", d.get("trend_id"))
            .limit(1)
            .execute()
            .data
            if d.get("trend_id") else None
        )
        source_raw_t = ""
        if isinstance(trend_row_t, list) and trend_row_t:
            # 2026-06-10: yazar-gate kaynak simetrisi — tek tanım
            # (tools.cansu_voice.assemble_source_text). Ayrıntı için
            # approve_draft içindeki nota bak.
            _inject_hype_crew_path()
            from tools.cansu_voice import assemble_source_text as _asrc_t
            source_raw_t = _asrc_t(trend_row_t[0] or {})
        outcome_t = await _assert_publishable_thread(
            draft_text=pp.content,
            source_raw_content=source_raw_t,
            path="manual_approve_thread",
            draft_id=d["id"],
        )
        if outcome_t.verdict == "HARD_BLOCK":
            # 2026-06-10 — otonom onarım: thread'i atomik iptal etmeden
            # önce bloklanan platformu ihlal-geri-beslemeli tek rewrite
            # ile onarmayı dene. PASS → yeni içerik Postiz post'una ve
            # DB'ye yazılır, thread devam eder.
            _repaired_t = await _gate_block_auto_rewrite(
                sb, d, source_raw_t, outcome_t, path="manual_approve_thread",
            )
            if _repaired_t:
                new_content_t, outcome_t = _repaired_t
                try:
                    pp.content = new_content_t
                except Exception:
                    logger.warning(
                        f"[gate-rewrite] pp.content set edilemedi "
                        f"(draft={d['id'][:8]}) — DB güncellendi ama post "
                        f"eski içerikle gidebilir; blok davranışına dön"
                    )
                    outcome_t = await _assert_publishable_thread(
                        draft_text=pp.content,
                        source_raw_content=source_raw_t,
                        path="manual_approve_thread",
                        draft_id=d["id"],
                    )
        gate_outcomes_thread.append(outcome_t)
        if outcome_t.verdict != "PASS":
            v = outcome_t.raw_verdict
            is_block = outcome_t.verdict == "HARD_BLOCK"
            tier0_missing = (v.tier0_entities_missing if v else []) or []
            tier1_ungrounded = (v.tier1_ungrounded_claims if v else []) or []
            # Build operator-language message naming the platform + cause.
            plat = d.get("platform") or "?"
            if is_block:
                bits = []
                if tier0_missing:
                    bits.append(f"kaynakta geçmeyen unsurlar: {', '.join(tier0_missing[:4])}")
                if tier1_ungrounded:
                    bits.append(f"desteklenmemiş iddialar: {len(tier1_ungrounded)}")
                why = "; ".join(bits) or "faithfulness gate engelledi"
                op_msg = f"{plat} platformu gate'e takıldı — {why}. Thread atomik olarak iptal edildi."
            else:
                op_msg = (
                    f"{plat} platformu için gate erişilebilir değil "
                    "(gate_unavailable). Thread atomik olarak iptal edildi; "
                    "lütfen tekrar deneyin veya logs'a bakın."
                )
            raise HTTPException(
                status_code=409 if is_block else 503,
                detail={
                    "error": "faithfulness_block" if is_block else "gate_unavailable",
                    "message": op_msg,
                    "draft_id": d["id"],
                    "platform": plat,
                    "tier0_entities_missing": tier0_missing,
                    "tier1_ungrounded_claims": tier1_ungrounded,
                    "reasoning": outcome_t.reasoning,
                },
            )

    try:
        # SEV-1 guard (2026-06-07) — same operator-UI marker as approve_draft.
        # 2026-06-08 fix: was 'from hype_crew.tools.guarded_postiz...' which
        # doesn't resolve on prod (hype_crew lives at /opt/hype-crew/, not
        # as a package under contentfactory). sys.path was already injected
        # above at lines 1483-1488.
        from tools.guarded_postiz import operator_publish_context
        with operator_publish_context():
            resp = pc.schedule_posts(
                platform_posts, scheduled_at_dt,
                gate_outcomes=gate_outcomes_thread,
            )
    except Exception as e:
        logger.exception(f"[approve_thread] Postiz schedule failed: {e}")
        raise HTTPException(
            502,
            detail={
                "error": "postiz_schedule_failed",
                "message": (
                    f"Postiz zamanlama hatası ({type(e).__name__}): "
                    f"{str(e)[:200]}. Hiçbir taslak yayınlanmadı."
                ),
                "exception_kind": type(e).__name__,
            },
        )

    # Postiz returns: list of {postId, integration} — map back to drafts via integration_id
    post_id_by_integration: dict[str, str] = {}
    if isinstance(resp, list):
        for item in resp:
            if isinstance(item, dict):
                pid = str(item.get("postId") or item.get("id") or "")
                iid = str(item.get("integration") or "")
                if pid and iid:
                    post_id_by_integration[iid] = pid

    # ── ATOMICITY GATE (2026-06-07 PART A2) ──
    # Before flipping ANY draft to status=approved, verify that every
    # platform_post got a real Postiz id back. If not, the schedule
    # half-succeeded — for the failing siblings there's no real post in
    # Postiz's queue, and flipping them to status=approved would create
    # the 29ad35cc-class half-state (status=approved + PENDING_/NULL
    # post id). All-or-nothing: refuse the WHOLE call, leave EVERY
    # sibling at its existing pending_review status, and tell the
    # operator exactly which platform Postiz didn't accept.
    missing_for_drafts: list[dict] = []
    for pp, draft in zip(platform_posts, draft_by_post_idx):
        rid = post_id_by_integration.get(pp.integration_id) or ""
        if (not rid) or rid.startswith(("PENDING_", "DRY_RUN_")):
            missing_for_drafts.append({
                "draft_id": draft["id"],
                "platform": draft.get("platform"),
                "integration_id": pp.integration_id,
                "postiz_returned": rid or "(none)",
            })
    if missing_for_drafts:
        logger.error(
            f"[approve_thread] atomic-refuse: Postiz returned no real id for "
            f"{len(missing_for_drafts)}/{len(platform_posts)} drafts. "
            f"No DB mutation — drafts remain in pending_review. "
            f"Missing={missing_for_drafts}"
        )
        bad = [m['platform'] for m in missing_for_drafts]
        raise HTTPException(
            502,
            detail={
                "error": "postiz_partial_response",
                "message": (
                    f"{', '.join(bad)} platformu için Postiz gerçek bir "
                    "post id döndürmedi; thread atomik olarak iptal "
                    "edildi. Hiçbir taslak yayınlanmadı."
                ),
                "missing": missing_for_drafts,
                "raw_postiz_response_kind": type(resp).__name__,
            },
        )

    # Audit follow-up — auto-arm the per-platform publish verifier ~5 min
    # after the scheduled time, covering EVERY post in this thread.
    _arm_publish_verifier(list(post_id_by_integration.values()), scheduled_at_dt)

    # 5. Update each draft + log feedback + save memory
    approved_count = 0
    skipped_count = 0
    for pp, draft in zip(platform_posts, draft_by_post_idx):
        new_post_id = post_id_by_integration.get(pp.integration_id)
        # Atomic invariant: we already validated above that every
        # platform_post has a real id. Defensive assert in case the
        # invariant is violated by a future refactor.
        assert new_post_id and not new_post_id.startswith(("PENDING_", "DRY_RUN_")), (
            f"[approve_thread] atomic invariant violated: draft {draft['id']} "
            f"has no real post id at update time"
        )
        update_payload = {
            "status": "approved",
            "scheduled_at": scheduled_at_iso,
            "postiz_post_id": new_post_id,
        }
        sb.table("daily_drafts").update(update_payload).eq("id", draft["id"]).execute()

        _save_memory(
            account_id=draft["account_id"],
            memory_type="approved_drafts",
            content=draft["content"],
            metadata={
                "trend_id": None,
                "trend_topic": draft.get("trend_topic"),
                "postiz_post_id": new_post_id,
                "scheduled_at": scheduled_at_iso,
                "platform": draft.get("platform"),
                "has_video": pp.is_video,
                "thread_id": content_thread_id,
            },
            importance=0.8,
        )
        _log_feedback(
            run_id=draft.get("hype_run_id"),
            draft_id=draft["id"],
            account_id=draft["account_id"],
            user_id=user.id,
            action="approved",
            original_content=draft["content"],
        )
        approved_count += 1

    # Drafts that we couldn't schedule (skipped earlier) stay in pending_review.
    skipped_count = len(drafts) - len(platform_posts)

    # Update content_thread row to reflect approval
    try:
        sb.table("content_threads").update({"status": "approved"}).eq(
            "id", content_thread_id
        ).execute()
    except Exception:
        pass  # non-fatal

    return {
        "status": "approved",
        "thread_id": content_thread_id,
        "approved": approved_count,
        "skipped": skipped_count,
        "scheduled_at": scheduled_at_iso,
        # Per-platform results — each row carries postiz_post_id (or None
        # if Postiz didn't return one for this integration).
        "platforms": [
            {
                "platform": pp.provider,
                "postiz_post_id": post_id_by_integration.get(pp.integration_id),
                "is_video": pp.is_video,
            }
            for pp in platform_posts
        ],
        # Per-audit fail-closed surface: any draft whose video/image upload
        # raised gets reported here. These rows are still pending_review
        # and were not scheduled — operator needs to fix the media URL.
        "upload_failures": locals().get("upload_failures", []),
    }


@router.post("/drafts/{draft_id}/reject")
async def reject_draft(draft_id: str, body: RejectRequest, user=Depends(require_auth)):
    """Reject an auto-draft. Cancels Postiz schedule + logs to memory.

    Side effects:
    - Postiz DELETE /posts/{postiz_post_id} (best-effort)
    - daily_drafts.status = 'auto_rejected'
    - hype_memory: insert into 'rejected_drafts' (negative example with reason)
    - hype_feedback: action='rejected' + category + free_text
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    # ── Shadow-mode: capture the human reject decision ─────────────────
    try:
        import sys as _sys_hs
        for _hp in ("/opt/hype-crew", "../hype_crew", "../../hype_crew"):
            if _hp not in _sys_hs.path:
                _sys_hs.path.insert(0, _hp)
        from tools.guarded_postiz import (
            record_human_decision as _record_human,
            classify_reject_reason as _classify_reject,
        )
        _cat = getattr(body, "category", "") or ""
        _free = getattr(body, "free_text", "") or ""
        _record_human(
            draft_id, "reject",
            reason=f"{_cat}: {_free}"[:1000],
            decided_by=str(user.id),
            reject_reason_class=_classify_reject(_cat, _free),
        )
    except Exception as _he:
        logger.warning(f"[hype/reject] shadow-human capture failed (non-fatal): {_he!r}")

    # Phase 28.C — if the draft was never scheduled (pending_review path), skip
    # the Postiz cancel call entirely. DRY_RUN_ / PENDING_ prefixed synthetic
    # ids and NULL ids do not exist on Postiz and would raise 404/400.
    pid = draft.get("postiz_post_id")
    if pid and not pid.startswith(("DRY_RUN_", "PENDING_")):
        _cancel_postiz(pid)

    sb.table("daily_drafts").update({
        "status": "auto_rejected",
        "postiz_post_id": None,   # clear any synthetic/cancelled id
    }).eq("id", draft_id).execute()

    # Phase 28 Fix 3 — split feedback by rejection_target so Strategist and Visual
    # Director get distinct learning signals.
    target = body.rejection_target or "both"
    image_reason = body.image_rejection_reason
    image_url = draft.get("image_url")

    # Always log the user's action in hype_feedback (with the new target columns)
    _log_feedback(
        run_id=draft.get("hype_run_id"),
        draft_id=draft_id,
        account_id=draft["account_id"],
        user_id=user.id,
        action="rejected",
        rejection_category=body.category,
        free_text=body.feedback,
        original_content=draft["content"],
        rejection_target=target,
        image_rejection_reason=image_reason,
    )

    # Text signal — Strategist + Writer learn from this. Skip when only the image
    # was bad (the wording was fine; saving a text-rejection signal would teach
    # the system to avoid a draft that was actually OK).
    if target in ("text", "both"):
        _save_memory(
            account_id=draft["account_id"],
            memory_type="rejected_drafts",
            content=draft["content"],
            metadata={
                "trend_id": draft.get("trend_id"),
                "trend_topic": draft.get("trend_topic"),
                "category": body.category,
                "reason": body.feedback,
                "rejection_target": target,
            },
            importance=0.9,  # negative signals are valuable
        )

    # Image signal — Visual Director learns from this. We write into the same
    # rejected_drafts memory_type but tagged with rejection_target='image' so
    # consumers can filter. The content field stores a short summary so the
    # Visual Director can later render it as "avoid these patterns".
    if target in ("image", "both") and image_url:
        visual_summary = (
            f"GÖRSEL REDDEDİLDİ — sebep: {image_reason or 'belirtilmemiş'}\n"
            f"trend: {draft.get('trend_topic') or '—'}\n"
            f"kullanıcı notu: {body.feedback or '(boş)'}\n"
            f"image_url: {image_url}"
        )
        _save_memory(
            account_id=draft["account_id"],
            memory_type="rejected_drafts",
            content=visual_summary,
            metadata={
                "rejection_target": "image" if target == "image" else "both",
                "image_rejection_reason": image_reason,
                "image_url": image_url,
                "image_asset_id": draft.get("image_asset_id"),
                "trend_topic": draft.get("trend_topic"),
                "persona_id": draft.get("persona_id"),
            },
            importance=0.95,  # visual mistakes are expensive to repeat
        )

    # Phase 28.P — mark all pending iteration rows as rejected too (final reject).
    # When the user uses /iterate the pending row is already flipped there; this
    # is a safety net for the "Tümünü iptal et" path that ends an iteration
    # session without approving.
    try:
        sb.table("draft_iterations").update({
            "status": "rejected",
            "rejection_category": body.category,
            "rejection_feedback": body.feedback,
            "image_rejection_reason": image_reason,
            "rejection_target": target,
            "rejected_by": user.id,
            "rejected_at": datetime.now(timezone.utc).isoformat(),
        }).eq("draft_id", draft_id).eq("status", "pending").execute()
    except Exception as e:
        logger.warning(f"reject_draft: iteration mark failed: {e}")

    return {
        "status": "rejected",
        "draft_id": draft_id,
        "category": body.category,
        "rejection_target": target,
        "image_rejection_reason": image_reason,
    }


# ─────────────────────────────────────────────────────────────────────
# Phase 43.C — POST /drafts/{id}/reject-video
# ─────────────────────────────────────────────────────────────────────
# Reject ONLY the video for a draft (text + image stay intact). Enqueues
# a `regen_type='video'` job that the worker dispatches to the HeyGen
# split-screen pipeline. Hard cap: 2 video regens per draft (Berkay's
# $4 ceiling — Avatar V is ~$1.30 per attempt). Caps the daily video
# spend via personas.daily_video_budget_usd.
#
# Distinct from /regen-image because:
#   · text and image survive — we don't write rejected_drafts for them
#   · status stays 'pending_review'; video_regen_pending=true is the
#     guard signal that blocks approve until the worker writes
#     video_regen_done
#   · worker dispatch is HeyGen, not Wiro

class _BudgetCheckResult(NamedTuple):
    daily_spend: float
    daily_cap: float
    allowed: bool


def _check_daily_video_budget(sb, persona_id: str) -> _BudgetCheckResult:
    """Phase 43.C — guard against runaway video regen spend.

    Sums today's video-related hype_runs cost for this persona and
    refuses if the next ~$2 attempt would breach the daily cap (default
    $5/day from Phase 35.2.2). On any error we fail open (let the regen
    through) and log — running with a degraded guard is safer than
    losing user-driven regens because of a flaky read.
    """
    daily_cap = 5.00  # safe fallback if personas row read fails
    try:
        p = (
            sb.table("personas")
            .select("daily_video_budget_usd")
            .eq("id", persona_id)
            .limit(1)
            .execute()
        )
        if p.data and (p.data[0].get("daily_video_budget_usd") is not None):
            daily_cap = float(p.data[0]["daily_video_budget_usd"])
    except Exception as e:
        logger.warning(f"_check_daily_video_budget: persona read failed: {e}")

    # Spend = sum of today's hype_runs.total_cost_usd for runs that
    # touched a video draft for this persona. We approximate via runs
    # linked to drafts with persona_id + video_url IS NOT NULL.
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    daily_spend = 0.0
    try:
        runs = (
            sb.table("hype_runs")
            .select("total_cost_usd")
            .gte("started_at", today_start)
            .execute()
        )
        # NB: rough — sums ALL runs today, not strictly video. The HeyGen
        # spend dominates on video-enabled days so this is a safe upper
        # bound. V2: filter by linked draft.video_url.
        daily_spend = sum(
            float(r.get("total_cost_usd") or 0) for r in (runs.data or [])
        )
    except Exception as e:
        logger.warning(f"_check_daily_video_budget: hype_runs sum failed: {e}")

    # ~$2 per HeyGen Avatar V attempt; refuse if the next attempt
    # would breach the cap.
    HEYGEN_ATTEMPT_COST = 2.00
    allowed = (daily_spend + HEYGEN_ATTEMPT_COST) <= daily_cap
    return _BudgetCheckResult(daily_spend, daily_cap, allowed)


VIDEO_REGEN_PER_DRAFT_CAP = 2  # Berkay's hard cap: max 2 attempts ≈ $4


@router.post("/drafts/{draft_id}/reject-video")
async def reject_video_draft(
    draft_id: str,
    body: RejectVideoRequest,
    user=Depends(require_auth),
):
    """Phase 43.C — reject only the video portion of a draft.

    Flow:
      1. Verify ownership (workspace-aware).
      2. Refuse if no video_url (nothing to reject).
      3. Refuse if video_regen_pending already true (race guard).
      4. Refuse if video_regen_count >= 2 (per-draft hard cap).
      5. Refuse if daily HeyGen budget would breach personas.daily_video_budget_usd.
      6. Cancel current Postiz schedule (best-effort; preserves text+image draft).
      7. Insert image_regen_jobs row with regen_type='video' + video_params overrides.
      8. Flip daily_drafts: video_regen_pending=true, video_regen_count++,
         regen_started_at=now() (for watchdog), postiz_post_id=NULL.
      9. Save memory signal (rejected_drafts, rejection_target='video').
     10. Log to hype_feedback.

    Worker will:
      · Honor video_params overrides (look_id, voice_id, script_text)
      · Run HeyGen split-screen pipeline
      · UPDATE the linked draft with new video_url + video_thumbnail_url
      · Flip video_regen_pending=false, status='regen_done'
      · Watchdog flips to regen_failed if stuck > 15min (Phase 43.B.5)
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    # 2. Must have a video to reject
    if not draft.get("video_url"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_video",
                "message": "Bu draftta video yok — reddedilecek bir şey yok.",
            },
        )

    # 3. Already pending
    if draft.get("video_regen_pending"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "video_regen_in_progress",
                "message": "Bu draft için zaten bir video yeniden üretiliyor.",
            },
        )

    # 4. Per-draft cap ($4 ceiling)
    current_count = int(draft.get("video_regen_count") or 0)
    if current_count >= VIDEO_REGEN_PER_DRAFT_CAP:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "max_video_regens_reached",
                "limit": VIDEO_REGEN_PER_DRAFT_CAP,
                "message": (
                    f"Bu draft için maksimum {VIDEO_REGEN_PER_DRAFT_CAP} "
                    "video denemesi kullanıldı."
                ),
            },
        )

    # 5. Daily budget guard
    persona_id = draft.get("persona_id")
    if persona_id:
        budget = _check_daily_video_budget(sb, persona_id)
        if not budget.allowed:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "daily_video_budget_exceeded",
                    "daily_spend": round(budget.daily_spend, 4),
                    "daily_cap": round(budget.daily_cap, 2),
                    "message": (
                        f"Günlük video bütçesi doldu (${budget.daily_spend:.2f}/"
                        f"${budget.daily_cap:.2f}). Yarın tekrar dene veya "
                        "personas.daily_video_budget_usd değerini artır."
                    ),
                },
            )

    # 6. Cancel the existing Postiz schedule so the bad video doesn't ship
    #    while we wait for the regen. text+image will be re-scheduled when
    #    the user approves the new version.
    pid = draft.get("postiz_post_id")
    if pid and not pid.startswith(("DRY_RUN_", "PENDING_")):
        _cancel_postiz(pid)

    # 7. Enqueue the video regen job. We reuse image_regen_jobs with
    #    regen_type='video' so we don't fork the queue schema. video_params
    #    holds HeyGen-specific overrides (look_id, voice_id, script).
    video_params: dict = {
        "video_rejection_reason": body.video_rejection_reason,
        "feedback": body.feedback,
        "previous_video_url": draft.get("video_url"),
        "previous_video_duration_sec": draft.get("video_duration_sec"),
    }
    if body.override_look_id:
        video_params["override_look_id"] = body.override_look_id
    if body.override_voice_id:
        video_params["override_voice_id"] = body.override_voice_id
    if body.override_script_text:
        video_params["override_script_text"] = body.override_script_text

    workspace_owner = draft.get("user_id") or user.id
    next_iter_version = current_count + 1

    job_id: Optional[str] = None
    try:
        job_ins = sb.table("image_regen_jobs").insert({
            "draft_id": draft_id,
            "iteration_version": next_iter_version,
            "persona_id": persona_id,
            "rejection_target": "video",
            "rejection_category": "user_video_regen",
            "rejection_feedback": (body.feedback or "")[:2000],
            "image_rejection_reason": None,  # this is video, not image
            "trend_topic": draft.get("trend_topic"),
            "owner_user_id": workspace_owner,
            "created_by_user_id": user.id,
            "status": "queued",
            "regen_type": "video",
            "video_params": video_params,
        }).execute()
        if job_ins.data:
            job_id = job_ins.data[0]["id"]
    except Exception as e:
        logger.exception(f"reject-video: queue insert failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"video_regen_enqueue_failed: {type(e).__name__}",
        )

    # 8. Flip draft state. Watchdog will recover if stuck >15min.
    try:
        sb.table("daily_drafts").update({
            "video_regen_pending": True,
            "video_regen_count": next_iter_version,
            "regen_started_at": datetime.now(timezone.utc).isoformat(),
            "postiz_post_id": None,
        }).eq("id", draft_id).execute()
    except Exception as e:
        logger.warning(f"reject-video: draft state flip failed (non-fatal): {e}")

    # 9. Memory signal — Visual Director / HeyGen pipeline learns
    _save_memory(
        account_id=draft["account_id"],
        memory_type="rejected_drafts",
        content=(
            f"VIDEO REDDEDİLDİ — sebep: {body.video_rejection_reason or 'belirtilmemiş'}\n"
            f"trend: {draft.get('trend_topic') or '—'}\n"
            f"kullanıcı notu: {body.feedback or '(boş)'}\n"
            f"previous_video_url: {draft.get('video_url')}"
        ),
        metadata={
            "rejection_target": "video",
            "video_rejection_reason": body.video_rejection_reason,
            "trend_topic": draft.get("trend_topic"),
            "persona_id": persona_id,
            "previous_video_url": draft.get("video_url"),
        },
        importance=0.95,  # video mistakes are expensive ($2/attempt) — heavy weight
    )

    # 10. Audit trail
    _log_feedback(
        run_id=draft.get("hype_run_id"),
        draft_id=draft_id,
        account_id=draft["account_id"],
        user_id=user.id,
        action="rejected",
        rejection_category="user_video_regen",
        free_text=body.feedback,
        original_content=draft["content"],
        rejection_target="video",
        image_rejection_reason=None,
    )

    logger.info(
        f"reject-video: queued job={job_id} draft={draft_id} v{next_iter_version}/"
        f"{VIDEO_REGEN_PER_DRAFT_CAP} reason={body.video_rejection_reason}"
    )

    return {
        "status": "video_regen_queued",
        "draft_id": draft_id,
        "job_id": job_id,
        "iteration_version": next_iter_version,
        "remaining_attempts": VIDEO_REGEN_PER_DRAFT_CAP - next_iter_version,
        "max_video_regens": VIDEO_REGEN_PER_DRAFT_CAP,
        "estimated_seconds": 240,  # HeyGen pilot avg ~3-5min
    }


@router.post("/drafts/{draft_id}/regen-video")
async def regen_video_draft(draft_id: str, user=Depends(require_auth)):
    """SEV-1 P0 fix (2026-06-07) — system-triggered video re-render.

    Operator's one-click recovery for the "video out of sync with
    edited content" 409. Same machinery as /reject-video (enqueues a
    regen_type='video' job that the worker picks up + writes the new
    video_url + new video_content_sha + clears video_stale), but with
    no manual rejection reason — this is the "rebuild the video to
    match what I just edited" path.

    The endpoint reuses the existing budget + per-draft cap guards.
    The video pipeline reads daily_drafts.content fresh, so whatever
    the operator's last edit was is what gets rendered. On completion
    the worker updates:
      video_url             new file
      video_content_sha     sha256 of the live content at render time
      video_stale           false
      video_regen_pending   false
      status                regen_done
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    if not draft.get("video_url"):
        # Not strictly out-of-sync — but we still want a video. If a
        # video draft has never been rendered yet, /regen-video is the
        # path to kick it off.
        if (draft.get("platform") or "").lower() not in {
            "instagram", "youtube", "tiktok"
        }:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "no_video_platform",
                    "message": "Bu platform için video desteklenmiyor.",
                },
            )

    # Reuse the existing cap + budget guards from /reject-video.
    if draft.get("video_regen_pending"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "video_regen_in_progress",
                "message": "Bu draft için zaten bir video yeniden üretiliyor.",
            },
        )
    current_count = int(draft.get("video_regen_count") or 0)
    if current_count >= VIDEO_REGEN_PER_DRAFT_CAP:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "max_video_regens_reached",
                "limit": VIDEO_REGEN_PER_DRAFT_CAP,
                "message": (
                    f"Bu draft için maksimum {VIDEO_REGEN_PER_DRAFT_CAP} "
                    "video denemesi kullanıldı."
                ),
            },
        )
    persona_id = draft.get("persona_id")
    if persona_id:
        budget = _check_daily_video_budget(sb, persona_id)
        if not budget.allowed:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "daily_video_budget_exceeded",
                    "daily_spend": round(budget.daily_spend, 4),
                    "daily_cap": round(budget.daily_cap, 2),
                    "message": (
                        f"Günlük video bütçesi doldu "
                        f"(${budget.daily_spend:.2f}/${budget.daily_cap:.2f})."
                    ),
                },
            )

    # Cancel current Postiz schedule (best-effort) so the old video
    # can't ship while the worker re-renders.
    pid = draft.get("postiz_post_id")
    if pid and not pid.startswith(("DRY_RUN_", "PENDING_")):
        _cancel_postiz(pid)

    workspace_owner = draft.get("user_id") or user.id
    next_iter_version = current_count + 1

    job_id: Optional[str] = None
    try:
        job_ins = sb.table("image_regen_jobs").insert({
            "draft_id": draft_id,
            "iteration_version": next_iter_version,
            "persona_id": persona_id,
            "regen_type": "video",
            "user_id": workspace_owner,
            "status": "queued",
            "video_params": {
                "trigger": "out_of_sync",
                "previous_video_url": draft.get("video_url"),
                "previous_video_duration_sec": draft.get("video_duration_sec"),
            },
            "trend_topic": draft.get("trend_topic"),
            "rejection_category": "system_video_out_of_sync",
            "max_retries": 1,
        }).execute()
        if job_ins.data:
            job_id = job_ins.data[0].get("id")
    except Exception as e:
        logger.exception(f"[regen-video] enqueue failed: {e}")
        raise HTTPException(500, f"video regen enqueue failed: {e}")

    try:
        sb.table("daily_drafts").update({
            "video_regen_pending": True,
            "video_regen_count": next_iter_version,
            "regen_started_at": datetime.now(timezone.utc).isoformat(),
            "postiz_post_id": None,
        }).eq("id", draft_id).execute()
    except Exception as e:
        logger.warning(f"[regen-video] draft flag update failed: {e}")

    return {
        "queued": True,
        "job_id": job_id,
        "iteration_version": next_iter_version,
        "estimated_seconds": 240,
    }


@router.post("/drafts/{draft_id}/edit")
async def edit_draft(draft_id: str, body: EditRequest, user=Depends(require_auth)):
    """Edit an auto-draft. Stores diff for voice learning.

    Phase 43.A (Berkay 2 Jun 2026) — multi-field edit + race-condition guard.
    The endpoint now:
      - Accepts an optional `edit_fields` JSON patch (text/scene/composition/voice)
        alongside the legacy `edited_content` text. Keys are optional and
        future-proof for Phase 43.B regen pipeline reads.
      - Generates an `edit_token` UUID on every edit; the next /approve call
        can pass this back to detect concurrent edits (409 mismatch).
      - Persists `edit_fields` and `edit_token` on `daily_drafts` if the
        columns exist; otherwise silently degrades to today's behaviour.
        This makes the deploy safe BEFORE the migration runs — once Berkay
        adds the two nullable columns in Supabase Studio, the feature
        activates automatically.

    Side effects (unchanged from pre-43.A):
    - daily_drafts.content = edited_content, status = 'edited'
    - hype_memory: insert into 'editor_diffs' (CRITICAL voice signal)
    - hype_memory: insert edited version into 'voice_examples' (positive)
    - hype_feedback: action='edited' + diff
    Note: Postiz schedule NOT cancelled — the new content needs to be pushed.
          For V1 we leave Postiz with original; user can re-approve manually.
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    diff = _diff_words(draft["content"], body.edited_content)

    # SEV-1 P0 fix (2026-06-07) — video↔content binding.
    # If the draft has a video AND the new content's sha256 differs
    # from the sha the video was rendered against, mark the video
    # stale. The approve path refuses to ship video drafts whose
    # video_stale=true (or whose live sha mismatches the stored sha).
    # Without this, an edited caption ships with the OLD voice-over
    # — that's exactly the audio/text mismatch from the 10:49
    # incident.
    import hashlib as _hl_edit
    new_sha = _hl_edit.sha256((body.edited_content or "").encode("utf-8")).hexdigest()
    has_video = bool(draft.get("video_url"))
    stored_video_sha = draft.get("video_content_sha")
    video_now_stale = (
        has_video
        and stored_video_sha is not None
        and stored_video_sha != new_sha
    )

    # Phase 43.A — always-on legacy update
    update_payload: dict = {
        "content": body.edited_content,
        "status": "edited",
    }
    if video_now_stale:
        # Don't NULL video_url (operator may want to see the old preview).
        # The approve guard reads video_stale + the live sha comparison.
        update_payload["video_stale"] = True
        update_payload["video_regen_pending"] = True
        logger.warning(
            f"[hype/edit] draft={draft_id[:8]} video INVALIDATED — "
            f"content sha changed from {stored_video_sha[:12]}… to {new_sha[:12]}…; "
            f"approve will refuse until re-render."
        )
    # Phase 43.A — opportunistic write of new columns; tolerates missing schema
    new_edit_token = str(uuid4())
    try:
        # First attempt: include new columns. If columns don't exist yet,
        # the PostgREST call returns a schema-cache error which we catch +
        # retry without them.
        extra: dict = {"edit_token": new_edit_token}
        if body.edit_fields:
            extra["edit_fields"] = body.edit_fields
        sb.table("daily_drafts").update({**update_payload, **extra}).eq("id", draft_id).execute()
    except Exception as e:
        msg = str(e)[:300]
        if "edit_token" in msg or "edit_fields" in msg or "schema" in msg.lower() or "column" in msg.lower():
            logger.warning(
                f"[hype/edit] new Phase 43.A columns not present yet; "
                f"falling back to legacy update (run ALTER TABLE to enable). msg={msg[:120]}"
            )
            sb.table("daily_drafts").update(update_payload).eq("id", draft_id).execute()
            new_edit_token = ""  # signal: not persisted
        else:
            raise

    _save_memory(
        account_id=draft["account_id"],
        memory_type="editor_diffs",
        content=(
            f"ORIGINAL:\n{draft['content']}\n\n"
            f"EDITED:\n{body.edited_content}\n\n"
            f"REASON: {body.feedback or 'no comment'}"
        ),
        metadata={
            "diff": diff,
            "trend_id": draft.get("trend_id"),
            # Phase 43.A — record edit_fields shape for memory layer downstream
            "edit_fields": body.edit_fields or None,
            # Phase 43.B.3 — scope_tag is what _is_scope_visible filters on.
            # We also keep the legacy 'scope' key for backwards compat with
            # older readers that haven't migrated.
            "scope_tag": "draft_only",
            "scope": "draft_only",
        },
        importance=1.0,
    )
    _save_memory(
        account_id=draft["account_id"],
        memory_type="voice_examples",
        content=body.edited_content,
        metadata={"source": "user_edit", "draft_id": draft_id},
        importance=0.9,
    )
    _log_feedback(
        run_id=draft.get("hype_run_id"),
        draft_id=draft_id,
        account_id=draft["account_id"],
        user_id=user.id,
        action="edited",
        free_text=body.feedback,
        original_content=draft["content"],
        edited_content=body.edited_content,
        content_diff=diff,
    )
    return {
        "status": "edited",
        "draft_id": draft_id,
        "diff": diff,
        # Phase 43.A — client should send this back on /approve for race-safety.
        # Empty string means columns not migrated yet — client can ignore.
        "edit_token": new_edit_token,
    }


class SaveAndApproveRequest(BaseModel):
    """Phase 43.A — combined edit + approve in one round-trip.

    Use this when the user has reviewed a draft, decided to ship it, but
    made a final tweak to the text first. The handler:
      1. Writes the edited content (same as /edit)
      2. Validates the freshly-generated edit_token matches before
         approving (race-free by construction — no client involvement)
      3. Calls the existing approve flow (Postiz schedule + memory write)

    All fields except `edited_content` are optional and mirror /edit's
    contract so the client doesn't need to learn two payloads.
    """
    edited_content: str = Field(..., min_length=1, max_length=4000)
    feedback: Optional[str] = Field(None, max_length=2000)
    edit_fields: Optional[dict] = Field(default=None)


@router.post("/drafts/{draft_id}/save-and-approve")
async def save_and_approve_draft(
    draft_id: str,
    body: SaveAndApproveRequest,
    user=Depends(require_auth),
):
    """Phase 43.A — atomic edit + approve shortcut.

    Race-free by construction: the edit_token generated inside /edit is
    re-used immediately as the approve guard, so no concurrent edit can
    slip in between the two operations. If the user wants race-safety
    across UI tabs, they should call /edit then /approve separately and
    forward the edit_token themselves.

    On Postiz schedule failure (502) the edit is NOT rolled back —
    `daily_drafts.content` is already saved as 'edited' status, and the
    user can retry /approve manually. This matches the existing /edit +
    /approve two-step semantics: edit always persists.
    """
    # 1) Reuse the /edit handler as-is (writes content, fires memory
    #    hooks, returns edit_token). Wrapping in a thin internal call
    #    keeps a single source of truth for the edit pipeline.
    edit_result = await edit_draft(
        draft_id=draft_id,
        body=EditRequest(
            edited_content=body.edited_content,
            feedback=body.feedback,
            edit_fields=body.edit_fields,
        ),
        user=user,
    )
    fresh_token = edit_result.get("edit_token") or None

    # 2) Approve with the token we just generated — guaranteed to match
    #    the row we just wrote unless a concurrent /edit landed between
    #    the two SQL statements (impossible in single-process Postgres).
    approve_result = await approve_draft(
        draft_id=draft_id,
        body=ApproveRequest(edit_token=fresh_token) if fresh_token else None,
        user=user,
    )

    return {
        "status": "saved_and_approved",
        "draft_id": draft_id,
        "edit": edit_result,
        "approve": approve_result,
    }


# ─────────────────────────────────────────────────────────────────────
# Phase 43.B.2 — POST /drafts/{id}/regen-image
# ─────────────────────────────────────────────────────────────────────
# A first-class image regen endpoint that bypasses the heuristic
# pick_scene() keyword mapping when the user provides explicit overrides.
# Distinct from /iterate (which is text-centric and may also enqueue an
# image job): /regen-image is the "fix the visual only" path used by the
# Düzelt → Görseli yenile UX. The worker (process_image_regen_queue.py)
# reads override_scene_description + user_composition_type and skips its
# keyword classifier when either is present (see 43.B.2 worker patch).
#
# Per-draft cap: 5 image regens (image_regen_count). Beyond that the user
# must hard-reject. State machine: draft flips to 'regen_pending' and the
# /approve endpoint refuses with 409 until the worker writes 'regen_done'
# or 'regen_failed' (watchdog at 15min).

class RegenImageRequest(BaseModel):
    """Phase 43.B.2 — user-driven image regeneration.

    All three fields are optional. When `override_scene_description` or
    `user_composition_type` is set, the worker bypasses keyword mapping
    and uses the override verbatim. Compliance gate still runs.
    """
    override_scene_description: Optional[str] = Field(None, max_length=2000)
    user_composition_type: Optional[str] = Field(None, max_length=64)
    feedback: Optional[str] = Field(None, max_length=2000)
    image_rejection_reason: Optional[str] = Field(None, max_length=64)


@router.post("/drafts/{draft_id}/regen-image")
async def regen_image_draft(
    draft_id: str,
    body: RegenImageRequest,
    user=Depends(require_auth),
):
    """Phase 43.B.2 — enqueue an image-only regen job with overrides.

    Returns 409 if image_regen_count >= 5 (per-draft cap) or if status is
    already 'regen_pending' (another job in flight). On success returns
    {job_id, status: 'queued'}; the worker UPDATEs daily_drafts.image_url
    when it finishes (~30-60s). State guard prevents approve during regen.
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    # State machine guard — block double-fire
    cur_status = (draft.get("status") or "").lower()
    if cur_status == "regen_pending":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "regen_in_progress",
                "message": "Bu draft için zaten bir görsel yeniden üretiliyor. Lütfen ~1 dk bekleyin.",
            },
        )

    # Per-draft cap. Field may not exist yet (schema migration pending) —
    # default to 0 and rely on opportunistic update below.
    current_count = int(draft.get("image_regen_count") or 0)
    if current_count >= 5:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "max_regen_reached",
                "message": "Bu draft için maksimum 5 görsel denemesi kullanıldı.",
                "limit": 5,
            },
        )

    # Resolve persona_id (same pattern as iterate_draft above)
    persona_id = draft.get("persona_id")
    if not persona_id:
        acc_id = draft.get("account_id")
        if acc_id:
            try:
                p_row = (
                    sb.table("personas")
                    .select("id")
                    .eq("primary_account_id", acc_id)
                    .limit(1)
                    .execute()
                )
                if p_row.data:
                    persona_id = p_row.data[0]["id"]
            except Exception:
                pass

    workspace_owner = draft.get("user_id") or user.id
    next_iter_version = current_count + 1

    # Build the job payload. Override columns may not exist yet (schema
    # migration pending) — graceful degrade catches PGRST204 and retries
    # without them, matching the Phase 43.A edit_token pattern.
    base_payload = {
        "draft_id": draft_id,
        "iteration_version": next_iter_version,
        "persona_id": persona_id,
        "rejection_target": "image",
        "rejection_category": "user_regen_request",
        "rejection_feedback": body.feedback or "",
        "image_rejection_reason": body.image_rejection_reason or None,
        "trend_topic": draft.get("trend_topic"),
        "owner_user_id": workspace_owner,
        "created_by_user_id": user.id,
        "status": "queued",
    }
    override_extra = {}
    if body.override_scene_description:
        override_extra["override_scene_description"] = body.override_scene_description
    if body.user_composition_type:
        override_extra["user_composition_type"] = body.user_composition_type

    job_id: Optional[str] = None
    try:
        job_ins = sb.table("image_regen_jobs").insert(
            {**base_payload, **override_extra}
        ).execute()
    except Exception as e:
        msg = str(e)[:300]
        if (
            "override_scene_description" in msg
            or "user_composition_type" in msg
            or "schema" in msg.lower()
            or "column" in msg.lower()
            or "PGRST204" in msg
        ):
            logger.warning(
                f"regen-image: override columns missing in image_regen_jobs "
                f"(migration pending). Inserting without overrides. err={msg}"
            )
            # Stash overrides in feedback so the worker can recover them
            # even before the schema lands.
            if override_extra:
                fb = base_payload.get("rejection_feedback") or ""
                marker_parts = []
                if "override_scene_description" in override_extra:
                    marker_parts.append(
                        f"[OVERRIDE_SCENE] {override_extra['override_scene_description']}"
                    )
                if "user_composition_type" in override_extra:
                    marker_parts.append(
                        f"[OVERRIDE_COMP] {override_extra['user_composition_type']}"
                    )
                base_payload["rejection_feedback"] = (
                    (fb + "\n\n" if fb else "") + "\n".join(marker_parts)
                )[:2000]
            job_ins = sb.table("image_regen_jobs").insert(base_payload).execute()
        else:
            logger.exception(f"regen-image: insert failed: {e}")
            raise HTTPException(status_code=500, detail=f"regen_insert_failed: {type(e).__name__}")

    if job_ins.data:
        job_id = job_ins.data[0]["id"]

    # Flip draft to 'regen_pending' so /approve refuses until the worker
    # finishes. Opportunistic write of regen_started_at + image_regen_count;
    # gracefully degrade if columns don't exist yet (43.B migration).
    update_payload: dict = {"status": "regen_pending"}
    try:
        extra = {
            "regen_started_at": datetime.now(timezone.utc).isoformat(),
            "image_regen_count": next_iter_version,
        }
        sb.table("daily_drafts").update({**update_payload, **extra}).eq("id", draft_id).execute()
    except Exception as e:
        msg = str(e)[:300]
        if (
            "regen_started_at" in msg
            or "image_regen_count" in msg
            or "schema" in msg.lower()
            or "column" in msg.lower()
            or "PGRST204" in msg
        ):
            logger.warning(
                f"regen-image: status columns missing (migration pending). "
                f"Setting status only. err={msg}"
            )
            try:
                sb.table("daily_drafts").update(update_payload).eq("id", draft_id).execute()
            except Exception:
                logger.exception("regen-image: even bare status update failed; continuing")
        else:
            logger.warning(f"regen-image: draft status flip failed (non-fatal): {e}")

    logger.info(
        f"regen-image: queued job={job_id} for draft={draft_id} "
        f"v{next_iter_version} overrides={bool(override_extra)}"
    )

    return {
        "status": "queued",
        "job_id": job_id,
        "draft_id": draft_id,
        "iteration_version": next_iter_version,
        "remaining_attempts": max(0, 5 - next_iter_version),
        "max_regens": 5,
        "overrides_applied": bool(override_extra),
    }


@router.get("/config/{account_id}")
async def get_config(account_id: str, user=Depends(require_auth)):
    """Get hype_account_config for an account (creates default if missing)."""
    _verify_account_ownership(account_id, user.id)
    sb = get_supabase()
    result = (
        sb.table("hype_account_config")
        .select("*")
        .eq("account_id", account_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]

    # Auto-create default config
    default = {
        "account_id": account_id,
        "voice_description": "direct, conversational, no corporate jargon",
        "topics_focus": [],
        "forbidden_topics": ["politics", "religion", "medical_advice", "financial_advice"],
        "reactive_enabled": True,
        "reactive_triggers": ["launch", "breaking", "milestone"],
        "daily_post_quota": 2,
        "auto_publish_enabled": False,
        "dry_run_mode": True,
    }
    inserted = sb.table("hype_account_config").insert(default).execute()
    return inserted.data[0] if inserted.data else default


@router.patch("/config/{account_id}")
async def update_config(account_id: str, body: ConfigUpdate, user=Depends(require_auth)):
    """Update hype_account_config. Only provided fields are changed (sparse update).

    UUID/optional columns can be explicitly cleared by sending null (or "") —
    we keep those keys in the payload so the row is updated to NULL in DB.
    All other None values are filtered (sparse update semantics).
    """
    _verify_account_ownership(account_id, user.id)

    # Columns that may legitimately be set to NULL by the user (clear action).
    CLEARABLE_UUID_COLS = {"active_style_profile_id"}

    raw = body.model_dump(exclude_unset=True)
    payload: dict = {}
    for k, v in raw.items():
        if k in CLEARABLE_UUID_COLS:
            # Empty string is the JS Select pattern for "no selection" — treat
            # as explicit NULL so the FK can be cleared.
            payload[k] = None if v in (None, "") else v
        elif v is not None:
            payload[k] = v

    if not payload:
        raise HTTPException(status_code=400, detail="no fields to update")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    sb = get_supabase()
    # Upsert: create row if missing
    existing = sb.table("hype_account_config").select("account_id").eq("account_id", account_id).limit(1).execute()
    if existing.data:
        result = sb.table("hype_account_config").update(payload).eq("account_id", account_id).execute()
    else:
        payload["account_id"] = account_id
        result = sb.table("hype_account_config").insert(payload).execute()
    return result.data[0] if result.data else payload


# ─── C2 (2026-06-07) — Lifecycle endpoint ──────────────────────────
# Operator-language draft-lifecycle view. 7-join coalesce:
#   daily_drafts → trends → editorial_lead_judgments
#                → hype_stages (full-flow runs)
#                → persona_assets (visual + ai-image score)
#                → faithfulness_verdicts coalesced with the Compliance
#                  hype_stage row (split surface — see below)
#                → thread siblings via content_thread_id
#
# Gate verdict is SPLIT: thread/video drafts log into
# `faithfulness_verdicts.draft_id` (text); full-flow drafts pass through
# `hype_stages` with `agent_name='Compliance'`. Coalesce both, degrade
# gracefully when either is missing. `fv.draft_id` is TEXT while
# `daily_drafts.id` is UUID; cast on the lookup side.
@router.get("/lifecycle/{draft_id}")
async def get_draft_lifecycle(draft_id: str, user=Depends(require_auth)):
    """Operator-language draft lifecycle. See block comment above.

    Output shape — outer keys are OPERATOR labels (Turkish), not infra
    terms. Internal field names (agent_name, gate_version, …) live ONLY
    inside the `engineer` sub-object so the page can keep them behind a
    collapsed "Detaylar (teknik)" drawer.
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    # ─── source story ────────────────────────────────────────────────
    trend_id = draft.get("trend_id")
    trend_row: Optional[dict] = None
    if trend_id:
        tr = (sb.table("trends")
                .select("id, topic, source_name, url, raw_content, "
                        "published_at, created_at, category, score")
                .eq("id", trend_id).limit(1).execute().data) or []
        trend_row = tr[0] if tr else None

    # ─── why-coverable: editor's-desk judgment for this trend, if any ─
    desk_row: Optional[dict] = None
    try:
        d = (sb.table("editorial_lead_judgments")
                .select("id, judgment_date, dry_run, lead_trend_id, "
                        "lead_topic, lead_outcome, operator_sentence, "
                        "passed_over_trend_id, passed_over_topic, "
                        "reason_clauses, created_at")
                .eq("lead_trend_id", trend_id)
                .eq("account_id", draft.get("account_id"))
                .order("created_at", desc=True).limit(1).execute().data) or []
        desk_row = d[0] if d else None
    except Exception:
        desk_row = None

    # ─── what-written: this draft + sibling drafts on the same thread ─
    thread_id = draft.get("content_thread_id")
    siblings: list[dict] = []
    if thread_id:
        try:
            s = (sb.table("daily_drafts")
                    .select("id, platform, status, postiz_state, release_url, "
                            "scheduled_at, video_url, image_url, content")
                    .eq("content_thread_id", thread_id)
                    .neq("id", draft["id"]).execute().data) or []
            siblings = s
        except Exception:
            siblings = []

    # ─── visual ───────────────────────────────────────────────────────
    asset: Optional[dict] = None
    if draft.get("image_asset_id"):
        try:
            a = (sb.table("persona_assets")
                    .select("id, image_url, scene_type, composition_type, "
                            "generation_metadata, clip_similarity, aesthetic_score, "
                            "model_used, cost_usd, status, created_at")
                    .eq("id", draft["image_asset_id"]).limit(1)
                    .execute().data) or []
            asset = a[0] if a else None
        except Exception:
            asset = None

    # ─── gate verdict (split surface, coalesce both) ──────────────────
    # 1) faithfulness_verdicts: thread/video path. draft_id is TEXT, so
    #    compare as text.
    fv_row: Optional[dict] = None
    try:
        v = (sb.table("faithfulness_verdicts")
                .select("verdict, final_action, path, gate_version, "
                        "tier0_blocked, tier1_blocked, tier2_blocked, "
                        "tier1_pass_ratio, ungrounded_entities, "
                        "ungrounded_claims, ungrounded_angles, healed, "
                        "reject_reason_class, reasoning, created_at")
                .eq("draft_id", str(draft["id"]))
                .order("created_at", desc=True).limit(1)
                .execute().data) or []
        fv_row = v[0] if v else None
    except Exception:
        fv_row = None
    # 2) hype_stages Compliance row: full-flow path.
    compliance_stage: Optional[dict] = None
    run_id = draft.get("hype_run_id")
    if run_id:
        try:
            s = (sb.table("hype_stages")
                    .select("agent_name, status, output, model_used, "
                            "tokens_used, duration_ms, started_at, completed_at, error")
                    .eq("run_id", run_id)
                    .ilike("agent_name", "Compliance%")
                    .order("stage_order", desc=True).limit(1)
                    .execute().data) or []
            compliance_stage = s[0] if s else None
        except Exception:
            compliance_stage = None

    # Coalesce gate verdict to a single operator-label.
    gate_state = "bilinmiyor"
    gate_label_detail: Optional[str] = None
    if fv_row:
        v = fv_row.get("verdict") or ""
        if v == "PASS":
            gate_state = "geçti"
        elif v in ("HARD_BLOCK", "ERROR"):
            gate_state = "engellendi"
            gate_label_detail = (fv_row.get("reject_reason_class")
                                  or fv_row.get("verdict") or "").lower() or None
        else:
            gate_state = v.lower()
    elif compliance_stage:
        st = (compliance_stage.get("status") or "").lower()
        if st == "success":
            gate_state = "geçti"
        elif st in ("failed", "error"):
            gate_state = "engellendi"
        else:
            gate_state = st or "bilinmiyor"

    # ─── where-published ──────────────────────────────────────────────
    published_at = draft.get("scheduled_at")
    release_url = draft.get("release_url")
    postiz_state = draft.get("postiz_state")
    where_state = "yayında değil"
    if release_url and postiz_state == "PUBLISHED":
        where_state = "yayında"
    elif postiz_state in ("ERROR",):
        where_state = "yayınlanamadı"
    elif draft.get("status") == "approved":
        where_state = "kuyrukta"
    elif draft.get("status") in ("pending", "pending_review"):
        where_state = "onay bekliyor"

    # ─── shape response (operator-language outer; engineer drawer)────
    return {
        "draft": {
            "id": draft["id"],
            "title": draft.get("trend_topic") or "(başlıksız)",
            "platform": draft.get("platform"),
            "status_label": where_state,
            "content": draft.get("content"),
            "image_url": draft.get("image_url"),
            "video_url": draft.get("video_url"),
            "release_url": release_url,
            "scheduled_at": published_at,
            "created_at": draft.get("created_at"),
        },
        "source": {
            "topic": (trend_row or {}).get("topic"),
            "source_name": (trend_row or {}).get("source_name"),
            "url": (trend_row or {}).get("url"),
            "published_at": (trend_row or {}).get("published_at"),
            "discovered_at": (trend_row or {}).get("created_at"),
            "category": (trend_row or {}).get("category"),
        },
        "why_coverable": (
            {
                "decision": (
                    "yazıldı"
                    if (desk_row.get("lead_trend_id") == trend_id and not desk_row.get("dry_run"))
                    else "değerlendirildi"
                ),
                "operator_sentence": desk_row.get("operator_sentence"),
                "lead_outcome": desk_row.get("lead_outcome"),
                "judgment_date": desk_row.get("judgment_date"),
            } if desk_row else None
        ),
        "what_written": {
            "this_post": {
                "platform": draft.get("platform"),
                "content": draft.get("content"),
                "char_count": len(draft.get("content") or ""),
            },
            "thread_siblings": [
                {
                    "draft_id": s["id"],
                    "platform": s.get("platform"),
                    "status": s.get("status"),
                    "release_url": s.get("release_url"),
                    "has_video": bool(s.get("video_url")),
                } for s in siblings
            ],
        },
        "visual": (
            {
                "image_url": asset.get("image_url"),
                "scene_type": asset.get("scene_type"),
                "composition_type": asset.get("composition_type"),
            } if asset else None
        ),
        # SEV-1 follow-up P0 — render-time integrity verdict, operator
        # facing. Surfaced even when the draft has no `asset` row
        # because video integrity belongs alongside the visual block.
        "video_integrity": (
            {
                # actual / expected in seconds, plus a render-quality
                # label the UI can show inline: ✓ "video tam: 42s /
                # beklenen 44s ✓" — or ⚠ for FAIL.
                "actual_duration_s": draft.get("video_duration_s"),
                "expected_duration_s": draft.get("expected_duration_s"),
                "ok": draft.get("video_integrity_ok"),
                "reason": draft.get("video_integrity_reason"),
                "checked_at": draft.get("video_integrity_checked_at"),
            } if draft.get("video_url") else None
        ),
        "gate_passed": {
            "state": gate_state,
            "detail": gate_label_detail,
        },
        "where_published": {
            "state": where_state,
            "release_url": release_url,
            "scheduled_at": published_at,
            "platform": draft.get("platform"),
        },
        # Collapsed by default in the UI under "Detaylar (teknik)".
        # Keeping these names verbatim (faithfulness_verdicts /
        # hype_stages / persona_assets) because the engineer reading
        # this drawer is looking at the underlying tables anyway.
        "engineer": {
            "faithfulness_verdict": fv_row,
            "compliance_stage": compliance_stage,
            "persona_asset": asset,
            "editorial_lead_judgment": desk_row,
            "hype_run_id": run_id,
            "trend_raw": trend_row,
        },
    }


@router.get("/drafts/{draft_id}/stages")
async def get_draft_stages(draft_id: str, user=Depends(require_auth)):
    """Phase 17.5 — Per-agent breakdown for the draft's underlying hype_run.

    Returns rich structured outputs for each agent stage (TrendScout, Content
    Strategist, TypeHype V3 Generator, Compliance). Drives the "Hype Crew
    nasıl düşündü?" accordion in the UI.
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)
    run_id = draft.get("hype_run_id")
    if not run_id:
        return {"stages": [], "run": None}

    stages = (
        sb.table("hype_stages")
        .select(
            "stage_order, agent_name, output, model_used, tokens_used, duration_ms, "
            "status, error, started_at, completed_at"
        )
        .eq("run_id", run_id)
        .order("stage_order")
        .execute()
    )
    run = (
        sb.table("hype_runs")
        .select("id, total_tokens, total_cost_usd, started_at, completed_at, status")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    return {
        "stages": stages.data or [],
        "run": (run.data or [None])[0],
    }


@router.get("/stats/user-feedback")
async def stats_user_feedback(
    account_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    user=Depends(require_auth),
):
    """Phase 17.4 — Counts of the USER's explicit approve/reject/edit decisions
    over the last N days. Distinct from `hype_runs.status` which includes
    system auto-rejections (`rejected_by_compliance`) that the user never saw.
    """
    # Phase 28.M — workspace-wide: count actions from ALL collaborators
    # (owner + accepted teammates), not just the current viewer.
    from datetime import datetime, timezone, timedelta
    from services.access_control import accessible_owner_ids
    sb = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = (
        sb.table("hype_feedback")
        .select("action, created_at")
        .in_("user_id", accessible_owner_ids(user.id))
        .gte("created_at", cutoff)
    )
    if account_id:
        _verify_account_ownership(account_id, user.id)
        q = q.eq("account_id", account_id)
    rows = q.execute().data or []
    counts = {"approved": 0, "rejected": 0, "edited": 0}
    for r in rows:
        a = r.get("action")
        if a in counts:
            counts[a] += 1
    return {"days": days, "counts": counts, "total": len(rows)}


@router.post("/drafts/{draft_id}/refine")
async def refine_draft(
    draft_id: str,
    body: dict,
    user=Depends(require_auth),
):
    """AI-refine an auto-draft using the same quick-tags + feedback flow as XAIModule.

    Reuses backend.prompts.evolve.build_evolve_prompt and
    backend.server.generate_with_openrouter. Does NOT write to daily_drafts —
    returns variants for the user to pick from in the UI. Apply selection
    happens via the existing /drafts/:id/edit endpoint.
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    feedback = (body.get("feedback") or "").strip()
    quick_tags = body.get("quick_tags") or []
    variant_count = max(1, min(5, int(body.get("variant_count") or 3)))

    # Resolve user's style profile prompt (if any) so refine respects voice.
    style_prompt = ""
    try:
        cfg = sb.table("hype_account_config").select("active_style_profile_id").eq("account_id", draft["account_id"]).limit(1).execute()
        sid = (cfg.data or [{}])[0].get("active_style_profile_id") if cfg.data else None
        if sid:
            from services.access_control import accessible_owner_ids
            prof = sb.table("style_profiles").select("style_fingerprint").eq("id", sid).in_("user_id", accessible_owner_ids(user.id)).limit(1).execute()
            if prof.data:
                fp = prof.data[0].get("style_fingerprint") or {}
                # Compact summary — full DNA is overkill for refine
                import json as _json
                style_prompt = "Style fingerprint:\n" + _json.dumps(fp, ensure_ascii=False, indent=2)[:1500]
    except Exception as e:
        logger.warning(f"refine_draft: style resolve failed: {e}")

    from prompts.evolve import build_evolve_prompt

    system_prompt = build_evolve_prompt(
        selected_variants=[draft["content"]],
        feedback=feedback,
        quick_tags=quick_tags,
        original_topic=draft.get("trend_topic") or "",
        platform=draft.get("platform") or "twitter",
        content_type="tweet",
        variant_count=variant_count,
        style_prompt=style_prompt,
    )

    # We bypass generate_with_openrouter here because its uzunluk-enforcement
    # path replaces "\n" with ". " on retry to shrink overlong content, which
    # corrupts the JSON envelope build_evolve_prompt asks for. /api/evolve
    # uses the OpenAI SDK directly for the same reason — we mirror that here
    # but point at OpenRouter so we get Gemini-Flash pricing.
    import os, json as _json
    from openai import OpenAI

    or_api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not or_api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")
    or_client = OpenAI(api_key=or_api_key, base_url="https://openrouter.ai/api/v1")

    # Strip CrewAI's "openrouter/" prefix — direct OpenAI SDK doesn't want it.
    model_id = os.environ.get("HYPE_MODEL_FAST", "google/gemini-3-flash-preview")
    if model_id.startswith("openrouter/"):
        model_id = model_id[len("openrouter/"):]

    try:
        resp = or_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "Sen bir sosyal medya içerik uzmanısın. İstenen formatta JSON döndür."},
                {"role": "user", "content": system_prompt},
            ],
            temperature=0.8,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
    except Exception as e:
        logger.error(f"refine_draft generation error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"refine failed: {type(e).__name__}")

    variants_clean = []
    try:
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("```", 2)[1] if "```" in s[3:] else s[3:]
            if s.startswith("json"):
                s = s[4:].lstrip()
            s = s.rsplit("```", 1)[0].strip()
        parsed = _json.loads(s)
        raw_variants = parsed.get("variants") if isinstance(parsed, dict) else None
        if isinstance(raw_variants, list):
            for i, v in enumerate(raw_variants[:variant_count]):
                if isinstance(v, dict) and isinstance(v.get("content"), str) and v["content"].strip():
                    variants_clean.append({"index": i, "content": v["content"].strip()})
                elif isinstance(v, str) and v.strip():
                    variants_clean.append({"index": i, "content": v.strip()})
    except Exception as e:
        logger.warning(f"refine_draft: variants parse failed ({type(e).__name__}); returning raw single variant")
        if raw.strip():
            variants_clean = [{"index": 0, "content": raw.strip()}]

    return {
        "variants": variants_clean,
        "tokens_used": tokens,
        "draft_id": draft_id,
        "quick_tags": quick_tags,
    }


# ─────────────────────────────────────────────────────────────────────────
# Phase 28.P — Iterative refinement loop
# /iterate generates ONE new version per call, records every step in
# draft_iterations, bounded by MAX_ITERATIONS. Each rejection's feedback
# accumulates into the LLM prompt so the model sees the full chain.
# ─────────────────────────────────────────────────────────────────────────

PHASE_28P_MAX_ITERATIONS = 10


@router.get("/image-regen-jobs/{job_id}")
async def get_image_regen_job(job_id: str, user=Depends(require_auth)):
    """Sprint 1B — frontend polls this to track image regen progress.

    Returns job status + image_url when completed. Frontend can call every
    3-5s after triggering /iterate with scope=image|both.
    """
    from services.access_control import accessible_owner_ids
    sb = get_supabase()
    row = (
        sb.table("image_regen_jobs")
        .select(
            "id, draft_id, iteration_version, status, retry_count, max_retries, "
            "image_url, image_asset_id, cost_usd, error, "
            "created_at, started_at, completed_at"
        )
        .eq("id", job_id)
        .in_("owner_user_id", accessible_owner_ids(user.id))
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "image regen job not found or access denied")
    return row.data[0]


@router.get("/drafts/{draft_id}/iterations")
async def get_draft_iterations(
    draft_id: str,
    user=Depends(require_auth),
):
    """Phase 28.R-Lite — server-side truth for IterationDialog.

    The draft list response includes a stale `iterations` array (cached
    at list time). When the dialog re-opens after a previous iteration
    was persisted, the UI needs the latest server state so v2/v3/... are
    visible. Frontend calls this on every dialog open.
    """
    sb = get_supabase()
    _verify_draft_ownership(draft_id, user.id)  # raises 404 if no access
    rows = (
        sb.table("draft_iterations")
        .select(
            "version, content, status, "
            "image_url, image_asset_id, "
            "rejection_category, rejection_feedback, rejection_target, "
            "image_rejection_reason, "
            "tokens_used, cost_usd, llm_model, "
            "rejected_by, rejected_at, approved_at, created_at"
        )
        .eq("draft_id", draft_id)
        .order("version", desc=False)
        .execute()
    )
    return {"draft_id": draft_id, "iterations": rows.data or []}


@router.post("/drafts/{draft_id}/iterate")
async def iterate_draft(
    draft_id: str,
    body: dict,
    user=Depends(require_auth),
):
    """Phase 28.P — generate the NEXT iteration for a draft after user
    rejected the current version.

    Flow:
      1. Verify draft access (workspace-aware).
      2. Mark current/latest iteration row as 'rejected' with the user's
         feedback (creating version=1 lazily if no rows exist yet).
      3. Build cumulative feedback chain from ALL prior iterations.
      4. Call LLM via evolve prompt with previous_iterations context.
      5. Insert new draft_iterations row (version = prev + 1, status=pending).
      6. Return new content + version + cumulative cost so UI can update.

    Body:
      {
        rejection_category: str,
        rejection_feedback: str,
        rejection_target: 'text' | 'image' | 'both',
        image_rejection_reason: str | None,
        quick_tags: list[str] (optional, hint for prompt builder)
      }

    Errors:
      - 409 if version >= 10 → frontend must show "manuel düzelt" message
      - 500 on LLM failure (iteration row NOT inserted)
    """
    sb = get_supabase()
    draft = _verify_draft_ownership(draft_id, user.id)

    rejection_category = (body.get("rejection_category") or "other").strip()
    rejection_feedback = (body.get("rejection_feedback") or "").strip()
    rejection_target = body.get("rejection_target") or "both"
    image_rejection_reason = body.get("image_rejection_reason")
    quick_tags = body.get("quick_tags") or []

    # Phase 43.B.4 — anchor-preserve regen. When the user manually edited
    # a portion of the draft (e.g. corrected a name, fixed a stat) and now
    # wants to regenerate the rest, `preserve_user_edits=True` instructs
    # the LLM to carry `preserved_segments` byte-for-byte and only rewrite
    # the surrounding text. Caller supplies the segments verbatim — we
    # don't infer them.
    preserve_user_edits = bool(body.get("preserve_user_edits"))
    preserved_segments_raw = body.get("preserved_segments") or []
    preserved_segments: list[str] = [
        str(s).strip()
        for s in preserved_segments_raw
        if isinstance(s, str) and s.strip()
    ][:8]  # hard cap — more than 8 anchors means the user should re-edit by hand

    # ── 1. Load existing iterations (ordered by version asc) ────────────
    iter_rows_q = (
        sb.table("draft_iterations")
        .select("id, version, content, rejection_category, rejection_feedback, status")
        .eq("draft_id", draft_id)
        .order("version", desc=False)
        .execute()
    )
    iter_rows = iter_rows_q.data or []

    # Bootstrap v1 from daily_drafts.content if no iteration rows exist yet
    # (old drafts predating Phase 28.P).
    if not iter_rows:
        v1_insert = (
            sb.table("draft_iterations")
            .insert({
                "draft_id": draft_id,
                "version": 1,
                "content": draft["content"],
                "status": "rejected",
                "rejection_category": rejection_category,
                "rejection_feedback": rejection_feedback,
                "image_rejection_reason": image_rejection_reason,
                "rejection_target": rejection_target,
                "rejected_by": user.id,
                "rejected_at": datetime.now(timezone.utc).isoformat(),
            })
            .execute()
        )
        iter_rows = v1_insert.data or []
        latest_version = 1
    else:
        # Mark the most recent (pending) iteration as rejected
        latest = iter_rows[-1]
        latest_version = latest["version"]
        if latest["status"] == "pending":
            sb.table("draft_iterations").update({
                "status": "rejected",
                "rejection_category": rejection_category,
                "rejection_feedback": rejection_feedback,
                "image_rejection_reason": image_rejection_reason,
                "rejection_target": rejection_target,
                "rejected_by": user.id,
                "rejected_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", latest["id"]).execute()
            # refresh the local copy so prompt sees the new feedback
            latest["status"] = "rejected"
            latest["rejection_category"] = rejection_category
            latest["rejection_feedback"] = rejection_feedback

    # ── 2. Guard MAX_ITERATIONS ────────────────────────────────────────
    next_version = latest_version + 1
    if next_version > PHASE_28P_MAX_ITERATIONS:
        raise HTTPException(
            status_code=409,
            detail=f"max_iterations_reached:{PHASE_28P_MAX_ITERATIONS}",
        )

    # ── 3. Resolve style fingerprint (same as refine) ──────────────────
    style_prompt = ""
    try:
        cfg = sb.table("hype_account_config").select("active_style_profile_id").eq("account_id", draft["account_id"]).limit(1).execute()
        sid = (cfg.data or [{}])[0].get("active_style_profile_id") if cfg.data else None
        if sid:
            from services.access_control import accessible_owner_ids
            prof = sb.table("style_profiles").select("style_fingerprint").eq("id", sid).in_("user_id", accessible_owner_ids(user.id)).limit(1).execute()
            if prof.data:
                fp = prof.data[0].get("style_fingerprint") or {}
                import json as _json_sp
                style_prompt = "Style fingerprint:\n" + _json_sp.dumps(fp, ensure_ascii=False, indent=2)[:1500]
    except Exception as e:
        logger.warning(f"iterate_draft: style resolve failed: {e}")

    # ── 4. Build prompt with cumulative iteration history ──────────────
    from prompts.evolve import build_evolve_prompt

    # Format previous iterations for prompt context
    prev_iterations = []
    for r in iter_rows:
        prev_iterations.append({
            "version": r.get("version"),
            "content": r.get("content"),
            "rejection_category": r.get("rejection_category"),
            "rejection_feedback": r.get("rejection_feedback"),
        })

    system_prompt = build_evolve_prompt(
        selected_variants=[draft["content"]],
        feedback=rejection_feedback,
        quick_tags=quick_tags,
        original_topic=draft.get("trend_topic") or "",
        platform=draft.get("platform") or "twitter",
        content_type="tweet",
        variant_count=1,  # Phase 28.P: single variant per iteration
        style_prompt=style_prompt,
        previous_iterations=prev_iterations,  # NEW Phase 28.P
        # Phase 43.B.4 — anchor-preserve directive (XML-delimited).
        preserve_user_edits=preserve_user_edits,
        preserved_segments=preserved_segments,
    )

    # ── 5. LLM call ─────────────────────────────────────────────────────
    import os, json as _json
    from openai import OpenAI
    or_api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not or_api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")
    or_client = OpenAI(api_key=or_api_key, base_url="https://openrouter.ai/api/v1")

    model_id = os.environ.get("HYPE_MODEL_FAST", "google/gemini-3-flash-preview")
    if model_id.startswith("openrouter/"):
        model_id = model_id[len("openrouter/"):]

    try:
        resp = or_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "Sen bir sosyal medya içerik uzmanısın. İstenen formatta JSON döndür."},
                {"role": "user", "content": system_prompt},
            ],
            temperature=0.85,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
    except Exception as e:
        logger.error(f"iterate_draft generation error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"iterate failed: {type(e).__name__}")

    # Parse single variant
    new_content = ""
    try:
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("```", 2)[1] if "```" in s[3:] else s[3:]
            if s.startswith("json"):
                s = s[4:].lstrip()
            s = s.rsplit("```", 1)[0].strip()
        parsed = _json.loads(s)
        raw_variants = parsed.get("variants") if isinstance(parsed, dict) else None
        if isinstance(raw_variants, list) and raw_variants:
            first = raw_variants[0]
            if isinstance(first, dict) and isinstance(first.get("content"), str):
                new_content = first["content"].strip()
            elif isinstance(first, str):
                new_content = first.strip()
    except Exception as e:
        logger.warning(f"iterate_draft: parse failed ({type(e).__name__}); using raw")
        new_content = raw.strip()

    # Phase 28.J critic B7 — empty content guard: retry ONCE with bumped temperature
    # before raising. User's feedback is precious; don't lose it on a single bad LLM turn.
    if not new_content:
        logger.warning(f"iterate_draft: empty content on first try; retrying with t=1.0")
        try:
            resp2 = or_client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": "Sen bir sosyal medya icerik uzmanisin. SADECE JSON don, baska metin EKLEME."},
                    {"role": "user", "content": system_prompt},
                ],
                temperature=1.0,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            raw2 = resp2.choices[0].message.content or ""
            tokens += resp2.usage.total_tokens if resp2.usage else 0
            s = raw2.strip()
            if s.startswith("```"):
                s = s.split("```", 2)[1] if "```" in s[3:] else s[3:]
                if s.startswith("json"): s = s[4:].lstrip()
                s = s.rsplit("```", 1)[0].strip()
            parsed = _json.loads(s)
            vs = parsed.get("variants") or []
            if vs:
                first = vs[0]
                new_content = first.get("content", "").strip() if isinstance(first, dict) else (first.strip() if isinstance(first, str) else "")
        except Exception as e:
            logger.error(f"iterate_draft retry failed: {e}")

    if not new_content:
        raise HTTPException(status_code=500, detail="iterate_empty_content")

    # ── Phase 43.B.4 — anchor-preserve compliance check ────────────────
    # The decision was: ship with success-rate logging so we can disable
    # the feature if compliance falls below ~70% (Critic's threshold). We
    # report per-segment hits/misses in the response so the UI can warn
    # the user when the LLM mangled their preserved edit, and we log a
    # structured signal for offline analysis.
    preserve_stats: dict = {}
    if preserve_user_edits and preserved_segments:
        misses: list[str] = []
        for seg in preserved_segments:
            if seg and seg not in new_content:
                misses.append(seg)
        total = len(preserved_segments)
        hits = total - len(misses)
        success_rate = round(hits / total, 3) if total else 1.0
        preserve_stats = {
            "requested": total,
            "preserved": hits,
            "lost": len(misses),
            "success_rate": success_rate,
            # Truncate miss samples so the JSON stays small in logs/UI
            "miss_samples": [m[:80] for m in misses[:3]],
        }
        # Structured log line for offline analysis. Once we have a few
        # hundred samples we'll know whether anchor-preserve compliance
        # is high enough to keep the feature on by default.
        logger.info(
            f"iterate_draft anchor_preserve: draft={draft_id} "
            f"requested={total} preserved={hits} rate={success_rate:.2f} "
            f"model={model_id}"
        )

    # Naive cost estimate (Gemini Flash ~$0.15/M)
    cost_usd = round((tokens / 1_000_000) * 0.15, 6)

    # ── 6a. Resolve inherited image for scope='text' ──────────────────
    # Critic Bulgu 9 (P1) — if user changes only text, the new iteration
    # row would have image_url=NULL, leaving the card visually empty.
    # Carry forward the parent draft's image so the card stays whole.
    # When scope='image' or 'both' the worker will overwrite this; null
    # is fine there because the spinner placeholder owns the slot until
    # then.
    inherited_image_url = None
    inherited_image_asset = None
    if rejection_target == "text":
        # Latest iteration's image (if any), else parent daily_drafts.image_url
        latest_with_image = (
            sb.table("draft_iterations")
            .select("image_url, image_asset_id")
            .eq("draft_id", draft_id)
            .not_.is_("image_url", "null")
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        if latest_with_image.data:
            inherited_image_url = latest_with_image.data[0].get("image_url")
            inherited_image_asset = latest_with_image.data[0].get("image_asset_id")
        else:
            inherited_image_url = draft.get("image_url")
            inherited_image_asset = draft.get("image_asset_id")

    # ── 6b. Insert new iteration row (race-safe: critic A1) ────────────
    # Two concurrent /iterate calls would both compute next_version=N
    # and both INSERT, hitting UNIQUE(draft_id, version) → 23505. We
    # catch that and re-read the chain so the winning version is what
    # we return, and the losing caller still sees the iteration that
    # actually got persisted.
    inserted_data = None
    try:
        ins = (
            sb.table("draft_iterations")
            .insert({
                "draft_id": draft_id,
                "version": next_version,
                "content": new_content,
                "status": "pending",
                "tokens_used": tokens,
                "cost_usd": cost_usd,
                "llm_model": model_id,
                # Phase 28.R-Lite — carry forward parent image when text-only
                "image_url": inherited_image_url,
                "image_asset_id": inherited_image_asset,
            })
            .execute()
        )
        inserted_data = ins.data or []
    except Exception as e:
        msg = str(e).lower()
        if "23505" in msg or "duplicate" in msg or "unique" in msg:
            logger.warning(f"iterate_draft: concurrent INSERT race on v{next_version}; re-reading chain")
            # Another caller won; refetch and return the persisted iteration
            recheck = (
                sb.table("draft_iterations")
                .select("id, version, content, status, tokens_used, cost_usd")
                .eq("draft_id", draft_id)
                .eq("version", next_version)
                .limit(1)
                .execute()
            )
            inserted_data = recheck.data or []
            if not inserted_data:
                raise HTTPException(status_code=409, detail="iteration_race")
        else:
            logger.exception(f"iterate_draft INSERT failed: {e}")
            raise HTTPException(status_code=500, detail=f"iterate_insert_failed: {type(e).__name__}")
    inserted = type("R", (), {"data": inserted_data})  # mimic sb response shape

    # ── 7. Sprint 1B — Enqueue image regen job if scope demands it ─────
    # When the user requested image regeneration, we don't block the
    # response (Wiro+compliance takes ~30-60s). We persist a queued job
    # to `image_regen_jobs`; the hype-crew worker (systemd timer, every
    # 30s) picks it up, runs the pipeline, and UPDATEs the iteration row
    # with the new image_url. Frontend polls or subscribes to this table.
    image_job_id = None
    if rejection_target in ("image", "both"):
        try:
            # Resolve persona_id: prefer daily_drafts.persona_id, fall back
            # to personas.primary_account_id == draft.account_id lookup.
            persona_id = draft.get("persona_id")
            if not persona_id:
                acc_id = draft.get("account_id")
                if acc_id:
                    p_row = (
                        sb.table("personas")
                        .select("id")
                        .eq("primary_account_id", acc_id)
                        .limit(1)
                        .execute()
                    )
                    if p_row.data:
                        persona_id = p_row.data[0]["id"]
            # V2 backlog #5 — owner_user_id is the workspace owner (so RLS
            # still works after a collaborator off-boards); created_by_user_id
            # is the audit trail of who actually clicked Düzelt.
            workspace_owner = draft.get("user_id") or user.id
            job_ins = sb.table("image_regen_jobs").insert({
                "draft_id": draft_id,
                "iteration_version": next_version,
                "persona_id": persona_id,
                "rejection_target": rejection_target,
                "rejection_category": rejection_category,
                "rejection_feedback": rejection_feedback,
                "image_rejection_reason": image_rejection_reason,
                "trend_topic": draft.get("trend_topic"),
                "owner_user_id": workspace_owner,
                "created_by_user_id": user.id,
                "status": "queued",
            }).execute()
            if job_ins.data:
                image_job_id = job_ins.data[0]["id"]
                logger.info(
                    f"iterate_draft: queued image regen job {image_job_id} "
                    f"for draft={draft_id} v{next_version}"
                )
        except Exception as e:
            # Best-effort: text iteration already succeeded. Log + continue.
            logger.warning(f"iterate_draft: image job enqueue failed (non-fatal): {e}")

    return {
        "version": next_version,
        "content": new_content,
        "tokens_used": tokens,
        "cost_usd": cost_usd,
        "remaining_attempts": PHASE_28P_MAX_ITERATIONS - next_version,
        "max_iterations": PHASE_28P_MAX_ITERATIONS,
        "image_job_id": image_job_id,  # Sprint 1B: frontend polls this for progress
        # Phase 43.B.4 — anchor-preserve compliance report (only present
        # when the caller asked for preservation). Empty dict otherwise so
        # the UI can switch on truthiness.
        "preserve_stats": preserve_stats,
        "iterations": [
            {
                "version": r.get("version"),
                "status": r.get("status"),
                "rejection_category": r.get("rejection_category"),
                "content": r.get("content"),
            }
            for r in (iter_rows + (inserted.data or []))
        ],
    }


@router.get("/style-profiles")
async def list_style_profiles(user=Depends(require_auth)):
    """Return all style_profiles in the workspace (owner + accepted collaborators)."""
    from services.access_control import accessible_owner_ids
    sb = get_supabase()
    result = (
        sb.table("style_profiles")
        .select("id, name, source_type, tweet_count, profile_version, account_id, created_at")
        .in_("user_id", accessible_owner_ids(user.id))  # Phase 28.M
        .order("created_at", desc=True)
        .execute()
    )
    return {"items": result.data or [], "count": len(result.data or [])}


@router.get("/runs/recent")
async def list_recent_runs(
    account_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=500),
    user=Depends(require_auth),
):
    """Recent Hype Crew runs for observability (frontend "Auto-Drafts" admin tab)."""
    from services.access_control import accessible_owner_ids
    sb = get_supabase()
    # Phase 28.M — accounts visible to me (owner OR accepted collaborator)
    owned = (
        sb.table("connected_accounts")
        .select("id")
        .in_("user_id", accessible_owner_ids(user.id))
        .execute()
    )
    owned_ids = [r["id"] for r in (owned.data or []) if isinstance(r, dict) and r.get("id")]
    if not owned_ids:
        return {"items": [], "count": 0}

    q = (
        sb.table("hype_runs")
        .select(
            "id, account_id, trend_id, status, dry_run, total_tokens, "
            "total_cost_usd, draft_content, postiz_post_id, scheduled_at, "
            "started_at, completed_at, error, flow_state, "
            # Crew Akışı — single-query PostgREST embeds (no N+1):
            #   trends(topic)       → forward FK on trend_id
            #   hype_stages(status) → reverse FK (list of stage statuses)
            "trends(topic), hype_stages(status)"
        )
        .in_("account_id", owned_ids)
        .order("started_at", desc=True)
        .limit(limit)
    )
    if account_id:
        _verify_account_ownership(account_id, user.id)
        q = q.eq("account_id", account_id)
    result = q.execute()

    items = []
    for r in (result.data or []):
        if not isinstance(r, dict):
            continue
        # Pop embed columns — they are an implementation detail, the
        # response keeps the original flat shape + 3 derived fields.
        trend = r.pop("trends", None)
        stages = r.pop("hype_stages", None) or []

        # Kart run'ı mı? flow_state.run_kind → rozet + başlık (RunList)
        _fs = r.pop("flow_state", None) if isinstance(r.get("flow_state"), (dict, type(None))) else None
        run_kind = "news"
        card_source = None
        reason = None
        if isinstance(_fs, dict):
            reason = _fs.get("reason")
            if _fs.get("run_kind") == "cards":
                run_kind = "cards"
                card_source = _fs.get("card_source")
        r["run_kind"] = run_kind
        r["card_source"] = card_source
        r["reason"] = reason
        # produced: bu run gerçekten bir post/draft üretti mi? (boş cron run'ları ayırt et)
        produced = bool(r.get("trend_id") or r.get("draft_content") or r.get("postiz_post_id"))
        r["produced"] = produced or run_kind == "cards"

        trend_title = None
        try:
            if run_kind == "cards":
                trend_title = "SÖZLÜK + SENCE? kartları" + (
                    " (haber-sonrası)" if card_source == "companion" else " (kurak gün)"
                )
            elif isinstance(trend, dict) and trend.get("topic"):
                trend_title = trend["topic"]
            elif r.get("draft_content"):
                trend_title = str(r["draft_content"])[:60]
            elif not produced:
                # Boş cron run'ı → "—" yerine anlamlı sebep
                trend_title = "Aday yok · taze AI haberi bulunamadı"
        except Exception:
            trend_title = None
        r["trend_title"] = trend_title

        try:
            bad_run = r.get("status") in (
                "failed", "blocked_by_gate", "rejected_by_compliance"
            )
            bad_stage = any(
                isinstance(s, dict) and s.get("status") != "success"
                for s in stages
            )
            r["has_warnings"] = bool(bad_run or r.get("error") or bad_stage)
        except Exception:
            r["has_warnings"] = False

        r["duration_ms"] = _flow_duration_ms(
            r.get("started_at"), r.get("completed_at")
        )
        items.append(r)
    return {"items": items, "count": len(items)}


# ═════════════════════════════════════════════════════════════════════
# Crew Akışı — GET /runs/{run_id}/flow (operator pipeline view)
# ═════════════════════════════════════════════════════════════════════
# Fixed 7-node pipeline. First 6 map to hype_stages rows by agent_name;
# "publish" is virtual, derived from the run's daily_drafts.

_FLOW_NODE_DEFS = [
    ("trend_scout", "Haber Seçimi"),
    ("strategist", "Strateji"),
    ("writer", "Yazım"),
    ("gate", "Sadakat Kapısı"),
    ("visual", "Görsel"),
    ("video", "Video"),
    ("publish", "Yayın"),
]

# SÖZLÜK/SENCE? kart run'ları için AYRI node-seti (haber 7-node'undan bağımsız).
# Kart run'ı flow_state.run_kind=="cards" ile algılanır; stage'ler output.node +
# output.card_index ile bu node'lara eşlenir. Crew Flow'da tam şeffaflık.
_CARD_NODE_DEFS = [
    ("icerik", "İçerik Üret"),
    ("card_gate", "Kart Kapısı"),
    ("render", "Render"),
    ("publish", "Yayın"),
]

# Platform display order for the drafts list (then alphabetical).
_FLOW_PLATFORM_ORDER = {
    "twitter": 0, "linkedin": 1, "instagram": 2, "youtube": 3, "devto": 4,
}


def _flow_parse_ts(v) -> Optional[datetime]:
    """ISO timestamp → aware datetime; null-tolerant, never raises."""
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _flow_duration_ms(started_at, completed_at) -> Optional[int]:
    """completed - started in ms; None if either side is missing/unparseable."""
    s = _flow_parse_ts(started_at)
    e = _flow_parse_ts(completed_at)
    if s is None or e is None:
        return None
    try:
        return max(0, int((e - s).total_seconds() * 1000))
    except Exception:
        return None


def _flow_node_key_for_agent(agent_name) -> Optional[str]:
    """agent_name (hype_stages) → fixed node key. None = unknown stage."""
    n = (agent_name or "").strip() if isinstance(agent_name, str) else ""
    if n == "Trend Scout":
        return "trend_scout"
    if n == "Content Strategist":
        return "strategist"
    if n == "TypeHype V3 Generator":
        return "writer"
    if n.startswith("Compliance"):
        return "gate"
    if n == "Visual Director":
        return "visual"
    if n == "Video Director":
        return "video"
    return None


def _flow_publish_node(drafts: list, dry_run: bool) -> dict:
    """Derive the virtual 'publish' node from the run's daily_drafts."""
    published = [
        d for d in drafts
        if d.get("postiz_state") == "PUBLISHED" and d.get("release_url")
    ]
    if published:
        state_label, state = "yayında", "success"
    elif any(d.get("postiz_state") == "ERROR" for d in drafts):
        state_label, state = "yayın hatası", "failed"
    elif any(
        d.get("status") == "approved" or d.get("postiz_post_id")
        for d in drafts
    ):
        state_label, state = "kuyrukta", "success"
    elif any(
        d.get("status") in ("pending", "pending_review") for d in drafts
    ):
        state_label, state = "onay bekliyor", "success"
    elif dry_run:
        state_label, state = "dry-run", "skipped"
    else:
        state_label, state = "ulaşılmadı", "skipped"
    return {
        "state": state,
        "publish": {
            "state_label": state_label,
            "published_count": len(published),
            "total_count": len(drafts),
            "first_release_url": (
                published[0].get("release_url") if published else None
            ),
        },
    }


def _build_card_flow(run, trend, stage_rows, draft_rows, run_duration, fs) -> dict:
    """SÖZLÜK/SENCE? kart run'ı için flow yanıtı. Her kart = 4 node
    (icerik→card_gate→render→publish); stage'ler output.card_index ile gruplanır.
    Çoklu kart → `cards[]`; frontend kart seçiciyle gezer. Tam şeffaflık."""
    by_card: dict = {}
    saat: Optional[dict] = None
    for s in stage_rows:
        out = s.get("output") if isinstance(s.get("output"), dict) else {}
        node = out.get("node")
        ci = out.get("card_index")
        if node == "saat":
            saat = out
            continue
        if node and ci is not None:
            by_card.setdefault(ci, {})[node] = s

    summaries = fs.get("cards") if isinstance(fs.get("cards"), list) else []
    indices = sorted(by_card.keys()) if by_card else [
        c.get("index") for c in summaries if isinstance(c, dict)
    ]

    def _node(key, label, s):
        if s is None:
            return {"key": key, "label": label, "state": "pending", "output": None,
                    "tokens_used": 0, "tokens_estimated": False, "model_used": None,
                    "derived_duration_ms": None, "stage_order": None, "error": None,
                    "output_truncated": False}
        # Kart stage'leri gerçek duration_ms taşır (üret/gate/render/yayın ayrı ölçülür);
        # yoksa completed_at deltasına düş. "0 sn" sorununu çözer.
        dur = s.get("duration_ms")
        if not dur:
            dur = s.get("_derived_duration_ms")
        return {"key": key, "label": label,
                "state": "failed" if s.get("status") == "failed" else "success",
                "output": s.get("output"), "output_truncated": False,
                "tokens_used": s.get("tokens_used") or 0, "tokens_estimated": False,
                "model_used": s.get("model_used") or None,
                "derived_duration_ms": dur,
                "stage_order": s.get("stage_order"), "error": s.get("error")}

    cards = []
    for ci in indices:
        nm = by_card.get(ci, {})
        nodes = [_node(k, lbl, nm.get(k)) for k, lbl in _CARD_NODE_DEFS]
        meta = next((c for c in summaries if isinstance(c, dict) and c.get("index") == ci), {})
        render_out = (nm.get("render") or {}).get("output")
        img = meta.get("image_url") or (render_out.get("image_url") if isinstance(render_out, dict) else None)
        icerik_out = (nm.get("icerik") or {}).get("output")
        kind = meta.get("kind") or (icerik_out.get("kind") if isinstance(icerik_out, dict) else None)
        cards.append({"index": ci, "kind": kind, "key": meta.get("key"),
                      "image_url": img, "nodes": nodes})

    drafts = [{
        "id": d.get("id"), "platform": d.get("platform"), "content": d.get("content"),
        "status": d.get("status"), "postiz_state": d.get("postiz_state"),
        "postiz_post_id": d.get("postiz_post_id"), "image_url": d.get("image_url"),
        "scheduled_at": d.get("scheduled_at"),
        "char_count": len(d.get("content") or "") if isinstance(d.get("content"), str) else 0,
    } for d in draft_rows]

    return {
        "run": {
            "id": run.get("id"), "account_id": run.get("account_id"),
            "status": run.get("status"), "dry_run": run.get("dry_run"),
            "started_at": run.get("started_at"), "completed_at": run.get("completed_at"),
            "duration_ms": run_duration, "total_tokens": run.get("total_tokens"),
            "total_cost_usd": run.get("total_cost_usd"), "error": run.get("error"),
            "run_kind": "cards", "card_source": fs.get("card_source"),
            "card_count": fs.get("card_count"), "pick_times": (saat or {}).get("times"),
            "trend": trend,
        },
        "cards": cards,
        "default_card": 0,
        "nodes": cards[0]["nodes"] if cards else [],  # backward-compat (kart 0)
        "drafts": drafts,
        "trust_signals": {"opening_similarity": None, "gate_repairs": None,
                          "video_topic_match": "n/a", "cost_anomaly": None},
        "default_selected_node": "icerik",
    }


def _flow_opening_similarity(drafts: list) -> Optional[dict]:
    """Max pairwise similarity of the first 80 chars across platform drafts."""
    import difflib
    openings = []
    for d in drafts:
        content = d.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        norm = re.sub(r"[^\wçğıöşü ]", "", content[:80].lower()).strip()
        if norm:
            openings.append((d.get("platform"), norm))
    best = None
    for i in range(len(openings)):
        for j in range(i + 1, len(openings)):
            r = difflib.SequenceMatcher(
                None, openings[i][1], openings[j][1]
            ).ratio()
            if best is None or r > best[0]:
                best = (r, openings[i][0], openings[j][0])
    if best and best[0] >= 0.80:
        return {
            "max_ratio": round(best[0], 2),
            "platforms": [best[1], best[2]],
            "threshold": 0.8,
        }
    return None


def _flow_gate_repairs(sb, run: dict) -> Optional[dict]:
    """faithfulness_verdicts (path='cron_auto') in the run window, grouped
    per draft: a group that saw any non-PASS verdict but whose LAST verdict
    is PASS counts as 'repaired'. None when there are no rows at all."""
    started = run.get("started_at")
    if not started:
        return None
    end_dt = _flow_parse_ts(run.get("completed_at")) or datetime.now(timezone.utc)
    # 2026-06-11: pencere üst sınırı started+35dk ile KIRPILIR. Reaper'ın
    # saatler sonra kapattığı run'larda (completed_at=04:00 vakası) pencere
    # sonraki run'lara taşıp onların flow-cron-N verdict'lerini yutuyordu
    # (sentetik draft_id'ler run'lar arası çakışır) → sahte "repaired".
    # Gerçek run süresi systemd TimeoutStartSec=1800s ile sınırlı.
    _started_dt = _flow_parse_ts(started)
    if _started_dt is not None:
        _hard_cap = _started_dt + timedelta(minutes=35)
        if end_dt > _hard_cap:
            end_dt = _hard_cap
    end_iso = (end_dt + timedelta(seconds=60)).isoformat()
    rows = (
        sb.table("faithfulness_verdicts")
        .select("draft_id, verdict, created_at")
        .eq("path", "cron_auto")
        # 2026-06-11: cron verdict'lerinde account_id NULL yazılıyor — düz
        # eq filtresi HEPSİNİ eliyordu (canlıda yakalandı: 01:01 run'ının
        # HARD_BLOCK'u görünmüyordu). Hesap satırları VEYA NULL satırlar.
        .or_(f"account_id.eq.{run.get('account_id')},account_id.is.null")
        .gte("created_at", started)
        .lte("created_at", end_iso)
        .order("created_at")
        .execute()
        .data
    ) or []
    if not rows:
        return None
    groups: dict = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        groups.setdefault(r.get("draft_id"), []).append(r.get("verdict"))
    attempted = repaired = still_blocked = 0
    for verdicts in groups.values():
        saw_block = any(v != "PASS" for v in verdicts)
        if not saw_block:
            continue
        attempted += 1
        if verdicts[-1] == "PASS":
            repaired += 1
        else:
            still_blocked += 1
    return {
        "attempted": attempted,
        "repaired": repaired,
        "still_blocked": still_blocked,
    }


def _flow_cost_anomaly(sb, run: dict) -> Optional[dict]:
    """Run cost vs the median of the account's last 20 completed runs."""
    import statistics
    run_cost = run.get("total_cost_usd")
    if not isinstance(run_cost, (int, float)) or run_cost <= 0:
        return None
    rows = (
        sb.table("hype_runs")
        .select("total_cost_usd")
        .eq("account_id", run.get("account_id"))
        .eq("status", "completed")
        .neq("id", run.get("id"))
        .order("started_at", desc=True)
        .limit(20)
        .execute()
        .data
    ) or []
    costs = [
        r["total_cost_usd"] for r in rows
        if isinstance(r, dict) and isinstance(r.get("total_cost_usd"), (int, float))
    ]
    if not costs:
        return None
    median = statistics.median(costs)
    if median > 0 and run_cost > 2 * median:
        return {
            "median_usd": round(median, 4),
            "run_usd": round(float(run_cost), 4),
            "ratio": round(run_cost / median, 1),
        }
    return None


@router.get("/runs/{run_id}/flow")
async def get_run_flow(run_id: str, user=Depends(require_auth)):
    """Crew Akışı — full pipeline view of a single Hype Crew run.

    Always returns exactly 7 nodes in a fixed order; trust_signals are
    best-effort (each computed in its own try/except — a broken signal
    becomes null, the endpoint never 500s because of them).

    Exactly 5 queries: run+trend embed, stages, drafts, gate verdicts,
    cost history.
    """
    sb = get_supabase()

    # ── Query 1: run + trend embed ───────────────────────────────────
    run_rows = (
        sb.table("hype_runs")
        .select(
            "id, account_id, trend_id, status, dry_run, total_tokens, "
            "total_cost_usd, started_at, completed_at, error, flow_state, "
            "trends(id, topic, source_name, url, category)"
        )
        .eq("id", run_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not run_rows:
        raise HTTPException(status_code=404, detail="run not found")
    run = run_rows[0]
    _verify_account_ownership(run.get("account_id"), user.id)

    trend_embed = run.get("trends")
    trend = None
    if isinstance(trend_embed, dict):
        trend = {
            "id": trend_embed.get("id"),
            "topic": trend_embed.get("topic"),
            "source_name": trend_embed.get("source_name"),
            "url": trend_embed.get("url"),
            "category": trend_embed.get("category"),
        }

    run_status = run.get("status")
    is_running = run_status == "running"
    is_completed = run_status == "completed"

    now_iso = datetime.now(timezone.utc).isoformat()
    run_duration = _flow_duration_ms(
        run.get("started_at"),
        run.get("completed_at") if run.get("completed_at") else (
            now_iso if is_running else None
        ),
    )

    # ── Query 2: stages ──────────────────────────────────────────────
    stage_rows = (
        sb.table("hype_stages")
        .select(
            "agent_name, stage_order, status, output, tokens_used, "
            "model_used, error, completed_at, duration_ms"
        )
        .eq("run_id", run_id)
        .order("stage_order")
        .execute()
        .data
    ) or []
    stage_rows = [s for s in stage_rows if isinstance(s, dict)]

    # derived_duration_ms: stage[n].completed_at − previous stage's
    # completed_at (run.started_at for the first). The duration_ms column
    # is always NULL in hype_stages — never use it.
    prev_ts = _flow_parse_ts(run.get("started_at"))
    for s in stage_rows:
        cur_ts = _flow_parse_ts(s.get("completed_at"))
        if prev_ts is not None and cur_ts is not None:
            s["_derived_duration_ms"] = max(
                0, int((cur_ts - prev_ts).total_seconds() * 1000)
            )
        else:
            s["_derived_duration_ms"] = None
        if cur_ts is not None:
            prev_ts = cur_ts

    # Map stages → node keys (last stage wins per key, e.g. gate retries)
    stage_by_key: dict = {}
    for s in stage_rows:
        key = _flow_node_key_for_agent(s.get("agent_name"))
        if key:
            stage_by_key[key] = s

    # ── Query 3: drafts ──────────────────────────────────────────────
    draft_rows = (
        sb.table("daily_drafts")
        .select(
            "id, platform, content, status, postiz_state, postiz_post_id, "
            "release_url, image_url, video_url, scheduled_at"
        )
        .eq("hype_run_id", run_id)
        .is_("deleted_at", "null")
        .execute()
        .data
    ) or []
    draft_rows = [d for d in draft_rows if isinstance(d, dict)]
    draft_rows.sort(
        key=lambda d: (
            _FLOW_PLATFORM_ORDER.get(d.get("platform") or "", 99),
            d.get("platform") or "",
        )
    )

    # ── Kart run'ı? → ayrı kart node-seti (haber 7-node yoluna girmeden) ──
    _fs = run.get("flow_state") if isinstance(run.get("flow_state"), dict) else {}
    if _fs.get("run_kind") == "cards":
        return _build_card_flow(run, trend, stage_rows, draft_rows, run_duration, _fs)

    # ── Build the 7 nodes ────────────────────────────────────────────
    real_keys = [k for k, _ in _FLOW_NODE_DEFS if k != "publish"]
    last_present_idx = -1
    for i, k in enumerate(real_keys):
        if k in stage_by_key:
            last_present_idx = i

    # video skip reason from Trend Scout output (video_worthy flag)
    video_skip_reason = None
    try:
        scout_out = (stage_by_key.get("trend_scout") or {}).get("output")
        if isinstance(scout_out, dict) and scout_out.get("video_worthy") is False:
            video_skip_reason = "video_worthy=false"
            reason = scout_out.get("video_reason")
            if isinstance(reason, str) and reason.strip():
                video_skip_reason = f"video_worthy=false: {reason.strip()}"
    except Exception:
        video_skip_reason = None

    nodes = []
    failed_assigned = False  # only the FIRST missing node after the last
    running_assigned = False  # stage gets failed/running
    for key, label in _FLOW_NODE_DEFS:
        node = {
            "key": key,
            "label": label,
            "state": "skipped",
            "skip_reason": None,
            "derived_duration_ms": None,
            "tokens_used": 0,
            "tokens_estimated": key in ("trend_scout", "strategist"),
            "model_used": None,
            "stage_order": None,
            "output": {},
            "output_truncated": False,
            "error": None,
            "publish": None,
        }
        if key == "publish":
            try:
                pub = _flow_publish_node(draft_rows, bool(run.get("dry_run")))
                node["state"] = pub["state"]
                node["publish"] = pub["publish"]
            except Exception:
                logger.warning("[flow] publish node derivation failed", exc_info=True)
            nodes.append(node)
            continue

        stage = stage_by_key.get(key)
        if stage is not None:
            node["state"] = "success" if stage.get("status") == "success" else "failed"
            node["derived_duration_ms"] = stage.get("_derived_duration_ms")
            node["tokens_used"] = stage.get("tokens_used") or 0
            node["model_used"] = stage.get("model_used") or None
            node["stage_order"] = stage.get("stage_order")
            out = stage.get("output")
            if isinstance(out, str):
                node["output"] = out
                node["output_truncated"] = True
            elif out is not None:
                node["output"] = out
            node["error"] = stage.get("error")
        else:
            idx = real_keys.index(key)
            if idx > last_present_idx:
                # Missing nodes AFTER the last executed stage: their state
                # depends on the run outcome.
                if is_running:
                    if not running_assigned:
                        node["state"] = "running"
                        running_assigned = True
                    else:
                        node["state"] = "pending"
                elif not is_completed:
                    # failed / blocked_by_gate / rejected_by_compliance …
                    if not failed_assigned:
                        node["state"] = "failed"
                        node["error"] = run.get("error")
                        failed_assigned = True
                    # subsequent missing nodes stay "skipped"
            # Missing nodes BEFORE later existing stages stay "skipped".
            if key == "video" and node["state"] == "skipped":
                node["skip_reason"] = video_skip_reason
        nodes.append(node)

    # ── Drafts payload ───────────────────────────────────────────────
    drafts_out = [
        {
            "id": d.get("id"),
            "platform": d.get("platform"),
            "content": d.get("content"),
            "status": d.get("status"),
            "postiz_state": d.get("postiz_state"),
            "release_url": d.get("release_url"),
            "image_url": d.get("image_url"),
            "video_url": d.get("video_url"),
            "scheduled_at": d.get("scheduled_at"),
            "char_count": len(d.get("content") or ""),
        }
        for d in draft_rows
    ]

    # ── Trust signals (each best-effort; failure → null) ─────────────
    opening_similarity = None
    try:
        opening_similarity = _flow_opening_similarity(draft_rows)
    except Exception:
        logger.warning("[flow] opening_similarity failed", exc_info=True)

    gate_repairs = None
    try:
        # Query 4: faithfulness_verdicts window
        gate_repairs = _flow_gate_repairs(sb, run)
    except Exception:
        logger.warning("[flow] gate_repairs failed", exc_info=True)

    video_topic_match = "pass_implicit" if "video" in stage_by_key else "n/a"

    cost_anomaly = None
    try:
        # Query 5: last 20 completed runs of this account
        cost_anomaly = _flow_cost_anomaly(sb, run)
    except Exception:
        logger.warning("[flow] cost_anomaly failed", exc_info=True)

    # ── Default selected node ────────────────────────────────────────
    default_selected = "publish"
    try:
        failed_node = next(
            (n["key"] for n in nodes if n["state"] == "failed"), None
        )
        if failed_node:
            default_selected = failed_node
        elif opening_similarity:
            default_selected = "writer"
        elif gate_repairs and (gate_repairs.get("attempted") or 0) > 0:
            default_selected = "gate"
    except Exception:
        default_selected = "publish"

    return {
        "run": {
            "id": run.get("id"),
            "account_id": run.get("account_id"),
            "status": run_status,
            "dry_run": run.get("dry_run"),
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "duration_ms": run_duration,
            "total_tokens": run.get("total_tokens"),
            "total_cost_usd": run.get("total_cost_usd"),
            "error": run.get("error"),
            "trend": trend,
            "run_kind": "news",
            # Şeffaflık: boş/skip run'da neden + aday-eleme dökümü (graph "Aday Yok" node'u)
            "reason": _fs.get("reason"),
            "gate_breakdown": _fs.get("gate_breakdown"),
        },
        "nodes": nodes,
        "drafts": drafts_out,
        "trust_signals": {
            "opening_similarity": opening_similarity,
            "gate_repairs": gate_repairs,
            "video_topic_match": video_topic_match,
            "cost_anomaly": cost_anomaly,
        },
        "default_selected_node": default_selected,
    }


# ═════════════════════════════════════════════════════════════════════
# Phase 43.D — autonomy gates + monthly quality audit endpoints
# ═════════════════════════════════════════════════════════════════════
#   GET  /personas/{id}/autonomy-score   — UI gauge of per-bucket gate
#   GET  /audits/{id}/pass               — Slack-link Pass click
#   GET  /audits/{id}/fail               — Slack-link Fail click +
#                                          auto-freeze on ≥3 fail/cycle

from fastapi.responses import HTMLResponse  # noqa: E402

PHASE_43D_AUDIT_FAIL_THRESHOLD = 3
PHASE_43D_AUDIT_BATCH_SIZE = 10


@router.get("/personas")
async def list_personas(user=Depends(require_auth)):
    """Phase 43.D / Tier 2 — workspace-scoped persona list.

    Surfaces the small per-persona metadata the dashboard needs to
    decide which UI states to render (autonomy unlock flags, video
    pipeline status, owner). Used by AutonomyScorePage, EditElevation
    page, and any future per-persona dashboard.
    """
    sb = get_supabase()
    from services.access_control import accessible_owner_ids
    rows = (
        sb.table("personas")
        .select(
            "id, slug, display_name, is_active, "
            "primary_account_id, owner_user_id, "
            "text_autonomy_unlocked, image_autonomy_unlocked, "
            "video_autonomy_unlocked, last_autonomy_check_at, "
            "last_consecutive_reject_at, video_enabled, "
            "video_pipeline_default"
        )
        .in_("owner_user_id", accessible_owner_ids(user.id))
        .order("is_active", desc=True)
        .order("created_at", desc=False)
        .execute()
    )
    return {"items": rows.data or [], "count": len(rows.data or [])}


@router.get("/personas/{persona_id}/autonomy-score")
async def get_persona_autonomy_score(
    persona_id: str,
    user=Depends(require_auth),
):
    """Per-bucket autonomy gate state (live recompute, no DB write).

    Mirrors the bucket logic in scripts/check_autonomy_gates.py so the
    UI always shows the same numbers the cron sees — minus the unlock
    UPDATE, which only the cron writes.
    """
    sb = get_supabase()
    from services.access_control import accessible_owner_ids

    p_row = (
        sb.table("personas")
        .select(
            "id, slug, owner_user_id, is_active, "
            "text_autonomy_unlocked, image_autonomy_unlocked, "
            "video_autonomy_unlocked, last_autonomy_check_at, "
            "last_consecutive_reject_at"
        )
        .eq("id", persona_id)
        .in_("owner_user_id", accessible_owner_ids(user.id))
        .limit(1)
        .execute()
    )
    if not p_row.data:
        raise HTTPException(404, "persona not found or access denied")
    persona = p_row.data[0]

    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(days=30)
    ).isoformat()

    drafts_q = (
        sb.table("daily_drafts")
        .select("id, content_type, video_url, status, created_at")
        .eq("persona_id", persona_id)
        .eq("source", "hype_auto")
        .gte("created_at", cutoff_iso)
        .execute()
    )
    drafts = drafts_q.data or []
    draft_ids = [d["id"] for d in drafts]

    actions_by_draft: dict[str, list[str]] = {}
    if draft_ids:
        for i in range(0, len(draft_ids), 200):
            chunk = draft_ids[i:i + 200]
            try:
                a_rows = (
                    sb.table("hype_feedback")
                    .select("draft_id, action")
                    .in_("draft_id", chunk)
                    .gte("created_at", cutoff_iso)
                    .execute()
                )
                for a in (a_rows.data or []):
                    did = a.get("draft_id")
                    act = (a.get("action") or "").lower()
                    if did and act:
                        actions_by_draft.setdefault(did, []).append(act)
            except Exception:
                pass

    TEXT_CT = {
        "first_person_witty", "blog_post", "access_expansion", "other",
        "research_summary", "opinion_piece",
    }
    IMAGE_CT = {
        "model_launch", "feature_major", "feature_minor", "api_update",
        "pricing", "research", "security", "partnership", "product_launch",
    }
    SAMPLE_MIN = {"text": 30, "image": 20, "video": 10}

    def _bucket(d: dict) -> Optional[str]:
        if d.get("video_url"):
            return "video"
        ct = (d.get("content_type") or "").lower()
        if ct in TEXT_CT: return "text"
        if ct in IMAGE_CT: return "image"
        return None

    counts: dict[str, dict] = {
        b: {"n": 0, "reject": 0, "edit": 0} for b in ("text","image","video")
    }
    for d in drafts:
        b = _bucket(d)
        if not b:
            continue
        c = counts[b]
        c["n"] += 1
        acts = actions_by_draft.get(d["id"], [])
        if "rejected" in acts: c["reject"] += 1
        if "edited" in acts:   c["edit"] += 1

    buckets_out: dict[str, dict] = {}
    for b, c in counts.items():
        n = c["n"]
        reject_rate = (c["reject"] / n) if n else 0.0
        edit_rate = (c["edit"] / n) if n else 0.0
        passes_sample = n >= SAMPLE_MIN[b]
        passes_reject = reject_rate < 0.05
        passes_edit = edit_rate < 0.10
        will_unlock = passes_sample and passes_reject and passes_edit
        buckets_out[b] = {
            "sample_count": n,
            "sample_min": SAMPLE_MIN[b],
            "reject_count": c["reject"],
            "edit_count": c["edit"],
            "reject_rate": round(reject_rate, 4),
            "edit_rate": round(edit_rate, 4),
            "passes_sample": passes_sample,
            "passes_reject": passes_reject,
            "passes_edit": passes_edit,
            "currently_unlocked": bool(persona.get(f"{b}_autonomy_unlocked")),
            "qualifies_for_unlock": will_unlock,
        }

    return {
        "persona_id": persona_id,
        "slug": persona.get("slug"),
        "buckets": buckets_out,
        "last_autonomy_check_at": persona.get("last_autonomy_check_at"),
        "last_consecutive_reject_at": persona.get("last_consecutive_reject_at"),
        "lookback_days": 30,
    }


async def _record_audit_rating(
    audit_id: str,
    rating: Literal["pass", "fail"],
    user_id: Optional[str],
    notes: Optional[str] = None,
) -> dict:
    """Shared body for /audits/{id}/{pass,fail} (Slack) and /audits/{id}/rate
    (Phase 43.E UI dashboard).

    Records the rating and — if this rating causes the persona's
    current-month batch to cross the freeze threshold — flips
    auto_publish_enabled to false on every account belonging to that
    persona's owner. Idempotent: re-clicks just update rated_at without
    re-triggering the freeze.

    Phase 43.E — `notes` (FailDialog textarea) is stored on
    `pending_audits.notes`. If the column isn't there yet (legacy
    deploys) we retry the update without it — the rating still lands.
    """
    sb = get_supabase()
    row = (
        sb.table("pending_audits")
        .select("id, persona_id, draft_id, audit_month, rating")
        .eq("id", audit_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "audit not found")
    audit = row.data[0]
    persona_id = audit["persona_id"]
    audit_month = audit["audit_month"]

    update_payload: dict = {
        "rating": rating,
        "rater_user_id": user_id,
        "rated_at": datetime.now(timezone.utc).isoformat(),
    }
    if notes is not None:
        update_payload["notes"] = notes[:2000]

    try:
        sb.table("pending_audits").update(update_payload).eq("id", audit_id).execute()
    except Exception as e:
        msg = str(e)[:300]
        if "notes" in msg and ("column" in msg.lower() or "PGRST204" in msg):
            logger.warning(
                "[audit-rate] pending_audits.notes column missing; "
                "retrying without notes (migration pending)."
            )
            update_payload.pop("notes", None)
            sb.table("pending_audits").update(update_payload).eq("id", audit_id).execute()
        else:
            raise

    try:
        sb.table("daily_drafts").update({
            "quality_audit_pending": False,
        }).eq("id", audit["draft_id"]).execute()
    except Exception as e:
        logger.warning(f"audit rate: draft clear failed: {e}")

    fail_count = 0
    total_rated = 0
    try:
        siblings = (
            sb.table("pending_audits")
            .select("rating")
            .eq("persona_id", persona_id)
            .eq("audit_month", audit_month)
            .execute()
        )
        for r in (siblings.data or []):
            rt = (r.get("rating") or "").lower()
            if rt in ("pass", "fail"):
                total_rated += 1
            if rt == "fail":
                fail_count += 1
    except Exception as e:
        logger.warning(f"audit rate: sibling count failed: {e}")

    froze_accounts: list[str] = []
    if fail_count >= PHASE_43D_AUDIT_FAIL_THRESHOLD:
        try:
            p = (
                sb.table("personas")
                .select("owner_user_id, slug")
                .eq("id", persona_id)
                .limit(1)
                .execute()
            )
            owner_uid = (p.data or [{}])[0].get("owner_user_id")
            if owner_uid:
                accs = (
                    sb.table("connected_accounts")
                    .select("id")
                    .eq("user_id", owner_uid)
                    .execute()
                )
                acc_ids = [a["id"] for a in (accs.data or []) if a.get("id")]
                if acc_ids:
                    sb.table("hype_account_config").update({
                        "auto_publish_enabled": False,
                    }).in_("account_id", acc_ids).execute()
                    froze_accounts = acc_ids
                    logger.warning(
                        f"[quality-audit] FREEZE persona={persona_id} "
                        f"fails={fail_count}/{total_rated} → "
                        f"auto_publish_enabled=false on {len(acc_ids)} accounts"
                    )
        except Exception as e:
            logger.exception(f"audit rate: freeze cascade failed: {e}")

    return {
        "audit_id": audit_id,
        "rating": rating,
        "fail_count_this_month": fail_count,
        "rated_count_this_month": total_rated,
        "freeze_threshold": PHASE_43D_AUDIT_FAIL_THRESHOLD,
        "froze_accounts": froze_accounts,
    }


def _audit_ack_html(result: dict, rating: str) -> str:
    """Friendly confirmation page so the Slack click lands somewhere
    nicer than raw JSON."""
    color = "#16a34a" if rating == "pass" else "#dc2626"
    label = "✅ Pass" if rating == "pass" else "❌ Fail"
    extra = ""
    if result.get("froze_accounts"):
        extra = (
            "<p style='color:#dc2626'><strong>auto_publish_enabled "
            "kapatıldı</strong> — bu cycle 3+ fail ile sonuçlandı.</p>"
        )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Audit recorded</title></head>
<body style="font-family:system-ui;max-width:480px;margin:60px auto;padding:24px">
  <h1 style="color:{color}">{label}</h1>
  <p>Rating saved for audit <code>{result['audit_id'][:8]}…</code></p>
  <p>Bu cycle: <strong>{result['fail_count_this_month']} fail</strong>
     / {result['rated_count_this_month']} rated /
     freeze threshold {result['freeze_threshold']}</p>
  {extra}
  <p style="color:#9ca3af;font-size:12px">Bu sayfayı kapatabilirsin.</p>
</body></html>"""


@router.get("/audits/{audit_id}/pass", response_class=HTMLResponse)
async def audit_pass(audit_id: str):
    """Slack 'Pass' link target. Auth-less by design (UUID = capability)."""
    result = await _record_audit_rating(audit_id, "pass", user_id=None)
    return _audit_ack_html(result, "pass")


@router.get("/audits/{audit_id}/fail", response_class=HTMLResponse)
async def audit_fail(audit_id: str):
    """Slack 'Fail' link target — may trigger auto-freeze."""
    result = await _record_audit_rating(audit_id, "fail", user_id=None)
    return _audit_ack_html(result, "fail")


# ═════════════════════════════════════════════════════════════════════
# Phase 43.E — Quality Audit dashboard endpoints
# ═════════════════════════════════════════════════════════════════════
# Slack is no longer the only delivery channel. The typehype.io dashboard
# now hosts a /dashboard/quality-audit page that lists pending audits,
# accepts Pass/Fail with an optional notes textarea on Fail, and shows the
# freeze banner when the cycle crosses ≥3 fails.
#
#   POST /api/hype/audits/{id}/rate                — auth'd JSON rate
#   GET  /api/hype/quality-audits?status=...       — workspace list
#   GET  /api/hype/quality-audits/summary          — sidebar badge feed
#   POST /api/hype/quality-audits/trigger          — manual audit kick
#
# The legacy /audits/{id}/{pass,fail} HTMLResponse endpoints stay
# untouched for back-compat with any Slack webhooks that get re-enabled.

# Phase 43.E — freeze cascade fresh-look window. Re-reading
# auto_publish_enabled per request keeps the FrozenBanner truthful even
# when Berkay flips it back on from Settings.


class AuditRateBody(BaseModel):
    rating: Literal["pass", "fail"]
    notes: Optional[str] = Field(None, max_length=2000)


@router.post("/audits/{audit_id}/rate")
async def rate_audit(
    audit_id: str,
    body: AuditRateBody,
    user=Depends(require_auth),
):
    """Phase 43.E.1 — dashboard rate endpoint. Auth'd, JSON response,
    notes captured. Mirrors the freeze cascade semantics of the Slack
    HTML route but returns structured data the UI can render."""
    result = await _record_audit_rating(
        audit_id,
        body.rating,
        user_id=user.id,
        notes=body.notes,
    )
    return result


def _audit_workspace_filter(sb, user_id: str) -> list[str]:
    """Resolve persona_ids accessible to this user (owned or
    accepted-collaborator)."""
    from services.access_control import accessible_owner_ids
    owner_ids = accessible_owner_ids(user_id)
    if not owner_ids:
        return []
    rows = (
        sb.table("personas")
        .select("id")
        .in_("owner_user_id", owner_ids)
        .execute()
    )
    return [r["id"] for r in (rows.data or []) if isinstance(r, dict) and r.get("id")]


@router.get("/quality-audits")
async def list_quality_audits(
    status: Literal["pending", "history", "all"] = "pending",
    limit: int = 60,
    user=Depends(require_auth),
):
    """Phase 43.E.1 — workspace-scoped audit list with JOIN'd draft snapshot.

    `status=pending` returns only `rating='pending'` rows for the active
    audit_month (current calendar month). `history` returns rated rows
    grouped by audit_month, newest first. `all` returns the union without
    grouping (used by the AuditHistoryRow expander).
    """
    sb = get_supabase()
    persona_ids = _audit_workspace_filter(sb, user.id)
    if not persona_ids:
        return {"items": [], "count": 0, "freeze_meta": {}}

    q = (
        sb.table("pending_audits")
        .select(
            "id, persona_id, draft_id, audit_month, rating, "
            "rater_user_id, rated_at, notes, slack_message_ts, created_at"
        )
        .in_("persona_id", persona_ids)
    )
    if status == "pending":
        q = q.eq("rating", "pending")
    elif status == "history":
        q = q.in_("rating", ["pass", "fail"])
    audits = (
        q.order("audit_month", desc=True)
         .order("created_at", desc=True)
         .limit(max(1, min(200, limit)))
         .execute()
    ).data or []

    if not audits:
        return {"items": [], "count": 0, "freeze_meta": {}}

    # JOIN'd draft snapshot. Single batched fetch.
    draft_ids = list({a["draft_id"] for a in audits if a.get("draft_id")})
    draft_map: dict[str, dict] = {}
    if draft_ids:
        d_rows = (
            sb.table("daily_drafts")
            .select(
                "id, content, image_url, video_url, video_thumbnail_url, "
                "video_duration_sec, platform, trend_topic, scheduled_at, "
                "postiz_post_id, auto_published, content_type, voice_mode"
            )
            .in_("id", draft_ids)
            .execute()
        )
        for d in (d_rows.data or []):
            if isinstance(d, dict) and d.get("id"):
                draft_map[d["id"]] = d

    # persona slug embed for UI label/badge
    persona_slug_map: dict[str, str] = {}
    try:
        ps = (
            sb.table("personas")
            .select("id, slug, owner_user_id")
            .in_("id", list({a["persona_id"] for a in audits if a.get("persona_id")}))
            .execute()
        )
        for p in (ps.data or []):
            persona_slug_map[p["id"]] = p.get("slug")
    except Exception:
        pass

    # Per-month aggregate (so the UI can render the progress bar without
    # a second roundtrip). Computed off the pulled set when possible;
    # the pending-only call falls back to a small ad-hoc count.
    freeze_meta: dict[str, dict] = {}
    current_month = datetime.now(timezone.utc).date().replace(day=1).isoformat()
    try:
        all_this_month = (
            sb.table("pending_audits")
            .select("persona_id, rating")
            .in_("persona_id", persona_ids)
            .eq("audit_month", current_month)
            .execute()
        ).data or []
        for row in all_this_month:
            pid = row.get("persona_id")
            if not pid:
                continue
            meta = freeze_meta.setdefault(pid, {
                "total": 0, "rated": 0, "fail": 0, "pass": 0, "pending": 0,
            })
            meta["total"] += 1
            rt = (row.get("rating") or "").lower()
            if rt == "pass":
                meta["pass"] += 1; meta["rated"] += 1
            elif rt == "fail":
                meta["fail"] += 1; meta["rated"] += 1
            elif rt == "pending":
                meta["pending"] += 1
    except Exception as e:
        logger.warning(f"audit list: freeze_meta compute failed: {e}")

    items: list[dict] = []
    for a in audits:
        d = draft_map.get(a.get("draft_id")) or None
        items.append({
            "id": a["id"],
            "persona_id": a.get("persona_id"),
            "persona_slug": persona_slug_map.get(a.get("persona_id")),
            "draft_id": a.get("draft_id"),
            "audit_month": a.get("audit_month"),
            "rating": a.get("rating"),
            "rater_user_id": a.get("rater_user_id"),
            "rated_at": a.get("rated_at"),
            "notes": a.get("notes"),
            "created_at": a.get("created_at"),
            "draft_snapshot": d,  # NULL-safe: UI handles missing
        })

    return {
        "items": items,
        "count": len(items),
        "freeze_meta": freeze_meta,
        "freeze_threshold": PHASE_43D_AUDIT_FAIL_THRESHOLD,
        "current_audit_month": current_month,
    }


@router.get("/quality-audits/summary")
async def quality_audit_summary(user=Depends(require_auth)):
    """Phase 43.E.1 — small payload for sidebar badge + frozen banner.

    Returns per-persona pending count, this-month fail count, and whether
    the persona's owner has any `auto_publish_enabled=true` accounts left
    (so we can tell "frozen by this audit" from "auto-publish was off
    from the start")."""
    sb = get_supabase()
    persona_ids = _audit_workspace_filter(sb, user.id)
    if not persona_ids:
        return {
            "personas": [],
            "pending_total": 0,
            "auto_publish_enabled_anywhere": False,
        }

    current_month = datetime.now(timezone.utc).date().replace(day=1).isoformat()

    # Per-persona pending + this-month rated breakdown
    rows = (
        sb.table("pending_audits")
        .select("persona_id, rating, audit_month")
        .in_("persona_id", persona_ids)
        .gte("audit_month", current_month)
        .execute()
    ).data or []

    per_persona: dict[str, dict] = {pid: {
        "pending": 0, "pass": 0, "fail": 0, "rated": 0, "total": 0,
    } for pid in persona_ids}
    for r in rows:
        pid = r.get("persona_id")
        if pid not in per_persona:
            continue
        rt = (r.get("rating") or "").lower()
        per_persona[pid]["total"] += 1
        if rt == "pass":
            per_persona[pid]["pass"] += 1; per_persona[pid]["rated"] += 1
        elif rt == "fail":
            per_persona[pid]["fail"] += 1; per_persona[pid]["rated"] += 1
        elif rt == "pending":
            per_persona[pid]["pending"] += 1

    # Persona meta (slug + owner) and active auto_publish flag check
    persona_meta: dict[str, dict] = {}
    try:
        pmeta = (
            sb.table("personas")
            .select("id, slug, owner_user_id")
            .in_("id", persona_ids)
            .execute()
        ).data or []
        for p in pmeta:
            persona_meta[p["id"]] = p
    except Exception:
        pass

    owner_ids = list({
        p.get("owner_user_id") for p in persona_meta.values() if p.get("owner_user_id")
    })
    auto_publish_anywhere = False
    if owner_ids:
        try:
            accs = (
                sb.table("connected_accounts")
                .select("id, user_id")
                .in_("user_id", owner_ids)
                .execute()
            ).data or []
            account_ids = [a["id"] for a in accs if a.get("id")]
            if account_ids:
                cfg = (
                    sb.table("hype_account_config")
                    .select("auto_publish_enabled")
                    .in_("account_id", account_ids)
                    .eq("auto_publish_enabled", True)
                    .limit(1)
                    .execute()
                ).data or []
                auto_publish_anywhere = len(cfg) > 0
        except Exception as e:
            logger.warning(f"audit summary: auto_publish probe failed: {e}")

    out_personas: list[dict] = []
    pending_total = 0
    for pid, agg in per_persona.items():
        pending_total += agg["pending"]
        out_personas.append({
            "persona_id": pid,
            "slug": (persona_meta.get(pid) or {}).get("slug"),
            **agg,
            "freeze_threshold": PHASE_43D_AUDIT_FAIL_THRESHOLD,
        })

    return {
        "personas": out_personas,
        "pending_total": pending_total,
        "auto_publish_enabled_anywhere": auto_publish_anywhere,
        "current_audit_month": current_month,
    }


class AuditTriggerBody(BaseModel):
    """Phase 43.E.2 — manuel "Yeni denetim başlat" body. persona_id boş
    bırakılırsa workspace'teki tüm aktif persona'lar denetlenir."""
    persona_id: Optional[str] = None
    sample_size: int = Field(10, ge=1, le=20)


# How many days back the manual trigger pulls auto_published candidates
# from. Mirrors scripts/quality_audit.py:LOOKBACK_DAYS so the cron + UI
# behave identically.
_QUALITY_AUDIT_LOOKBACK_DAYS = 30


def _trigger_audit_for_persona(
    sb,
    persona: dict,
    *,
    sample_size: int,
) -> dict:
    """Phase 43.E.2 — sample + insert pending_audits rows for a single
    persona. Mirrors the cron path in scripts/quality_audit.py but is
    inlined here so the backend doesn't pull from /opt/hype-crew (the
    two services run in separate venvs and import paths get awkward).

    Refuses (409) if there are pending rows for the current calendar
    month already — protects against double-trigger spam.
    """
    persona_id = persona["id"]
    slug = persona.get("slug") or persona_id
    current_month = datetime.now(timezone.utc).date().replace(day=1)

    # Already pending? Refuse — backend caller should surface this to UI
    # as the "denetim zaten aktif" toast.
    existing = (
        sb.table("pending_audits")
        .select("id", count="exact")
        .eq("persona_id", persona_id)
        .eq("audit_month", current_month.isoformat())
        .eq("rating", "pending")
        .limit(1)
        .execute()
    )
    existing_count = getattr(existing, "count", 0) or len(existing.data or [])
    if existing_count > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "audit_already_active_this_month",
                "persona_id": persona_id,
                "slug": slug,
                "existing_count": existing_count,
                "message": (
                    "Bu ay için zaten bekleyen bir denetim var. Önce mevcut "
                    "denetimi tamamla."
                ),
            },
        )

    # Pick `sample_size` random auto_published drafts from the last
    # LOOKBACK_DAYS that haven't been picked for this audit_month.
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=_QUALITY_AUDIT_LOOKBACK_DAYS)
    ).isoformat()
    candidates = (
        sb.table("daily_drafts")
        .select("id, audit_picked_for_month")
        .eq("persona_id", persona_id)
        .eq("auto_published", True)
        .gte("created_at", cutoff)
        .execute()
    ).data or []
    pool = [
        r for r in candidates
        if r.get("audit_picked_for_month") != current_month.isoformat()
    ]
    if not pool:
        return {
            "persona_id": persona_id,
            "slug": slug,
            "audit_month": current_month.isoformat(),
            "inserted": 0,
            "audit_ids": [],
            "skipped": "empty_pool",
        }

    import random as _rnd
    _rnd.shuffle(pool)
    picks = pool[:sample_size]

    audit_ids: list[str] = []
    for p in picks:
        row = {
            "persona_id": persona_id,
            "draft_id": p["id"],
            "audit_month": current_month.isoformat(),
            "rating": "pending",
        }
        try:
            ins = sb.table("pending_audits").insert(row).execute()
            if ins.data:
                audit_ids.append(ins.data[0]["id"])
        except Exception as e:
            logger.warning(
                f"[trigger-audit][{slug}] pending_audits insert failed "
                f"for {p['id']}: {e}"
            )
        try:
            sb.table("daily_drafts").update({
                "audit_picked_for_month": current_month.isoformat(),
                "quality_audit_pending": True,
            }).eq("id", p["id"]).execute()
        except Exception as e:
            logger.warning(
                f"[trigger-audit][{slug}] draft pick-mark failed for "
                f"{p['id']}: {e}"
            )

    # Bookmark on persona (cron dedupe alignment). Best-effort.
    try:
        sb.table("personas").update({
            "last_quality_audit_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", persona_id).execute()
    except Exception:
        pass

    return {
        "persona_id": persona_id,
        "slug": slug,
        "audit_month": current_month.isoformat(),
        "inserted": len(audit_ids),
        "audit_ids": audit_ids,
    }


@router.post("/quality-audits/trigger")
async def trigger_quality_audit(
    body: AuditTriggerBody | None = None,
    user=Depends(require_auth),
):
    """Phase 43.E.2 — manuel "Yeni denetim başlat" CTA. workspace-scoped.

    Backend filters target personas through accessible_owner_ids so
    collaborators can also kick audits but can't reach personas outside
    their workspace.
    """
    body = body or AuditTriggerBody()
    sb = get_supabase()
    persona_ids = _audit_workspace_filter(sb, user.id)
    if not persona_ids:
        raise HTTPException(404, "no accessible personas")

    target_ids: list[str] = []
    if body.persona_id:
        if body.persona_id not in persona_ids:
            raise HTTPException(403, "persona not in your workspace")
        target_ids = [body.persona_id]
    else:
        target_ids = persona_ids

    persona_rows = (
        sb.table("personas")
        .select("id, slug, primary_account_id, owner_user_id, is_active")
        .in_("id", target_ids)
        .eq("is_active", True)
        .execute()
    ).data or []

    results: list[dict] = []
    raised_conflict: Optional[HTTPException] = None
    for p in persona_rows:
        try:
            r = _trigger_audit_for_persona(sb, p, sample_size=body.sample_size)
            results.append(r)
        except HTTPException as e:
            # Capture the 409 to surface but keep iterating other personas
            results.append({
                "persona_id": p["id"],
                "slug": p.get("slug"),
                "skipped": "audit_already_active_this_month",
                "detail": e.detail,
            })
            raised_conflict = e

    # If we asked for a single persona and got a 409, surface that as
    # the response status. Workspace-wide triggers stay 200 with the
    # mixed report so the UI can render per-persona feedback.
    if body.persona_id and raised_conflict is not None:
        raise raised_conflict

    current_month = datetime.now(timezone.utc).date().replace(day=1).isoformat()
    inserted_total = sum(r.get("inserted") or 0 for r in results)
    return {
        "audit_month": current_month,
        "personas": results,
        "inserted_total": inserted_total,
    }


# ═════════════════════════════════════════════════════════════════════
# Phase 43.D — Edit Elevation endpoints
# ═════════════════════════════════════════════════════════════════════
# scripts/scan_edit_elevations.py discovers patterns where the user has
# applied the same edit_fields shape 3+ times on the same content_type
# cluster. The UI lists them via GET /personas/{id}/edit-elevations and
# Berkay accepts / rejects each one. Accept = promote the underlying
# editor_diffs rows' scope_tag from 'draft_only' → the chosen scope
# ('trend_type' by default, 'global' opt-in). Reject = mark and never
# resurface (until the script generates a fundamentally different
# signature).


@router.get("/personas/{persona_id}/edit-elevations")
async def list_edit_elevations(
    persona_id: str,
    status: Literal["pending", "accepted", "rejected", "expired", "all"] = "pending",
    limit: int = 50,
    user=Depends(require_auth),
):
    """List edit-elevation candidates for a persona."""
    sb = get_supabase()
    from services.access_control import accessible_owner_ids

    # Verify persona access via workspace
    p_row = (
        sb.table("personas")
        .select("id, slug, owner_user_id")
        .eq("id", persona_id)
        .in_("owner_user_id", accessible_owner_ids(user.id))
        .limit(1)
        .execute()
    )
    if not p_row.data:
        raise HTTPException(404, "persona not found or access denied")

    q = (
        sb.table("edit_elevation_candidates")
        .select(
            "id, content_type, edit_signature, edit_pattern, sample_count, "
            "example_draft_ids, first_seen, last_seen, status, decided_at, "
            "promoted_scope, notes"
        )
        .eq("persona_id", persona_id)
        .order("last_seen", desc=True)
        .limit(max(1, min(200, limit)))
    )
    if status != "all":
        q = q.eq("status", status)
    rows = q.execute().data or []
    return {"persona_id": persona_id, "items": rows, "count": len(rows)}


class ElevationDecisionBody(BaseModel):
    """Phase 43.D — accept payload allows scope override; default is
    'trend_type' (Critic-mandated narrower-than-global default)."""
    scope: Literal["trend_type", "global"] = "trend_type"
    notes: Optional[str] = Field(None, max_length=500)


def _verify_elevation_access(elevation_id: str, user_id: str) -> dict:
    sb = get_supabase()
    from services.access_control import accessible_owner_ids

    row = (
        sb.table("edit_elevation_candidates")
        .select(
            "id, persona_id, account_id, content_type, edit_signature, "
            "edit_pattern, sample_count, status, example_draft_ids"
        )
        .eq("id", elevation_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "elevation candidate not found")
    cand = row.data[0]
    # Re-check via owner_user_id on the underlying persona
    p = (
        sb.table("personas")
        .select("owner_user_id")
        .eq("id", cand["persona_id"])
        .in_("owner_user_id", accessible_owner_ids(user_id))
        .limit(1)
        .execute()
    )
    if not p.data:
        raise HTTPException(403, "elevation candidate not in your workspace")
    return cand


@router.post("/elevations/{elevation_id}/accept")
async def accept_elevation(
    elevation_id: str,
    body: ElevationDecisionBody | None = None,
    user=Depends(require_auth),
):
    """Promote the editor_diffs underlying this candidate. The matching
    hype_memory rows have their `metadata.scope_tag` bumped from
    'draft_only' → the chosen scope so Strategist / Writer / Visual
    Director start consuming them. Auto-promotion to 'global' requires
    explicit body={"scope":"global"}.
    """
    sb = get_supabase()
    cand = _verify_elevation_access(elevation_id, user.id)
    if cand["status"] not in ("pending", "expired"):
        raise HTTPException(
            409,
            f"elevation already {cand['status']}; only pending candidates "
            "can be accepted",
        )

    decision = body or ElevationDecisionBody()
    new_scope = decision.scope

    # Promote matching editor_diffs. We find them by content_type +
    # signature regenerated from each memory row's edit_fields. The
    # script already knows which drafts contributed, so we promote by
    # draft_id when possible (precise) and fall back to scanning the
    # account's editor_diffs (broad but bounded).
    sample_drafts: list[str] = cand.get("example_draft_ids") or []
    promoted = 0
    try:
        if sample_drafts:
            # Promote editor_diffs whose metadata.draft_id is in the
            # candidate's example set. The metadata key is JSONB so we
            # use postgrest's overlap-by-equality.
            for did in sample_drafts:
                rows = (
                    sb.table("hype_memory")
                    .select("id, metadata")
                    .eq("account_id", cand["account_id"])
                    .eq("memory_type", "editor_diffs")
                    .filter("metadata->>draft_id", "eq", did)
                    .execute()
                )
                for r in (rows.data or []):
                    md = r.get("metadata") or {}
                    if not isinstance(md, dict):
                        continue
                    md["scope_tag"] = new_scope
                    md["elevated_by"] = user.id
                    md["elevated_at"] = datetime.now(timezone.utc).isoformat()
                    md["elevation_candidate_id"] = elevation_id
                    sb.table("hype_memory").update({
                        "metadata": md,
                    }).eq("id", r["id"]).execute()
                    promoted += 1
    except Exception as e:
        logger.exception(f"accept_elevation: editor_diffs promote failed: {e}")
        raise HTTPException(500, f"promotion failed: {type(e).__name__}")

    sb.table("edit_elevation_candidates").update({
        "status": "accepted",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "decided_by": user.id,
        "promoted_scope": new_scope,
        "notes": decision.notes,
    }).eq("id", elevation_id).execute()

    return {
        "status": "accepted",
        "elevation_id": elevation_id,
        "promoted_scope": new_scope,
        "editor_diffs_promoted": promoted,
    }


@router.post("/elevations/{elevation_id}/reject")
async def reject_elevation(
    elevation_id: str,
    body: ElevationDecisionBody | None = None,
    user=Depends(require_auth),
):
    """Reject the candidate so it doesn't resurface. Underlying editor_diffs
    stay 'draft_only' — they keep helping their own draft refinement loops
    but never bleed into Strategist context."""
    sb = get_supabase()
    cand = _verify_elevation_access(elevation_id, user.id)
    if cand["status"] not in ("pending", "expired"):
        raise HTTPException(
            409,
            f"elevation already {cand['status']}; only pending candidates "
            "can be rejected",
        )
    sb.table("edit_elevation_candidates").update({
        "status": "rejected",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "decided_by": user.id,
        "notes": (body.notes if body else None),
    }).eq("id", elevation_id).execute()

    return {
        "status": "rejected",
        "elevation_id": elevation_id,
    }


# ═════════════════════════════════════════════════════════════════════
# Tier 3 — System Health (cost cap + failure rate + Postiz health)
# ═════════════════════════════════════════════════════════════════════
# GET  /api/hype/system-health           — dashboard payload
# PATCH /api/hype/personas/{id}/budget   — update daily_video_budget_usd
#
# /system-health surfaces three sections so /dashboard/system-health
# can render the cost gauge, the reliability panel, and the Postiz
# health check in a single page without juggling multiple endpoints.

PHASE_TIER3_FAIL_RATE_WARN = 0.05      # warn at ≥5% hourly fail rate
PHASE_TIER3_FAIL_RATE_DANGER = 0.10    # danger at ≥10%
PHASE_TIER3_RECENT_FAIL_LIMIT = 5      # surface the last N failures


def _today_start_iso() -> str:
    return datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()


def _week_ago_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()


def _check_postiz_health() -> dict:
    """Cheap Postiz check: instantiate the client and call list_posts on
    a 1-hour window. We only want to confirm the credential isn't 401."""
    try:
        import sys
        for hype_path in ("/opt/hype-crew", "../hype_crew", "../../hype_crew"):
            if hype_path not in sys.path:
                sys.path.insert(0, hype_path)
        # Use the guarded subclass — inherits list_posts unchanged.
        # This is a READ-only probe (no publish) but funneling everything
        # through GuardedPostizClient lets the CI test ban any direct
        # PostizClient() construction outside the wrapper module.
        from tools.guarded_postiz import GuardedPostizClient as PostizClient  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"import_failed: {type(e).__name__}", "stage": "import"}

    try:
        pc = PostizClient()
        # Cheap probe — most Postiz instances respond to list_posts with
        # an empty array; if the key is bad we get 401/403.
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        start = (_dt.now(_tz.utc) - _td(hours=1)).isoformat()
        end = _dt.now(_tz.utc).isoformat()
        try:
            posts = pc.list_posts(start=start, end=end)  # type: ignore[attr-defined]
            return {
                "ok": True,
                "stage": "list_posts",
                "recent_count": len(posts or []) if isinstance(posts, list) else 0,
            }
        except AttributeError:
            # Older PostizClient without list_posts — just confirm constructor worked.
            return {"ok": True, "stage": "client_init", "recent_count": None}
    except Exception as e:
        msg = str(e)[:200]
        status = None
        if "401" in msg:
            status = 401
        elif "403" in msg:
            status = 403
        return {
            "ok": False,
            "error": msg,
            "stage": "list_posts",
            "http_status": status,
        }


@router.get("/system-health")
async def system_health(user=Depends(require_auth)):
    """Tier 3 — workspace-wide health snapshot for /dashboard/system-health.

    Returns three sections:
      cost       — today vs cap, week trend, regen spend
      reliability — last 24h success/fail mix, recent failure samples
      postiz     — credential probe
    """
    sb = get_supabase()
    from services.access_control import accessible_owner_ids

    owner_ids = accessible_owner_ids(user.id)
    if not owner_ids:
        return {
            "cost": {}, "reliability": {}, "postiz": {"ok": False, "error": "no_workspace"},
        }

    # All connected_accounts owned/accessible
    accs = (
        sb.table("connected_accounts")
        .select("id, user_id, platform")
        .in_("user_id", owner_ids)
        .execute()
    ).data or []
    account_ids = [a["id"] for a in accs if a.get("id")]

    # Cost caps
    cap_run = 1.00
    cap_video = 5.00
    try:
        if account_ids:
            cfgs = (
                sb.table("hype_account_config")
                .select("account_id, daily_cost_cap_usd, dry_run_mode, auto_publish_enabled")
                .in_("account_id", account_ids)
                .execute()
            ).data or []
            # Use the max cap among the workspace's accounts (they're typically all the same)
            caps = [float(c.get("daily_cost_cap_usd") or 0) for c in cfgs if c.get("daily_cost_cap_usd") is not None]
            if caps:
                cap_run = max(caps)
            dry_run_active = any(bool(c.get("dry_run_mode")) for c in cfgs)
            auto_publish_active = any(bool(c.get("auto_publish_enabled")) for c in cfgs)
        else:
            dry_run_active = True
            auto_publish_active = False
    except Exception as e:
        logger.warning(f"system-health: config read failed: {e}")
        dry_run_active = True
        auto_publish_active = False

    # Persona video caps (workspace-wide max)
    try:
        ps = (
            sb.table("personas")
            .select("id, slug, daily_video_budget_usd, video_enabled")
            .in_("owner_user_id", owner_ids)
            .execute()
        ).data or []
        video_caps = [float(p.get("daily_video_budget_usd") or 0) for p in ps if p.get("daily_video_budget_usd") is not None]
        if video_caps:
            cap_video = max(video_caps)
        persona_video_meta = [
            {
                "persona_id": p.get("id"),
                "slug": p.get("slug"),
                "daily_video_budget_usd": float(p.get("daily_video_budget_usd") or 0),
                "video_enabled": bool(p.get("video_enabled")),
            }
            for p in ps
        ]
    except Exception as e:
        logger.warning(f"system-health: persona read failed: {e}")
        persona_video_meta = []

    today_iso = _today_start_iso()
    week_iso = _week_ago_iso()

    # ── Cost section ──────────────────────────────────────────────────
    today_runs = 0
    today_cost = 0.0
    today_failed = 0
    week_runs = 0
    week_cost = 0.0
    week_failed = 0
    recent_failures: list[dict] = []
    runs_by_status: dict[str, int] = {}

    try:
        if account_ids:
            today_q = (
                sb.table("hype_runs")
                .select("id, status, total_cost_usd, started_at, error, account_id")
                .in_("account_id", account_ids)
                .gte("started_at", today_iso)
                .execute()
            ).data or []
            today_runs = len(today_q)
            for r in today_q:
                today_cost += float(r.get("total_cost_usd") or 0)
                st = (r.get("status") or "").lower()
                runs_by_status[st] = runs_by_status.get(st, 0) + 1
                if st == "failed":
                    today_failed += 1

            week_q = (
                sb.table("hype_runs")
                .select("status, total_cost_usd, started_at")
                .in_("account_id", account_ids)
                .gte("started_at", week_iso)
                .execute()
            ).data or []
            week_runs = len(week_q)
            for r in week_q:
                week_cost += float(r.get("total_cost_usd") or 0)
                if (r.get("status") or "").lower() == "failed":
                    week_failed += 1

            # Recent failure samples (with error text) — newest first
            fail_q = (
                sb.table("hype_runs")
                .select("id, started_at, error, account_id")
                .in_("account_id", account_ids)
                .eq("status", "failed")
                .order("started_at", desc=True)
                .limit(PHASE_TIER3_RECENT_FAIL_LIMIT)
                .execute()
            ).data or []
            recent_failures = [
                {
                    "id": r.get("id"),
                    "started_at": r.get("started_at"),
                    "error": (r.get("error") or "")[:300],
                }
                for r in fail_q
            ]
    except Exception as e:
        logger.warning(f"system-health: hype_runs read failed: {e}")

    # Regen spend today
    regen_today_count = 0
    regen_today_cost = 0.0
    regen_today_failed = 0
    try:
        rj = (
            sb.table("image_regen_jobs")
            .select("status, cost_usd, created_at")
            .in_("owner_user_id", owner_ids)
            .gte("created_at", today_iso)
            .execute()
        ).data or []
        regen_today_count = len(rj)
        for j in rj:
            regen_today_cost += float(j.get("cost_usd") or 0)
            if (j.get("status") or "").lower() == "failed":
                regen_today_failed += 1
    except Exception as e:
        logger.warning(f"system-health: image_regen_jobs read failed: {e}")

    # Last successful Postiz post (per draft → postiz_post_id surrogate)
    last_published_at = None
    try:
        if account_ids:
            pp = (
                sb.table("daily_drafts")
                .select("scheduled_at, status, postiz_post_id")
                .in_("account_id", account_ids)
                .eq("source", "hype_auto")
                .not_.is_("postiz_post_id", "null")
                .order("scheduled_at", desc=True)
                .limit(1)
                .execute()
            ).data or []
            if pp:
                last_published_at = pp[0].get("scheduled_at")
    except Exception:
        pass

    # Postiz health probe
    postiz_health = _check_postiz_health()
    postiz_health["last_published_at"] = last_published_at
    postiz_health["integrations_count"] = len([
        a for a in accs if a.get("platform")
    ])

    cost_today_pct = (today_cost / cap_run) if cap_run > 0 else 0.0
    video_today_cost = 0.0
    # NB: HeyGen video cost lives inside hype_runs.total_cost_usd, not a
    # separate column. We approximate "video cost today" as a fraction
    # of today_cost weighted by the count of drafts with non-NULL
    # video_url. Cheap heuristic; refined later if needed.
    try:
        if account_ids:
            d_today = (
                sb.table("daily_drafts")
                .select("video_url, hype_run_id")
                .in_("account_id", account_ids)
                .gte("created_at", today_iso)
                .execute()
            ).data or []
            with_video = sum(1 for d in d_today if d.get("video_url"))
            if d_today:
                video_today_cost = today_cost * (with_video / len(d_today))
    except Exception:
        pass
    video_today_pct = (video_today_cost / cap_video) if cap_video > 0 else 0.0

    fail_rate_today = (today_failed / today_runs) if today_runs else 0.0
    fail_rate_week = (week_failed / week_runs) if week_runs else 0.0

    tone = "ok"
    if fail_rate_today >= PHASE_TIER3_FAIL_RATE_DANGER:
        tone = "danger"
    elif fail_rate_today >= PHASE_TIER3_FAIL_RATE_WARN:
        tone = "warn"

    return {
        "cost": {
            "today_runs": today_runs,
            "today_cost_usd": round(today_cost, 4),
            "today_cap_usd": round(cap_run, 2),
            "today_pct": round(cost_today_pct, 4),
            "week_runs": week_runs,
            "week_cost_usd": round(week_cost, 4),
            "week_avg_per_day_usd": round(week_cost / 7.0, 4),
            "regen_today_count": regen_today_count,
            "regen_today_cost_usd": round(regen_today_cost, 4),
            "video_today_cost_usd": round(video_today_cost, 4),
            "video_cap_usd": round(cap_video, 2),
            "video_today_pct": round(video_today_pct, 4),
            "video_personas": persona_video_meta,
        },
        "reliability": {
            "today_runs": today_runs,
            "today_failed": today_failed,
            "today_fail_rate": round(fail_rate_today, 4),
            "today_fail_rate_pct": round(fail_rate_today * 100, 1),
            "week_runs": week_runs,
            "week_failed": week_failed,
            "week_fail_rate": round(fail_rate_week, 4),
            "regen_today_count": regen_today_count,
            "regen_today_failed": regen_today_failed,
            "regen_today_fail_rate": round(
                (regen_today_failed / regen_today_count) if regen_today_count else 0.0, 4
            ),
            "runs_by_status": runs_by_status,
            "recent_failures": recent_failures,
            "tone": tone,
            "warn_threshold": PHASE_TIER3_FAIL_RATE_WARN,
            "danger_threshold": PHASE_TIER3_FAIL_RATE_DANGER,
        },
        "postiz": postiz_health,
        "modes": {
            "dry_run_mode_anywhere": dry_run_active,
            "auto_publish_enabled_anywhere": auto_publish_active,
        },
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


class PersonaBudgetUpdate(BaseModel):
    daily_video_budget_usd: Optional[float] = Field(None, ge=0, le=50)
    video_enabled: Optional[bool] = None


@router.patch("/personas/{persona_id}/budget")
async def update_persona_budget(
    persona_id: str,
    body: PersonaBudgetUpdate,
    user=Depends(require_auth),
):
    """Tier 3 — sparse update of persona-level budget knobs.

    Only the keys the user actually sent get written, so the page can
    PATCH a single field without nuking the other one.
    """
    sb = get_supabase()
    from services.access_control import accessible_owner_ids

    p = (
        sb.table("personas")
        .select("id, owner_user_id")
        .eq("id", persona_id)
        .in_("owner_user_id", accessible_owner_ids(user.id))
        .limit(1)
        .execute()
    )
    if not p.data:
        raise HTTPException(404, "persona not found")

    raw = body.model_dump(exclude_unset=True)
    payload = {k: v for k, v in raw.items() if v is not None}
    if not payload:
        raise HTTPException(400, "no fields to update")

    sb.table("personas").update(payload).eq("id", persona_id).execute()
    return {"persona_id": persona_id, "updated": payload}


# ═══════════════════════════════════════════════════════════════════════════
# Home v1 — operator-facing editorial briefing (`/control`)
#
# Source of truth: projects/post-capstone/product-structure.md and
# projects/post-capstone/home-v1-implementation-plan.md. Read those before
# editing this section.
#
# Step 1 (this commit): scaffold only.
#   - GET  /hype/home-summary  → returns status_only hero + real pause state
#                                + real cron liveness. Pairing/composer come
#                                in Steps 2–3.
#   - POST /hype/kill-switch   → flips hype_account_config.executive_freeze
#                                for the account. Returns new pause state.
# ═══════════════════════════════════════════════════════════════════════════


class KillSwitchRequest(BaseModel):
    paused: bool


def _read_pause_state(sb, account_id: str) -> dict:
    """Read the current executive_freeze flag for an account. If no config row
    exists yet, treat as not-paused + pausable (the row gets created on first
    kill-switch toggle, mirroring update_config's upsert pattern)."""
    res = (
        sb.table("hype_account_config")
        .select("executive_freeze")
        .eq("account_id", account_id)
        .limit(1)
        .execute()
    )
    is_paused = bool((res.data or [{}])[0].get("executive_freeze") or False)
    return {"is_paused": is_paused, "can_pause": True}


def _liveness_snapshot(sb, account_id: str) -> dict:
    """Step-1 liveness: cron freshness only (most recent hype_runs row for the
    account). Reconciler + per-platform reachability arrive with Step 5.
    Status logic mirrors product-structure.md Principle 6 thresholds."""
    now = datetime.now(timezone.utc)
    cron_iso = None
    cron_relative = None
    cron_age_min: Optional[float] = None

    try:
        last_run = (
            sb.table("hype_runs")
            .select("started_at")
            .eq("account_id", account_id)
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        if last_run.data:
            cron_iso = last_run.data[0]["started_at"]
            try:
                dt = datetime.fromisoformat(cron_iso.replace("Z", "+00:00"))
                cron_age_min = (now - dt).total_seconds() / 60.0
                if cron_age_min < 60:
                    cron_relative = f"{int(cron_age_min)} dakika önce"
                elif cron_age_min < 60 * 24:
                    cron_relative = f"{int(cron_age_min / 60)} saat önce"
                else:
                    cron_relative = f"{int(cron_age_min / (60 * 24))} gün önce"
            except Exception:
                cron_relative = None
    except Exception:
        logger.exception("[home-summary] liveness query failed")

    issues: list[str] = []
    status = "green"
    if cron_age_min is None:
        status = "yellow"
        issues.append("no_recent_evaluation")
    elif cron_age_min > 360:  # >6h → red (system dark)
        status = "red"
        issues.append("system_dark")
    elif cron_age_min > 90:   # >90min → yellow
        status = "yellow"
        issues.append("system_quiet_longer_than_usual")

    return {
        "status": status,
        "reconciler_last_run_iso": None,   # Step 5
        "reconciler_relative": None,       # Step 5
        "cron_last_run_iso": cron_iso,
        "cron_relative": cron_relative,
        "platforms_reachable": {},         # Step 5
        "issues": issues,
    }


def _status_only_hero(reason: str) -> dict:
    """status_only fallback when no usable decision pair / closest call exists.
    Sentence chosen by reason code. Turkish v1 (locked)."""
    sentences = {
        "scaffold":      "Cansu bugünün haberlerini hâlâ inceliyor.",
        "cold_install":  "Cansu henüz haber değerlendirmeye başlamadı.",
        "system_dark":   "Sistem son bir saattir kendini kontrol etmedi.",
        "no_decisions":  "Cansu bugün için henüz bir değerlendirme yapmadı.",
    }
    return {
        "kind": "status_only",
        "sentence": sentences.get(reason, sentences["scaffold"]),
        "covered": None,
        "skipped": None,
        "reason": None,
    }


def _today_utc_start() -> datetime:
    """Start-of-today in UTC. Day boundary is UTC midnight (not operator
    local time) — matches how hype_runs and persona_gate_log timestamp."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _format_relative(iso: str) -> Optional[str]:
    """Plain-language relative time in Turkish. Used by latest_published."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        mins = int(delta.total_seconds() / 60)
        if mins < 1:
            return "az önce"
        if mins < 60:
            return f"{mins} dakika önce"
        hours = mins // 60
        if hours < 24:
            return f"{hours} saat önce"
        days = hours // 24
        return f"{days} gün önce"
    except Exception:
        return None


def _load_latest_published(sb, account_id: str) -> Optional[dict]:
    """Most recent published item across all days for this account. Anchors
    the page on quiet days (proves publishing still works)."""
    try:
        res = (
            sb.table("daily_drafts")
            .select("trend_topic, platform, release_url, scheduled_at")
            .eq("account_id", account_id)
            .eq("postiz_state", "PUBLISHED")
            .order("scheduled_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("[home-summary] latest_published query failed")
        return None
    if not res.data:
        return None
    row = res.data[0]
    return {
        "title": row.get("trend_topic") or "",
        "platform": row.get("platform"),
        "release_url": row.get("release_url"),
        "published_at": row.get("scheduled_at"),
        "relative_time": _format_relative(row.get("scheduled_at") or "") or "",
    }


# ── 2026-06-11: today_feed — Home'daki "bugün ne yayınlandı / sırada ne
# var / ne ters gitti" akışı. _load_today_decisions'tan AYRI tutuldu:
# o helper hero için trend bazında dedup eder ve yalnız PUBLISHED filtreler;
# feed ise her platform satırını (kuyrukta/hatalı/takılı dahil) ham gösterir.

_FEED_PLATFORM_ORDER = ["twitter", "linkedin", "instagram", "youtube", "devto"]


def _derive_feed_state(row: dict) -> str:
    """Tek bir daily_drafts satırından operatör-dilinde feed durumu türetir.
    Saf fonksiyon — test edilebilirlik için modül seviyesinde."""
    if row.get("release_url"):
        return "published"
    if row.get("postiz_state") == "ERROR":
        return "error"
    if row.get("status") == "pending_review":
        return "stuck"
    return "queued"


def _load_today_feed(sb, account_id: str) -> list:
    """Bugünün draft akışı, trend bazında gruplu. created_at'i de kapsıyoruz
    ki scheduled_at'i null/bugün-öncesi kalmış stuck draftlar da görünsün.
    Hata halinde boş liste döner — endpoint bu yüzden asla patlamamalı."""
    today_iso = _today_utc_start().isoformat()

    # Hesap AİLESİ: platform draftları kardeş connected_accounts satırlarına
    # yazılır (devto/youtube/instagram ayrı account_id). Yalnız primary'yi
    # filtrelersek feed'de sadece twitter görünür (2026-06-11'de canlıda
    # yakalandı). Aynı user_id'nin tüm hesapları kapsanır; hata → tek hesap.
    account_ids = [account_id]
    try:
        own = (
            sb.table("connected_accounts").select("user_id")
            .eq("id", account_id).limit(1).execute()
        ).data or []
        if own and own[0].get("user_id"):
            sibs = (
                sb.table("connected_accounts").select("id")
                .eq("user_id", own[0]["user_id"]).execute()
            ).data or []
            if sibs:
                account_ids = [s["id"] for s in sibs]
    except Exception:
        logger.exception("[home-summary] today_feed account family lookup failed")

    try:
        res = (
            sb.table("daily_drafts")
            .select("id, trend_id, trend_topic, platform, status, "
                    "release_url, scheduled_at, postiz_state, "
                    "postiz_post_id, created_at")
            .in_("account_id", account_ids)
            .is_("deleted_at", "null")
            .not_.in_("status", ["rejected", "auto_rejected", "dismissed"])
            .or_(f"scheduled_at.gte.{today_iso},created_at.gte.{today_iso}")
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
    except Exception:
        logger.exception("[home-summary] today_feed query failed")
        return []

    try:
        groups: dict = {}   # key → {story, trend_id, posts}
        order: list = []    # ekleme sırası = en yeni created_at önce (query sıralı)
        for r in rows:
            key = r.get("trend_id") or f"topic:{(r.get('trend_topic') or '').strip()}"
            if key not in groups:
                groups[key] = {
                    "story": (r.get("trend_topic") or "").strip(),
                    "trend_id": r.get("trend_id"),
                    "posts": [],
                }
                order.append(key)
            groups[key]["posts"].append({
                "platform": r.get("platform"),
                "state": _derive_feed_state(r),
                "release_url": r.get("release_url"),
                "scheduled_at": r.get("scheduled_at"),
                "postiz_post_id": r.get("postiz_post_id"),
                "draft_id": r.get("id"),
            })

        def _plat_rank(p: dict) -> int:
            try:
                return _FEED_PLATFORM_ORDER.index(p.get("platform"))
            except ValueError:
                return len(_FEED_PLATFORM_ORDER)

        out = []
        for key in order:
            g = groups[key]
            g["posts"].sort(key=_plat_rank)
            out.append(g)
        return out
    except Exception:
        logger.exception("[home-summary] today_feed grouping failed")
        return []


def _load_today_decisions(sb, account_id: str) -> dict:
    """Returns today's gate-log accepts + rejects + the published drafts that
    came out of them. Used both for `considered_today` counts and for the
    covered × skipped pairing in the hero."""
    today_iso = _today_utc_start().isoformat()
    out = {
        "covered": [],   # list of {title, platform, release_url, published_at, trend_id, category}
        "skipped": [],   # list of {title, source_url, category, trend_id, gate_reason, source_name}
        "evaluated": 0,
        "passed": 0,
        "rejected": 0,
    }

    # Gate log — accepts and rejects, with category snapshot for pairing.
    try:
        gate = (
            sb.table("persona_gate_log")
            .select("trend_id, decision, topic_snapshot, category_snapshot, "
                    "source_snapshot, matched_reason, created_at")
            .eq("account_id", account_id)
            .gte("created_at", today_iso)
            .order("created_at", desc=True)
            .execute()
        )
        gate_rows = gate.data or []
    except Exception:
        logger.exception("[home-summary] gate_log query failed")
        gate_rows = []

    accepts_by_trend: dict = {}
    skipped: list = []
    for r in gate_rows:
        out["evaluated"] += 1
        if r.get("decision") == "accept":
            out["passed"] += 1
            if r.get("trend_id"):
                accepts_by_trend[r["trend_id"]] = r
        else:
            out["rejected"] += 1
            skipped.append({
                "title": (r.get("topic_snapshot") or "").strip(),
                "source_url": None,
                "category": (r.get("category_snapshot") or "").strip() or None,
                "trend_id": r.get("trend_id"),
                "gate_reason": r.get("matched_reason"),
                "matched_reason": r.get("matched_reason"),  # for composer hint translation
                "source_name": (r.get("source_snapshot") or "").strip() or None,
            })

    # Covered — today's published drafts; cross-reference with accepts for category.
    try:
        published = (
            sb.table("daily_drafts")
            .select("trend_id, trend_topic, platform, release_url, scheduled_at, postiz_state")
            .eq("account_id", account_id)
            .eq("postiz_state", "PUBLISHED")
            .gte("scheduled_at", today_iso)
            .order("scheduled_at", desc=True)
            .execute()
        )
        pub_rows = published.data or []
    except Exception:
        logger.exception("[home-summary] published query failed")
        pub_rows = []

    # Deduplicate by trend_id so multi-platform fan-outs count as one decision.
    seen_trends: set = set()
    covered: list = []
    for d in pub_rows:
        tid = d.get("trend_id")
        if tid and tid in seen_trends:
            continue
        if tid:
            seen_trends.add(tid)
        accept_row = accepts_by_trend.get(tid) if tid else None
        covered.append({
            "title": (d.get("trend_topic") or "").strip(),
            "platform": d.get("platform"),
            "release_url": d.get("release_url"),
            "published_at": d.get("scheduled_at"),
            "trend_id": tid,
            "category": (accept_row or {}).get("category_snapshot") or None,
            "matched_reason": (accept_row or {}).get("matched_reason"),  # composer hint
            "source_name": (accept_row or {}).get("source_snapshot") or None,
        })

    out["covered"] = covered
    out["skipped"] = skipped
    return out


def _pair_decisions(covered: list, skipped: list) -> Optional[tuple[dict, dict, int]]:
    """Step 2 pairing algorithm — picks the operationally most contrastive
    pair from today's decisions. Returns (covered_item, skipped_item, score)
    or None when no pairing is possible. The algorithm is intentionally
    auditable: same category +3, same source +2, base +1. Tie-broken by
    insertion order (today's first-named covered + first-named skipped).
    Step 3's composer wraps this output in prose."""
    if not covered or not skipped:
        return None
    best: Optional[tuple[dict, dict, int]] = None
    for c in covered:
        for s in skipped:
            score = 1  # base — any pairing is better than no pairing
            c_cat = (c.get("category") or "").lower()
            s_cat = (s.get("category") or "").lower()
            if c_cat and s_cat and c_cat == s_cat:
                score += 3
            # Source-domain match falls back to a string contains check on the
            # skipped item's source_name — published items don't carry a clean
            # domain field yet, so we use the skipped item's source as a proxy.
            # Best-effort only; the +2 stays small enough that it doesn't
            # dominate the category match.
            s_src = (s.get("source_name") or "").lower()
            if s_src and s_src in (c.get("title") or "").lower():
                score += 2
            if best is None or score > best[2]:
                best = (c, s, score)
    return best


def _closest_call(skipped: list) -> Optional[dict]:
    """When today has no covered items, surface the closest call — the
    skipped item we judge most newsworthy. Step 2: take the first reject
    (gate-log is ordered desc by created_at, so this is the most recent
    rejection, which is a reasonable proxy for 'closest call' until Step 3
    introduces a real gate-score ranking)."""
    return skipped[0] if skipped else None


def _decision_pair_hero(covered: dict, skipped: dict, reason: Optional[str] = None) -> dict:
    """Honest decision_pair hero. Both titles appear verbatim. The reason
    clause, when present, comes from `selection_delta.winning_reason` of
    the same firing (Phase 2). Endpoint never invents a reason."""
    if reason:
        sentence = (
            f"Cansu bugün “{covered['title']}” hakkında yazdı; "
            f"“{skipped['title']}” hakkında yazmadı çünkü {reason}"
        )
    else:
        sentence = (
            f"Cansu bugün “{covered['title']}” hakkında yazdı; "
            f"“{skipped['title']}” hakkında yazmadı."
        )
    return {
        "kind": "decision_pair",
        "sentence": sentence,
        "covered": {
            "title": covered["title"],
            "platform": covered.get("platform"),
            "release_url": covered.get("release_url"),
            "published_at": covered.get("published_at"),
            "trend_id": covered.get("trend_id"),
        },
        "skipped": {
            "title": skipped["title"],
            "source_url": skipped.get("source_url"),
            "category_hint": skipped.get("category"),
            "trend_id": skipped.get("trend_id"),
        },
        "reason": reason,
    }


# ─── Phase 2 — Honest reason derivation from selection_delta ──────────────
def _operator_reason_from_delta(delta: dict) -> Optional[str]:
    """Map a selection_delta.winning_reason code to operator-facing Turkish.
    Returns None when the recorded reason cannot honestly support an editorial
    framing — caller MUST fall back to status_only in that case (never invent).

    Honest mappings (all anchored in recorded fields):
      first_coverage_vs_already_covered → novelty axis (selected is fresh,
        runner-up has documented prior coverage in last 7 days).
      agent_preference_no_clear_axis    → None (no recorded differentiator).
      agent_preference_despite_runner_up_freshness → None (selection cannot
        be honestly justified from recorded fields).
    """
    code = (delta or {}).get("winning_reason")
    if code == "first_coverage_vs_already_covered":
        n = int((delta or {}).get("runner_up_url_match_count") or 0)
        if n > 0:
            return (
                f"bu konuyu ilk kez ele aldı; diğer aday son 7 günde {n} kez işlenmişti."
            )
        return "bu konuyu ilk kez ele aldı; diğer aday daha önce işlenmişti."
    return None


def _load_todays_editorial_pair(sb, account_id: str) -> Optional[dict]:
    """Phase 2 + Phase 3 — Today's REAL editorial decision from the most
    recent firing that recorded a within-beat comparison. Returns a dict
    {covered, skipped, reason} or None when no honest pair is available
    today.

    Source of truth: hype_stages where agent_name='Trend Scout' AND
    output->'candidates_considered' is populated (written by flow.py Phase 1).
    """
    today_iso = _today_utc_start().isoformat()
    try:
        # Today's runs that selected a trend
        runs = (
            sb.table("hype_runs")
            .select("id, trend_id, started_at, account_id")
            .eq("account_id", account_id)
            .not_.is_("trend_id", "null")
            .gte("started_at", today_iso)
            .order("started_at", desc=True)
            .limit(20)
            .execute()
        ).data or []
    except Exception:
        logger.exception("[home-summary] todays_editorial_pair: runs query failed")
        return None
    if not runs:
        return None

    run_ids = [r["id"] for r in runs if r.get("id")]
    try:
        stages = (
            sb.table("hype_stages")
            .select("run_id, output, completed_at")
            .in_("run_id", run_ids)
            .eq("agent_name", "Trend Scout")
            .order("completed_at", desc=True)
            .execute()
        ).data or []
    except Exception:
        logger.exception("[home-summary] todays_editorial_pair: stages query failed")
        return None

    # Walk stages most-recent first; pick the first one whose output
    # carries candidates_considered AND a usable selection_delta with an
    # honest reason.
    for st in stages:
        output = st.get("output") or {}
        if not isinstance(output, dict):
            continue
        cands = output.get("candidates_considered")
        delta = output.get("selection_delta")
        if not isinstance(cands, list) or not isinstance(delta, dict):
            continue
        selected = next(
            (c for c in cands if isinstance(c, dict) and c.get("outcome") == "selected"),
            None,
        )
        runner_up_tid = delta.get("runner_up_trend_id")
        runner_up = next(
            (c for c in cands if isinstance(c, dict) and c.get("trend_id") == runner_up_tid),
            None,
        )
        if not (selected and runner_up):
            continue
        reason = _operator_reason_from_delta(delta)
        if not reason:
            # No honest reason → skip this firing; do not invent.
            continue

        # Enrich covered with the daily_draft (release_url / platform /
        # published_at) created from this run, if any.
        covered = {
            "title": (selected.get("topic") or "").strip(),
            "category": selected.get("category"),
            "trend_id": selected.get("trend_id"),
            "source_name": selected.get("source_name"),
            "platform": None,
            "release_url": None,
            "published_at": None,
        }
        try:
            drafts = (
                sb.table("daily_drafts")
                .select("platform, release_url, scheduled_at, postiz_state, postiz_post_id")
                .eq("hype_run_id", st["run_id"])
                .order("scheduled_at", desc=True)
                .limit(1)
                .execute()
            ).data or []
            if drafts:
                d = drafts[0]
                covered["platform"] = d.get("platform")
                covered["release_url"] = d.get("release_url")
                covered["published_at"] = d.get("scheduled_at")
        except Exception:
            pass

        # Skipped = runner-up from same firing. source_url comes from the
        # Phase 1 capture (trends.url lookup at firing time).
        skipped = {
            "title": (runner_up.get("topic") or "").strip(),
            "category": runner_up.get("category"),
            "trend_id": runner_up.get("trend_id"),
            "source_url": runner_up.get("source_url"),
            "source_name": runner_up.get("source_name"),
        }
        return {
            "covered": covered,
            "skipped": skipped,
            "reason": reason,
            "firing_started_at": st.get("completed_at"),
        }
    return None


def _closest_call_hero(skipped: dict) -> dict:
    """Step 2 deterministic hero sentence for closest_call kind (quiet day
    with a usable near-miss)."""
    sentence = f"Cansu bugün yazmadı. En yakın aday: “{skipped['title']}”."
    return {
        "kind": "closest_call",
        "sentence": sentence,
        "covered": None,
        "skipped": {
            "title": skipped["title"],
            "source_url": skipped.get("source_url"),
            "category_hint": skipped.get("category"),
        },
        "reason": None,
    }


# ─── Phase A — Day-level honest pair (no head-to-head fabrication) ────────
def _daylevel_hero(
    covered: dict,
    skipped: dict,
    match_count: int,
    *,
    is_published: bool,
    first_coverage_confirmed: bool,
) -> dict:
    """Phase B sentence — two independent grounded facts, never phrased as
    a head-to-head comparison.

    Lever 1: only include "ilk kez ele aldığı" when the structural first-
    coverage check confirmed it (zero prior trend_id matches in last 7d).
    On inconclusive: drop the novelty phrase rather than risk a false claim.

    Lever 3: use "yazdı" only when Cansu's draft has been published
    (release_url non-null). When still pending Postiz publish, switch to
    "hazırladı" (prepared) and never expose source_url as if it were her
    post.
    """
    # Lever 3: "yazdı" (wrote) only when actually published; "hakkında bir
    # gönderi hazırladı" (prepared a post about) when authored but pending
    # Postiz publish. Both verbs are honest about the state.
    if is_published:
        action_clause = f"“{covered['title']}” hakkında yazdı"
    else:
        action_clause = f"“{covered['title']}” hakkında bir gönderi hazırladı"
    novelty_clause = " — ilk kez ele aldığı bir konu" if first_coverage_confirmed else ""
    sentence = (
        f"Cansu bugün {action_clause}{novelty_clause}. "
        f"“{skipped['title']}” hakkında yazmadı; bu haberi son bir "
        f"haftada zaten {match_count} kez işlemişti."
    )
    # Reason field reflects only honest grounded facts.
    if first_coverage_confirmed:
        reason_text = (
            f"ilk kez ele aldığı bir konu; diğeri son haftada {match_count} kez işlenmişti."
        )
    else:
        reason_text = f"diğer haber son haftada {match_count} kez işlenmişti."

    # Lever 3 — never expose trends.url on covered side (would conflate
    # source story with Cansu's post). Only release_url. When pending,
    # release_url is null and frontend renders title unlinked.
    covered_payload = {
        "title": covered["title"],
        "platform": covered.get("platform"),
        "release_url": covered.get("release_url"),
        "published_at": covered.get("published_at"),
        "is_published": is_published,
        "trend_id": covered.get("trend_id"),
    }
    return {
        "kind": "decision_pair",
        "sentence": sentence,
        "covered": covered_payload,
        "skipped": {
            "title": skipped["title"],
            "source_url": skipped.get("source_url"),
            "category_hint": skipped.get("category"),
            "trend_id": skipped.get("trend_id"),
        },
        "reason": reason_text,
    }


def _count_prior_coverage_by_url(
    sb,
    account_id: str,
    trend_url: Optional[str],
    exclude_run_id: Optional[str],
    days: int = 7,
) -> Optional[int]:
    """Lever 1 — structural prior-coverage count.

    Returns the number of daily_drafts in the last `days` for `account_id`
    that map (via hype_runs.trend_id) to a trends row sharing `trend_url`.
    Returns None on any query failure → caller treats as INCONCLUSIVE and
    drops the novelty claim rather than risking a false 'ilk kez'.
    """
    if not trend_url:
        return None
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        tr_rows = (
            sb.table("trends")
            .select("id")
            .eq("url", trend_url)
            .execute()
        ).data or []
        trend_ids = [r["id"] for r in tr_rows if isinstance(r, dict) and r.get("id")]
        if not trend_ids:
            # URL absent from trends table — no structural match possible.
            return 0
        hr = (
            sb.table("hype_runs")
            .select("id")
            .in_("trend_id", trend_ids)
            .gte("started_at", cutoff)
            .execute()
        ).data or []
        hr_ids = [
            r["id"] for r in hr
            if isinstance(r, dict) and r.get("id")
            and (not exclude_run_id or r["id"] != exclude_run_id)
        ]
        if not hr_ids:
            return 0
        dd = (
            sb.table("daily_drafts")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .in_("hype_run_id", hr_ids)
            .gte("created_at", cutoff)
            .limit(1)
            .execute()
        )
        return int(dd.count or 0) if hasattr(dd, "count") else 0
    except Exception:
        return None


def _covered_only_hero(covered: dict, *, is_published: bool, first_coverage_confirmed: bool) -> dict:
    """Phase A.5 sentence — honest covered-only fallback when a fresh covered
    selection exists but no grounded skipped fact to contrast with.

    Same verb honesty as _daylevel_hero (yazdı vs hazırladı) and same novelty
    rule (only assert "ilk kez ele aldığı" when structurally confirmed).
    """
    if is_published:
        action_clause = f"“{covered['title']}” hakkında yazdı"
    else:
        action_clause = f"“{covered['title']}” hakkında bir gönderi hazırladı"
    novelty_clause = " — ilk kez ele aldığı bir konu" if first_coverage_confirmed else ""
    sentence = f"Cansu bugün {action_clause}{novelty_clause}."
    reason_text = "ilk kez ele aldığı bir konu." if first_coverage_confirmed else None
    return {
        "kind": "decision_covered_only",
        "sentence": sentence,
        "covered": {
            "title": covered["title"],
            "platform": covered.get("platform"),
            "release_url": covered.get("release_url"),
            "published_at": covered.get("published_at"),
            "is_published": is_published,
            "trend_id": covered.get("trend_id"),
        },
        "skipped": None,
        "reason": reason_text,
    }


def _load_recent_publish_hero(
    sb, account_id: str, max_age_hours: int = 12
) -> Optional[dict]:
    """Publish-anchored hero — kills the midnight contradiction.

    Cron's "today" (UTC midnight start) drifts out of sync with the
    operator-facing day when publishes drain across midnight. At 03:06
    local a fresh new-day cron may not have fired yet, but a publish
    from 15 minutes ago is still Cansu's most recent editorial act —
    and the hero must reflect THAT, not say "henüz değerlendirme yapmadı".

    This loader finds the most recent published `daily_drafts` row within
    `max_age_hours`, walks back to its hype_run_id's Trend Scout output,
    and builds a covered-only hero anchored on that publish. The
    first-coverage check uses the SAME structural URL prior-count rule
    as the today-anchored loaders (Lever 1).

    Caller must invoke this only when the today-anchored chain returned
    no hero — never as a primary path (today's data still wins).
    """
    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    ).isoformat()
    try:
        recent = (
            sb.table("daily_drafts")
            .select(
                "hype_run_id, platform, release_url, scheduled_at, trend_topic, trend_id"
            )
            .eq("account_id", account_id)
            .not_.is_("release_url", "null")
            .gte("scheduled_at", cutoff_iso)
            .order("scheduled_at", desc=True)
            .limit(1)
            .execute()
        ).data or []
    except Exception:
        logger.exception("[home-summary] recent-publish lookup failed")
        return None
    if not recent:
        return None
    pub = recent[0]
    run_id = pub.get("hype_run_id")
    if not run_id:
        return None
    try:
        stages = (
            sb.table("hype_stages")
            .select("output")
            .eq("run_id", run_id)
            .eq("agent_name", "Trend Scout")
            .limit(1)
            .execute()
        ).data or []
    except Exception:
        logger.exception("[home-summary] recent-publish stage fetch failed")
        return None
    out = (stages[0].get("output") if stages else None) or {}
    if not isinstance(out, dict) or out.get("passed") is not True:
        return None
    title = (out.get("topic") or pub.get("trend_topic") or "").strip()
    if not title:
        return None
    trend_id = out.get("trend_id") or pub.get("trend_id")
    c_url: Optional[str] = None
    if trend_id:
        try:
            tr = (
                sb.table("trends")
                .select("url")
                .eq("id", trend_id)
                .limit(1)
                .execute()
            ).data or []
            if tr and isinstance(tr[0], dict):
                c_url = tr[0].get("url")
        except Exception:
            c_url = None
    prior_count = _count_prior_coverage_by_url(
        sb, account_id, c_url, exclude_run_id=run_id, days=7
    )
    first_coverage_confirmed = prior_count == 0
    covered = {
        "title": title,
        "platform": pub.get("platform"),
        "release_url": pub.get("release_url"),
        "published_at": pub.get("scheduled_at"),
        "trend_id": trend_id,
    }
    return _covered_only_hero(
        covered,
        is_published=True,
        first_coverage_confirmed=first_coverage_confirmed,
    )


def _load_todays_covered_only(sb, account_id: str) -> Optional[dict]:
    """Phase A.5 — Pick the most recent passed=true Trend Scout selection
    today whose draft exists (published preferred). Returns the covered side
    with first-coverage + is_published flags. Returns None when no covered
    candidate today reaches the daily_drafts stage.

    Mirrors the covered-side selection inside _load_todays_daylevel_pair
    without requiring a skipped counterpart.
    """
    today_iso = _today_utc_start().isoformat()
    try:
        runs = (
            sb.table("hype_runs")
            .select("id, trend_id, started_at")
            .eq("account_id", account_id)
            .gte("started_at", today_iso)
            .order("started_at", desc=True)
            .limit(60)
            .execute()
        ).data or []
    except Exception:
        logger.exception("[home-summary] covered_only: runs query failed")
        return None
    if not runs:
        return None
    run_ids = [r["id"] for r in runs if r.get("id")]
    try:
        stages = (
            sb.table("hype_stages")
            .select("run_id, output, completed_at")
            .in_("run_id", run_ids)
            .eq("agent_name", "Trend Scout")
            .order("completed_at", desc=True)
            .execute()
        ).data or []
    except Exception:
        logger.exception("[home-summary] covered_only: stages query failed")
        return None
    covered_candidates: list[tuple[dict, dict]] = []
    for st in stages:
        out = st.get("output") or {}
        if isinstance(out, dict) and out.get("passed") is True:
            covered_candidates.append((st, out))
    if not covered_candidates:
        return None

    for pass_published_required in (True, False):
        for st_cand, out_cand in covered_candidates:
            tid = out_cand.get("trend_id")
            if not tid:
                continue
            c_url_local: Optional[str] = None
            try:
                tr = sb.table("trends").select("url").eq("id", tid).limit(1).execute().data or []
                if tr and isinstance(tr[0], dict):
                    c_url_local = tr[0].get("url")
            except Exception:
                c_url_local = None
            prior_count = _count_prior_coverage_by_url(
                sb, account_id, c_url_local, exclude_run_id=st_cand["run_id"], days=7
            )
            if prior_count is not None and prior_count > 0:
                continue
            is_first_local = prior_count == 0
            try:
                drafts = (
                    sb.table("daily_drafts")
                    .select("platform, release_url, scheduled_at, postiz_state")
                    .eq("hype_run_id", st_cand["run_id"])
                    .order("scheduled_at", desc=True)
                    .limit(5)
                    .execute()
                ).data or []
            except Exception:
                drafts = []
            if not drafts:
                continue
            published = next((d for d in drafts if d.get("release_url")), None)
            if pass_published_required and not published:
                continue
            chosen = published or drafts[0]
            is_pub = bool(chosen.get("release_url"))
            return {
                "covered": {
                    "title": (out_cand.get("topic") or "").strip(),
                    "platform": chosen.get("platform"),
                    "release_url": chosen.get("release_url"),
                    "published_at": chosen.get("scheduled_at"),
                    "trend_id": tid,
                },
                "is_published": is_pub,
                "first_coverage_confirmed": bool(is_first_local),
            }
    return None


def _load_todays_daylevel_pair(sb, account_id: str) -> Optional[dict]:
    """Phase A — When no same-firing pair exists, assemble a day-level
    statement from two INDEPENDENT recorded facts on today's data:
      covered: most-recent passed=true Trend Scout selection today whose
               url-dedup match_count == 0 (first-coverage on the open world).
      skipped: most-recent passed=false Trend Scout outcome today where
               skip_reason starts with 'duplicate_source_url' AND match_count
               can be parsed from that string.

    These are NOT paired as a comparison — only listed as two true facts
    from the same day, with each side's `because` clause attached only to
    its own recorded fact. Never phrased as 'chose A over B'.
    """
    today_iso = _today_utc_start().isoformat()

    # 1. Pull today's runs that produced a Trend Scout output (passed or not).
    try:
        runs = (
            sb.table("hype_runs")
            .select("id, trend_id, started_at")
            .eq("account_id", account_id)
            .gte("started_at", today_iso)
            .order("started_at", desc=True)
            .limit(60)
            .execute()
        ).data or []
    except Exception:
        logger.exception("[home-summary] daylevel: runs query failed")
        return None
    if not runs:
        return None

    run_ids = [r["id"] for r in runs if r.get("id")]
    try:
        stages = (
            sb.table("hype_stages")
            .select("run_id, output, completed_at")
            .in_("run_id", run_ids)
            .eq("agent_name", "Trend Scout")
            .order("completed_at", desc=True)
            .execute()
        ).data or []
    except Exception:
        logger.exception("[home-summary] daylevel: stages query failed")
        return None

    # 2. Walk stages most-recent first. Collect ALL passed=true selections
    #    (covered candidates) and ALL passed=false duplicate_source_url
    #    skips (skipped candidates). Order: most-recent first.
    covered_candidates: list[tuple[dict, dict]] = []
    skipped_candidates: list[tuple[Optional[dict], dict, int]] = []
    dup_re = re.compile(r"duplicate_source_url\s*\(\s*(\d+)\s+match")
    rc_re = re.compile(r"recently_covered\s*\(\s*(\d+)\s+match")
    for st in stages:
        out = st.get("output") or {}
        if not isinstance(out, dict):
            continue
        passed = out.get("passed")
        skip_reason = (out.get("skip_reason") or "").strip()
        if passed is True:
            covered_candidates.append((st, out))
        elif passed is False and "duplicate_source_url" in skip_reason:
            m = dup_re.search(skip_reason)
            if m:
                skipped_candidates.append((st, out, int(m.group(1))))
    if not covered_candidates:
        return None

    # Lever 2 — Also consume persona_gate_log rows of decision='recently_covered'
    # written today by the query_trends pre-filter logger. These are AI-relevant
    # trends that were skipped before TrendScout because they had been covered
    # recently — exactly the editorial "we already wrote about this" signal we
    # want to surface on Home's skipped side.
    try:
        rc_rows = (
            sb.table("persona_gate_log")
            .select("trend_id, topic_snapshot, category_snapshot, source_snapshot, matched_reason, created_at")
            .eq("account_id", account_id)
            .eq("decision", "recently_covered")
            .gte("created_at", today_iso)
            .order("created_at", desc=True)
            .execute()
        ).data or []
        for rc in rc_rows:
            if not isinstance(rc, dict):
                continue
            mr = rc.get("matched_reason") or ""
            m = rc_re.search(mr)
            if not m:
                continue
            n = int(m.group(1))
            if n <= 0:
                continue
            synthetic_out = {
                "trend_id": rc.get("trend_id"),
                "topic": rc.get("topic_snapshot") or "",
                "category": rc.get("category_snapshot"),
                "skip_reason": (
                    f"recently_covered ({n} match(es) in last 7d, scope=user)"
                ),
                "passed": False,
            }
            skipped_candidates.append((None, synthetic_out, n))
    except Exception:
        logger.exception("[home-summary] recently_covered fetch failed")

    if not skipped_candidates:
        return None

    # Pick the skipped candidate with the highest match_count (strongest
    # editorial signal that we'd already covered it).
    skipped_candidates.sort(key=lambda t: t[2], reverse=True)
    skp_st, skp_out, match_count = skipped_candidates[0]
    cov_st: Optional[dict] = None
    cov_out: Optional[dict] = None

    # 3. Iterate covered candidates (most-recent first). Lever 1: use
    #    structural prior-coverage check (trend_id / url, not ILIKE). Lever 3:
    #    prefer published candidates (release_url non-null) over pending,
    #    and track is_published honestly.
    cov_release_url: Optional[str] = None
    cov_platform: Optional[str] = None
    cov_published_at: Optional[str] = None
    cov_url: Optional[str] = None
    cov_trend_id: Optional[str] = None
    cov_is_published: bool = False
    cov_first_coverage_confirmed: bool = False
    cov_draft_id: Optional[str] = None      # C1 (2026-06-07) — link target for /control/lifecycle/{id}

    def _evaluate_covered_candidate(st_cand, out_cand):
        """Returns (is_first_confirmed, c_url, drafts_list) or (None, None, None)
        when the candidate cannot even reach the daily_drafts stage."""
        tid = out_cand.get("trend_id")
        if not tid:
            return (None, None, None)
        c_url_local: Optional[str] = None
        try:
            tr = (
                sb.table("trends")
                .select("url")
                .eq("id", tid)
                .limit(1)
                .execute()
            ).data or []
            if tr and isinstance(tr[0], dict):
                c_url_local = tr[0].get("url")
        except Exception:
            c_url_local = None
        prior_count = _count_prior_coverage_by_url(
            sb, account_id, c_url_local, exclude_run_id=st_cand["run_id"], days=7
        )
        # prior_count: None=inconclusive, 0=confirmed first, >0=confirmed not-first
        if prior_count is not None and prior_count > 0:
            return (False, c_url_local, None)  # confirmed not-first → skip
        is_first_local = prior_count == 0
        try:
            drafts = (
                sb.table("daily_drafts")
                .select("id, platform, release_url, scheduled_at, postiz_state")
                .eq("hype_run_id", st_cand["run_id"])
                .order("scheduled_at", desc=True)
                .limit(5)
                .execute()
            ).data or []
        except Exception:
            drafts = []
        if not drafts:
            return (None, None, None)
        return (is_first_local, c_url_local, drafts)

    # Two-pass: first pass picks published; second pass picks pending.
    for pass_published_required in (True, False):
        for st_cand, out_cand in covered_candidates:
            is_first_local, c_url_local, drafts = _evaluate_covered_candidate(
                st_cand, out_cand
            )
            if drafts is None:
                continue
            published = next(
                (d for d in drafts if d.get("release_url")),
                None,
            )
            if pass_published_required:
                if not published:
                    continue
                chosen = published
                is_pub = True
            else:
                # Second pass: take first draft regardless of release_url.
                chosen = published or drafts[0]
                is_pub = bool(chosen.get("release_url"))
            cov_st = st_cand
            cov_out = out_cand
            cov_trend_id = out_cand.get("trend_id")
            cov_url = c_url_local
            cov_platform = chosen.get("platform")
            cov_release_url = chosen.get("release_url")
            cov_published_at = chosen.get("scheduled_at")
            cov_is_published = is_pub
            cov_first_coverage_confirmed = bool(is_first_local)
            cov_draft_id = chosen.get("id")        # C1 (2026-06-07) — Lifecycle entry point
            break
        if cov_st is not None:
            break
    if cov_out is None:
        return None

    # 5. Pull skipped trend's source_url from trends table.
    skp_trend_id = skp_out.get("trend_id")
    skp_url: Optional[str] = None
    if skp_trend_id:
        try:
            tr = (
                sb.table("trends")
                .select("url")
                .eq("id", skp_trend_id)
                .limit(1)
                .execute()
            ).data or []
            if tr and isinstance(tr[0], dict):
                skp_url = tr[0].get("url")
        except Exception:
            pass

    # Lever 3: do NOT expose trends.url on covered side — it would
    # conflate source story with Cansu's authored post. release_url is
    # the only honest clickable for covered; pending state shows no link.
    covered = {
        "title": (cov_out.get("topic") or "").strip(),
        "category": cov_out.get("category"),
        "trend_id": cov_trend_id,
        "platform": cov_platform,
        "release_url": cov_release_url,
        "published_at": cov_published_at,
        # C1 (2026-06-07) — UI navigates to /control/lifecycle/{draft_id}
        # when this is non-null. Null means "covered but draft row not
        # surfaceable" (rare; first-coverage path) — UI falls back to
        # the release_url link only.
        "draft_id": cov_draft_id,
    }
    skipped = {
        "title": (skp_out.get("topic") or "").strip(),
        "category": skp_out.get("category"),
        "trend_id": skp_trend_id,
        "source_url": skp_url,
    }
    return {
        "covered": covered,
        "skipped": skipped,
        "match_count": match_count,
        "is_published": cov_is_published,
        "first_coverage_confirmed": cov_first_coverage_confirmed,
    }


@router.get("/home-summary")
async def get_home_summary(
    account_id: str = Query(...),
    user=Depends(require_auth),
):
    """Home v1 endpoint — Step 1 scaffold.

    Returns the structured payload documented in
    projects/post-capstone/home-v1-implementation-plan.md §1.1. In this step
    `hero.kind` is always `status_only` (sentence chosen by liveness state);
    pairing and Sonnet composition come in Steps 2–3.

    Hero, latest_published, considered_today are intentionally minimal in
    Step 1 — the frontend renders status_only and the kill switch + liveness
    strip. Step 2 wires the decision-pair selection algorithm. Step 3 wires
    the composer.

    No caching here yet — the cache layer lands in Step 3 alongside the
    composer (composed sentence persisted on the underlying decision row).
    """
    _verify_account_ownership(account_id, user.id)
    sb = get_supabase()

    liveness = _liveness_snapshot(sb, account_id)
    pause = _read_pause_state(sb, account_id)

    # Step 2 — load today's real decisions + latest published item.
    decisions = _load_today_decisions(sb, account_id)
    latest_published = _load_latest_published(sb, account_id)

    # Hero selection priority — Phase 2/3 honest hierarchy:
    # 1. system_dark / cold_install short-circuit to status_only
    # 2. decision_pair from the most recent firing that recorded a real
    #    within-beat comparison with an honest reason (Phase 1 + 2 data).
    # 3. status_only when no such pair exists today. We DO NOT fall back to
    #    the old cross-firing decision_pair or to a tautological closest_call
    #    derived from gate rejects — both fabricate editorial framing.
    picked_covered: Optional[dict] = None
    picked_skipped: Optional[dict] = None
    decision_reason: Optional[str] = None
    if "system_dark" in liveness["issues"]:
        hero = _status_only_hero("system_dark")
    elif "no_recent_evaluation" in liveness["issues"]:
        hero = _status_only_hero("cold_install")
    else:
        # Hero priority (purity-first):
        #   1. Same-firing pair with a recorded honest reason (purest — covered
        #      and skipped were in the same query_trends pool head-to-head).
        #   2. Day-level grounded pair (two independent recorded facts from
        #      today; never phrased as "chose X over Y").
        #   3. status_only otherwise.
        editorial = _load_todays_editorial_pair(sb, account_id)
        if editorial is not None:
            picked_covered = editorial["covered"]
            picked_skipped = editorial["skipped"]
            decision_reason = editorial["reason"]
            hero = _decision_pair_hero(picked_covered, picked_skipped, reason=decision_reason)
        else:
            daylevel = _load_todays_daylevel_pair(sb, account_id)
            if daylevel is not None:
                picked_covered = daylevel["covered"]
                picked_skipped = daylevel["skipped"]
                hero = _daylevel_hero(
                    picked_covered,
                    picked_skipped,
                    daylevel["match_count"],
                    is_published=daylevel.get("is_published", False),
                    first_coverage_confirmed=daylevel.get(
                        "first_coverage_confirmed", False
                    ),
                )
                decision_reason = hero.get("reason")
            else:
                # Phase A.5 — covered-only honest fallback. When today has a
                # fresh covered pick (passed=true, first-coverage confirmed)
                # but NO grounded skip to contrast against, render covered
                # alone rather than fall to status_only.
                covered_only = _load_todays_covered_only(sb, account_id)
                if covered_only is not None:
                    picked_covered = covered_only["covered"]
                    picked_skipped = None
                    hero = _covered_only_hero(
                        picked_covered,
                        is_published=covered_only["is_published"],
                        first_coverage_confirmed=covered_only["first_coverage_confirmed"],
                    )
                    decision_reason = hero.get("reason")
                else:
                    # Midnight contradiction killer: today-anchored chain
                    # found nothing, but a recent publish may still be
                    # Cansu's most recent editorial act. Pivot to publish-
                    # anchored hero before falling to status_only.
                    recent_hero = _load_recent_publish_hero(
                        sb, account_id, max_age_hours=12
                    )
                    if recent_hero is not None:
                        hero = recent_hero
                        picked_covered = recent_hero.get("covered")
                        picked_skipped = None
                        decision_reason = recent_hero.get("reason")
                    else:
                        hero = _status_only_hero("no_decisions")

    # ─── Step 3 — Sonnet composer (opt-in via HOME_COMPOSER_ENABLED) ───
    # Replaces the deterministic Step-2 sentence with LLM-composed prose
    # when:
    #   - HOME_COMPOSER_ENABLED is true
    #   - hero is decision_pair or closest_call (status_only never goes
    #     through the LLM by design)
    #   - the composer doesn't fall back to template (which it does on
    #     2 failed validation attempts or API unavailability)
    # In-memory cache with 10-min TTL means repeated /control fetches in
    # the same window reuse one composed sentence.
    if hero["kind"] in ("decision_pair", "closest_call"):
        try:
            from services.home_composer import (
                is_enabled as composer_is_enabled,
                build_payload as composer_build_payload,
                build_side_from_row as composer_build_side,
                compose_hero as composer_compose,
            )
        except Exception:  # noqa: BLE001
            composer_is_enabled = lambda: False  # type: ignore
        if composer_is_enabled():
            # Pull raw_content lazily for the picked trend_ids only.
            picked_tids = [t for t in (
                (picked_covered or {}).get("trend_id"),
                (picked_skipped or {}).get("trend_id"),
            ) if t]
            raw_by_tid: dict = {}
            if picked_tids:
                try:
                    tr = (sb.table("trends")
                        .select("id, raw_content, source_name")
                        .in_("id", picked_tids).execute()).data or []
                    raw_by_tid = {r["id"]: r for r in tr}
                except Exception:
                    logger.exception("[home-composer] trends fetch failed")

            def _enriched(side: Optional[dict]) -> Optional[dict]:
                if side is None:
                    return None
                tid = side.get("trend_id")
                tr = raw_by_tid.get(tid) if tid else None
                summary = ((tr or {}).get("raw_content") or "").strip() or None
                return composer_build_side(
                    title=side.get("title") or "",
                    category=side.get("category"),
                    source_name=side.get("source_name") or (tr or {}).get("source_name"),
                    source_summary=summary,
                    matched_reason=side.get("matched_reason"),
                    trend_id=tid,
                    platform=side.get("platform"),
                )

            payload = composer_build_payload(
                hero["kind"],
                _enriched(picked_covered) if hero["kind"] == "decision_pair" else None,
                _enriched(picked_skipped),
                cansu_recent_topics=[],  # Step 3.1 will populate from hype_memory
                recorded_reason=decision_reason,  # Phase 2 — honest grounding
            )
            result = composer_compose(account_id, payload)
            if result.sentence and result.reason and not result.used_fallback:
                # Replace deterministic Step-2 sentence with composed prose.
                hero["sentence"] = result.sentence
                hero["reason"] = result.reason
                logger.info(
                    f"[home-composer] composed kind={hero['kind']} "
                    f"cache_hit={result.cache_hit} retry={result.retry_used} "
                    f"strength={result.evidence_strength}"
                )
            else:
                logger.info(
                    f"[home-composer] fallback kind={hero['kind']} "
                    f"strength={result.evidence_strength}"
                )

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "hero": hero,
        "latest_published": latest_published,
        "considered_today": {
            "evaluated": decisions["evaluated"],
            "published": decisions["passed"],
            "skipped": decisions["rejected"],
        },
        "pause": pause,
        "liveness": liveness,
        # 2026-06-11: bugünün akışı (yayınlandı/kuyrukta/hata/takılı) — hero'dan
        # bağımsız ayrı kaynak; hata halinde boş liste, endpoint patlamaz.
        "today_feed": _load_today_feed(sb, account_id),
    }


@router.post("/kill-switch")
async def post_kill_switch(
    body: KillSwitchRequest,
    account_id: str = Query(...),
    user=Depends(require_auth),
):
    """Flip hype_account_config.executive_freeze for the account.

    Idempotent — same input twice in a row returns the same end state.
    Upserts the config row if missing, mirroring update_config's pattern.
    """
    _verify_account_ownership(account_id, user.id)
    sb = get_supabase()

    payload = {
        "executive_freeze": bool(body.paused),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    existing = (
        sb.table("hype_account_config")
        .select("account_id")
        .eq("account_id", account_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        sb.table("hype_account_config").update(payload).eq(
            "account_id", account_id
        ).execute()
    else:
        payload["account_id"] = account_id
        sb.table("hype_account_config").insert(payload).execute()

    return _read_pause_state(sb, account_id)


# ───────────────────────────────────────────────────────────────────────
# Editorial decision-trail (karar izi) — read-only transparency view over
# persisted editor's-desk judgments. Renders the dry_run rows in
# editorial_lead_judgments enriched with per-candidate facts (topic,
# content_type, score, semantic_triggers, proof URL) + Cansu's actual
# publishes that day. Read-only: does NOT trigger any LLM call, does NOT
# write, does NOT affect live publishing.
# ───────────────────────────────────────────────────────────────────────


def _editorial_trail_enrich_candidates(sb, judgment_row: dict) -> list[dict]:
    """Enrich a persisted ranking[] (which has just trend_id+rank) with
    {topic, source_url, source_name, content_type, score, semantic_triggers}
    by joining trends + the day's Trend Scout outputs.
    """
    ranking = judgment_row.get("ranking") or []
    if not ranking:
        return []
    trend_ids = [r.get("trend_id") for r in ranking if r.get("trend_id")]
    if not trend_ids:
        return []
    try:
        trends_rows = (
            sb.table("trends")
            .select("id, topic, url, source_name, published_at")
            .in_("id", trend_ids)
            .execute()
        ).data or []
    except Exception:
        trends_rows = []
    trends_by_id = {t["id"]: t for t in trends_rows}

    # Pull Trend Scout outputs for the candidates' day so we can attach
    # content_type / score / semantic_triggers. Walk hype_runs by date.
    day_str = judgment_row.get("judgment_date")
    stage_by_tid: dict[str, dict] = {}
    if day_str:
        try:
            day_start = f"{day_str}T00:00:00+00:00"
            day_end_dt = datetime.fromisoformat(day_str) + timedelta(days=1)
            day_end = day_end_dt.strftime("%Y-%m-%dT00:00:00+00:00")
            # Scope to Cansu accounts only
            cansu = (
                sb.table("connected_accounts")
                .select("id")
                .ilike("username", "cansu%")
                .execute()
            ).data or []
            cansu_ids = [c["id"] for c in cansu]
            if cansu_ids:
                runs = (
                    sb.table("hype_runs")
                    .select("id")
                    .in_("account_id", cansu_ids)
                    .gte("started_at", day_start)
                    .lt("started_at", day_end)
                    .execute()
                ).data or []
                run_ids = [r["id"] for r in runs]
                if run_ids:
                    stages = (
                        sb.table("hype_stages")
                        .select("output")
                        .in_("run_id", run_ids)
                        .eq("agent_name", "Trend Scout")
                        .execute()
                    ).data or []
                    for st in stages:
                        out = st.get("output") or {}
                        if not isinstance(out, dict):
                            continue
                        tid = out.get("trend_id")
                        if tid and tid in trend_ids and tid not in stage_by_tid:
                            stage_by_tid[tid] = {
                                "content_type": out.get("content_type"),
                                "category": out.get("category"),
                                "score": out.get("score"),
                                "semantic_triggers": out.get("semantic_triggers") or [],
                            }
        except Exception:
            logger.exception("[editorial-trail] stage enrich failed")

    lead_tid = judgment_row.get("lead_trend_id")
    passed_tid = judgment_row.get("passed_over_trend_id")
    enriched: list[dict] = []
    for r in ranking:
        tid = r.get("trend_id")
        t = trends_by_id.get(tid) or {}
        st = stage_by_tid.get(tid) or {}
        if tid == lead_tid:
            role = "lead"
        elif tid == passed_tid:
            role = "passed_over"
        else:
            role = "other"
        enriched.append({
            "rank": r.get("rank"),
            "label": r.get("label"),
            "trend_id": tid,
            "role": role,
            "topic": t.get("topic"),
            "source_url": t.get("url"),
            "source_name": t.get("source_name"),
            "published_at": t.get("published_at"),
            "content_type": st.get("content_type"),
            "category": st.get("category"),
            "score": st.get("score"),
            "semantic_triggers": st.get("semantic_triggers"),
        })
    return enriched


def _editorial_trail_actual_publishes(sb, day_str: str) -> list[dict]:
    """What Cansu actually shipped that day (publishes with release_url)."""
    try:
        day_start = f"{day_str}T00:00:00+00:00"
        day_end_dt = datetime.fromisoformat(day_str) + timedelta(days=1)
        day_end = day_end_dt.strftime("%Y-%m-%dT00:00:00+00:00")
        cansu = (
            sb.table("connected_accounts")
            .select("id")
            .ilike("username", "cansu%")
            .execute()
        ).data or []
        cansu_ids = [c["id"] for c in cansu]
        if not cansu_ids:
            return []
        rows = (
            sb.table("daily_drafts")
            # C1 (2026-06-07) — surface id so the UI can deep-link into
            # /control/lifecycle/{id} from each trail card.
            .select("id, trend_id, trend_topic, platform, release_url, scheduled_at")
            .in_("account_id", cansu_ids)
            .gte("scheduled_at", day_start)
            .lt("scheduled_at", day_end)
            .not_.is_("release_url", "null")
            .execute()
        ).data or []
        seen: dict[str, dict] = {}
        for r in rows:
            tid = r.get("trend_id")
            if not tid or tid in seen:
                continue
            # Surface as draft_id (consumer-facing key) alongside the row.
            r["draft_id"] = r.get("id")
            seen[tid] = r
        return list(seen.values())
    except Exception:
        logger.exception("[editorial-trail] actual publishes fetch failed")
        return []


@router.get("/editorial-trail")
async def get_editorial_trail(
    days: int = Query(7, ge=1, le=30),
    user=Depends(require_auth),
):
    """Read-only transparency view over persisted editor's-desk judgments.

    Returns the most recent N dry_run rows enriched with per-candidate
    facts and Cansu's actual publishes for the same day. Does NOT call
    the LLM, does NOT write, does NOT affect publishing.
    """
    sb = get_supabase()
    try:
        # Phase live (06-06): the endpoint now surfaces BOTH dry-run history
        # AND live editorial picks (dry_run=false). dry_run is exposed as a
        # per-card flag so the UI can render them distinctly. Live picks are
        # what drove the actual draft; dry-run rows are historical validation.
        rows = (
            sb.table("editorial_lead_judgments")
            .select(
                "id, judgment_date, candidate_count, lead_topic, lead_trend_id, "
                "lead_source_url, passed_over_topic, passed_over_trend_id, "
                "passed_over_source_url, ranking, reason_clauses, dropped_claims, "
                "operator_sentence, model, dry_run, notes, created_at, "
                # C4 (2026-06-07) — stored archive of whether the lead
                # was actually covered / refused. Backfill in migration 014.
                "lead_outcome"
            )
            .order("judgment_date", desc=True)
            .order("created_at", desc=True)
            .limit(days * 2)   # leave headroom for multiple firings/day
            .execute()
        ).data or []
    except Exception:
        logger.exception("[editorial-trail] judgments fetch failed")
        rows = []

    cards: list[dict] = []
    for jr in rows:
        candidates = _editorial_trail_enrich_candidates(sb, jr)
        actual = _editorial_trail_actual_publishes(sb, jr["judgment_date"])
        actual_tids = {p.get("trend_id") for p in actual}
        lead_in_actual = jr.get("lead_trend_id") in actual_tids
        passed_in_actual = jr.get("passed_over_trend_id") in actual_tids
        cards.append({
            "judgment_id": jr.get("id"),
            "judgment_date": jr.get("judgment_date"),
            "candidate_count": jr.get("candidate_count"),
            "lead_topic": jr.get("lead_topic"),
            "lead_source_url": jr.get("lead_source_url"),
            "passed_over_topic": jr.get("passed_over_topic"),
            "passed_over_source_url": jr.get("passed_over_source_url"),
            "operator_sentence": jr.get("operator_sentence"),
            "reason_clauses": jr.get("reason_clauses") or [],
            "dropped_claims": jr.get("dropped_claims") or [],
            "candidates": candidates,
            "actual_publishes": actual,
            "lead_matches_actual": lead_in_actual,
            "passed_over_matches_actual": passed_in_actual,
            "model": jr.get("model"),
            "is_live": not bool(jr.get("dry_run")),       # NEW: live vs dry-run
            "dry_run": bool(jr.get("dry_run")),
            "lead_outcome": jr.get("lead_outcome"),       # C4: archive outcome
            "notes": jr.get("notes"),
            "created_at": jr.get("created_at"),
        })

    return {
        "view": "editorial-trail",
        "scope": "dry_run only — no live publishing impact",
        "days": cards,
    }


# ────────────────────────────────────────────────────────────────────────
# GET /api/hype/quality-health
#
# Operator-language health surface so Berkay catches breakage & waste
# automatically instead of by eye. Aggregates a single 24h snapshot from
# tables already used elsewhere (daily_drafts, hype_runs, tweet_feed,
# faithfulness_verdicts, editorial_lead_judgments). No new heavy
# computation; every number must answer "is something broken or wasteful?"
# ────────────────────────────────────────────────────────────────────────


_HEYGEN_USD_PER_SEC = 0.10  # mirror video_pipeline.py:1758 (Avatar V)


_DEPLOY_MANIFEST_PATH = "/opt/contentfactory/.deployed_manifest.json"


def _deploy_drift_summary() -> dict:
    """Surface the same drift signal the cron-side deploy_drift_check.py
    fires alerts on. Reads the deployed-manifest baseline (PART B
    2026-06-07) so the comparison is meaningful when prod's git tree
    is divergent from origin."""
    import hashlib
    import json as _json
    import os as _os
    import subprocess as _sp
    here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    repo_root = _os.path.dirname(here)
    backend_files = ["backend/routes/hype.py", "backend/server.py"]
    drift: list[dict] = []
    baseline = "none"
    manifest_commit = None
    manifest_deployed_at = None
    notes = (
        "Backend-only view. Cron-side hype-deploy-drift.timer covers "
        "/opt/hype-crew too."
    )

    # ── Preferred baseline: deployed manifest ──
    manifest = None
    try:
        with open(_DEPLOY_MANIFEST_PATH) as f:
            manifest = _json.load(f)
    except Exception:
        manifest = None

    if manifest:
        baseline = "deployed_manifest"
        manifest_commit = manifest.get("commit")
        manifest_deployed_at = manifest.get("deployed_at")
        critical = manifest.get("critical_md5s") or {}
        for rel in backend_files:
            full = _os.path.join(repo_root, rel)
            try:
                with open(full, "rb") as f:
                    disk = hashlib.md5(f.read()).hexdigest()
                expected = critical.get(rel)
                if expected and expected != "MISSING" and disk != expected:
                    drift.append({
                        "file": rel, "disk": disk, "expected": expected,
                        "baseline": "deployed_manifest",
                    })
            except Exception:
                pass
    else:
        # ── Legacy fallback: prod git HEAD ──
        baseline = "prod_git_head"
        for rel in backend_files:
            full = _os.path.join(repo_root, rel)
            try:
                with open(full, "rb") as f:
                    disk = hashlib.md5(f.read()).hexdigest()
                head = hashlib.md5(_sp.check_output(
                    ["git", "-C", repo_root, "show", f"HEAD:{rel}"],
                    stderr=_sp.DEVNULL, timeout=2,
                )).hexdigest()
                if disk != head:
                    drift.append({
                        "file": rel, "disk": disk, "expected": head,
                        "baseline": "prod_git_head",
                    })
            except Exception:
                pass

    try:
        head_sha = _sp.check_output(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            stderr=_sp.DEVNULL, timeout=2,
        ).decode().strip()
    except Exception:
        head_sha = "unknown"

    tone = "danger" if drift else "ok"
    if drift:
        label = f"Drift: {len(drift)} dosya geride"
    elif baseline == "deployed_manifest":
        label = (
            f"Manifest ile uyumlu (deploy={manifest_commit[:8] if manifest_commit else '?'})"
        )
    else:
        label = f"Prod git HEAD ile aynı ({head_sha[:8]})"

    return {
        "tone": tone,
        "label": label,
        "baseline": baseline,
        "git_head": head_sha,
        "manifest_commit": manifest_commit,
        "manifest_deployed_at": manifest_deployed_at,
        "drift_files": drift,
        "notes": notes,
    }

_FORMULA_PATTERNS = [
    r"bence\s+as[ıi]l\s+olay",
    r"herkes\s+(?:bunu\s+)?(?:\S+\s+){0,8}?san[ıi]yor",
    r"ço[ğg]u\s+ki[şs]i\s+(?:bunu\s+)?(?:\S+\s+){0,8}?san[ıi]yor",
    r"as[ıi]l\s+olay\s+(?:bu|şu)",
    r"kimse\s+bunu\s+konu[şs]m[ıi]yor",
    r"as[ıi]l\s+mesele",
    r"ama\s+bence\s+as[ıi]l",
    r"ço[ğg]u\s+(?:insan|ki[şs]i)\s+(?:bunu\s+)?(?:\S+\s+){0,6}?(?:san[ıi]yor|d[üu][şs][üu]n[üu]yor)",
]


def _is_formulaic_opener(content: str | None) -> bool:
    if not content:
        return False
    head = content.strip().lower()[:300]
    if not head:
        return False
    return any(re.search(p, head) for p in _FORMULA_PATTERNS)


def _tone(value: float, *, ok_max: float | None = None, warn_max: float | None = None,
          ok_min: float | None = None, warn_min: float | None = None) -> str:
    """Three-band traffic light. Pass either *_max OR *_min thresholds."""
    if ok_max is not None:
        if value <= ok_max:
            return "ok"
        if warn_max is not None and value <= warn_max:
            return "warn"
        return "danger"
    if ok_min is not None:
        if value >= ok_min:
            return "ok"
        if warn_min is not None and value >= warn_min:
            return "warn"
        return "danger"
    return "ok"


@router.get("/quality-health")
async def get_quality_health(user=Depends(require_auth)) -> dict:
    """Operator-readable health surface for /control/health.

    Returns nested under operator-language outer keys (produced, video,
    text, gate, money, supply, cron, queue) plus an `engineer` subobject
    with the raw figures. Every offending list contains draft_ids /
    run_ids the operator can click through to.
    """
    sb = get_supabase()
    from services.access_control import accessible_owner_ids
    owner_ids = accessible_owner_ids(user.id)

    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    accs = (
        sb.table("connected_accounts")
        .select("id, user_id, platform, username")
        .in_("user_id", owner_ids or ["00000000-0000-0000-0000-000000000000"])
        .execute()
    ).data or []
    account_ids = [a["id"] for a in accs if a.get("id")]

    # ─── üretim & kalite ──────────────────────────────────────────────
    drafts_24h = []
    drafts_active = []
    drafts_archived = []
    try:
        if account_ids:
            drafts_24h = (
                sb.table("daily_drafts")
                .select(
                    "id, status, platform, content, video_url, video_duration_s, "
                    "video_integrity_ok, video_integrity_reason, account_id, created_at"
                )
                .in_("account_id", account_ids)
                .gte("created_at", cutoff_24h.isoformat())
                .execute()
            ).data or []
            drafts_active = (
                sb.table("daily_drafts")
                .select("id, status, platform, content, account_id, created_at")
                .in_("account_id", account_ids)
                .in_("status", ["pending", "pending_review"])
                .execute()
            ).data or []
            drafts_archived = (
                sb.table("daily_drafts")
                .select("id, deleted_reason, account_id, deleted_at")
                .in_("account_id", account_ids)
                .eq("status", "archived_quality_sweep")
                .gte("deleted_at", cutoff_7d.isoformat())
                .execute()
            ).data or []
    except Exception as e:
        logger.warning(f"quality-health: drafts read failed: {e}")

    produced_24h = len(drafts_24h)
    published_24h = sum(1 for d in drafts_24h if d.get("status") == "published")
    stuck_pending = sum(
        1 for d in drafts_24h
        if d.get("status") in ("pending", "pending_review")
    )

    video_drafts = [
        d for d in drafts_24h
        if d.get("video_url") and d.get("video_integrity_ok") is not None
    ]
    video_total = len(video_drafts)
    video_pass = sum(1 for d in video_drafts if d.get("video_integrity_ok") is True)
    video_fail_list = [
        {
            "draft_id": d["id"],
            "platform": d.get("platform"),
            "actual_s": float(d.get("video_duration_s") or 0),
            "reason": d.get("video_integrity_reason"),
        }
        for d in video_drafts if d.get("video_integrity_ok") is False
    ]
    video_pass_pct = (video_pass / video_total * 100.0) if video_total else 100.0

    formulaic_list = [
        {"draft_id": d["id"], "platform": d.get("platform"), "opener": (d.get("content") or "")[:120]}
        for d in drafts_24h if _is_formulaic_opener(d.get("content"))
    ]
    formulaic_count = len(formulaic_list)
    formulaic_pct = (formulaic_count / produced_24h * 100.0) if produced_24h else 0.0

    # ─── faithfulness gate counts (24h) ───────────────────────────────
    gate_pass = gate_block = gate_error = 0
    try:
        if account_ids:
            verdicts = (
                sb.table("faithfulness_verdicts")
                .select("verdict, final_action, created_at, draft_id")
                .gte("created_at", cutoff_24h.isoformat())
                .execute()
            ).data or []
            for v in verdicts:
                fa = (v.get("final_action") or "").lower()
                ver = (v.get("verdict") or "").lower()
                if fa == "error" or ver == "error":
                    gate_error += 1
                elif fa == "block" or ver == "fail":
                    gate_block += 1
                elif fa in ("pass", "publish") or ver == "pass":
                    gate_pass += 1
    except Exception as e:
        logger.warning(f"quality-health: verdicts read failed: {e}")

    # ─── money ────────────────────────────────────────────────────────
    heygen_today_usd = sum(
        float(d.get("video_duration_s") or 0) * _HEYGEN_USD_PER_SEC
        for d in video_drafts
    )
    heygen_wasted_usd = sum(
        float(d.get("video_duration_s") or 0) * _HEYGEN_USD_PER_SEC
        for d in video_drafts if d.get("video_integrity_ok") is False
    )

    runs_24h = []
    failed_runs = []
    try:
        if account_ids:
            runs_24h = (
                sb.table("hype_runs")
                .select("id, status, total_cost_usd, started_at, error, account_id")
                .in_("account_id", account_ids)
                .gte("started_at", cutoff_24h.isoformat())
                .execute()
            ).data or []
            failed_runs = [
                {
                    "run_id": r["id"],
                    "account_id": r.get("account_id"),
                    "error": (r.get("error") or "")[:240],
                    "started_at": r.get("started_at"),
                }
                for r in runs_24h
                if (r.get("status") in ("failed", "error")) or r.get("error")
            ]
    except Exception as e:
        logger.warning(f"quality-health: hype_runs read failed: {e}")

    runs_total_cost = sum(float(r.get("total_cost_usd") or 0) for r in runs_24h)
    cost_per_published = (
        (runs_total_cost + heygen_today_usd) / published_24h
        if published_24h else None
    )

    # ─── pipeline canlı mı: supply, cron, editor ──────────────────────
    supply_batches = {"ai_core": 0, "ai_news_tr": 0}
    try:
        feed_rows = (
            sb.table("tweet_feed")
            .select("batch_type, tweet_created_at")
            .gte("tweet_created_at", cutoff_24h.isoformat())
            .in_("batch_type", list(supply_batches.keys()))
            .execute()
        ).data or []
        for r in feed_rows:
            b = r.get("batch_type")
            if b in supply_batches:
                supply_batches[b] += 1
    except Exception as e:
        logger.warning(f"quality-health: tweet_feed read failed: {e}")

    supply_gap = [b for b, n in supply_batches.items() if n == 0]

    editor_24h = 0
    editor_early_exit = 0
    try:
        if account_ids:
            judg = (
                sb.table("editorial_lead_judgments")
                .select("id, lead_outcome, created_at, account_id")
                .in_("account_id", account_ids)
                .gte("created_at", cutoff_24h.isoformat())
                .execute()
            ).data or []
            editor_24h = len(judg)
            editor_early_exit = sum(
                1 for j in judg
                if (j.get("lead_outcome") or "").lower() in ("no_publish", "early_exit", "rejected")
            )
    except Exception as e:
        logger.warning(f"quality-health: editorial_lead_judgments read failed: {e}")

    # ─── queue ─────────────────────────────────────────────────────────
    active_count = len(drafts_active)
    archived_by_reason: dict[str, int] = {}
    for d in drafts_archived:
        reason = (d.get("deleted_reason") or "unknown")
        head = reason.split(":", 1)[-1].strip()
        primary = head.split(",")[0] if head else "unknown"
        archived_by_reason[primary] = archived_by_reason.get(primary, 0) + 1

    stale_active = 0
    try:
        cutoff_3d = now - timedelta(days=3)
        for d in drafts_active:
            c_at = d.get("created_at") or ""
            if not c_at:
                continue
            dt = datetime.fromisoformat(c_at.replace("Z", "+00:00"))
            if dt < cutoff_3d:
                stale_active += 1
    except Exception:
        pass

    # ─── thresholds + tones ────────────────────────────────────────────
    video_tone = _tone(video_pass_pct, ok_min=90, warn_min=75)
    formulaic_tone = _tone(formulaic_pct, ok_max=2.0, warn_max=10.0)
    gate_tone = "danger" if gate_error > 0 else ("warn" if gate_block > gate_pass else "ok")
    money_waste_tone = _tone(heygen_wasted_usd, ok_max=1.0, warn_max=5.0)
    supply_tone = "danger" if supply_gap else ("warn" if any(n < 5 for n in supply_batches.values()) else "ok")
    cron_tone = "danger" if len(failed_runs) > 0 else "ok"
    queue_tone = _tone(stale_active, ok_max=2, warn_max=10)
    produced_tone = _tone(produced_24h, ok_min=3, warn_min=1)

    return {
        "generated_at": now.isoformat(),
        "window_hours": 24,
        "account_count": len(account_ids),

        # ── Operator-language outer keys ──
        "produced": {
            "tone": produced_tone,
            "label": f"Bugün {produced_24h} taslak üretildi",
            "produced_24h": produced_24h,
            "published_24h": published_24h,
            "stuck_pending": stuck_pending,
        },
        "video": {
            "tone": video_tone,
            "label": (
                f"{video_pass}/{video_total} tam"
                + (f", {len(video_fail_list)} kesik" if video_fail_list else "")
                if video_total else "Bugün video üretilmedi"
            ),
            "pass_pct": round(video_pass_pct, 1),
            "pass_count": video_pass,
            "fail_count": len(video_fail_list),
            "total": video_total,
            "fail_list": video_fail_list[:20],
        },
        "text": {
            "tone": formulaic_tone,
            "label": (
                f"%{formulaic_pct:.0f} formülaik açılış"
                if produced_24h else "Bugün metin üretilmedi"
            ),
            "formulaic_pct": round(formulaic_pct, 1),
            "formulaic_count": formulaic_count,
            "produced_24h": produced_24h,
            "flagged_list": formulaic_list[:20],
        },
        "gate": {
            "tone": gate_tone,
            "label": (
                f"{gate_block} engellendi, {gate_error} hata"
                if (gate_block or gate_error) else f"{gate_pass} kontrol, hata yok"
            ),
            "pass": gate_pass,
            "block": gate_block,
            "error": gate_error,
        },
        "money": {
            "tone": money_waste_tone,
            "label": (
                f"Bugün ${heygen_today_usd:.2f} HeyGen"
                + (f", ${heygen_wasted_usd:.2f} israf" if heygen_wasted_usd > 0 else "")
            ),
            "heygen_today_usd": round(heygen_today_usd, 4),
            "heygen_wasted_usd": round(heygen_wasted_usd, 4),
            "pipeline_usd": round(runs_total_cost, 4),
            "cost_per_published_usd": (
                round(cost_per_published, 4) if cost_per_published is not None else None
            ),
        },
        "supply": {
            "tone": supply_tone,
            "label": (
                "Tedarik boş: " + ", ".join(supply_gap)
                if supply_gap else
                "Tedarik OK: " + ", ".join(f"{b}={n}" for b, n in supply_batches.items())
            ),
            "batches_24h": supply_batches,
            "supply_gap": supply_gap,
        },
        "cron": {
            "tone": cron_tone,
            "label": (
                f"{len(failed_runs)} başarısız run"
                if failed_runs else f"{len(runs_24h)} run, hata yok"
            ),
            "runs_24h": len(runs_24h),
            "failed_count": len(failed_runs),
            "failed_list": failed_runs[:10],
            "editor_24h": editor_24h,
            "editor_early_exit": editor_early_exit,
        },
        "queue": {
            "tone": queue_tone,
            "label": (
                f"{active_count} onay-bekliyor, {len(drafts_archived)} arşiv"
            ),
            "active_publishable": active_count,
            "archived_7d": len(drafts_archived),
            "archived_by_reason": archived_by_reason,
            "stale_buildup": stale_active,
        },

        # ── Deploy drift surface ──
        "deploy": _deploy_drift_summary(),

        # ── Engineer drawer: raw figures ──
        "engineer": {
            "owner_ids": owner_ids,
            "account_ids": account_ids,
            "cutoffs": {
                "24h_iso": cutoff_24h.isoformat(),
                "7d_iso": cutoff_7d.isoformat(),
            },
            "heygen_usd_per_sec": _HEYGEN_USD_PER_SEC,
            "thresholds": {
                "video_pass_pct_min": 90,
                "formulaic_pct_max": 10,
                "gate_error_max": 0,
                "heygen_waste_usd_max": 5.0,
                "produced_min": 1,
                "stale_active_max": 10,
            },
            "raw": {
                "drafts_24h_count": len(drafts_24h),
                "video_drafts_24h": video_total,
                "verdicts_counts": {"pass": gate_pass, "block": gate_block, "error": gate_error},
                "runs_24h": len(runs_24h),
                "failed_runs": len(failed_runs),
            },
        },
    }


# ────────────────────────────────────────────────────────────────────────
# Threshold breach check — shared with scripts/check_quality_thresholds.py
# ────────────────────────────────────────────────────────────────────────


def evaluate_quality_thresholds(payload: dict) -> list[dict]:
    """Pure: given the /quality-health payload, return a list of breaches.

    Each breach is {key, severity, summary, metric, value, threshold}.
    Severity is CRITICAL for: gate error > 0, any failed cron run, zero
    drafts in 24h, supply batch at 0. WARN for video pass < 90 %,
    formulaic > 10 %, HeyGen waste > $5.
    """
    breaches: list[dict] = []

    video = payload.get("video", {})
    if video.get("total", 0) > 0 and (video.get("pass_pct") or 0) < 90:
        breaches.append({
            "key": "video_pass_pct_below_90",
            "severity": "WARN",
            "summary": (
                f"Video integrity {video['pass_pct']}% < 90% — "
                f"{video['fail_count']}/{video['total']} kesik"
            ),
            "metric": "video.pass_pct",
            "value": video.get("pass_pct"),
            "threshold": 90,
        })

    text = payload.get("text", {})
    if text.get("produced_24h", 0) > 0 and (text.get("formulaic_pct") or 0) > 10:
        breaches.append({
            "key": "formulaic_rate_above_10",
            "severity": "WARN",
            "summary": (
                f"Formülaik açılış oranı %{text['formulaic_pct']} > %10 — "
                f"{text['formulaic_count']}/{text['produced_24h']} metin"
            ),
            "metric": "text.formulaic_pct",
            "value": text.get("formulaic_pct"),
            "threshold": 10,
        })

    gate = payload.get("gate", {})
    if (gate.get("error") or 0) > 0:
        breaches.append({
            "key": "gate_error_above_0",
            "severity": "CRITICAL",
            "summary": f"Gate ERROR x{gate['error']} — faithfulness pipeline patladı",
            "metric": "gate.error",
            "value": gate.get("error"),
            "threshold": 0,
        })

    cron = payload.get("cron", {})
    if (cron.get("failed_count") or 0) > 0:
        first_err = (cron.get("failed_list") or [{}])[0].get("error", "")[:120]
        breaches.append({
            "key": "any_failed_cron",
            "severity": "CRITICAL",
            "summary": f"{cron['failed_count']} cron run failed — \"{first_err}\"",
            "metric": "cron.failed_count",
            "value": cron.get("failed_count"),
            "threshold": 0,
        })

    money = payload.get("money", {})
    if (money.get("heygen_wasted_usd") or 0) > 5:
        breaches.append({
            "key": "heygen_waste_above_5usd",
            "severity": "WARN",
            "summary": (
                f"HeyGen israfı ${money['heygen_wasted_usd']:.2f} > $5 — "
                "kesik videolara harcanan para"
            ),
            "metric": "money.heygen_wasted_usd",
            "value": money.get("heygen_wasted_usd"),
            "threshold": 5,
        })

    produced = payload.get("produced", {})
    if (produced.get("produced_24h") or 0) == 0:
        breaches.append({
            "key": "zero_drafts_24h",
            "severity": "CRITICAL",
            "summary": "Son 24 saatte hiç taslak üretilmedi — pipeline durmuş olabilir",
            "metric": "produced.produced_24h",
            "value": 0,
            "threshold": 1,
        })

    supply = payload.get("supply", {})
    for batch in (supply.get("supply_gap") or []):
        breaches.append({
            "key": f"supply_batch_zero_{batch}",
            "severity": "CRITICAL",
            "summary": f"Tedarik batch '{batch}' son 24 saatte 0 — sebep boş kuyruk olabilir",
            "metric": f"supply.batches_24h.{batch}",
            "value": 0,
            "threshold": 1,
        })

    return breaches


@router.get("/quality-health/breaches")
async def get_quality_health_breaches(user=Depends(require_auth)) -> dict:
    """Returns the same breach list the alerter timer evaluates."""
    payload = await get_quality_health(user)  # type: ignore[arg-type]
    return {
        "generated_at": payload["generated_at"],
        "breaches": evaluate_quality_thresholds(payload),
    }


# ─── Sistem Sağlığı + Huni paneli (/control/sistem) ──────────────────────────
# "Sistem çalışıyor mu, nerede tıkandı" tek bakışta. Supply → huni → son-run →
# cron. Çoğunlukla mevcut veriyi OKUR (huni dökümü flow_state.gate_breakdown'da
# zaten hesaplı); cron sağlığı systemd yerine DB-zamanlarından TÜRETİLİR.

# Supply eşikleri — run_supply_health_check.py:43-48 ile AYNI env'ler (tek kaynak).
def _supply_thresholds() -> tuple[dict[str, int], int]:
    import os
    return (
        {
            "ai_core":    int(os.environ.get("SUPPLY_HEALTH_MIN_TWEETS_AI_CORE", "8")),
            "ai_news_en": int(os.environ.get("SUPPLY_HEALTH_MIN_TWEETS_AI_NEWS_EN", "5")),
            "ai_news_tr": int(os.environ.get("SUPPLY_HEALTH_MIN_TWEETS_AI_NEWS_TR", "5")),
        },
        int(os.environ.get("SUPPLY_HEALTH_MIN_DISTINCT_ACCOUNTS", "3")),
    )

# query_trends (supabase_tools.py) ile aynı kategori dışlaması.
_FUNNEL_EXCLUDED_CATS = {"Politics", "Entertainment"}

# bottleneck anahtarı → operatör-dili (jargonsuz) mesaj. /control/health özeti de bunu kullanır.
_BOTTLENECK_MESSAGES = {
    "supply":        "Tedarik tıkandı: yeni tweet az veya yok",
    "fetch":         "Trend çekme durdu: son 48 saatte yeni trend gelmedi",
    "trend_quality": "Gelen trendler eşiği geçemiyor (skor/kategori)",
    "dedup":         "Yeni içerik yok: adaylar son 7 günde zaten işlendi",
    "ai_reject":     "Adaylar AI-dışı bulunup elendi",
}


def _age_minutes(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 60
    except Exception:
        return None


@router.get("/funnel-health")
async def funnel_health(user=Depends(require_auth)) -> dict:
    """Sistem Sağlığı + Huni — /control/sistem paneli (+ /control/health özeti).

    Bloklar: supply (tweet_feed 24h) · funnel (trends + son run gate_breakdown) ·
    last_run · fetch (trends tazeliği + trend_fetch_runs) · cron (DB-türetilmiş) ·
    bottleneck (tek bakışta "nerede tıkandı"). Her blok fail-open — biri patlarsa
    panel komple ölmez (şeffaflık aracı asla sessizce boş düşmez)."""
    import json
    sb = get_supabase()
    from services.access_control import accessible_owner_ids

    now = datetime.now(timezone.utc)
    owner_ids = accessible_owner_ids(user.id)
    if not owner_ids:
        return {"supply": {}, "funnel": {}, "last_run": None, "fetch": {},
                "cron": {}, "bottleneck": None, "bottleneck_message": None,
                "checked_at": now.isoformat()}

    accs = (
        sb.table("connected_accounts").select("id, user_id, platform")
        .in_("user_id", owner_ids).execute()
    ).data or []
    account_ids = [a["id"] for a in accs if a.get("id")]

    # ── supply (workspace-genel besleme; owner-scope YOK) ──────────────
    supply: dict[str, dict] = {}
    try:
        thresholds, min_accounts = _supply_thresholds()
        since_24h = (now - timedelta(hours=24)).isoformat()
        tf_rows = (
            sb.table("tweet_feed").select("batch_type, username, tweet_created_at")
            .in_("batch_type", list(thresholds.keys()))
            .gt("tweet_created_at", since_24h).limit(5000).execute()
        ).data or []
        for bt, thr in thresholds.items():
            rows = [r for r in tf_rows if r.get("batch_type") == bt]
            tweets = len(rows)
            accounts = len({(r.get("username") or "").lower() for r in rows if r.get("username")})
            supply[bt] = {
                "tweets": tweets, "accounts": accounts,
                "threshold": thr, "min_accounts": min_accounts,
                "tone": "ok" if (tweets >= thr and accounts >= min_accounts) else "danger",
            }
    except Exception as e:
        logger.warning(f"funnel-health: supply block failed: {e}")

    # ── funnel üst-aşamalar (trends son 48h) ───────────────────────────
    trends_48h = score_ok = visible = 0
    last_trend_at: Optional[str] = None
    new_trends_4h = 0
    try:
        since_48h = (now - timedelta(hours=48)).isoformat()
        since_4h = (now - timedelta(hours=4)).isoformat()
        tr_rows = (
            sb.table("trends").select("score, is_visible, is_archived, category, created_at")
            .gt("created_at", since_48h).limit(2000).execute()
        ).data or []
        trends_48h = len(tr_rows)
        for r in tr_rows:
            sc = r.get("score") or 0
            ca = r.get("created_at")
            if ca and (last_trend_at is None or ca > last_trend_at):
                last_trend_at = ca
            if ca and ca > since_4h:
                new_trends_4h += 1
            if sc >= 75:
                score_ok += 1
                if r.get("is_visible") and not r.get("is_archived") \
                        and (r.get("category") or "") not in _FUNNEL_EXCLUDED_CATS:
                    visible += 1
    except Exception as e:
        logger.warning(f"funnel-health: trends block failed: {e}")

    # ── son hype_run + gate_breakdown ──────────────────────────────────
    last_run = None
    gate_breakdown: dict = {}
    try:
        if account_ids:
            lr = (
                sb.table("hype_runs").select("started_at, status, trend_id, flow_state")
                .in_("account_id", account_ids).order("started_at", desc=True)
                .limit(1).execute()
            ).data or []
            if lr:
                r = lr[0]
                fs = r.get("flow_state") or {}
                if isinstance(fs, str):
                    try:
                        fs = json.loads(fs)
                    except Exception:
                        fs = {}
                gate_breakdown = (fs.get("gate_breakdown") if isinstance(fs, dict) else {}) or {}
                status = (r.get("status") or "").lower()
                produced = status == "completed" and bool(r.get("trend_id"))
                started = r.get("started_at")
                last_run = {
                    "started_at": started,
                    "rel": _format_relative(started) if started else None,
                    "status": status,
                    "reason": gate_breakdown.get("reason"),
                    "gate_breakdown": gate_breakdown,
                    "produced": produced,
                    "tone": "ok" if produced else ("warn" if status in ("skipped", "completed") else "danger"),
                }
    except Exception as e:
        logger.warning(f"funnel-health: last_run block failed: {e}")

    funnel = {
        "trends_48h": trends_48h,
        "score_ok": score_ok,
        "visible": visible,
        "last_run_gate": gate_breakdown,
    }

    # ── fetch (trend_fetch_runs son tetik durumu) ──────────────────────
    fetch_run = None
    try:
        fr = (
            sb.table("trend_fetch_runs").select(
                "status, twitter_items, trends_saved, error, started_at, finished_at, triggered_by")
            .order("started_at", desc=True).limit(1).execute()
        ).data or []
        if fr:
            row = fr[0]
            st = row.get("status")
            started = row.get("started_at")
            # running'de >10dk → süreç ölmüş olabilir, "takıldı" göster (yalancı "çalışıyor" olmaz)
            if st == "running":
                age = _age_minutes(started)
                if age is not None and age > 10:
                    st = "stuck"
            fetch_run = {
                "status": st,
                "twitter_items": row.get("twitter_items"),
                "trends_saved": row.get("trends_saved"),
                "error": row.get("error"),
                "started_at": started,
                "rel": _format_relative(started) if started else None,
                "triggered_by": row.get("triggered_by"),
            }
    except Exception as e:
        # Tablo henüz yoksa (migration öncesi) sessizce geç.
        logger.warning(f"funnel-health: trend_fetch_runs read failed: {e}")

    fetch = {
        "last_trend_at": last_trend_at,
        "last_trend_rel": _format_relative(last_trend_at) if last_trend_at else None,
        "new_trends_4h": new_trends_4h,
        "run": fetch_run,
    }

    # ── cron sağlığı (DB-türetilmiş; systemctl YOK) ────────────────────
    cron = {}
    try:
        tf_last = (
            sb.table("tweet_feed").select("collected_at")
            .order("collected_at", desc=True).limit(1).execute()
        ).data or []
        last_tweet_feed = tf_last[0]["collected_at"] if tf_last else None

        def _cron_entry(iso, stale_min):
            age = _age_minutes(iso)
            return {"at": iso, "rel": _format_relative(iso) if iso else None,
                    "stale": (age is None or age > stale_min)}

        cron = {
            "last_hype_run":   _cron_entry(last_run["started_at"] if last_run else None, 90),
            "last_tweet_feed": _cron_entry(last_tweet_feed, 90),
            "last_trend":      _cron_entry(last_trend_at, 300),
        }
        cron["tone"] = "danger" if any(
            cron[k]["stale"] for k in ("last_hype_run", "last_tweet_feed", "last_trend")
        ) else "ok"
    except Exception as e:
        logger.warning(f"funnel-health: cron block failed: {e}")

    # ── bottleneck (panelin kalbi — tek alan "nerede tıkandı" der) ─────
    supply_danger = any(s.get("tone") == "danger" for s in supply.values())
    passed = gate_breakdown.get("passed")
    dedup = gate_breakdown.get("dedup") or 0
    ai_reject = gate_breakdown.get("ai_reject") or 0
    if supply_danger:
        bottleneck = "supply"
    elif trends_48h == 0:
        bottleneck = "fetch"
    elif visible == 0:
        bottleneck = "trend_quality"
    elif passed == 0 and dedup > 0:
        bottleneck = "dedup"
    elif passed == 0 and ai_reject > 0:
        bottleneck = "ai_reject"
    else:
        bottleneck = None

    return {
        "supply": supply,
        "funnel": funnel,
        "last_run": last_run,
        "fetch": fetch,
        "cron": cron,
        "bottleneck": bottleneck,
        "bottleneck_message": _BOTTLENECK_MESSAGES.get(bottleneck) if bottleneck else None,
        "checked_at": now.isoformat(),
    }


async def _run_manual_trend_fetch(fetch_run_id: str):
    """Arka-plan: refresh_all() koş + trend_fetch_runs satırını done/failed yap.
    try/finally — görev ASLA satırı 'running' bırakıp ölmesin (panel güvenilirliği)."""
    import os
    sb = get_supabase()
    twitter_items = trends_saved = None
    status = "done"
    err: Optional[str] = None
    try:
        # Faz 4 — flag ON ise LangGraph kabuğu (checkpoint+resume), OFF ise eski yol birebir.
        _use_lg = os.environ.get("TREND_INGEST_LANGGRAPH_ENABLED", "").lower() in ("1", "true", "yes", "on")
        if _use_lg:
            from lg.ingest_graph import run_or_resume_ingest
            result = await run_or_resume_ingest(fetch_run_id, triggered_by="manual")
        else:
            from services.trend_engine import trend_engine
            # NOT: prod refresh_all() argümansız (cron _run_trend_refresh ile aynı yol).
            result = await trend_engine.refresh_all()
        twitter_items = result.get("twitter_items")
        trends_saved = result.get("trends_saved")
        if not result.get("success", True):
            status = "failed"
            err = str(result.get("error") or "refresh_all success=False")[:500]
    except Exception as e:
        status = "failed"
        err = str(e)[:500]
        logger.error(f"manual trend fetch failed: {e}")
    finally:
        # Secret sızdırma — service-key'i hata metninden temizle (trends.py deseni).
        if err:
            svc = os.environ.get("SUPABASE_SERVICE_KEY", "")
            if svc and len(svc) > 8:
                err = err.replace(svc, "***")
        upd: dict = {"status": status, "finished_at": datetime.now(timezone.utc).isoformat()}
        if twitter_items is not None:
            upd["twitter_items"] = twitter_items
        if trends_saved is not None:
            upd["trends_saved"] = trends_saved
        if err is not None:
            upd["error"] = err
        try:
            sb.table("trend_fetch_runs").update(upd).eq("id", fetch_run_id).execute()
        except Exception as e2:
            logger.error(f"manual trend fetch: status update failed: {e2}")


@router.post("/trend-fetch/trigger")
async def trigger_trend_fetch(background_tasks: BackgroundTasks, user=Depends(require_auth)) -> dict:
    """"Şimdi trend çek" — kuraklıkta manuel trend-fetch tetikler. %100 kanıtlanabilir:
    fire-and-forget DEĞİL; trend_fetch_runs'a running satırı yazar, arka-plan görevi
    done/failed yapar, panel sonucu gösterir. CRON_SECRET frontend'e GİTMEZ (user-auth)."""
    sb = get_supabase()
    from services.access_control import accessible_owner_ids
    if not accessible_owner_ids(user.id):
        raise HTTPException(status_code=403, detail="no_workspace")

    # DB-temelli kilit + rate-limit (tek sorgu): son 5 dk'da bir tetik var mı?
    #  - running  → 409 "zaten çalışıyor" (>10dk running ise pencerede değil → takılmış sayılır, engellemez)
    #  - bitmiş   → 429 "çok sık" (maliyet koruması; refresh_all GPT+XQuik çağırır)
    try:
        five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        recent = (
            sb.table("trend_fetch_runs").select("status, started_at")
            .gt("started_at", five_min_ago).order("started_at", desc=True)
            .limit(1).execute()
        ).data or []
        if recent:
            if recent[0].get("status") == "running":
                raise HTTPException(status_code=409, detail="Trend taraması zaten çalışıyor")
            raise HTTPException(status_code=429, detail="Çok sık tetik — son taramadan 5 dakika geçmeli")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"trend-fetch trigger: lock check failed (devam ediliyor): {e}")

    # running satırı yarat (arka-plan görevi bunu done/failed'a çevirecek).
    try:
        ins = (
            sb.table("trend_fetch_runs")
            .insert({"triggered_by": f"manual:{user.id}", "status": "running"})
            .execute()
        )
        fetch_run_id = (ins.data or [{}])[0].get("id")
    except Exception as e:
        logger.error(f"trend-fetch trigger: insert running row failed: {e}")
        raise HTTPException(status_code=500, detail="Tetik kaydı oluşturulamadı")

    background_tasks.add_task(_run_manual_trend_fetch, fetch_run_id)
    return {"status": "started", "fetch_run_id": fetch_run_id,
            "message": "Trend taraması başlatıldı"}
