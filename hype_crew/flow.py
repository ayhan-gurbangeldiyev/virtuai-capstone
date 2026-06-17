"""AutonomousContentFlow — orchestrates one autonomous content run end-to-end.

Lifecycle per kickoff (one account, one trend → one draft):
  1. @start             load account config, init hype_runs row
  2. @listen(initialize) run the 5-agent crew
  3. @router            quality check
       → "skip"         compliance rejected → finalize as rejected
       → "dry_run_log"  HYPE_DRY_RUN=true → log only
       → "publish"      live mode → write daily_drafts, postiz already scheduled by Publisher
  4. @listen(...)       each branch finalizes hype_runs

NOTE: Human approval is OUT of this Flow. After "publish" branch, draft sits
in daily_drafts (status='auto_scheduled') awaiting user action via TypeHype UI.
The backend `/api/hype/drafts/*` endpoints handle approve/reject/edit.
"""
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from crewai.flow.flow import Flow, listen, start, router
from loguru import logger
from pydantic import BaseModel, Field

from config import settings
from crew_factory import build_content_crew
from callbacks import init_run, log_stage, finalize_run
from schemas import (
    TrendScoutOutput, PlannerOutput, WriterOutput,
    ComplianceOutput, PublisherOutput,
)
from schemas.visual import VisualDirectorOutput
from tools import load_account_config
from tools.supabase_client import make_supabase
# Phase 23 video pipeline imports are OPTIONAL — production deploys (Hetzner)
# may run without tools/video_pipeline.py present. Anything that needs the
# video pipeline is gated behind persona.video_enabled, which stays False in
# production until the video pipeline is finalised + deployed.
try:
    from tools.video_pipeline import StoredVideoAsset  # type: ignore
except ModuleNotFoundError:
    StoredVideoAsset = None  # type: ignore[assignment,misc]
# PostizClient is imported lazily inside publish_to_drafts (Phase 20 multi-platform path)


# ────────────────────────────────────────────────────────────────────────────
# Phase 22 — Platform metadata + hashtag enforcement (deterministic post-process)
# ────────────────────────────────────────────────────────────────────────────

# 2026-06-08 — Berkay direct order: NO AI disclosure, NO hashtags, NO emoji.
# Phase 33 had already disabled disclosure; the brief intermediate manifest
# restoration was reversed. Cansu reads as a normal human creator — no
# "#AIcreated", no "— Cansu, AI persona ✨", no machine-tag of any kind.
# Hashtags and emojis are stripped from writer output by the sanitize pass.
_DISCLOSURE_RULES: dict[str, tuple[str, str]] = {}


# 2026-06-10 — voice tek-kaynak modülü: directive + lugatlar + sanitize
# zinciri tools/cansu_voice.py'a taşındı (backend approve onarım döngüsü
# de aynı modülü import eder; crewai bağımlılığı yok).
from tools.cansu_voice import (  # noqa: E402
    _LUGAT_PLACEHOLDER,
    _lugat_for_platform,
    build_cansu_directive,
    _sanitize_em_dash,
    _strip_all_hashtags,
    _strip_emojis,
    _strip_persona_disclosure,
    _enforce_platform_length,
    assemble_source_text,
)

# Per-platform tweet/post hashtag max counts.
_HASHTAG_MAX: dict[str, int] = {
    "twitter": 2,
    "x": 2,
    "linkedin": 5,
    "instagram": 10,
}

# Per-platform hard char cap (for trimming if disclosure inflates beyond limit).
_HARD_CHAR_CAP: dict[str, int] = {
    "twitter": 280,
    "x": 280,
    # LinkedIn 3000 max, IG caption 2200 max, devto unlimited — only X is tight.
}

def _apply_platform_metadata(content: str, platform: str) -> str:
    """Append/prepend mandatory AI disclosure for the given platform.

    Idempotent: if the disclosure snippet is already present, the content is
    returned untouched. For X/Twitter, if appending would exceed 280 chars,
    we trim trailing whitespace + ellipsize the original content first.
    """
    plat = platform.lower()
    rule = _DISCLOSURE_RULES.get(plat)
    if not rule:
        return content
    snippet, placement = rule

    # Idempotency: only normalize whitespace for comparison
    if snippet.strip().lower() in content.lower():
        return content

    if placement == "suffix":
        if plat in ("twitter", "x"):
            # X hard cap: 280 chars. Reserve space for " " + snippet.
            cap = _HARD_CHAR_CAP[plat]
            reserve = len(snippet) + 1  # " " separator
            if len(content) + reserve > cap:
                # Trim original content to fit; prefer word boundary
                target = cap - reserve
                trimmed = content[:target].rstrip()
                # Back off to last whitespace if we cut mid-word
                if " " in trimmed:
                    trimmed = trimmed.rsplit(" ", 1)[0].rstrip(",.;:!?-")
                content = trimmed
            return f"{content.rstrip()} {snippet}"
        return f"{content.rstrip()}{snippet}" if snippet.startswith(("\n", "—", " ", "-")) else f"{content.rstrip()} {snippet}"

    if placement == "prefix":
        return f"{snippet}\n\n{content.lstrip()}"

    if placement == "footer_block":
        return f"{content.rstrip()}\n\n{snippet}"

    return content


def _enforce_hashtag_count(content: str, platform: str) -> str:
    """Strip excess hashtags beyond per-platform cap. Preserves mandatory
    disclosure hashtag (#AIcreated). Hashtags are matched as ``#word`` runs.

    If the count is within limit, content is returned untouched.
    Order: keeps the FIRST N hashtags that appear in the text; trailing
    hashtags beyond the cap are removed in place.
    """
    plat = platform.lower()
    cap = _HASHTAG_MAX.get(plat)
    if cap is None:
        return content

    hashtag_re = re.compile(r"#\w+")
    matches = list(hashtag_re.finditer(content))
    if not matches:
        return content

    # 2026-06-08 (restored): #AIcreated is mandatory on twitter/x per brand
    # manifest. Keep it OUT of the per-platform cap (it's disclosure, not
    # organic), so cap=2 still gives the writer room for 2 real hashtags.
    # On LinkedIn the manifest explicitly forbids #AIcreated — strip it.
    # Other AI-disclosure-style hashtags (#AIgenerated, #AIpersona) are
    # writer noise; drop them everywhere except the platforms that name
    # them as mandatory (currently only #AIcreated on twitter/x).
    mandatory_for_plat = {"twitter": "#aicreated", "x": "#aicreated"}.get(plat)
    keep_spans: list[tuple[int, int]] = []
    drop_spans: list[tuple[int, int]] = []
    organic_kept = 0
    for m in matches:
        tag = m.group(0).lower()
        if tag == mandatory_for_plat:
            # Mandatory disclosure hashtag — always keep, never counts toward cap
            keep_spans.append((m.start(), m.end()))
            continue
        if tag in {"#aicreated", "#aigenerated", "#aipersona"}:
            # AI-disclosure hashtag on a platform that doesn't mandate it
            # (e.g. LinkedIn). Strip per brand manifest "linkedin: no #AIcreated".
            drop_spans.append((m.start(), m.end()))
            continue
        if organic_kept < cap:
            keep_spans.append((m.start(), m.end()))
            organic_kept += 1
        else:
            drop_spans.append((m.start(), m.end()))

    if not drop_spans:
        return content

    # Drop excess hashtags by rebuilding content (preserve everything not in drop_spans)
    result_parts: list[str] = []
    cursor = 0
    for start, end in drop_spans:
        result_parts.append(content[cursor:start])
        cursor = end
    result_parts.append(content[cursor:])
    rebuilt = "".join(result_parts)
    # Collapse double whitespace introduced by stripped hashtags
    rebuilt = re.sub(r"[ \t]{2,}", " ", rebuilt)
    rebuilt = re.sub(r"\n{3,}", "\n\n", rebuilt)
    return rebuilt.rstrip()


# ────────────────────────────────────────────────────────────────────────────


# Phase 40 (Berkay 1 Haz 2026) — the same 9:16 vertical video produced by
# heygen_split_screen pipeline is reused across YouTube (Shorts), Instagram
# (Reels), and LinkedIn (vertical video post). Previously only `youtube` got
# the video_url, leaving IG + LinkedIn drafts as text+image even on major
# launches where a video was generated.
_VIDEO_PLATFORMS = {"youtube", "youtube-shorts", "instagram", "instagram-reels", "linkedin", "tiktok"}


class VideoOutput(BaseModel):
    """Serializable wrapper around StoredVideoAsset for Flow state + DB log."""
    pipeline_used: str
    video_url: str
    thumbnail_url: str
    duration_sec: float
    file_size_bytes: int
    cost_usd: float
    generation_latency_ms: int
    target_platform: str  # which platform target drove this video (youtube / reels / ...)

    @classmethod
    def from_asset(cls, asset: "StoredVideoAsset", *, target_platform: str) -> "VideoOutput":
        return cls(
            pipeline_used=asset.pipeline_used,
            video_url=asset.video_url,
            thumbnail_url=asset.thumbnail_url,
            duration_sec=asset.duration_sec,
            file_size_bytes=asset.file_size_bytes,
            cost_usd=asset.cost_usd,
            generation_latency_ms=asset.generation_latency_ms,
            target_platform=target_platform,
        )


class PlatformDraft(BaseModel):
    """One platform variant of a content thread (Phase 20)."""
    platform: str                       # 'twitter' | 'linkedin' | 'devto' | 'instagram' | 'youtube'
    integration_id: str                 # Postiz integration to schedule with
    account_id: str                     # connected_accounts row id for this platform
    content: str                        # generated text body
    title: Optional[str] = None         # devto/medium articles need a title (first line of content)
    tags: Optional[list[str]] = None    # devto/medium tags
    tokens_used: int = 0
    model_used: str = ""
    char_count: int = 0
    compliance_passed: bool = True
    compliance_reason: Optional[str] = None
    # Postiz output (filled after publish)
    postiz_post_id: Optional[str] = None
    scheduled_at: Optional[str] = None
    # daily_drafts row id (filled after insert)
    daily_draft_id: Optional[str] = None


class HypeFlowState(BaseModel):
    """Per-run mutable state, propagated through Flow decorators."""
    account_id: str = ""                # primary account (twitter) — drives crew lookup
    run_id: str = ""
    triggered_by: str = "cron"
    dry_run: bool = True
    started_at_ts: float = 0.0          # for elapsed time in finalize
    total_tokens: int = 0               # crew-level total from kickoff result

    # Phase 20 — Multi-platform targets
    # Empty / None / ["twitter"] → behaves exactly like pre-Phase-20 single-platform path.
    target_platforms: list[str] = []    # e.g. ["twitter", "linkedin", "devto"]
    platform_drafts: list[PlatformDraft] = []
    content_thread_id: Optional[str] = None  # links multi-platform daily_drafts together

    # Stage outputs (populated as crew progresses)
    trend: Optional[TrendScoutOutput] = None
    plan: Optional[PlannerOutput] = None
    draft: Optional[WriterOutput] = None  # Backwards-compat: copy of twitter draft for legacy callers
    compliance: Optional[ComplianceOutput] = None
    visual: Optional[VisualDirectorOutput] = None  # Phase 21 — optional image
    video: Optional[VideoOutput] = None             # Phase 23 — optional video (Shorts/Reels)
    publish: Optional[PublisherOutput] = None

    # Final disposition
    final_status: str = ""
    error: Optional[str] = None

    # Editor's-desk telemetry — promoted from instance attrs (self._editor_*)
    # so a fresh per-node instance (LangGraph resume-safe binding) doesn't lose
    # them before _finalize reads them. Defaults preserve pre-promotion behavior:
    # editor_decision matches the run_crew literal seed ("rubric_fallback_no_candidates"
    # is set in run_crew before any decision; None here is the safe pre-run default).
    editor_decision: Optional[str] = None
    editor_decision_error: Optional[str] = None

    # Phase 1 fabrication-guard kaynak cache'leri (trend_id→str). Önceden instance
    # side-channel'dı (self._trend_*_cache); LangGraph fresh-instance/resume'da
    # KAYBOLUYORDU → boş cache → writer "## KAYNAK METİN: (yok)" alır → olgu-uydurma
    # koruması çöker + publish gate boş kaynakla çalışır. State'e promote edildi
    # (resume-güvenli). Field(default_factory) — mutable default.
    trend_raw_content_cache: dict = Field(default_factory=dict)
    trend_source_url_cache: dict = Field(default_factory=dict)


# Phase 42.B-08A — Schema version constant. Bumped on any incompatible
# change to the visual_brief_json payload structure. Stamped on every
# flag-ON payload (success and all fallback states). Allows downstream
# auditors to detect schema drift at parse time without inspecting fields.
_PHASE_42B_SCHEMA_VERSION = "42b.v1"


def _try_phase42b_brand_brief(
    *,
    trend_topic: Optional[str],
    content_type: Optional[str],
) -> tuple[str, dict, dict]:
    """Phase 42.B-07 — attempt the brand visual brief builder.
    Phase 42.B-08 — audit-readable visual_brief_json payload structure.
    Phase 42.B-08A — schema_version stamped on every payload.

    Pure function. Caller (visual_branch) decides whether to use the
    returned scene_description override based on the state value.

    Returns:
        (state, visual_brief_json_payload, scene_overrides)

        state — one of:
            'success'                — builder produced a brief
            'no_brand_entities'      — multi-brand extractor returned []
            'builder_returned_none'  — builder returned None (defensive)
            'builder_import_failed'  — could not import builder module
            'builder_failed'         — builder raised an exception

        visual_brief_json_payload — dict to set on result['visual_brief_json'].
            Phase 42.B-08 schema invariants (when caller sets it on flag ON):
              - 'enabled'        : always True
              - 'source'         : always 'brand_visual_brief_builder'
              - 'state'          : one of the 5 strings above
              - 'content_type'   : input content_type (may be None)
              - 'fallback'       : present iff state != 'success'
              - 'brand_entities' : present when known (post-extraction)
              - 'primary_brand'  : present on success only
              - 'serialized_brief_chars' : present on success only (int)
              - 'brief'          : full builder dict on success only
              - 'reason'         : present on exception-class states

        scene_overrides — dict with keys 'scene_description',
            'content_context', 'brand_used'. Populated ONLY on 'success'.
            Empty dict on any failure mode (caller falls back to Phase 34
            single-brand path).

    Never raises. All failure modes return a state + diagnostic envelope.
    """
    # Step 1 — import the builder (cross-module: backend/prompts/...)
    try:
        from prompts.brand_visual_brief_builder import (  # type: ignore
            build_brand_visual_brief,
            serialize_brief_to_prose,
        )
    except Exception as e:
        reason = f"{type(e).__name__}: {str(e)[:200]}"
        logger.warning(
            f"[Flow][42B-07] builder import failed: {reason}; "
            f"falling back to plain scene_description"
        )
        return (
            "builder_import_failed",
            {
                "enabled": True,
                "source": "brand_visual_brief_builder",
                "schema_version": _PHASE_42B_SCHEMA_VERSION,
                "state": "builder_import_failed",
                "content_type": content_type,
                "fallback": "plain_scene_description",
                "reason": reason,
                "override_sent_to_generate_and_check": False,
            },
            {},
        )

    # Step 2 — extract brands (multi-brand helper added in 42B-05A)
    try:
        from tools.brand_extractor import extract_brands_from_topic
        brands = extract_brands_from_topic(trend_topic)
    except Exception as e:
        reason = f"extractor: {type(e).__name__}: {str(e)[:200]}"
        logger.warning(
            f"[Flow][42B-07] brand extraction failed: {reason}; "
            f"falling back to plain scene_description"
        )
        return (
            "builder_failed",
            {
                "enabled": True,
                "source": "brand_visual_brief_builder",
                "schema_version": _PHASE_42B_SCHEMA_VERSION,
                "state": "builder_failed",
                "content_type": content_type,
                "fallback": "plain_scene_description",
                "reason": reason,
                "override_sent_to_generate_and_check": False,
            },
            {},
        )

    if not brands:
        logger.info(
            f"[Flow][42B-07] no brands extracted from trend topic; "
            f"falling back to plain scene_description"
        )
        return (
            "no_brand_entities",
            {
                "enabled": True,
                "source": "brand_visual_brief_builder",
                "schema_version": _PHASE_42B_SCHEMA_VERSION,
                "state": "no_brand_entities",
                "content_type": content_type,
                "fallback": "plain_scene_description",
                "brand_entities": [],
                "override_sent_to_generate_and_check": False,
            },
            {},
        )

    # Step 3 — build the brief
    try:
        brief = build_brand_visual_brief(
            content_type=content_type or "_default",
            brand_entities=brands,
            aspect_ratio="1:1",
        )
    except Exception as e:
        reason = f"{type(e).__name__}: {str(e)[:200]}"
        logger.warning(
            f"[Flow][42B-07] builder raised exception: {reason}; "
            f"falling back to plain scene_description"
        )
        return (
            "builder_failed",
            {
                "enabled": True,
                "source": "brand_visual_brief_builder",
                "schema_version": _PHASE_42B_SCHEMA_VERSION,
                "state": "builder_failed",
                "content_type": content_type,
                "fallback": "plain_scene_description",
                "reason": reason,
                "brand_entities": brands,
                "override_sent_to_generate_and_check": False,
            },
            {},
        )

    if brief is None:
        logger.info(
            f"[Flow][42B-07] builder returned None for brands={brands} "
            f"content_type={content_type}; falling back to plain scene_description"
        )
        return (
            "builder_returned_none",
            {
                "enabled": True,
                "source": "brand_visual_brief_builder",
                "schema_version": _PHASE_42B_SCHEMA_VERSION,
                "state": "builder_returned_none",
                "content_type": content_type,
                "fallback": "plain_scene_description",
                "brand_entities": brands,
                "override_sent_to_generate_and_check": False,
            },
            {},
        )

    # Step 4 — success
    prose = serialize_brief_to_prose(brief)
    logger.info(
        f"[Flow][42B-07] builder used: brands={brands} "
        f"content_type={content_type} prose_chars={len(prose)}"
    )
    return (
        "success",
        {
            "enabled": True,
            "source": "brand_visual_brief_builder",
            "schema_version": _PHASE_42B_SCHEMA_VERSION,
            "state": "success",
            "content_type": content_type,
            "brand_entities": brands,
            "primary_brand": brands[0],
            "serialized_brief_chars": len(prose),
            "brief": brief.model_dump(),
            "override_sent_to_generate_and_check": True,
        },
        {
            "scene_description": prose,
            "content_context": (
                f"Brand visual brief (Phase 42.B): "
                f"{', '.join(brands)} → content_type={content_type or '_default'}"
            ),
            "brand_used": brands[0],
        },
    )


class AutonomousContentFlow(Flow[HypeFlowState]):
    """Hype Crew orchestrator. One kickoff = one trend processed for one account."""

    @start()
    def initialize(self) -> str:
        """Load config, create hype_runs row. Returns account_id for next step."""
        # State is set via kickoff inputs by runner; defaults filled if missing
        account_id = self.state.account_id
        if not account_id:
            raise RuntimeError("HypeFlowState.account_id required")

        # Resolve dry_run precedence: DB config wins when present, env is
        # fallback only when DB has no value. Previous OR-based logic made
        # env `HYPE_DRY_RUN=true` sticky — flipping DB row to false had no
        # effect, blocking live-mode transition (Gap #4 fix, 2026-05-18).
        config_fn = load_account_config.func if hasattr(load_account_config, "func") else load_account_config
        config = config_fn(account_id)
        config_dry = config.get("dry_run_mode")
        if config_dry is None:
            self.state.dry_run = settings.dry_run
        else:
            self.state.dry_run = bool(config_dry)

        # Create hype_runs row (run_id stored in flow state — no ContextVar).
        # LangGraph Faz 2: when run_or_resume pre-seeds state.run_id (= stable
        # thread_id), do NOT regenerate it — pass it through to init_run so the
        # hype_runs PK == thread_id and resume correlates across processes.
        # init_run is idempotent for a supplied id (no duplicate row on resume).
        # CrewAI path never pre-sets state.run_id → behaves exactly as before.
        preset_run_id = self.state.run_id or None
        run_id = init_run(
            account_id=account_id,
            triggered_by=self.state.triggered_by,
            dry_run=self.state.dry_run,
            run_id=preset_run_id,
        )
        self.state.run_id = run_id
        self.state.started_at_ts = time.time()
        logger.info(f"[Flow] initialize: account={account_id} run={run_id} dry_run={self.state.dry_run}")
        return account_id

    @listen(initialize)
    def run_crew(self, account_id: str) -> None:
        """Kick off the 2-agent Crew (TrendScout + Planner). Populates state.
        Router (route_after_crew) reads state to decide next branch.
        """
        # ── LEVER A — deterministic pre-check before LLM agents ─────────
        # Diagnosis (real DB data): 48 cron runs/day produce ≈ 5 drafts/wk;
        # ~98% of runs spend Gemini on TrendScout+Planner just to conclude
        # "no new qualifying trend." The fix: run the SAME deterministic
        # persona-gate + dedup the agents would use, BEFORE crew.kickoff().
        # If zero candidates survive, end the run with status='no_candidates'
        # and make NO LLM call. Preserves hourly responsiveness; kills the
        # empty-run cost. tools.persona_gate is keyword/regex only — no
        # hidden LLM call (verified by grep for openai/genai/httpx imports).
        try:
            from tools.supabase_tools import query_trends
            _qt = query_trends.func if hasattr(query_trends, "func") else query_trends
            _candidates = _qt(account_id=account_id)
            if not _candidates:
                logger.info(
                    f"[Flow] Lever A early-exit: zero qualifying candidates "
                    f"after persona-gate + dedup — SKIP crew.kickoff(). "
                    f"account={account_id[:8]} run={self.state.run_id}"
                )
                self.state.final_status = "no_candidates"
                # Şeffaflık: aday-eleme dökümü (kaç trend, kaçı dedup/AI-dışı) →
                # Crew Akışı boş-run satırında "Aday yok · 8 trend: 5 dedup, 3 AI-dışı".
                try:
                    from tools.supabase_tools import consume_gate_breakdown
                    _bd = consume_gate_breakdown(account_id)
                except Exception:
                    _bd = {}
                # Capture in flow_state so hype_runs row reflects the early-exit.
                try:
                    from callbacks.supabase_logger import finalize_run
                    finalize_run(
                        run_id=self.state.run_id,
                        status="completed",
                        flow_state={
                            "lever_a_early_exit": True,
                            "wrote_draft": False,
                            "candidates_considered": 0,
                            "reason": _bd.get("reason") or "no_candidates_after_persona_gate_and_dedup",
                            "gate_breakdown": _bd or None,
                            # No editor's-desk pass on an empty pool — explicit
                            # tag so observability queries don't have to infer.
                            "editor_decision": "skipped_lever_a_empty",
                        },
                        started_at_ts=self.state.started_at_ts,
                    )
                except Exception as _fe:
                    logger.warning(f"[Flow] Lever A finalize_run skipped: {_fe!r}")
                return
            logger.info(
                f"[Flow] Lever A pre-check OK: {len(_candidates)} candidate(s) "
                f"survived persona-gate + dedup — proceeding to crew.kickoff. "
                f"account={account_id[:8]}"
            )
        except Exception as _le:
            # Pre-check failure must NOT block: fall through to crew.kickoff
            # so the existing path still runs (defensive — never lose a draft
            # to a pre-check bug).
            logger.warning(f"[Flow] Lever A pre-check failed (non-fatal): {_le!r}")
            _candidates = []

        # ── EDITOR'S DESK — drives lead selection (Phase live, V3) ───────
        # Dry-run-validated 21× over 2026-05-29 → 2026-06-04 (incl. the
        # Memory-over-Rosalind test). Per-firing pass (NOT once-daily):
        # daily would create a "lead lottery" where the first firing's pool
        # locks the day's lead even if breaking news arrives at noon. Per-
        # firing keeps hourly responsiveness AND uses re-lead memory (3-day
        # trend_id / cluster / topic-signature exclusion) to prevent re-
        # leading the same story across firings. Lever A is the safety net:
        # editor's-desk only fires when persona-gate left ≥1 candidate, so
        # the cost added on empty runs is exactly zero.
        editorial_lead: Optional[dict] = None
        # Editor's-desk decision tag for observability (P1: silent-fallback
        # was hiding whether the editor's-desk was actually driving picks).
        # Values: "editor_led" | "editor_excluded_all" | "rubric_fallback_error"
        # | "rubric_fallback_no_candidates" | "rubric_fallback_disabled".
        editor_decision = "rubric_fallback_no_candidates"
        editor_error: Optional[str] = None
        try:
            if _candidates:
                editorial_lead = self._run_editors_desk(account_id, _candidates)
                if editorial_lead and editorial_lead.get("trend_id"):
                    editor_decision = "editor_led"
                else:
                    # _run_editors_desk returned None: either re-lead memory
                    # excluded every candidate, or select_lead() parse-failed.
                    # Both reasons are logged inside the helper; the operator
                    # only needs to see ONE bucket here.
                    editor_decision = "editor_excluded_all"
        except Exception as _ee:
            editor_decision = "rubric_fallback_error"
            editor_error = f"{type(_ee).__name__}: {str(_ee)[:240]}"
            logger.warning(
                f"[Flow] editor's-desk failed (non-fatal — fall through to "
                f"legacy rubric pick): {_ee!r}"
            )
            # P1 hardening: when editor's-desk crashes (not just "no lead"),
            # surface it via alert_supply so the silent log line stops being
            # the only signal.
            try:
                from services.alerter import alert_supply  # type: ignore
                alert_supply(
                    severity="WARN",
                    category="editors_desk_error",
                    summary=(
                        "Editor's-desk raised; flow fell back to legacy "
                        "rubric pick. Pick is still safe, but the desk is "
                        "not driving."
                    ),
                    evidence={
                        "account_id": account_id,
                        "run_id": getattr(self.state, "run_id", None),
                        "error": editor_error,
                    },
                )
            except Exception as _ae:
                logger.warning(f"[Flow] alert_supply on editors_desk_error skipped: {_ae!r}")

        # Stash the decision tag so finalize_run writes it into hype_runs.
        # Promoted into state (resume-safe for the LangGraph per-node binding);
        # self._* kept too for any legacy getattr reader, but _finalize reads
        # from self.state below.
        self.state.editor_decision = editor_decision
        self.state.editor_decision_error = editor_error
        self._editor_decision = editor_decision
        self._editor_decision_error = editor_error

        logger.info(
            f"[Flow] run_crew: building crew for account={account_id} "
            f"editorial_lead={editorial_lead.get('trend_id') if editorial_lead else None} "
            f"editor_decision={editor_decision}"
        )
        crew = build_content_crew(account_id, editorial_lead=editorial_lead)
        # Stash for downstream — flow saves the lead's grounded reason
        # into daily_drafts.metadata so /control/karar-izi can surface it
        # alongside the editorial_lead_judgments row.
        self._editorial_lead = editorial_lead

        try:
            result = crew.kickoff(inputs={"account_id": account_id})
        except Exception as e:
            logger.exception(f"[Flow] crew.kickoff() failed: {e}")
            self.state.error = f"{type(e).__name__}: {str(e)[:300]}"
            self.state.final_status = "failed"
            return  # router: fail_branch

        # Extract pydantic outputs (2 stages — Writer/Compliance/Publisher in Flow now)
        tasks_out = list(getattr(result, "tasks_output", []) or [])
        try:
            if len(tasks_out) >= 1:
                self.state.trend = tasks_out[0].pydantic if hasattr(tasks_out[0], "pydantic") else None
            if len(tasks_out) >= 2:
                self.state.plan = tasks_out[1].pydantic if hasattr(tasks_out[1], "pydantic") else None
        except Exception as e:
            logger.warning(f"[Flow] could not parse task outputs: {e}")

        # ── Güvenilir-küratör news-bar override ── (11 Haz 2026)
        # TrendScout rubriği (final_score_12>=9 & duyuru_tipi>=3) ürün/model
        # LANSMANI için ayarlı; "OpenAI fiyat düşürüyor" gibi AI-ama-lansman-
        # değil küratör haberini reddeder. Oysa news-filter (curator_filter)
        # zaten "gerçek, taze AI haberi mi?" kararını verdi. Bu yüzden YALNIZ
        # küratör-bayraklı (trends.is_curator) trendlerde, reddin sebebi SADECE
        # rubrik ise reddi geçersiz kıl. Güvenlik/yasak/duplicate sebepli
        # skip'ler override EDİLMEZ. Rubrik kod-gate değil LLM-prose
        # (schemas/trend.py) → enforce burada deterministik. URL pre-gate'TEN
        # ÖNCE çalışır çünkü o blok trend.passed=True'ya bağlı.
        try:
            _t = self.state.trend
            if _t is not None and _t.trend_id and not _t.passed and _t.skip_reason:
                _reason = (_t.skip_reason or "").lower()
                _rubric_reject = any(k in _reason for k in (
                    "low_rubric_score", "rubric", "off_domain",
                    "duyuru_tipi", "no_qualifying",
                ))
                _protected = any(k in _reason for k in (
                    "politic", "siyaset", "nsfw", "forbidden", "blocked",
                    "yasak", "duplicate_source_url", "recently_covered",
                ))
                if _rubric_reject and not _protected:
                    _sb_c = make_supabase()
                    _crow = (
                        _sb_c.table("trends").select("is_curator")
                        .eq("id", _t.trend_id).limit(1).execute().data
                    )
                    if _crow and _crow[0].get("is_curator"):
                        logger.info(
                            f"[curator] news-bar override — TrendScout rubrik reddini "
                            f"geçersiz kıldım (sebep={_t.skip_reason!r}); küratör haberi "
                            f"yayına uygun. trend_id={_t.trend_id}"
                        )
                        _t.passed = True
                        _t.skip_reason = None
        except Exception as _ce:
            logger.warning(
                f"[curator] news-bar override FAILED ({type(_ce).__name__}: {_ce})"
            )

        # Phase 43.H.1 — URL-level pre-gate dedup. After TrendScout has picked
        # a trend (cheap: rubric scoring on ~10 candidates), check whether any
        # of this user's accounts has already produced a draft for the same
        # source URL in the last 7 days. If so, short-circuit BEFORE Writer /
        # Compliance / Visual Director / Video pipeline fire — those are the
        # expensive stages. Mirrors the n8n Content Factory pattern.
        # TrendScoutOutput doesn't carry the URL itself (only trend_id), so we
        # round-trip through the trends table for the lookup.
        try:
            trend = self.state.trend
            if trend is not None and trend.passed and trend.trend_id:
                sb_lookup = make_supabase()
                trend_rows = (
                    sb_lookup.table("trends")
                    .select("url, raw_content, source_tweets, full_source_text")
                    .eq("id", trend.trend_id)
                    .limit(1)
                    .execute()
                    .data
                )
                trend_url = None
                trend_raw_content = None
                if isinstance(trend_rows, list) and trend_rows:
                    head = trend_rows[0]
                    if isinstance(head, dict):
                        trend_url = head.get("url")
                        # 2026-06-10 — kaynak birleşimi tek tanıma indi:
                        # assemble_source_text (fst + raw_content + tweet
                        # text'leri). Tarihçe: a96e9e3 union'ı yazar+gate'e
                        # eşitledi; 2026-06-09 prod hotfix'i gate'i yalnız
                        # full_source_text'e öncelikledi ama fst bazı
                        # trendlerde tweet'leri içermiyor (Apple Siri
                        # "Apple Intelligence" false-block vakası). Yazar
                        # ve gate artık AYNI helper'ı kullanır.
                        trend_raw_content = assemble_source_text(head) or None
                # Phase 1 (Berkay 6 Haz 2026 fabrication audit) — cache
                # raw_content so write_via_typehype can inject it into the
                # writer's base_context as the ## KAYNAK METİN section. Pre-
                # fix path the writer received only topic/angle/brief and
                # invented entities the source never named (e.g. "Starlink
                # physical link" on a $920M compute-purchase deal).
                # 2026-06-08 — now caches the source_tweets union.
                if trend_raw_content:
                    # State cache'i (declared field → LangGraph resume-güvenli; eskiden
                    # self._trend_raw_content_cache side-channel'dı, fresh-instance'ta kaybolurdu).
                    self.state.trend_raw_content_cache[trend.trend_id] = trend_raw_content
                if trend_url:
                    self.state.trend_source_url_cache[trend.trend_id] = trend_url

                    from tools.supabase_tools import url_dedup_check_impl
                    dup = url_dedup_check_impl(account_id, trend_url, days=7)
                    if dup.get("found"):
                        logger.info(
                            f"[Flow] URL pre-gate HIT — duplicate source already produced "
                            f"draft={dup.get('existing_draft_id')} scope={dup.get('match_scope')} "
                            f"matches={dup.get('match_count')} url={trend_url}"
                        )
                        # Flip the trend to a soft skip so the existing router
                        # lands us in skip_branch and the run is recorded as
                        # skipped, not failed. trend.passed is a declared field
                        # so direct attribute assignment is honoured.
                        trend.passed = False
                        trend.skip_reason = (
                            f"duplicate_source_url ({dup.get('match_count')} match(es) "
                            f"in last 7d, scope={dup.get('match_scope')})"
                        )
                    else:
                        logger.info(
                            f"[Flow] URL pre-gate OK — fresh trend, no prior draft "
                            f"(url={trend_url})"
                        )
                else:
                    logger.warning(
                        f"[Flow] URL pre-gate skipped — trends.url empty for "
                        f"trend_id={trend.trend_id}"
                    )
            elif trend is not None and not trend.passed:
                logger.debug(
                    f"[Flow] URL pre-gate skipped — trend did not pass TrendScout"
                )
        except Exception as e:
            logger.warning(f"[Flow] URL pre-gate check FAILED ({type(e).__name__}: {e})")

        # Phase 41.D (Berkay 2 Haz 2026) — Deterministic video_worthy elevation.
        # TrendScout's LLM bias is conservative → video_worthy=True only ~5% of
        # runs → user perceives "no videos". Auto-elevate when the rubric score
        # is at or above 10/12 AND category isn't in a no-video set. This is a
        # SAFE overlay on top of the LLM signal: we only flip False→True, never
        # the other way. Keeps the major-launch intent while raising volume.
        try:
            trend = self.state.trend
            if trend is not None and not bool(getattr(trend, "video_worthy", False)):
                rubric_score = int(getattr(trend, "final_score_12", 0) or 0)
                legacy_score = int(getattr(trend, "score", 0) or 0)
                # 2026-06-11 BUG FIX (Berkay: "skor 100 ama video yok"):
                # state.trend.score TrendScout LLM'inin YENİDEN HESAPLADIĞI
                # 0-100 (rubric*8.33 ≈ 75; schemas/trend.py:73) — trends
                # tablosundaki gerçek skor DEĞİL. Claude Platform (DB skor
                # 100) bu yüzden hi_legacy'yi hiç tetiklemedi → video/youtube
                # hep düştü. Gerçek skoru DB'den oku; hata → mevcut değer.
                try:
                    _db_rows = (
                        make_supabase().table("trends").select("score")
                        .eq("id", trend.trend_id).limit(1).execute()
                    ).data or []
                    if _db_rows:
                        legacy_score = max(
                            legacy_score, int(_db_rows[0].get("score") or 0)
                        )
                except Exception as _dbe:  # noqa: BLE001
                    logger.warning(f"[Flow] elevation db_score lookup failed: {_dbe}")
                cat = (getattr(trend, "category", "") or "").lower()
                NO_VIDEO_CATEGORIES = {"news", "politics", "entertainment"}
                hi_rubric = rubric_score >= 10
                hi_legacy = legacy_score >= 95
                if (hi_rubric or hi_legacy) and cat not in NO_VIDEO_CATEGORIES:
                    setattr(trend, "video_worthy", True)
                    if not getattr(trend, "video_reason", None):
                        setattr(
                            trend,
                            "video_reason",
                            f"Phase 41.D auto-elevation: score={rubric_score}/12 legacy={legacy_score} cat={cat}",
                        )
                    logger.info(
                        f"[Flow] video_worthy auto-elevated: rubric={rubric_score}/12 "
                        f"legacy={legacy_score} cat={cat} → True"
                    )
        except Exception as e:
            logger.warning(f"[Flow] video_worthy elevation skipped ({e})")

        # Capstone (3 Haz 2026) — Backfill final_trendscout_score into the
        # persona_gate_log row for this trend so we can correlate gate decisions
        # with rubric outcomes (e.g., "how many tier_1_brand_match passes ended
        # up with final_score_12 < 7?"). Audit-only; failure is non-fatal.
        try:
            trend = self.state.trend
            if trend is not None and trend.trend_id and trend.final_score_12 is not None:
                make_supabase().table("persona_gate_log").update(
                    {"final_trendscout_score": int(trend.final_score_12)}
                ).eq("trend_id", trend.trend_id).is_(
                    "final_trendscout_score", "null"
                ).execute()
        except Exception as e:
            logger.warning(f"[Flow] persona_gate_log backfill skipped ({e})")

        # Crew-level token usage (CrewAI 1.14: result.token_usage)
        crew_total_tokens = 0
        try:
            tu = getattr(result, "token_usage", None)
            if hasattr(tu, "total_tokens"):
                crew_total_tokens = int(tu.total_tokens or 0)
            elif isinstance(tu, dict):
                crew_total_tokens = int(tu.get("total_tokens") or 0)
        except Exception:
            pass
        self.state.total_tokens = crew_total_tokens

        # Phase 1 (within-beat comparison) — Persist the candidate pool the
        # agent saw, plus the same-firing runner-up analysis. The agent calls
        # query_trends once during selection; the tool stashes the returned
        # pool in a process-local cache keyed on account_id. We pop it here
        # and merge candidates_considered + selection_delta into the Trend
        # Scout stage output before log_stage serialises it.
        #
        # Honest framing: comparison is only valid within ONE cron firing.
        # selection_delta names the strongest non-selected candidate and the
        # recorded reason that distinguishes it from the winner.
        candidates_considered: list[dict[str, Any]] = []
        selection_delta: Optional[dict[str, Any]] = None
        try:
            from tools.supabase_tools import (
                consume_last_pool,
                url_dedup_check_impl,
            )
            pool = consume_last_pool(account_id)
            trend = self.state.trend
            selected_id = trend.trend_id if trend is not None else None

            # Per-candidate URL-dedup status (matches the 7d/user-scope check
            # flow.py runs on the selected trend, so candidates are compared
            # on identical novelty criteria).
            sb_pool = make_supabase()
            tid_to_url: dict[str, Optional[str]] = {}
            pool_ids = [c["id"] for c in pool if c.get("id")]
            if pool_ids:
                try:
                    url_rows = (
                        sb_pool.table("trends")
                        .select("id, url")
                        .in_("id", pool_ids)
                        .execute()
                        .data
                    )
                    if isinstance(url_rows, list):
                        for ur in url_rows:
                            if isinstance(ur, dict) and ur.get("id"):
                                tid_to_url[ur["id"]] = ur.get("url")
                except Exception:
                    logger.warning("[Flow] candidates_considered URL lookup failed")

            for c in pool:
                cid = c.get("id")
                if not cid:
                    continue
                is_selected = (cid == selected_id)
                c_url = tid_to_url.get(cid)
                dedup = {"checked": False}
                if c_url:
                    try:
                        d = url_dedup_check_impl(account_id, c_url, days=7)
                        dedup = {
                            "checked": True,
                            "url_match_count": int(d.get("match_count") or 0),
                            "first_coverage": not bool(d.get("found")),
                        }
                    except Exception:
                        dedup = {"checked": False}

                if is_selected:
                    outcome = "selected"
                    skip_reason = None
                elif trend is not None and trend.skip_reason and is_selected is False and (
                    not trend.passed and trend.trend_id == cid
                ):
                    # selected-then-flipped: handled by selected branch
                    outcome = "skipped"
                    skip_reason = trend.skip_reason
                else:
                    outcome = "skipped"
                    if dedup.get("checked") and not dedup.get("first_coverage"):
                        skip_reason = (
                            f"already_covered:{dedup.get('url_match_count')}_in_7d"
                        )
                    else:
                        # Honest: the system did not compare this candidate to
                        # the winner head-to-head; the only recorded fact is
                        # that the agent did not pick it. We do NOT invent an
                        # editorial reason here.
                        skip_reason = "not_selected_by_agent"

                cand_row = {
                    "trend_id": cid,
                    "topic": (c.get("topic") or "")[:300],
                    "category": c.get("category"),
                    "legacy_score": c.get("score"),
                    "semantic_triggers": c.get("semantic_triggers") or [],
                    "source_name": c.get("source_name"),
                    "source_url": c_url,
                    "url_dedup": dedup,
                    "outcome": outcome,
                    "skip_reason": skip_reason,
                }
                # Only the selected trend carries TrendScout-assigned rubric.
                if is_selected and trend is not None:
                    cand_row["final_score_12"] = trend.final_score_12
                    cand_row["content_type"] = trend.content_type
                    breakdown = getattr(trend, "breakdown", None)
                    if breakdown is not None:
                        cand_row["breakdown"] = (
                            breakdown.model_dump() if hasattr(breakdown, "model_dump")
                            else breakdown
                        )
                candidates_considered.append(cand_row)

            # selection_delta — pick the strongest non-selected candidate from
            # this firing. "Strongest" is the legacy trends.score, since
            # final_score_12 is only computed for the winner. Recorded fields
            # only; no editorial inference.
            if selected_id and candidates_considered:
                non_sel = [c for c in candidates_considered if c["outcome"] != "selected"]
                if non_sel:
                    non_sel_sorted = sorted(
                        non_sel,
                        key=lambda c: int(c.get("legacy_score") or 0),
                        reverse=True,
                    )
                    runner_up = non_sel_sorted[0]
                    sel_row = next(
                        (c for c in candidates_considered if c["outcome"] == "selected"),
                        None,
                    )
                    sel_first = bool(
                        sel_row and sel_row.get("url_dedup", {}).get("first_coverage")
                    )
                    ru_first = bool(runner_up.get("url_dedup", {}).get("first_coverage"))
                    if sel_first and not ru_first:
                        winning_reason = "first_coverage_vs_already_covered"
                    elif not sel_first and ru_first:
                        winning_reason = "agent_preference_despite_runner_up_freshness"
                    else:
                        winning_reason = "agent_preference_no_clear_axis"
                    selection_delta = {
                        "runner_up_trend_id": runner_up["trend_id"],
                        "runner_up_topic": runner_up["topic"],
                        "score_delta": (
                            (sel_row.get("final_score_12") or 0)
                            - int(runner_up.get("legacy_score") or 0) // 10
                        ) if sel_row else None,
                        "winning_reason": winning_reason,
                        "selected_first_coverage": sel_first,
                        "runner_up_first_coverage": ru_first,
                        "runner_up_url_match_count": int(
                            runner_up.get("url_dedup", {}).get("url_match_count") or 0
                        ),
                    }
        except Exception as e:
            logger.warning(f"[Flow] candidates_considered capture failed: {e}")

        # Log crew stages (2)
        per_stage_tokens = (crew_total_tokens // len(tasks_out)) if tasks_out else 0
        stage_pydantic = [self.state.trend, self.state.plan]
        stage_models = [settings.model_fast, settings.model_smart]
        for i, t_out in enumerate(tasks_out):
            agent_name = "unknown"
            try:
                a = getattr(t_out, "agent", None)
                if isinstance(a, str):
                    agent_name = a
                elif a is not None and hasattr(a, "role"):
                    agent_name = a.role
            except Exception:
                pass

            # Phase 1 — for Trend Scout stage, merge candidates_considered
            # and selection_delta into the output dict so they persist on
            # hype_stages.output for the home-summary endpoint to read.
            stage_output: Any = stage_pydantic[i] if i < len(stage_pydantic) else None
            if (
                agent_name.lower().startswith("trend")
                and stage_output is not None
                and (candidates_considered or selection_delta)
            ):
                try:
                    merged = (
                        stage_output.model_dump(mode="json")
                        if hasattr(stage_output, "model_dump")
                        else dict(stage_output)
                    )
                    if candidates_considered:
                        merged["candidates_considered"] = candidates_considered
                    if selection_delta is not None:
                        merged["selection_delta"] = selection_delta
                    stage_output = merged
                except Exception as e:
                    logger.warning(
                        f"[Flow] candidates_considered merge skipped: {e}"
                    )

            log_stage(
                run_id=self.state.run_id,
                agent_name=agent_name,
                stage_order=i + 1,
                output=stage_output,
                model_used=stage_models[i] if i < len(stage_models) else "",
                tokens_used=per_stage_tokens,
                status="success",
            )

        # Early exit signals (router reads state)
        if self.state.trend and not self.state.trend.passed:
            return  # router: skip_branch
        if not self.state.plan:
            self.state.error = "Planner produced no output"
            return  # router: fail_branch

    @router(run_crew)
    def route_after_crew(self) -> str:
        """After Crew finishes, decide: write, skip, or fail."""
        # Lever A early-exit — no candidates, no LLM was called
        if self.state.final_status == "no_candidates":
            return "skip_branch"
        if self.state.error:
            return "fail_branch"
        if self.state.trend and not self.state.trend.passed:
            return "skip_branch"
        if not self.state.plan:
            return "fail_branch"
        return "write_step"

    # ------------------------------------------------------------------
    # Phase 20 — multi-platform helpers
    # ------------------------------------------------------------------

    _CONTENT_TYPE_BY_PLATFORM = {
        "twitter": "tweet",
        "x": "tweet",
        "linkedin": "linkedin",
        "devto": "blog",          # devto articles use the blog template
        "instagram": "instagram",
        "youtube": "youtube",
    }
    # Per-platform length knob — V3 builder uses this to set token budget.
    # tweet path = original "punch"; longer formats override.
    _UZUNLUK_BY_PLATFORM = {
        "twitter": None,          # inherit plan.uzunluk
        "x": None,
        # Phase 37 — LinkedIn target 300-500 char (Berkay 31 May). TypeHype
        # API Literal only accepts micro/punch/spark/storm — "compact" YOK.
        # "spark" (400-600) seçildi + flow.py:_enforce_platform_length max
        # 500 hard cap → effective 400-500 char output. Same outcome,
        # backend Pydantic değişmeden.
        "linkedin": "spark",
        # 2026-06-11: devto "storm" idi → backend storm'u 1300c'de zorla
        # kesiyor ve kesme yolu '\n'→'. ' ile TÜM newline'ları siliyordu
        # (makale tek satıra yapıştı, başlıklar "?." aldı, son cümle ortada
        # kaldı). "thread" (800-3000c, 2048 token) bu yıkıcı enforcement'tan
        # muaf; bizim _enforce_platform_length (max 3500, markdown-aware)
        # son kapı olarak yeterli.
        "devto": "thread",        # blog body
        "instagram": "punch",     # caption
        "youtube": "spark",       # short script
    }

    def _run_editors_desk(self, account_id: str, candidates: list[dict]) -> Optional[dict]:
        """Run editor's-desk over the post-Lever-A candidate pool.

        Returns the persisted lead row (dict with trend_id, topic,
        operator_sentence, judgment_id, plus the full select_lead()
        judgment payload) or None when the editor's-desk yields no lead
        (re-lead memory excluded everything, or LLM call failed). Caller
        falls through to legacy rubric pick on None.

        Re-lead memory: looks back 3 days in editorial_lead_judgments for
        live picks made on this account. Excludes (a) those trend_ids,
        (b) their topic signatures, (c) their cluster_ids — matches the
        validated V3 select_lead() exclusion logic.

        Persistence: dry_run=False — these are real editorial decisions
        driving the live draft pipeline. They surface in /control/karar-izi.
        """
        # P1 hardening (2026-06-07): an import failure used to silently
        # fall through to the rubric pick. The editor's-desk would simply
        # stop driving and nobody would know. Make it loud: log CRITICAL,
        # fire alert_supply, and RAISE — the surrounding caller treats
        # the raise as `rubric_fallback_error` (still safe; doesn't lose
        # a draft) but it also fires a WARN alert so the operator notices.
        try:
            import sys as _sys_ed
            for _p in ("/opt/contentfactory", "../contentfactory", "../../contentfactory"):
                if _p not in _sys_ed.path:
                    _sys_ed.path.insert(0, _p)
            from backend.services.editors_desk import select_lead, persist_judgment  # type: ignore
        except Exception as e:
            logger.critical(
                f"[editors_desk] import FAILED — desk is OFF, rubric pick will "
                f"drive every run until this is fixed: {e!r}"
            )
            try:
                from services.alerter import alert_supply  # type: ignore
                alert_supply(
                    severity="CRITICAL",
                    category="editors_desk_import_failed",
                    summary=(
                        "Editor's-desk module could not be imported. Every "
                        "run on this host will silently fall through to the "
                        "legacy rubric pick until this is fixed."
                    ),
                    evidence={
                        "account_id": account_id,
                        "error": f"{type(e).__name__}: {str(e)[:300]}",
                        "sys_path_first": _sys_ed.path[:6],
                    },
                )
            except Exception as _ae:
                logger.warning(
                    f"[editors_desk] alert_supply on import failure skipped: {_ae!r}"
                )
            # Re-raise so the caller bucket is `rubric_fallback_error` (not
            # `editor_excluded_all`) — those two states must stay distinct
            # in hype_runs.flow_state.
            raise

        sb = make_supabase()

        # Enrich candidates with raw_content / source_url / published_at /
        # cluster_id from the trends table — select_lead requires these
        # for the grounded-reason layer.
        trend_ids = [c.get("id") for c in candidates if c.get("id")]
        if not trend_ids:
            return None
        try:
            trend_rows = (
                sb.table("trends")
                .select("id, raw_content, url, source_name, published_at, "
                        "cluster_id, semantic_triggers, category, topic, score")
                .in_("id", trend_ids)
                .execute()
                .data
            ) or []
        except Exception as e:
            logger.warning(f"[editors_desk] trends enrich failed: {e!r}")
            return None
        by_id = {r["id"]: r for r in trend_rows if isinstance(r, dict)}
        enriched: list[dict] = []
        for c in candidates:
            tid = c.get("id")
            row = by_id.get(tid, {})
            enriched.append({
                "trend_id": tid,
                "cluster_id": row.get("cluster_id"),
                "topic": c.get("topic") or row.get("topic") or "",
                "content_type": None,            # filled by TrendScout downstream
                "category": c.get("category") or row.get("category"),
                "semantic_triggers": c.get("semantic_triggers")
                                      or row.get("semantic_triggers") or [],
                "score": c.get("score") or row.get("score"),
                "source_url": row.get("url"),
                "source_name": row.get("source_name") or c.get("source_name"),
                "published_at": row.get("published_at"),
                "raw_content": (row.get("raw_content") or "").strip(),
            })

        # Re-lead memory — last 3 days of LIVE picks for this account.
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        cutoff = (_dt.now(_tz.utc) - _td(days=3)).date().isoformat()
        recent_trend_ids: list[str] = []
        recent_topics: list[str] = []
        recent_clusters: list[str] = []
        try:
            recent = (
                sb.table("editorial_lead_judgments")
                .select("lead_trend_id, lead_topic, dry_run")
                .eq("account_id", account_id)
                .gte("judgment_date", cutoff)
                .eq("dry_run", False)
                .execute()
                .data
            ) or []
            for r in recent:
                if r.get("lead_trend_id"):
                    recent_trend_ids.append(r["lead_trend_id"])
                if r.get("lead_topic"):
                    recent_topics.append(r["lead_topic"])
        except Exception as e:
            logger.warning(f"[editors_desk] re-lead memory lookup failed: {e!r}")

        # RE-LEAD (13 Haz, Berkay): işlenmiş bir KONUNUN yeni GELİŞMESİ (örn.
        # "Fable 5 tanıtıldı" işlendi → "Fable 5 KALDIRILDI") sessizce
        # dedup/exclusion'a takılmasın. Pool'da gelişme-işaretli taze bir aday
        # varsa, o konunun 3-gün topic-exclusion'ı DÜŞER → re-lead aday olur.
        # KONSERVATİF: yalnız açık gelişme kelimesi + kelime-örtüşmesi → sıradan
        # tekrar re-post edilmez. flow_state'e şeffaf yazılır.
        _DEV_MARKERS = (
            "kaldırıl", "geri çek", "geri çağr", "durdurul", "yasakla", "kapatıl",
            "sızdı", "sızıntı", "çöktü", "çökme", "özür", "askıya", "geri adım",
            "ertelen", "iptal", "pulled", "removed", "recall", "shut down",
            "banned", "outage", "breach", "apolog", "rollback", "deprecat",
        )

        def _is_new_dev(txt: str) -> bool:
            t = (txt or "").lower()
            return any(m in t for m in _DEV_MARKERS)

        relead_dropped: list[str] = []
        try:
            dev_cands = [c for c in enriched if _is_new_dev(str(c.get("topic", "")))]
            if dev_cands and recent_topics:
                import re as _re

                def _ov(a: str, b: str) -> bool:
                    wa = {w for w in _re.findall(r"\w+", a.lower()) if len(w) > 3}
                    wb = {w for w in _re.findall(r"\w+", b.lower()) if len(w) > 3}
                    return len(wa & wb) >= 2

                kept = []
                for rt in recent_topics:
                    if any(_ov(rt, str(c.get("topic", ""))) for c in dev_cands):
                        relead_dropped.append(rt)
                    else:
                        kept.append(rt)
                if relead_dropped:
                    recent_topics = kept
                    self._relead_dropped = relead_dropped
                    logger.info(
                        f"[editors_desk] RE-LEAD: yeni gelişme adayı → "
                        f"{len(relead_dropped)} konu exclusion'dan düştü: {relead_dropped}"
                    )
        except Exception as _re_e:  # noqa: BLE001
            logger.warning(f"[editors_desk] re-lead kontrolü atlandı: {_re_e!r}")

        judgment = select_lead(
            enriched,
            recent_lead_trend_ids=recent_trend_ids,
            excluded_topics=recent_topics,
            excluded_cluster_ids=recent_clusters,
        )
        if not judgment or not judgment.get("lead_label"):
            logger.info("[editors_desk] no lead returned (excluded / parse fail)")
            return None

        # Persist live (dry_run=False). Surfaces in /control/karar-izi.
        try:
            judgment_id = persist_judgment(
                sb,
                account_id=account_id,
                judgment_date=_dt.now(_tz.utc).date().isoformat(),
                judgment=judgment,
                dry_run=False,
                notes=f"live_pick run_id={self.state.run_id}",
            )
        except Exception as e:
            # If unique-index conflict on (account_id, judgment_date, live)
            # — we already led today; skip writing the row but still use
            # the lead. (This is rare with hourly: typically only the first
            # firing of the day gets a unique slot.)
            # 2026-06-10 — duplicate = İDEMPOTENT, hata değil: INFO'ya
            # indirildi (saatlik run'larda her gün 1+ kez normal).
            if "editorial_lead_judgments_uniq" in str(e):
                logger.info("[editors_desk] bugünün lead kaydı zaten var (idempotent, devam)")
            else:
                logger.warning(f"[editors_desk] persist failed (continuing): {e!r}")
            judgment_id = None

        # Find the lead candidate
        lead_label = judgment.get("lead_label")
        lead_cand = next(
            (c for c in judgment.get("_candidates") or []
             if c.get("label") == lead_label), None,
        )
        if not lead_cand:
            return None
        return {
            "trend_id": lead_cand.get("trend_id"),
            "topic": lead_cand.get("topic"),
            "operator_sentence": judgment.get("operator_sentence"),
            "reason_clauses": judgment.get("reason_clauses") or [],
            "passed_over_label": judgment.get("passed_over_label"),
            "judgment_id": judgment_id,
            "model": judgment.get("_model"),
            "candidate_count": len(judgment.get("_candidates") or []),
        }

    def _resolve_target_platforms(self) -> list[str]:
        """Return ordered platform list, prefer persona.default_target_platforms.

        Phase 40 (Berkay 1 Haz 2026) — YouTube is a video-only platform on
        Postiz (image-only YT posts get 400 Bad Request). So we drop YouTube
        from the target list whenever the run's trend isn't video_worthy.
        Major launches (GPT-6, Claude 5, etc.) keep YouTube in; routine
        feature updates don't waste a YT slot.

        Falls back to ['twitter'] if persona missing or column empty (no Phase 20
        behaviour change for non-multi-platform personas).
        """
        # State override wins (e.g. runner CLI flag in future)
        if self.state.target_platforms:
            plats = [p.lower() for p in self.state.target_platforms]
        else:
            persona = self._resolve_persona()
            if persona and persona.get("default_target_platforms"):
                plats = [p.lower() for p in persona["default_target_platforms"]]
            else:
                plats = ["twitter"]
            if not plats:
                plats = ["twitter"]

        # Phase 40 — drop YouTube unless trend is video-worthy
        trend = getattr(self.state, "trend", None)
        is_video_worthy = bool(getattr(trend, "video_worthy", False)) if trend else False
        if not is_video_worthy and "youtube" in plats:
            plats = [p for p in plats if p != "youtube"]
            logger.info(
                "[Flow] target_platforms: dropping youtube (trend not video_worthy)"
            )
        return plats

    def _resolve_account_for_platform(self, *, owner_user_id: str, platform: str) -> Optional[dict]:
        """Find a connected_accounts row for (user, platform). Postiz_provider
        is preferred over `platform` column because devto rows are stored with
        platform='default' but postiz_provider='devto'.
        """
        sb = make_supabase()
        try:
            r = (
                sb.table("connected_accounts")
                .select("id, platform, postiz_provider, username, postiz_integration_id")
                .eq("user_id", owner_user_id)
                .or_(f"platform.eq.{platform},postiz_provider.eq.{platform}")
                .limit(1)
                .execute()
            )
            rows = r.data or []
            row = rows[0] if rows else None
            if isinstance(row, dict):
                return dict(row)  # type: ignore[arg-type]
            return None
        except Exception as e:
            logger.warning(f"[Flow] _resolve_account_for_platform({platform}) failed: {e}")
            return None

    def _content_thread_id(self) -> str:
        """Lazy-create a content_threads row for the current run + return id.
        Idempotent — only creates on first call.
        """
        if self.state.content_thread_id:
            return self.state.content_thread_id
        sb = make_supabase()
        persona = self._resolve_persona()
        plan = self.state.plan
        trend = self.state.trend
        row = {
            "persona_id": persona["id"] if persona else None,
            "trend_id": trend.trend_id if trend else None,
            "topic_slug": (trend.topic[:80].lower().replace(" ", "-") if trend else None),
            "primary_angle": plan.angle if plan else None,
            "content_type": "trend",
            "status": "generating",
            "hype_run_id": self.state.run_id,
            "target_platforms": self.state.target_platforms or [],
        }
        try:
            r = sb.table("content_threads").insert(row).execute()
            data = r.data or []
            first = data[0] if data else None
            cid = first.get("id") if isinstance(first, dict) else None
            if isinstance(cid, str):
                self.state.content_thread_id = cid
                return cid
        except Exception as e:
            logger.warning(f"[Flow] content_thread create failed: {e}")
        return ""

    # ── Repetition lint (2026-06-08 Semih-DNA rewrite) ────────────
    # The old "variety shapes" registry forced a contrarian-pundit
    # frame (chosen_shape='contrarian-asil-mesele' + opener templates
    # like "bence asıl olay" / "perde arkası" / "operasyonel olarak").
    # That produced the formulaic voice Berkay wants killed. The new
    # repetition guard simply prevents two consecutive drafts from
    # opening with the same literal phrase — the VOICE itself comes
    # from the Cansu v2 style profile (Semih DNA distilled), not from
    # opener prescriptions. NO shape rotation. NO phrase prescription.

    # Universally-banned canned phrases — these are the residue of the
    # old persona that we kill outright, regardless of recent history.
    # If any future draft's opener still contains one of these, the
    # post-write retry kicks in (see _violates_variety below).
    _CANNED_PHRASES_GLOBAL_BAN = (
        # Original (0c47a11) — contrarian perde
        "bence asıl olay", "bence asıl mesele", "bence asıl önemli",
        "asıl önemli olan", "asıl mesele", "asıl olay",
        "perde arkası", "perde arkasında",
        "kimse bundan bahsetmiyor",
        "operasyonel olarak",
        # 2026-06-08 follow-up — engineer-frame perde (8/9 voice
        # samples leaked "mühendis olarak / gözüyle" tag-frames)
        "mühendis olarak",
        "mühendis gözüyle",
        "mühendis tarafından",
        "olarak söyleyeyim",
        "olarak bakınca",
        "gözüyle bakınca",
        "açısından bakınca",
        "tarafından bakınca",
        # 2026-06-08 follow-up — reveal-template perde (LLM invented
        # "asıl ilginç olan şu" as a substitute for the killed
        # "asıl olay/mesele" template)
        "asıl ilginç olan",
        "asıl önemli",
        "asıl soru",
        "asıl test",
        "işin özü",
        "burada işin altında",
        "işin altında şu",
        # Second-pass leakage patterns observed in regen run
        "benim için asıl",
        "asıl kısım",
    )

    # Generic self-ref-opener regex: matches "X olarak", "X gözüyle",
    # "X açısından" within the first ~40 chars of a draft. Catches
    # variants like "AI mühendisi olarak", "Yatırımcı gözüyle bakınca"
    # that the literal phrase list above can't enumerate.
    _SELF_REF_OPENER_RE = __import__("re").compile(
        r"^[^.\n]{0,40}?\b\w+\s+(olarak|gözüyle|açısından)\b",
        __import__("re").IGNORECASE,
    )

    def _build_repetition_guard(self, account_id: str) -> tuple[list[str], list[str], str]:
        """Pull the last ~5 drafts this account produced and extract their
        opener phrases for banning. Return shape kept for backwards-compat
        with two call sites (write_via_typehype + the post-write retry),
        but the third tuple element (chosen_shape) is now a no-op empty
        string — the v2 Cansu profile (Semih DNA) drives voice, not a
        shape selection.

        Returns:
          recent_openers — first ~50 chars of each of the last 5 drafts,
                           banned for THIS run so we don't repeat literal
                           openers.
          recent_phrases — empty list (kept for signature compat).
          chosen_shape   — empty string (kept for signature compat).
        """
        recent_openers: list[str] = []
        try:
            sb = make_supabase()
            rows = (
                sb.table("daily_drafts")
                .select("content, created_at")
                .eq("account_id", account_id)
                .not_.is_("content", "null")
                .order("created_at", desc=True)
                .limit(5)
                .execute()
                .data
            ) or []
        except Exception as e:
            logger.warning(f"[variety] recent-draft lookup failed (continuing): {e!r}")
            rows = []

        for r in rows:
            content = (r.get("content") or "").strip()
            if not content:
                continue
            # Extract the literal opener phrase: first 50 chars, trimmed
            # at the first sentence boundary (.!? \n) so we ban "Bakın bu
            # ciddi bir eşik" rather than 50 char of arbitrary text.
            head = content[:80]
            import re as _re
            m = _re.search(r"[.!?\n]", head)
            opener = (head[: m.start()] if m else head).strip()
            if opener and opener.lower() not in [o.lower() for o in recent_openers]:
                recent_openers.append(opener)

        logger.info(
            f"[variety] account={account_id[:8]} "
            f"banned_recent_openers={len(recent_openers)} "
            f"(literal-opener guard; no shape rotation, no phrase prescription)"
        )
        # Tuple signature kept for backwards compatibility with the two
        # call sites that destructure (openers, phrases, shape).
        return recent_openers, [], ""

    @listen("write_step")
    def write_via_typehype(self) -> None:
        """Phase 20 — Generate per-platform drafts in parallel via TypeHype V3.

        For backwards compatibility, when target_platforms = ['twitter'] (default
        for personas without multi-platform config), the flow behaves identically
        to the pre-Phase-20 single-tweet path.
        """
        import asyncio
        from tools.typehype_client import generate_tweet_via_typehype

        plan = self.state.plan
        trend = self.state.trend
        if not plan or not trend:
            self.state.error = "write_via_typehype: missing plan or trend in state"
            return

        target_platforms = self._resolve_target_platforms()
        self.state.target_platforms = target_platforms
        logger.info(f"[Flow] write: target_platforms={target_platforms}")

        # Resolve the persona's owner so we can look up connected_accounts.
        persona = self._resolve_persona()
        owner_user_id = persona.get("owner_user_id") if persona else None
        if not owner_user_id:
            owner_user_id = self._lookup_user_id()
        if not owner_user_id:
            self.state.error = "write_via_typehype: could not resolve owner user_id"
            return

        # ── 2026-06-08 Semih-DNA voice rewrite ─────────────────────
        # The previous "cansu_directive" block prescribed a contrarian-
        # pundit voice via an opener-shape menu + a list of "operatör-
        # tonu" word substitutions ("perde arkası" / "operasyonel
        # olarak" / "iş akışı" / "asıl mesele"). That scaffolding was
        # the actual source of the formulaic voice, not a downstream
        # writer bug. The new directive is minimal: identity + grounding
        # + a NEGATIVE ban-list of the canned phrases we want killed.
        # The POSITIVE voice (short, conclusion-first, curious + excited,
        # TR/EN technical mix, no CTA, no question close) comes from
        # the Cansu v2 style profile (Semih DNA distilled) that the
        # writer downstream fetches via account_id → style_profile_id.
        recent_openers, _, _ = (
            self._build_repetition_guard(account_id=self.state.account_id)
        )
        _canned_ban_lines = "\n".join(
            f'  - "{p}"' for p in self._CANNED_PHRASES_GLOBAL_BAN
        )
        _recent_ban_lines = (
            "\nSON 5 POSTUN AÇILIŞ CÜMLELERİ (aynı açılışı tekrarlama):\n"
            + "\n".join(f'  - "{o}"' for o in recent_openers)
            if recent_openers else ""
        )
        # ── 2026-06-08 follow-up: kill the engineer-frame perde ──
        # The prior version (0c47a11) instructed "hafif mühendis görüşü
        # ('mühendis olarak beni heyecanlandıran şu')" — which the LLM
        # picked up as a literal template. 8/9 voice samples opened with
        # "mühendis olarak / mühendis gözüyle bakınca". That is itself a
        # perde, same class as the old contrarian frame. The cure: the
        # engineering must SHOW (in what Cansu notices: mechanism,
        # specific number, event-connection) — never be ANNOUNCED via
        # a self-referential opener tag.
        cansu_directive = build_cansu_directive(
            canned_ban_lines=_canned_ban_lines,
            recent_ban_lines=_recent_ban_lines,
        )

        ctx_parts = [
            cansu_directive,
            _LUGAT_PLACEHOLDER,  # platform başına _lugat_for_platform ile dolar
            f"Trend konusu: {trend.topic}",
            f"Açı: {plan.angle}",
            f"Brief: {plan.brief}",
        ]
        if trend.semantic_triggers:
            ctx_parts.append(f"Sinyaller: {', '.join(trend.semantic_triggers)}")
        # Phase 1 (6 Haz 2026) — inject the FULL source text the writer
        # was previously never given. ALL claims must trace back here.
        _rc_cache = self.state.trend_raw_content_cache
        _trend_id = getattr(trend, "trend_id", None)
        raw_source = _rc_cache.get(_trend_id) if _trend_id else None
        if raw_source:
            ctx_parts.append(
                "## KAYNAK METİN (tüm iddialar buna bağlı olmalı — kaynak "
                "dışı bir entity / sayı / ürün / olay / sebep YAZMA)\n"
                + raw_source.strip()
            )
        else:
            ctx_parts.append(
                "## KAYNAK METİN: (yok)\nKaynak bulunamadı — yalnızca trend "
                "konusu ve açı kullanılarak yazılacak, spekülatif uzantı YOK."
            )
        base_context = "\n".join(ctx_parts)

        # Build per-platform invocation specs
        invocations = []
        for plat in target_platforms:
            acc = self._resolve_account_for_platform(owner_user_id=owner_user_id, platform=plat)
            if not acc:
                logger.warning(f"[Flow] no connected account for platform={plat}; skipping")
                continue
            if not acc.get("postiz_integration_id"):
                logger.warning(f"[Flow] platform={plat} has no postiz_integration_id; skipping")
                continue
            ctype = self._CONTENT_TYPE_BY_PLATFORM.get(plat, "tweet")
            uzunluk = self._UZUNLUK_BY_PLATFORM.get(plat) or plan.uzunluk
            # 2026-06-10 — her platform yalnız KENDİ lugat bloğunu görür
            # (önceden tüm platform yapıları tek directive'de gidiyordu →
            # blend). Lugat, directive'den hemen sonra ki kaynak metinden
            # önce gelsin: yapı kuralları olgulardan önce okunur.
            plat_context = base_context.replace(
                _LUGAT_PLACEHOLDER, _lugat_for_platform(plat), 1
            )
            invocations.append((plat, acc, ctype, uzunluk, plat_context))

        if not invocations:
            self.state.error = "write_via_typehype: no valid platforms after resolve"
            return

        # Phase 25.B/C — Resolve voice_mode from Strategist output (falls back
        # to content_type→voice_mode mapping when Strategist didn't emit one,
        # and finally to None which preserves pre-Phase-25 Cansu default).
        from schemas.plan import voice_mode_for_content_type
        plan_voice_mode = plan.voice_mode
        if not plan_voice_mode and plan.content_type:
            plan_voice_mode = voice_mode_for_content_type(plan.content_type)
        if plan_voice_mode:
            logger.info(
                f"[Flow] write: voice_mode={plan_voice_mode} "
                f"(content_type={plan.content_type})"
            )

        # Phase 37 — Per-platform voice_mode override (Berkay 31 May 2026:
        # "aynı haberi twitter linkedin blog için ayrı stillerde yazmalı").
        # Strategist tek plan.voice_mode atıyor, 4 platforma da gönderiyordu →
        # tüm tone'lar aynı çıkıyordu. Override öncelik sırası:
        #   1) Platform-specific override (varsa)
        #   2) plan.voice_mode (Strategist'in semantic kararı)
        #   3) voice_mode_for_content_type fallback
        # Override gerekçesi: platforms have intrinsic tone conventions
        # bağımsız content_type'tan (X always witty, LinkedIn always
        # editorial/neutral 3rd-person regardless of news type).
        # Capstone (4 Haz 2026) — F1: long-form platforms previously forced
        # third_person_neutral, which silently stripped Cansu Approved DNA via
        # style_prompt_v2:167. Result: LinkedIn / blog / Medium / Dev.to reads
        # like AP wire copy. Remap to `hybrid`: keeps 3.şahıs factual opener
        # (platform-appropriate) AND restores 1. şahıs insider reaction close
        # + Cansu DNA injection. YouTube also moves to hybrid (TTS narration
        # opens with fact + transitions to opinion — same pattern).
        platform_voice_overrides = {
            "twitter":   "first_person_witty",
            "x":         "first_person_witty",
            "instagram": "first_person_witty",
            "linkedin":  "hybrid",       # F1: was third_person_neutral
            "linkedin-page": "hybrid",   # F1
            "devto":     "hybrid",       # F1
            "blog":      "hybrid",       # F1
            "medium":    "hybrid",       # F1
            "youtube":   "hybrid",       # F1
        }

        # Run all platform generations in parallel via asyncio (sync httpx wrapped)
        def _one(plat: str, acc: dict, content_type: str, uzunluk_val: str, ctx: str) -> tuple[str, dict]:
            # Phase 37 — apply platform-specific voice override
            plat_voice = platform_voice_overrides.get(plat.lower(), plan_voice_mode)
            try:
                resp = generate_tweet_via_typehype(
                    account_id=acc["id"],
                    etki=plan.etki,
                    karakter=plan.karakter,
                    uzunluk=uzunluk_val,  # type: ignore[arg-type]
                    yapi="dogal",
                    additional_context=ctx,
                    is_ultra=False,
                    content_type=content_type,  # type: ignore[arg-type]
                    voice_mode=plat_voice,  # Phase 37 (Phase 25.C base)
                    model_override=getattr(settings, "writer_model", None) or None,
                    clean_source_input=True,
                )
                return plat, resp
            except Exception as e:
                logger.exception(f"[Flow] TypeHype generate failed for {plat}: {e}")
                return plat, {"_error": f"{type(e).__name__}: {str(e)[:200]}"}

        async def _run_batch(batch):
            tasks = [
                asyncio.to_thread(_one, plat, acc, ctype, uzunluk_val, ctx)
                for (plat, acc, ctype, uzunluk_val, ctx) in batch
            ]
            return await asyncio.gather(*tasks)

        # 2026-06-11 (Berkay: "5 platform aynı text") — deterministik AÇILIŞ
        # AYRIŞMASI. Tüm platformlar aynı topic+açı+kaynakla beslendiği için
        # paralel bağımsız çağrılar aynı açılış cümlesine yakınsıyordu
        # (Claude Platform seti: 3 platform birebir aynı cümleyle açıldı).
        # Çözüm: twitter (primary) ÖNCE yazılır; ilk cümlesi kalan
        # platformların context'ine "BU AÇILIŞI KULLANMA" yasağı olarak
        # eklenir. Tek serial adım; kalanlar yine paralel.
        def _first_sentence(text: str) -> str:
            t = (text or "").strip().split("\n")[0]
            m = re.search(r"[.!?…]", t)
            return (t[: m.end()] if m else t)[:160].strip()

        inv_twitter = [iv for iv in invocations if iv[0].lower() in ("twitter", "x")]
        inv_rest = [iv for iv in invocations if iv[0].lower() not in ("twitter", "x")]
        results = []
        if inv_twitter:
            results.extend(asyncio.run(_run_batch(inv_twitter)))
            _tw_resp = results[0][1] if results else {}
            _tw_open = _first_sentence(_tw_resp.get("content") or "")
            if _tw_open and inv_rest:
                _open_ban = (
                    "\n\n## AÇILIŞ AYRIŞMASI (zorunlu)\n"
                    f'Aynı haberin X postu şu cümleyle açıldı: "{_tw_open}"\n'
                    "Sen bu cümleyle, yakın bir varyantıyla ya da aynı bilgi "
                    "sıralamasıyla AÇMA. Lugatındaki AÇILIŞ KURALI'na göre "
                    "kendi farklı kancanı kur."
                )
                inv_rest = [
                    (p, a, c, u, ctx + _open_ban)
                    for (p, a, c, u, ctx) in inv_rest
                ]
        if inv_rest:
            results.extend(asyncio.run(_run_batch(inv_rest)))
        # zip(invocations, results) hizası için listeyi aynı sırayla yeniden kur
        invocations = inv_twitter + inv_rest

        # Build platform_drafts; copy twitter's into state.draft for legacy
        # compliance + visual stages.
        platform_drafts: list[PlatformDraft] = []
        twitter_draft_output: Optional[WriterOutput] = None
        total_typehype_tokens = 0

        # ── Variety lint (2026-06-08 Semih-DNA rewrite) ─────────────
        # Defensive post-write check: if the LLM still produced
        # output that opens with one of the GLOBAL-BAN canned phrases
        # OR repeats a literal recent opener, retry ONCE with a
        # sharper "don't start with X" instruction. Single retry,
        # not a loop.
        _banned_openers, _, _ = (
            self._build_repetition_guard(account_id=self.state.account_id)
        )

        def _violates_variety(text: str) -> Optional[str]:
            """Return a short reason string if `text` violates ANY of:
              - opens with a globally-banned canned phrase
              - matches the self-ref-opener regex (X olarak/gözüyle/açısından)
              - repeats a literal recent opener verbatim
              - contains an engineer-frame or reveal-template phrase
                ANYWHERE in the body (not just opener — the perde leaks
                into paragraph 2 / mid-text otherwise)
            None if OK."""
            head_raw = (text or "").strip()
            head_lc = head_raw[:200].lower()
            full_lc = head_raw.lower()
            # 2026-06-08 follow-up — regex-catch self-ref openers like
            # "AI mühendisi olarak ...", "Yatırımcı gözüyle bakınca ..."
            # that the literal ban-list can't enumerate. Run against the
            # FULL text — paragraph-2 leaks are the same perde.
            for paragraph in head_raw.split("\n"):
                stripped = paragraph.strip()
                if not stripped:
                    continue
                m = self._SELF_REF_OPENER_RE.match(stripped)
                if m:
                    return f"self-ref opener (in body): {m.group(0)!r}"
            # Scan WHOLE text for the canned ban list. The perde leaks
            # into paragraph 2 of LinkedIn / mid-sentence of YouTube
            # even when the opener is clean. The phrase is bad
            # everywhere it appears, so the check must scan everywhere.
            for canned in self._CANNED_PHRASES_GLOBAL_BAN:
                if canned in full_lc:
                    return f"contains globally-banned phrase: {canned!r}"
            for opener in _banned_openers:
                # opener is the literal first-clause string of a recent
                # draft; ban exact-prefix reuse so two consecutive
                # drafts don't share an opener verbatim.
                op_lc = opener.lower()
                if op_lc and head_lc.startswith(op_lc[:50]):
                    return f"repeats recent literal opener: {opener[:50]!r}"
            return None

        for (plat, acc, ctype, _uzunluk, _plat_ctx), (_, resp) in zip(invocations, results):
            if "_error" in resp:
                logger.warning(f"[Flow] {plat} skipped due to error: {resp['_error']}")
                continue
            content = (resp.get("content") or "").strip()
            if not content:
                continue
            total_typehype_tokens += int(resp.get("tokens_used", 0))

            # Post-write lint: retry ONCE with explicit "don't start
            # with X" if the produced content still hit a banned shape.
            _violation = _violates_variety(content)
            if _violation:
                logger.info(
                    f"[variety] retry {plat}: {_violation}. Regenerating with "
                    f"explicit ban list."
                )
                _retry_context = _plat_ctx + (
                    "\n\n## TEKRAR ENGELİ (zorunlu)\n"
                    f"Önceki çıktı kabul edilmedi: {_violation}.\n"
                    "Bu sefer İLK 80 karakteri TAMAMEN farklı bir cümle "
                    "yapısıyla yaz. Yasak kalıpları KESİNLİKLE kullanma. "
                    "Sonuç-önce, kısa, tek fikir — Semih DNA tonunda."
                )
                try:
                    plat_voice_retry = platform_voice_overrides.get(
                        plat.lower(), plan_voice_mode,
                    )
                    retry_resp = generate_tweet_via_typehype(
                        account_id=acc["id"],
                        etki=plan.etki,
                        karakter=plan.karakter,
                        uzunluk=_uzunluk,  # type: ignore[arg-type]
                        yapi="dogal",
                        additional_context=_retry_context,
                        is_ultra=False,
                        content_type=ctype,  # type: ignore[arg-type]
                        voice_mode=plat_voice_retry,
                        model_override=getattr(settings, "writer_model", None) or None,
                        clean_source_input=True,
                    )
                    retry_content = (retry_resp.get("content") or "").strip()
                    if retry_content and not _violates_variety(retry_content):
                        logger.info(f"[variety] retry success on {plat}")
                        content = retry_content
                        total_typehype_tokens += int(retry_resp.get("tokens_used", 0))
                    else:
                        logger.warning(
                            f"[variety] retry on {plat} also tripped lint; "
                            f"keeping first draft (operator can reject)."
                        )
                except Exception as _re:
                    logger.warning(f"[variety] retry call failed on {plat}: {_re!r}")

            # 2026-06-08 — Berkay sanitize chain. Order matters:
            #  1) em-dash → comma (writer may leak gazeteci punctuation)
            #  2) strip ALL hashtags (Berkay: no #AIcreated, no organic)
            #  3) strip ALL emojis (Berkay: no 🎉 / 🐛 / etc.)
            #  4) strip "Cansu, AI persona" / "AI generated" disclosures
            # _apply_platform_metadata is now a no-op (DISCLOSURE_RULES empty)
            # but kept for the call-site contract. _enforce_hashtag_count is
            # idempotent on now-empty hashtag content.
            content = _sanitize_em_dash(content)
            content = _strip_all_hashtags(content)
            content = _strip_emojis(content)
            content = _strip_persona_disclosure(content)
            content = _apply_platform_metadata(content, plat)
            content = _enforce_hashtag_count(content, plat)
            # Phase 35.3 — hard char cap enforcement (Twitter ≤280 critical
            # for Postiz publish; others warning-only).
            content = _enforce_platform_length(content, plat)

            # devto wants a title; use trend topic as fallback
            title = None
            tags = None
            if ctype == "blog":
                title = trend.topic[:120]
                # tags from semantic_triggers if present
                if trend.semantic_triggers:
                    tags = [t.lower().replace(" ", "")[:25] for t in trend.semantic_triggers[:4]]

            pd = PlatformDraft(
                platform=plat,
                integration_id=acc["postiz_integration_id"],
                account_id=acc["id"],
                content=content,
                title=title,
                tags=tags,
                tokens_used=int(resp.get("tokens_used", 0)),
                model_used=resp.get("model_used", "typehype-v3"),
                char_count=len(content),
            )
            platform_drafts.append(pd)

            if plat in ("twitter", "x") and twitter_draft_output is None:
                twitter_draft_output = WriterOutput(
                    content=content,
                    character_count=len(content),
                    hook_type=plan.hook_type,
                    line_count=content.count("\n") + 1,
                    has_em_dash=("—" in content or "–" in content),
                    has_corporate_words=[],
                    voice_alignment_score=85,
                )

        if not platform_drafts:
            self.state.error = "TypeHype produced no content for any platform"
            return

        self.state.platform_drafts = platform_drafts

        # Backwards-compat: state.draft = primary platform's WriterOutput.
        # If twitter is in the targets it wins; otherwise first platform's draft.
        if twitter_draft_output is None:
            first = platform_drafts[0]
            twitter_draft_output = WriterOutput(
                content=first.content,
                character_count=first.char_count,
                hook_type=plan.hook_type,
                line_count=first.content.count("\n") + 1,
                has_em_dash=("—" in first.content or "–" in first.content),
                has_corporate_words=[],
                voice_alignment_score=85,
            )
        self.state.draft = twitter_draft_output

        self.state.total_tokens += total_typehype_tokens

        # Single stage row for all platforms together (per-platform breakdown in
        # generation_metadata for debugging).
        log_stage(
            run_id=self.state.run_id,
            agent_name="TypeHype V3 Generator",
            stage_order=3,
            output=self.state.draft,
            model_used=platform_drafts[0].model_used or "typehype-v3",
            tokens_used=total_typehype_tokens,
            status="success",
        )
        logger.info(
            f"[Flow] write_via_typehype done — platforms={[p.platform for p in platform_drafts]} "
            f"total_chars={sum(p.char_count for p in platform_drafts)} tokens={total_typehype_tokens}"
        )

    @router(write_via_typehype)
    def route_after_write(self) -> str:
        """After TypeHype write: continue to compliance, or fail."""
        if self.state.error:
            return "fail_branch"
        if not self.state.draft:
            return "fail_branch"
        return "compliance_step"

    @listen("compliance_step")
    def run_compliance(self) -> None:
        """Run rule-based compliance checks + 1 mini LLM voice critic.

        Deterministic Python — no agent LLM orchestration. Saves another ~$0.005/run.
        Returns None; @router(run_compliance) decides branch from self.state.
        """
        from tools import dedup_check, forbidden_topics_check, hard_rules_check, brand_voice_score
        from tools import load_account_config

        if not self.state.draft:
            self.state.error = "run_compliance: no draft in state"
            return  # router will see state.error and pick fail_branch

        content = self.state.draft.content
        cfg_fn = load_account_config.func if hasattr(load_account_config, "func") else load_account_config
        config = cfg_fn(self.state.account_id)
        forbidden_topics = config.get("forbidden_topics") or []

        # Compose a rich voice description for the critic LLM. Priority:
        # 1. hype_account_config.voice_description (free text the user wrote)
        # 2. user_settings.brand_voice (Creator Hub: tones/principles/avoid/audience)
        # 3. Generic fallback (rarely used in practice)
        voice_desc = config.get("voice_description")
        if not voice_desc:
            try:
                sb = make_supabase()
                acc = sb.table("connected_accounts").select("user_id").eq("id", self.state.account_id).limit(1).execute()
                acc_rows = acc.data if isinstance(acc.data, list) else []
                first_acc = acc_rows[0] if acc_rows and isinstance(acc_rows[0], dict) else {}
                user_id = first_acc.get("user_id")
                if user_id:
                    us = sb.table("user_settings").select("brand_voice").eq("user_id", user_id).limit(1).execute()
                    us_rows = us.data if isinstance(us.data, list) else []
                    us_first = us_rows[0] if us_rows and isinstance(us_rows[0], dict) else {}
                    bv = us_first.get("brand_voice") if isinstance(us_first.get("brand_voice"), dict) else {}
                    if bv:
                        tones_raw = bv.get("tones")
                        tones = tones_raw if isinstance(tones_raw, dict) else {}
                        top_tones = sorted(
                            tones.items(),
                            key=lambda x: -int(x[1]) if isinstance(x[1], (int, float)) else 0,
                        )[:3]
                        tones_str = ", ".join(
                            f"{k} %{v}" for k, v in top_tones
                            if isinstance(v, (int, float)) and v > 0
                        )
                        principles_raw = bv.get("principles")
                        principles = ", ".join(str(p) for p in (principles_raw if isinstance(principles_raw, list) else []))
                        avoid_raw = bv.get("avoid")
                        avoid = ", ".join(str(a) for a in (avoid_raw if isinstance(avoid_raw, list) else []))
                        audience_raw = bv.get("target_audience")
                        audience = audience_raw if isinstance(audience_raw, str) else ""
                        parts = []
                        if tones_str:
                            parts.append(f"Tones: {tones_str}")
                        if principles:
                            parts.append(f"Principles: {principles}")
                        if avoid:
                            parts.append(f"Avoid: {avoid}")
                        if audience:
                            parts.append(f"Audience: {audience}")
                        if parts:
                            voice_desc = ". ".join(parts) + "."
            except Exception as e:
                logger.warning(f"[Flow] could not load brand_voice for critic: {e}")
        voice_desc = voice_desc or "creator's authentic voice"

        # 4 checks (callable .func for raw, fallback to direct call)
        def _raw(t):
            return t.func if hasattr(t, "func") else t

        dedup = _raw(dedup_check)(content=content, account_id=self.state.account_id, days=7)
        forb = _raw(forbidden_topics_check)(content=content, forbidden_topics=forbidden_topics)
        hard = _raw(hard_rules_check)(content=content)
        voice = _raw(brand_voice_score)(content=content, voice_description=voice_desc, account_id=self.state.account_id)

        # Compliance only blocks on HARD failures (dedup / forbidden topics /
        # hard rules). Voice score is recorded as a signal but does NOT auto-
        # reject — humans review weak-voice drafts via the UI and that feedback
        # tunes the system over time. Once we have enough approved samples in
        # memory the threshold can be raised.
        VOICE_SCORE_FLOOR = 30  # purely advisory: scores below this are flagged
        approved = (
            dedup.get("passed", False)
            and forb.get("passed", False)
            and hard.get("passed", False)
        )

        reasons = []
        if not dedup.get("passed"):
            reasons.append(f"dedup similarity {dedup.get('max_similarity', 0)}")
        if not forb.get("passed"):
            reasons.append(f"forbidden topics: {forb.get('detected')}")
        if not hard.get("passed"):
            reasons.append(f"hard rules: {hard.get('violations')}")
        if voice.get("score", 0) < VOICE_SCORE_FLOOR:
            reasons.append(f"voice score low: {voice.get('score')}/100 (advisory)")

        self.state.compliance = ComplianceOutput(
            approved=approved,
            dedup_passed=bool(dedup.get("passed")),
            similarity_to_recent=float(dedup.get("max_similarity", 0.0)),
            forbidden_topics_detected=list(forb.get("detected") or []),
            hard_rules_violated=list(hard.get("violations") or []),
            brand_voice_score=int(voice.get("score", 0)),
            rejection_reason=("; ".join(reasons) if reasons else None),
            confidence=int(voice.get("score", 50)),
        )

        # Account voice critic LLM cost (~$0.0001-0.001)
        voice_tokens = 100  # approx — brand_voice_score uses ~100 tokens
        self.state.total_tokens += voice_tokens

        # Log compliance as stage 4
        log_stage(
            run_id=self.state.run_id,
            agent_name="Compliance (Flow)",
            stage_order=4,
            output=self.state.compliance,
            model_used=settings.model_fast,
            tokens_used=voice_tokens,
            status="success",
        )

        # Phase 26.H — CRO auto-freeze hook.
        # If cro_auto_freeze_on_violation is enabled and this run failed compliance
        # with a hard rules / forbidden topic violation, set executive_freeze=true
        # so subsequent runner ticks abort cheaply. Also log a CRO-attributed
        # executive_decision row for audit. Voice-only failures do NOT trigger
        # freeze — they're advisory.
        try:
            if not approved and (forb.get("detected") or hard.get("violations")):
                from tools.supabase_client import make_supabase as _make_sb
                sb = _make_sb()
                cfg_row = sb.table("hype_account_config").select(
                    "cro_auto_freeze_on_violation, executive_freeze"
                ).eq("account_id", self.state.account_id).limit(1).execute()
                first_cfg = (cfg_row.data or [None])[0]
                if isinstance(first_cfg, dict) and first_cfg.get("cro_auto_freeze_on_violation") and not first_cfg.get("executive_freeze"):
                    sb.table("hype_account_config").update({"executive_freeze": True})\
                        .eq("account_id", self.state.account_id).execute()
                    sb.table("executive_decisions").insert({
                        "account_id": self.state.account_id,
                        "role_responsible": "CRO",
                        "decision_type": "compliance_halt",
                        "decision_text": (
                            f"Auto-freeze: forbidden={forb.get('detected')} hard_rules={hard.get('violations')}"
                        ),
                        "target_table": "hype_account_config",
                        "old_value": {"executive_freeze": False},
                        "new_value": {"executive_freeze": True},
                        "triggered_by": "event_realtime",
                        "status": "auto_executed",
                        "rationale_memo": "CRO auto-freeze triggered by compliance violation",
                    }).execute()
                    logger.warning(
                        f"[CRO-auto-freeze] account={self.state.account_id} frozen due to compliance violation"
                    )
        except Exception as e:
            logger.warning(f"[CRO-auto-freeze] check failed (non-fatal): {e}")

    @router(run_compliance)
    def route_after_compliance(self) -> str:
        """Decide next branch based on compliance result + dry_run flag.

        Order: compliance → (visual?) → (video?) → publish/dry_run.
        Visual (Phase 21): if persona.visual_enabled, generate image first.
        Video  (Phase 23): if persona.video_enabled AND any target platform is
        a video platform (youtube/reels/tiktok), generate video after image.
        """
        if self.state.error:
            return "fail_branch"
        if not (self.state.compliance and self.state.compliance.approved):
            return "skip_branch"
        persona = self._resolve_persona()
        if persona and persona.get("visual_enabled"):
            return "visual_branch"
        if persona and persona.get("video_enabled") and self._has_video_target():
            return "video_branch"
        if self.state.dry_run:
            return "dry_run_branch"
        return "publish_branch"

    @listen("visual_branch")
    def generate_visual(self) -> None:
        """Generate Cansu's image via Wiro + 4-layer compliance gate.

        Tool-driven (no LLM agent in this V1 — scene picked heuristically).
        Failure here is NON-FATAL: we still route to publish/dry_run with no image.
        """
        import asyncio
        import json
        from tools.visual_director_tools import _generate_and_check_async

        persona = self._resolve_persona()
        if not persona:
            logger.warning("[Flow] visual_branch: no persona for account; skipping")
            return  # router sees no state.visual, falls through

        # Scene rotation per visual.md brand manifest: Tier 1 (60%, 3 scenes),
        # Tier 2 (30%, 2 scenes), Tier 3 (10%, 1 scene). Random weighted pick
        # plus high-aesthetic augmentation each run keeps variety + reduces the
        # "always same home-office" pattern that was capping aesthetic at ~0.50.
        import random

        # Phase 42.A (Berkay 2 Jun 2026) — composition_type is now the
        # authoritative routing primitive (see /debate decision doc at
        # projects/debates/2026-06-02-visual-routing/decisions.md). The
        # legacy face/conceptual visual_mode is kept ONLY as a scene-library
        # selector key, derived deterministically via the shim mapping.
        from schemas.visual import (
            composition_type_for_content_type,
            COMPOSITION_TO_VISUAL_MODE,
        )
        plan_content_type = getattr(self.state.plan, "content_type", None) if self.state.plan else None
        plan_composition_type = composition_type_for_content_type(plan_content_type)

        # Capstone Sub-cause A (4 Jun 2026) — Routing alignment.
        # The Visual Director's deterministic kernel can promote a content_type
        # whose plan_composition_type is 'cansu_scene' to 'brand_news_visual'
        # when a Tier-1 brand is detected in the trend topic (kernel Rule 3
        # via brand_extractor). Pre-fix: the scene picker honored the
        # content_type mapping ('cansu_scene' → visual_mode='face') even
        # though VD's actual decision was 'brand_news_visual'. Result: a
        # 'Turkish woman at desk / café / Bosphorus' scene rendered in the
        # brand panel of a split-screen video, producing a SECOND
        # Cansu-lookalike alongside the real Cansu in the top half.
        # Fix: run the kernel up front (sync, no LLM, ~1 ms). Use its
        # decision when it fires; otherwise fall through to content_type
        # mapping. Phase 42.B will handle prompt quality on top of this.
        try:
            from tools.visual_decision import _apply_constraint_kernel
            trend_topic_for_kernel = (
                getattr(self.state.trend, "topic", None) if self.state.trend else None
            )
            plan_voice_mode_for_kernel = (
                getattr(self.state.plan, "voice_mode", None) if self.state.plan else None
            )
            kernel_decision = _apply_constraint_kernel(
                content_type=plan_content_type,
                voice_mode=plan_voice_mode_for_kernel,
                trend_topic=trend_topic_for_kernel,
            )
        except Exception as e:
            logger.warning(f"[Flow] kernel pre-check failed (using plan): {e}")
            kernel_decision = None

        effective_composition_type = (
            kernel_decision[0] if kernel_decision else plan_composition_type
        )
        kernel_reason = kernel_decision[1] if kernel_decision else "no kernel rule"
        visual_mode = COMPOSITION_TO_VISUAL_MODE[effective_composition_type]
        logger.info(
            f"[Flow] visual_branch: content_type={plan_content_type} → "
            f"plan_composition={plan_composition_type} → "
            f"kernel={effective_composition_type} ({kernel_reason}) → "
            f"visual_mode={visual_mode}"
        )

        # Each entry: (scene_type, scene_description, outfit, mood, content_context, weight, mode)
        # Mood vocabulary must match schemas/visual.py VisualMood literal:
        # "professional" | "warm" | "cinematic" | "technical" | "casual"
        SCENE_LIBRARY: list[tuple[str, str, str, str, str, int, str]] = [
            # Tier 1 — 60% — home office, café, campus (face mode)
            ("home_office",
             "young Turkish woman at her home desk, open MacBook on a real wooden table, "
             "soft natural daylight from a side window, healthy indoor plants, books "
             "stacked on the desk, half-finished latte, modern minimalist Istanbul apartment",
             "soft cream knit sweater",
             "professional",
             "reviewing a laptop dashboard mid-thought, both hands naturally near keyboard or trackpad",
             20, "face"),
            ("coffee_shop",
             "young Turkish woman in a cozy third-wave Istanbul specialty coffee shop, "
             "sitting at a warm wooden table, MacBook open, latte art visible in foreground, "
             "soft window light, blurred barista counter background, real cafe ambiance",
             "casual oversized cardigan over a plain tee",
             "warm",
             "leaning slightly toward the laptop screen, headphones around neck, candid moment between thoughts",
             20, "face"),
            ("campus",
             "young Turkish woman on Istanbul university campus, modern brutalist building "
             "behind, autumn golden-hour light, leather backpack, walking unposed, "
             "fellow students slightly out of focus in background, photoreal documentary feel",
             "fitted dark jeans, casual sneakers, layered jacket",
             "casual",
             "mid-stride between buildings, glance toward camera but not posing",
             20, "face"),
            # Tier 2 — 30% — cinematic portrait, outdoor Istanbul (face mode)
            ("cinematic_portrait",
             "intimate cinematic portrait of a young Turkish woman, golden hour light "
             "rim-lighting one side of the face, shallow depth of field f/1.4, soft "
             "film grain, candid expression, mid-thought, magazine cover quality, "
             "shot on Leica or Hasselblad medium format aesthetic",
             "neutral tone simple top, no logos",
             "cinematic",
             "looking slightly off-camera, lost in thought, single subtle gesture (hand to chin or hair)",
             15, "face"),
            ("outdoor_istanbul",
             "young Turkish woman in Bebek or Beşiktaş neighborhood by the Bosphorus, "
             "sea-and-bridge backdrop softly blurred, evening light, real city texture, "
             "tourists/locals slightly visible blurred in background, walking moment",
             "denim jacket over a simple blouse, neutral colors",
             "warm",
             "natural smile, hands relaxed, casual stroll cadence",
             15, "face"),
            # Tier 3 — 10% — tutorial / talking-head pose (face mode)
            ("tutorial_pose",
             "young Turkish woman explaining something to camera mid-gesture, "
             "friendly approachable expression, clean home setup background, "
             "soft 3-point studio-style lighting but natural-looking, no harsh shadows",
             "smart casual button-up shirt rolled at sleeves",
             "technical",
             "one hand raised mid-explanation, eye contact direct but warm",
             10, "face"),
            # Phase 25.D — Conceptual scenes (persona-free, n8n Content Factory style)
            ("ai_interface",
             "modern AI assistant interface on a clean computer screen, floating "
             "data visualizations and chat bubbles, glowing accent elements, no people, "
             "minimalist office background out of focus, magazine-quality editorial photo",
             "",  # no outfit (no person)
             "technical",
             "interface elements arranged in clean composition, depth of field shallow",
             25, "conceptual"),
            ("neural_network",
             "abstract neural network visualization, interconnected glowing nodes and "
             "pathways, data streams flowing, cinematic sci-fi aesthetic, deep blue and "
             "cyan with electric purple accents, no people, expansive digital space",
             "",
             "cinematic",
             "centered composition, eye-level perspective, atmospheric lighting",
             25, "conceptual"),
            ("tech_office_no_people",
             "modern empty tech workspace at golden hour, multiple monitors with code "
             "and diagrams, mechanical keyboard, plants, single mug, soft natural light "
             "through floor-to-ceiling windows, NO people, NO faces, editorial photograph",
             "",
             "professional",
             "wide angle composition emphasizing space and tools, candid documentary",
             25, "conceptual"),
            ("abstract_digital",
             "abstract digital concept art representing AI and software, geometric shapes "
             "and gradient meshes, soft glow, futuristic but minimal, no people, "
             "magazine cover quality, photoreal 3D render aesthetic",
             "",
             "cinematic",
             "centered composition, symmetric balance, atmospheric depth",
             25, "conceptual"),
            # Phase 25.D — Hybrid (Cansu small overlay + product/UI baskın)
            ("cansu_ui_overlay",
             "split composition: large product UI mockup or pricing table on left "
             "(70% of frame, sharp, in focus), small candid portrait of young Turkish "
             "woman on right (30%, soft focus, looking at the product), warm editorial "
             "lighting, magazine cover quality, photoreal",
             "soft cream knit sweater (visible only in small portrait portion)",
             "professional",
             "presenting / showcasing the product, subtle gesture toward UI",
             100, "conceptual"),  # Phase 39 — was 'hybrid', now collapsed to conceptual
        ]

        # Filter to current mode, then weighted random within mode
        scenes_in_mode = [s for s in SCENE_LIBRARY if s[6] == visual_mode]
        if not scenes_in_mode:
            logger.warning(
                f"[Flow] no scenes registered for mode={visual_mode}; falling back to face"
            )
            scenes_in_mode = [s for s in SCENE_LIBRARY if s[6] == "face"]
        weights = [s[5] for s in scenes_in_mode]
        picked = random.choices(scenes_in_mode, weights=weights, k=1)[0]
        scene_type, scene_description, outfit, mood, content_context, _, _ = picked

        # Phase 34 + 42.B — Brand awareness for conceptual mode.
        # WhatsApp/Anthropic gibi haberlerde Cansu YERINE brand logo + UI çıkar.
        # face mode'da Cansu baskın kalır (lifestyle content_type'ları).
        # Phase 39 — hybrid mode kaldırıldı, conceptual'a birleştirildi.
        #
        # Phase 42.B-07 (4 Jun 2026): when settings.brand_brief_builder_enabled
        # is True, try the structured labeled-prose brief from
        # backend/prompts/brand_visual_brief_builder. On any failure mode
        # (import error, no brands, builder None, builder exception) fall
        # back to the existing Phase 34 single-brand path unchanged. When the
        # flag is OFF, behavior is byte-for-byte identical to pre-42.B code:
        # the Phase 42.B block is skipped entirely and the Phase 34 block
        # runs as it did before.
        brand_used: str | None = None
        brand_brief_state: str = "disabled"   # 'disabled' = flag was OFF
        brand_brief_payload: dict | None = None  # surfaced on visual_brief_json

        if visual_mode == "conceptual":
            # ── Phase 42.B-07 attempt (flag-gated, default OFF) ─────────
            if settings.brand_brief_builder_enabled:
                (
                    brand_brief_state,
                    brand_brief_payload,
                    _42b_overrides,
                ) = _try_phase42b_brand_brief(
                    trend_topic=getattr(self.state.trend, "topic", None),
                    content_type=plan_content_type,
                )
                if brand_brief_state == "success":
                    scene_description = _42b_overrides["scene_description"]
                    content_context = _42b_overrides["content_context"]
                    brand_used = _42b_overrides["brand_used"]

            # ── Phase 34 path (UNCHANGED from pre-42.B code) ────────────
            # Runs when flag is OFF, or when the 42.B path did not yield
            # 'success'. Preserves byte-for-byte behavior of the pre-42.B
            # path for the OFF case.
            if brand_brief_state != "success":
                try:
                    from tools.brand_extractor import extract_brand_from_topic, build_brand_subject
                    trend_topic = getattr(self.state.trend, "topic", None) or ""
                    brand_used = extract_brand_from_topic(trend_topic)
                    if brand_used:
                        brand_subject = build_brand_subject(brand_used, visual_mode)
                        if brand_subject:
                            # Override scene_description tamamen (conceptual) veya
                            # foreground odağı değiştir (hybrid).
                            if visual_mode == "conceptual":
                                scene_description = brand_subject
                                content_context = (
                                    f"Product showcase frame featuring {brand_used} branding."
                                )
                            else:  # hybrid
                                scene_description = (
                                    f"{brand_subject}\n"
                                    f"Background lifestyle hint: {scene_description}"
                                )
                except Exception as e:
                    logger.warning(f"[Flow] brand extractor failed (continuing without): {e}")

        # High-aesthetic augmentation appended to scene_description — this lifts
        # aesthetic predictor scores from ~0.50 (sub-threshold) to ~0.60+ in
        # ad-hoc tests by pushing the model toward magazine-quality output.
        aesthetic_suffix = (
            ". Magazine-quality editorial photograph, professional photographer's "
            "single still from a lifestyle shoot, soft contrast, warm color grading, "
            "natural skin texture with visible pores, shallow depth of field, "
            "photoreal raw camera feel, no AI-look, no plastic skin, no over-smoothing"
        )
        scene_description_augmented = scene_description + aesthetic_suffix

        logger.info(
            f"[Flow] visual_branch: scene={scene_type} mood={mood} "
            f"mode={visual_mode} brand={brand_used or 'none'} "
            f"(weighted random from {len(scenes_in_mode)} scenes)"
        )

        # Phase 41.B — resolve the *real* Strategist signals so the Visual
        # Decision Agent (Phase 39) actually sees the news headline,
        # content_type and voice_mode instead of a scene description.
        from schemas.plan import voice_mode_for_content_type
        plan_voice_mode_val = getattr(self.state.plan, "voice_mode", None) if self.state.plan else None
        if not plan_voice_mode_val and plan_content_type:
            plan_voice_mode_val = voice_mode_for_content_type(plan_content_type)
        trend_topic_val = getattr(self.state.trend, "topic", None) if self.state.trend else None

        # Phase 42.B-10B — only pass the override when the flag is ON AND
        # the builder fired successfully. On any other state (flag OFF,
        # no_brand_entities, builder_returned_none, builder_import_failed,
        # builder_failed) we leave the parameter at its default (None) so
        # _generate_and_check_async falls back to the pre-existing
        # nano_banana_builder rewrite — byte-for-byte unchanged production
        # behavior.
        # Cansu frame i2i path — faceless framed news card via a SINGLE Wiro
        # Nano Banana Pro img2img call (frame template = input_image; model
        # fills the hero area + writes the headline). Flag-gated: when OFF the
        # existing brand/face path below runs byte-for-byte unchanged.
        if settings.cansu_frame_i2i_enabled:
            from tools.framed_news_image import generate_framed_news_image_async
            from tools.news_headline import generate_news_headline_async

            # Headline: a grounded ONE-sentence Turkish headline built from the
            # trend's REAL source content (trends.raw_content) — factually
            # accurate, no hallucination (aligns with the false-facts gate).
            # Falls back to the topic when source/LLM is unavailable.
            _raw_content = None
            try:
                _tid = getattr(self.state.trend, "trend_id", None) if self.state.trend else None
                if _tid:
                    _hrow = (
                        make_supabase().table("trends").select("raw_content")
                        .eq("id", _tid).limit(1).execute()
                    )
                    if _hrow.data:
                        _raw_content = _hrow.data[0].get("raw_content")
            except Exception as e:
                logger.warning(f"[Flow] frame_i2i raw_content fetch failed: {e}")
            frame_headline = asyncio.run(
                generate_news_headline_async(
                    topic=trend_topic_val or "", source_text=_raw_content
                )
            ) or (trend_topic_val or "").strip()
            # Hero concept: minimal-text, varied composition (keeps the real
            # brand logo, kills the gibberish-UI / always-a-tablet AI tell).
            # build_frame_hero_concept rotates archetypes by topic.
            from tools.framed_news_image import build_frame_hero_concept
            _frame_brand = None
            try:
                from tools.brand_extractor import extract_brand_from_topic
                _frame_brand = extract_brand_from_topic(trend_topic_val or "")
            except Exception as e:
                logger.warning(f"[Flow] frame_i2i brand extractor failed: {e}")
            frame_hero_concept = build_frame_hero_concept(
                _frame_brand, trend_topic_val or scene_description
            )

            try:
                result = asyncio.run(
                    generate_framed_news_image_async(
                        persona_id=persona["id"],
                        headline=frame_headline,
                        hero_concept=frame_hero_concept,
                        daily_draft_id=None,  # filled later by _write_daily_draft via asset link
                    )
                )
            except Exception as e:
                logger.exception(f"[Flow] frame_i2i generation failed: {e}")
                # Non-fatal — proceed to publish without image
                return
        else:
            _42b_override_kwargs: dict = {}
            if (
                settings.brand_brief_builder_enabled
                and brand_brief_state == "success"
            ):
                _42b_override_kwargs["brand_brief_override"] = scene_description_augmented

            try:
                result = asyncio.run(
                    _generate_and_check_async(
                        persona_id=persona["id"],
                        platform="instagram",  # square aspect; cross-posts as 1:1 too
                        scene_description=scene_description_augmented,
                        outfit=outfit,
                        mood=mood,
                        content_context=content_context,
                        daily_draft_id=None,  # filled later by _write_daily_draft via asset link
                        visual_mode=visual_mode,  # Phase 25.D
                        # Phase 41.B — feed real headline/content_type/voice_mode
                        trend_topic=trend_topic_val,
                        plan_content_type=plan_content_type,
                        voice_mode=plan_voice_mode_val,
                        **_42b_override_kwargs,
                    )
                )
            except Exception as e:
                logger.exception(f"[Flow] visual_branch generation failed: {e}")
                # Non-fatal — proceed to publish without image
                return

        if result.get("status") != "ok":
            logger.warning(f"[Flow] visual_branch returned error: {result.get('error')}")
            return

        # Phase 42.B-07 — surface the brand-brief-builder state on
        # result['visual_brief_json'] so the StageDetails accordion shows
        # which path fired (success / no_brand_entities / builder_returned_none
        # / builder_import_failed / builder_failed). When the flag was OFF,
        # brand_brief_payload is None and we leave the existing
        # nano_banana_builder output (set by visual_director_tools) untouched.
        if settings.brand_brief_builder_enabled and brand_brief_payload is not None:
            result["visual_brief_json"] = brand_brief_payload

        comp = result.get("compliance") or {}
        # Phase 41.E — pull the Visual Decision Agent snapshot so it lands
        # on hype_stages.output and becomes visible in the UI.
        vd = result.get("visual_decision") or {}
        # Phase 42.B — Nano Banana JSON brief surfaced for StageDetails
        # accordion (which SUBJECT_TEMPLATE variant fired, with what slots).
        nb_brief = result.get("visual_brief_json")
        self.state.visual = VisualDirectorOutput(
            needs_visual=True,
            visual_mode=visual_mode,  # Phase 25.D
            composition_type=vd.get("composition_type"),  # Phase 42.A
            scene_type=scene_type,
            scene_description=scene_description_augmented,
            mood=mood,
            outfit=outfit,
            content_context=content_context,
            aspect_ratio="1:1",
            rationale=(
                f"composition_type={vd.get('composition_type') or 'unknown'} "
                f"(content_type={plan_content_type}, via={vd.get('via') or 'n/a'}); "
                f"scene weighted random within visual_mode={visual_mode}"
            ),
            asset_id=result.get("asset_id"),
            image_url=result.get("image_url"),
            model_slug=result.get("model_slug"),
            cost_usd=result.get("cost_usd"),
            latency_ms=result.get("latency_ms"),
            clip_similarity=comp.get("clip"),
            aesthetic_score=comp.get("aesthetic"),
            ocr_flagged=comp.get("ocr_flagged"),
            compliance_verdict=comp.get("final_verdict") or "SKIPPED",
            compliance_reasoning=comp.get("llm_reasoning"),
            # Phase 42.B — Nano Banana brief
            visual_brief_json=nb_brief if isinstance(nb_brief, dict) else None,
            # Phase 41.E — Visual Decision Agent snapshot
            visual_decision_needs_cansu=vd.get("needs_cansu"),
            visual_decision_reason=vd.get("reason"),
            visual_decision_path=vd.get("path"),
            visual_decision_model=vd.get("model"),
        )
        logger.info(
            f"[Flow] visual generated: asset={self.state.visual.asset_id} "
            f"verdict={self.state.visual.compliance_verdict} "
            f"cost=${self.state.visual.cost_usd}"
        )

        # Log as stage 5 (after compliance is stage 4)
        log_stage(
            run_id=self.state.run_id,
            agent_name="Visual Director",
            stage_order=5,
            output=self.state.visual,
            model_used=self.state.visual.model_slug or "",
            tokens_used=0,
            status="success",
        )

    @router(generate_visual)
    def route_after_visual(self) -> str:
        """After visual: video if persona.video_enabled + has video target, else publish/dry_run."""
        if self.state.error:
            return "fail_branch"
        persona = self._resolve_persona()
        if persona and persona.get("video_enabled") and self._has_video_target():
            return "video_branch"
        if self.state.dry_run:
            return "dry_run_branch"
        return "publish_branch"

    # ─── Phase 23 — Video branch ────────────────────────────────────────────

    def _has_video_target(self) -> bool:
        """True if any of the resolved target platforms is a video platform."""
        plats = {p.lower() for p in (self.state.target_platforms or [])}
        return bool(plats & _VIDEO_PLATFORMS)

    def _resolve_video_target_platform(self) -> Optional[str]:
        """Pick which platform target drives the video script.

        Priority: youtube > instagram-reels > tiktok. Returns the literal
        platform string used in PlatformDraft (e.g. 'youtube', 'instagram-reels').
        """
        plats = [p.lower() for p in (self.state.target_platforms or [])]
        for preferred in ("youtube", "youtube-shorts", "instagram-reels", "tiktok"):
            if preferred in plats:
                return preferred
        return None

    # SEV-1 follow-up P0 (2026-06-07) — single canonical video script.
    # Berkay's spec (a): one render, one canonical script, every video
    # platform shows that script as its caption. No more
    # "video says X, YouTube caption says a 593-char Y".
    # PART 4 (2026-06-07 follow-up): the cap must respect the MOST
    # restrictive video target's platform limit. _VIDEO_PLATFORMS
    # includes youtube-shorts (60s hard cap), instagram-reels (90s
    # cap). Clamping canonical to the Shorts cap (60s × ~17 cps + a
    # safety margin for pause markers) keeps the cure from swinging
    # from "too short → truncated" to "rejected for too long".
    # 1000 chars ≈ 56-60s narration; safely under Shorts and Reels.
    # MiniMax API limit is 5000 chars; HeyGen avatar_v audio-length
    # bound; neither caps below 1000.
    CANONICAL_VIDEO_SCRIPT_CAP_CHARS = 1000   # ~60s @ ~17 cps; Shorts-safe

    def _resolve_video_script(self, target_platform: str) -> str:
        """Pick THE canonical narration script for this run.

        Replaces the previous "trim everything to 300 chars" heuristic
        that caused the SEV-1 truncation: a 744-char YouTube draft was
        sent to TTS as 300 chars → ~18s audio → 18s video → caption
        promised more than the voice-over delivered.

        New rule: prefer the LONGEST video-platform draft (within the
        canonical cap) so the narration covers the richest available
        text. Tie-break: youtube > linkedin > instagram > twitter.
        2026-06-10 — caption pinning kaldırıldı (Berkay): bu script yalnız
        TTS/video için kullanılır; platform caption'ları kendi lugatlarında
        yazılmış halleriyle yayınlanır.
        """
        target_platform = (target_platform or "").lower()

        # Priority order: target_platform first, then preferred video
        # platforms by descending content budget.
        _PRIORITY = [target_platform, "youtube", "linkedin", "instagram", "twitter", "x"]
        seen: set[str] = set()

        candidates: list[tuple[int, str, str]] = []  # (chars, platform, content)
        for plat_name in _PRIORITY:
            if plat_name in seen or not plat_name:
                continue
            seen.add(plat_name)
            for pd in self.state.platform_drafts:
                if pd.platform.lower() == plat_name:
                    candidates.append((len(pd.content or ""), pd.platform, pd.content or ""))
                    break

        if not candidates:
            return self.state.draft.content if self.state.draft else ""

        # Sort: longest first (within cap), break ties by priority order.
        cap = self.CANONICAL_VIDEO_SCRIPT_CAP_CHARS
        in_cap = [(c, p, t) for (c, p, t) in candidates if c <= cap]
        if in_cap:
            in_cap.sort(key=lambda r: -r[0])
            chosen_chars, chosen_plat, chosen_text = in_cap[0]
            logger.info(
                f"[Flow] video canonical script: platform={chosen_plat} "
                f"chars={chosen_chars}"
            )
            return chosen_text
        # Every candidate is over the cap — pick the smallest one that's
        # still over (and truncate it at cap on sentence boundary).
        candidates.sort(key=lambda r: r[0])
        chosen_chars, chosen_plat, chosen_text = candidates[0]
        truncated = chosen_text[:cap].rsplit(" ", 1)[0].rstrip(",.;:!?") + "."
        logger.warning(
            f"[Flow] video canonical script OVER cap: platform={chosen_plat} "
            f"raw_chars={chosen_chars} → trimmed to {len(truncated)}"
        )
        return truncated

    # ── cansu_video_v2 — complete-news narration (Berkay 10 Haz 2026) ──
    # Reel viewer must LEARN the whole news. Dedicated writer + autonomous
    # script_lint gate + tts_normalize, weak sources skipped. All behind the
    # cansu_video_v2_enabled flag; OFF → legacy _resolve_video_script path.
    V2_SCRIPT_MIN_CHARS = 380   # ~22s floor — below this isn't a complete telling
    V2_SCRIPT_MAX_CHARS = 685   # ~40s ceiling at the locked 1.1/light prosody

    def _video_source_text(self) -> tuple[str, str]:
        """(topic, full source text) for the current trend — for the v2 path.

        Prefers the cached raw_content+source_tweets union (the same full
        source the faithfulness gate saw), falls back to the
        trends.full_source_text column.
        """
        trend = getattr(self.state, "trend", None)
        topic = (getattr(trend, "topic", "") or "") if trend else ""
        tid = getattr(trend, "trend_id", None) if trend else None
        src = ""
        if tid:
            src = (self.state.trend_raw_content_cache or {}).get(tid, "") or ""
        if not src and tid:
            try:
                rows = (make_supabase().table("trends")
                        .select("full_source_text, raw_content")
                        .eq("id", tid).limit(1).execute()).data
                if rows:
                    src = rows[0].get("full_source_text") or rows[0].get("raw_content") or ""
            except Exception as e:
                logger.debug(f"[Flow] v2 source lookup failed: {e}")
        return topic, src

    def _richest_draft_text(self) -> str:
        """En zengin generated draft içeriği (devto > linkedin > twitter) — v2
        video kaynağını beslemek için. Draft zaten faithfulness'tan geçti, yani
        tweet ötesi OLGU yok; sadece dolu anlatım + Cansu açısı. (2026-06-12)"""
        drafts = getattr(self.state, "platform_drafts", None) or []
        _pri = {"devto": 3.0, "linkedin": 2.0, "twitter": 1.0}
        best = ""
        best_rank = -1.0
        for pd in drafts:
            c = (getattr(pd, "content", "") or "").strip()
            if not c:
                continue
            rank = _pri.get((getattr(pd, "platform", "") or "").lower(), 0.0) + len(c) / 10000.0
            if rank > best_rank:
                best_rank = rank
                best = c
        return best

    def _resolve_complete_news_script(self, topic: str, source: str) -> Optional[str]:
        """Complete-news narration through the autonomous gate.

        writer → assemble(+trim to ≤40s) → tts_normalize → script_lint.
        On a lint block: 1 retry (regenerate). Still blocked → None and the
        caller falls back to image-only. Length is deterministic (the assembler
        trims), so the retry is spent only on content artifacts (self-ref /
        banned char / in-body CTA), never on length.
        """
        import asyncio
        from tools.video_script_writer import (
            build_complete_news_script, assemble_complete_news, pick_outro,
        )
        from tools.tts_normalize import normalize_for_tts
        from tools.video_script_lint import lint_video_script

        outro = pick_outro(topic)
        for attempt in (1, 2):  # 1 try + 1 retry
            try:
                body = asyncio.run(build_complete_news_script(topic=topic, source=source))
            except Exception as e:
                logger.warning(f"[Flow] v2 writer error (attempt {attempt}): {e}")
                body = None
            if not body:
                continue
            script = normalize_for_tts(assemble_complete_news(body, topic))
            r = lint_video_script(script, outro=outro)
            if r.ok:
                logger.info(
                    f"[Flow] v2 script clean (attempt {attempt}): {len(script)}c "
                    f"exp={r.expected_duration_s:.1f}s"
                )
                return script
            logger.warning(
                f"[Flow] v2 script blocked (attempt {attempt}): codes={r.codes} | "
                + "; ".join(f"{v.code}:{v.detail}" for v in r.violations)
            )
        return None

    async def _resolve_anchor_url(self, persona_id: str) -> Optional[str]:
        """Get a short-lived signed URL for a persona anchor portrait.

        Falls back to the just-generated visual image URL (already public)
        if no anchors exist. Returns None if neither is available.
        """
        try:
            from tools.reference_anchors import (
                load_persona_anchors, prepare_reference_prompt_inputs,
            )
            anchors = await load_persona_anchors(persona_id)
            if anchors:
                refs = await prepare_reference_prompt_inputs(anchors, max_prompt_inputs=1)
                if refs.signed_reference_urls:
                    return refs.signed_reference_urls[0]
        except Exception as e:
            logger.warning(f"[Flow] anchor resolution failed: {e}; falling back to visual")
        if self.state.visual and self.state.visual.image_url:
            return self.state.visual.image_url
        return None

    @listen("video_branch")
    def generate_video(self) -> None:
        """Phase 23 — Produce lip-sync video (Türkçe TTS + talking head + FFmpeg).

        Triggered when persona.video_enabled AND target_platforms intersect
        {youtube, instagram-reels, tiktok}. Pipeline choice comes from
        ``personas.video_pipeline_default`` (defaults to 'talking_head_memo').

        Failure is NON-FATAL — flow continues to publish/dry_run without video.
        """
        import asyncio
        from tools.video_pipeline import VideoBrief, get_pipeline

        persona = self._resolve_persona()
        if not persona:
            logger.warning("[Flow] video_branch: no persona; skipping")
            return

        target_platform = self._resolve_video_target_platform()
        if not target_platform:
            logger.info("[Flow] video_branch: no video target platform; skipping")
            return

        # Phase 35.3 — Video worthiness gate (Berkay 30 May 2026: "her haber
        # için video yapamayız, haber skoru çok yüksek olanlar için yapılmalı").
        # Score-based threshold doesn't work because text+image baseline ≈ 67;
        # instead TrendScout emits a separate semantic boolean `video_worthy`
        # — only major launches / breaking news / milestones get True.
        try:
            trend = getattr(self.state, "trend", None) if getattr(self, "state", None) else None
            video_worthy = bool(getattr(trend, "video_worthy", False)) if trend else False
            trend_is_vip = bool(getattr(trend, "is_vip", False)) if trend else False
            # is_vip alone also unlocks video (VIP source = OpenAI/Anthropic/etc
            # direct announcement is always worth a video).
            if not (video_worthy or trend_is_vip):
                video_reason = (getattr(trend, "video_reason", "") or "—") if trend else "—"
                logger.info(
                    f"[Flow] video_branch: trend not video_worthy "
                    f"(worthy={video_worthy} vip={trend_is_vip} reason='{video_reason}'); "
                    f"skipping video (text+image still runs)"
                )
                return
            logger.info(
                f"[Flow] video worthiness gate OK: worthy={video_worthy} vip={trend_is_vip}"
            )
        except Exception as e:
            logger.warning(f"[Flow] video worthiness gate error (continuing): {e}")

        _v2 = settings.cansu_video_v2_enabled
        if _v2:
            # Weak-source gate: a thin source cannot be told completely without
            # hallucination (a 149-char source invented "Navya/Waymo"), so we
            # skip video entirely and let the image-only post stand.
            topic_v2, _raw_src = self._video_source_text()  # ham tweet = OLGU çapası
            # 2026-06-12 (Berkay): YAZIM kaynağını crew'un zengin draft'ıyla
            # besle (devto makalesi ~1000c). Tweet'ler ince (141-450c) olduğu
            # için video neredeyse hiç çıkmıyordu. Draft zaten faithfulness'tan
            # geçti → tweet ötesi OLGU yok, sadece dolu anlatım + Cansu açısı.
            # OLGU-denetimi yine HAM tweet'e karşı (aşağıda) — uydurma engellenir,
            # YORUM serbest.
            _draft_src = self._richest_draft_text()
            source_v2 = _raw_src
            if _draft_src and len(_draft_src) > len(_raw_src):
                source_v2 = (
                    _raw_src
                    + "\n\n[Cansu'nun tam anlatımı — yazım malzemesi]\n"
                    + _draft_src
                ).strip()
            min_src = settings.cansu_video_min_source_chars
            if len(source_v2) < min_src:
                logger.info(
                    f"[Flow] video_branch v2: weak source ({len(source_v2)}c < "
                    f"{min_src}); skipping video (image-only stands)"
                )
                return
            script = self._resolve_complete_news_script(topic_v2, source_v2)
            if not script:
                logger.warning(
                    "[Flow] video_branch v2: script failed lint gate after retry; "
                    "skipping video (image-only stands)"
                )
                return
            # OLGU-KATILIK (Berkay: "bilgi uydurmasın, çok katı; ama yorum
            # serbest"). Üretilen script'i HAM TWEET'e karşı faithfulness'tan
            # geçir: kaynakta OLMAYAN sayı/isim/iddia → HARD_BLOCK → render
            # İPTAL (image-only ayakta, HeyGen'e $ gitmez). Yorum/çerçeve →
            # arbiter fp/minor → geçer (Cansu'nun açısı korunur).
            try:
                import asyncio as _aio_fg
                from tools.faithfulness_gate import run_faithfulness_gate as _rfg
                _fv = _aio_fg.run(_rfg(draft_text=script, source_raw_content=_raw_src))
                if _fv.is_block:
                    logger.warning(
                        f"[Flow] video_branch v2: script UYDURMA içeriyor "
                        f"(ham tweet'e sadık değil) — render İPTAL: "
                        f"{str(getattr(_fv, 'reasoning', ''))[:160]}"
                    )
                    return
                logger.info(
                    "[Flow] video_branch v2: script faithfulness OK "
                    "(ham tweet grounding, olgu-katı)"
                )
            except Exception as _fe:  # fail-closed — şüphede video çıkmasın
                logger.warning(
                    f"[Flow] video script faithfulness hatası (fail-closed, "
                    f"render iptal): {type(_fe).__name__}: {_fe}"
                )
                return

            # SON SAVUNMA — render ÖNCESİ konu-tutarlılık kapısı (2026-06-11,
            # Berkay: "bir daha hata görmek istemiyorum"). Video anlatımı, post
            # caption'ı (operatörün yer-gerçeği) ile AYNI OLAYI anlatmıyorsa
            # HeyGen'e tek dolar gitmeden video iptal → image-only ayakta kalır.
            # Kök fix (trend_engine) kaynağı temizledi; bu, gelecekte HERHANGİ
            # bir yoldan sapma olursa parayı ve yanlış yayını durduran kilit.
            _caption = self.state.draft.content if self.state.draft else ""
            if _caption.strip():
                try:
                    from tools.video_topic_guard import check_script_matches_caption
                    _verdict = check_script_matches_caption(
                        script=script, caption=_caption, topic=topic_v2,
                    )
                except Exception as _ge:  # fail-closed
                    logger.warning(f"[Flow] video topic guard error (engelleniyor): {_ge}")
                    _verdict = None
                if _verdict is None or not _verdict.match:
                    _why = (
                        f"video='{_verdict.video_konusu}' post='{_verdict.post_konusu}' "
                        f"({_verdict.reason})" if _verdict else "hakem hatası (fail-closed)"
                    )
                    logger.warning(
                        f"[Flow] video_branch v2: KONU UYUŞMAZLIĞI — render İPTAL "
                        f"(image-only stands): {_why}"
                    )
                    try:
                        from tools.alerter import send_alert
                        send_alert(
                            "Video konu uyuşmazlığı — render iptal edildi",
                            severity="WARN",
                            platform=target_platform,
                            reason=(
                                f"Video anlatımı post ile farklı haberi anlatıyordu, "
                                f"render başlamadan durduruldu (para harcanmadı). {_why}"
                            ),
                            action="Otomatik korundu; gerekirse trendin kaynağını kontrol et.",
                            extra={"topic": topic_v2[:120]},
                        )
                    except Exception:
                        pass
                    return
        else:
            script = self._resolve_video_script(target_platform).strip()
            if not script:
                logger.warning("[Flow] video_branch: empty script; skipping")
                return
        # SEV-1 follow-up P0 (2026-06-07): the old hard 300-char cap was
        # the production-side truncation cause — a 593-char YouTube
        # caption was sent to TTS as 300 chars → ~18s audio → 18s
        # video → caption-vs-voice mismatch. _resolve_video_script now
        # honors CANONICAL_VIDEO_SCRIPT_CAP_CHARS=1500 (HeyGen +
        # MiniMax handle ~90s narration comfortably) and the cap-side
        # truncation already happened there if it was needed. No
        # second-layer trim.
        # NOTE (2026-06-08): caption pinning MOVED to after a SUCCESSFUL render
        # (below, once self.state.video is set). It used to run here — before
        # the render — so when the video failed or was skipped (image-only
        # post), every video-platform caption was still overwritten with the
        # one canonical script, making LinkedIn and Instagram identical. Pin
        # only when a video actually exists for the caption to match.

        pipeline_id = (persona.get("video_pipeline_default") or "talking_head_memo").strip()

        # Phase 35.2.8 — daily_video_budget guard (per-persona daily cost cap)
        # Checks total cost_usd from today's hype_runs for this persona's account.
        # If today + expected per-video ≥ budget, skip video stage gracefully.
        try:
            from datetime import datetime, timezone
            budget = float(persona.get("daily_video_budget_usd") or 0) or 5.0
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
            account_id = self.state.account_id
            spent = 0.0
            if account_id:
                try:
                    res = self.sb_admin.table("hype_runs").select("total_cost_usd")\
                        .eq("account_id", account_id)\
                        .gte("started_at", today_start)\
                        .execute()
                    for r in (res.data or []):
                        spent += float(r.get("total_cost_usd") or 0)
                except Exception as e:
                    logger.debug(f"[Flow] video budget query failed: {e}")
            # 2026-06-10 — render defteri görünürlüğü: ölen/öksüz denemelerin
            # harcaması hype_runs'a hiç yazılmıyordu, bütçe kör kalıyordu
            # (bugün cap fiilen aşıldı ama sistem görmedi). Defterdeki
            # consumed-OLMAYAN bugünkü kayıtlar da sayılır (consumed olanlar
            # run maliyetine girer — çift sayım yok).
            try:
                from tools.video_render_ledger import unconsumed_spend_today
                _persona_row = self._resolve_persona() or {}
                _pid = _persona_row.get("id")
                if _pid:
                    _orphan = unconsumed_spend_today(_pid)
                    if _orphan:
                        logger.info(
                            f"[Flow] video budget: +${_orphan:.2f} defter "
                            f"(öksüz/yolda render'lar)"
                        )
                    spent += _orphan
            except Exception as e:
                logger.debug(f"[Flow] render-ledger budget add failed: {e}")
            estimated_per_video = 2.10  # ~$2 Avatar V (20s) + MiniMax + storage
            if spent + estimated_per_video > budget:
                logger.warning(
                    f"[Flow] video_branch: daily budget exhausted "
                    f"(${spent:.2f} spent + ${estimated_per_video:.2f} est "
                    f"> ${budget:.2f} cap); skipping video"
                )
                return
            logger.info(
                f"[Flow] video budget OK: spent=${spent:.3f} "
                f"cap=${budget:.2f} estimated_next=${estimated_per_video:.2f}"
            )
        except Exception as e:
            logger.warning(f"[Flow] video budget guard error (continuing): {e}")

        logger.info(
            f"[Flow] video_branch: pipeline={pipeline_id} target={target_platform} "
            f"script_chars={len(script)}"
        )

        try:
            pipeline = get_pipeline(pipeline_id)
        except ValueError as e:
            logger.warning(f"[Flow] video_branch: {e}; falling back to talking_head_memo")
            pipeline = get_pipeline("talking_head_memo")

        persona_id = persona["id"]

        # Phase 35.3 — split-screen pipeline needs scene_descriptions for
        # the Wiro Seedream slideshow top half. Derive 3 brand-aware scenes
        # from the trend topic; pass as JSON inside action_prompt so the
        # pipeline's `produce_video()` can parse them.
        action_prompt: Optional[str] = None
        if pipeline_id == "heygen_split_screen":
            import json as _json
            from tools.brand_extractor import extract_brand_from_topic, build_brand_subject

            trend_topic = ""
            try:
                trend_topic = (
                    getattr(self.state.trend, "topic", "") or ""
                ) if getattr(self.state, "trend", None) else ""
            except Exception:
                trend_topic = ""

            brand = extract_brand_from_topic(trend_topic) or ""
            brand_subject = build_brand_subject(brand, "conceptual") if brand else ""
            scenes: list[str] = []
            if brand_subject:
                scenes.append(brand_subject)
                scenes.append(
                    f"Editorial wide shot: {brand} product context, futuristic "
                    f"workspace ambiance, soft cinematic lighting, no people, "
                    f"abstract tech atmosphere."
                )
                scenes.append(
                    f"Close-up macro: stylised UI elements and circuitry "
                    f"referencing {brand}, dramatic key light, shallow depth "
                    f"of field, no faces."
                )
            else:
                # Generic news visual fallback (brand-less trend)
                topic_hint = trend_topic[:80] if trend_topic else "AI breakthrough"
                scenes = [
                    (
                        f"Editorial tech news visual: stylised abstract scene "
                        f"representing '{topic_hint}', cinematic lighting, no "
                        f"people, modern aesthetic, vertical 1:1 framing."
                    ),
                    (
                        "Futuristic data visualisation, soft neon glow, "
                        "circuit-like patterns, abstract tech wallpaper, no "
                        "people, editorial product photography mood."
                    ),
                    (
                        "Clean minimalist tech workspace, modern device "
                        "screen showing abstract UI, soft window light, no "
                        "faces, brand-neutral editorial shot."
                    ),
                ]
            action_prompt = _json.dumps(scenes)
            logger.info(
                f"[Flow] video_branch: split-screen scenes derived "
                f"(brand={brand or 'none'}, count={len(scenes)})"
            )

        async def _run() -> Optional[StoredVideoAsset]:
            anchor_url = await self._resolve_anchor_url(persona_id)
            if not anchor_url:
                logger.warning("[Flow] video_branch: no anchor URL available; skipping")
                return None
            brief = VideoBrief(
                script_text=script,
                persona_id=persona_id,
                anchor_image_url=anchor_url,
                action_prompt=action_prompt,
                target_aspect="9:16",
                target_duration=15,
                daily_draft_id=getattr(self.state, "daily_draft_id", None),
                script_min_chars=self.V2_SCRIPT_MIN_CHARS if _v2 else None,
                script_max_chars=self.V2_SCRIPT_MAX_CHARS if _v2 else None,
                # TTS kalite kapısı kötü ses bulursa script'i bunlardan yeniden üretir.
                topic=(topic_v2 if _v2 else ""),
                source=(source_v2 if _v2 else ""),
            )
            return await pipeline.produce_video(brief)

        try:
            asset = asyncio.run(_run())
        except Exception as e:
            logger.exception(f"[Flow] video_branch generation failed: {e}")
            return

        if not asset:
            return

        self.state.video = VideoOutput.from_asset(asset, target_platform=target_platform)
        # 2026-06-10 (Berkay): caption pinning KALDIRILDI — "metin aynı
        # olmasına gerek yok". Video kendi script'ini konuşur; IG/LinkedIn/
        # YouTube caption'ları kendi platform lugatında yazılmış halleriyle
        # kalır (caption videonun transkripti değil, tamamlayıcısı).
        # video_content_sha bindingi etkilenmez: sha publish anındaki caption
        # içeriğinden hesaplanır, render-sonrası edit'i yine yakalar.
        logger.info(
            f"[Flow] video generated: pipeline={asset.pipeline_used} "
            f"url={asset.video_url} cost=${asset.cost_usd:.3f} "
            f"elapsed={asset.generation_latency_ms / 1000:.1f}s"
        )

        # Log as stage 6 (after visual stage 5)
        log_stage(
            run_id=self.state.run_id,
            agent_name="Video Director",
            stage_order=6,
            output=self.state.video,
            model_used=asset.pipeline_used,
            tokens_used=0,
            status="success",
        )

    @router(generate_video)
    def route_after_video(self) -> str:
        """After video: dry_run if dry mode, else publish."""
        if self.state.error:
            return "fail_branch"
        if self.state.dry_run:
            return "dry_run_branch"
        return "publish_branch"

    def _resolve_persona(self) -> Optional[dict]:
        """Find persona row whose primary_account_id matches this run's account."""
        sb = make_supabase()
        try:
            res = (
                sb.table("personas")
                .select(
                    "id, slug, display_name, owner_user_id, visual_enabled, "
                    "video_enabled, video_pipeline_default, daily_video_budget_usd, "
                    "video_min_trend_score, "
                    # D0-4: modality unlock bayrakları publish filtresinde
                    # enforce ediliyor — select'te olmazsa fail-closed kilit.
                    "text_autonomy_unlocked, image_autonomy_unlocked, "
                    "video_autonomy_unlocked, "
                    "topics_focus, forbidden_topics, default_target_platforms"
                )
                .eq("primary_account_id", self.state.account_id)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            row = rows[0] if rows else None
            return dict(row) if isinstance(row, dict) else None  # type: ignore[arg-type]
        except Exception as e:
            logger.warning(f"[Flow] _resolve_persona failed: {e}")
            return None

    @listen("dry_run_branch")
    def dry_run_complete(self) -> None:
        """Dry-run path: land drafts cleanly in the human-approval queue.

        2026-06-07 (FIX-3): previously this wrote status='pending' with
        a synthetic `DRY_RUN_<uuid>` postiz_post_id and a fabricated
        scheduled_at (now + N hours). The UI then rendered those rows as
        "scheduled" even though they would never publish — phantom
        scheduled state. Worse, status='pending' is what the operator
        queue treats as "approved, in Postiz, waiting to fire", so the
        rows never appeared in /dashboard/auto-drafts where the human
        could act on them.

        New behavior — with auto_publish_enabled=false (the standard
        prod state, and the only state we currently flip into):
          - status = 'pending_review'  (queue surface uses this)
          - postiz_post_id = NULL       (no phantom id to mislead verifier)
          - scheduled_at  = NULL        (no fake schedule on the UI)
        The platform_draft IDs are still stored so threads link
        correctly, and self.state.publish remains a sentinel for the
        downstream finalize.
        """
        if not self.state.draft or not self.state.platform_drafts:
            self._finalize("completed", flow_status_label="dry_run_no_draft")
            return

        thread_id = self._content_thread_id()

        # Mirror the publish-path Instagram safety: IG requires an image.
        if not (self.state.visual and self.state.visual.image_url):
            before = len(self.state.platform_drafts)
            self.state.platform_drafts = [
                p for p in self.state.platform_drafts
                if p.platform.lower() != "instagram"
            ]
            if len(self.state.platform_drafts) < before:
                logger.info(
                    "[Flow] dry-run path: dropped Instagram — no visual image present"
                )

        primary_draft_id: Optional[str] = None
        for pd in self.state.platform_drafts:
            # No phantom postiz_post_id, no fabricated scheduled_at.
            pd.postiz_post_id = None
            pd.scheduled_at = None
            did = self._write_daily_draft(
                platform_draft=pd,
                status="pending_review",
                postiz_post_id=None,
                scheduled_at=None,
                content_thread_id=thread_id or None,
            )
            pd.daily_draft_id = did
            if primary_draft_id is None:
                primary_draft_id = did

        # Sentinel publisher output (downstream finalize expects a non-None).
        self.state.publish = PublisherOutput(
            postiz_post_id="PENDING_REVIEW",
            integration_id="PENDING_REVIEW",
            scheduled_at=datetime.now(timezone.utc),
            platform=self.state.platform_drafts[0].platform,
            dry_run=True,
        )

        logger.info(
            f"[Flow] dry-run path — {len(self.state.platform_drafts)} platform "
            f"draft(s) saved as pending_review, thread={thread_id} "
            f"primary={primary_draft_id} (no phantom postiz ids; awaiting human approve)"
        )
        self._finalize(
            "completed",
            daily_draft_id=primary_draft_id,
            draft_content=self.state.draft.content,
            postiz_post_id=None,
            scheduled_at=None,
            flow_status_label="dry_run_logged",
        )

    @listen("skip_branch")
    def skip_complete(self) -> None:
        """Trend rejected OR compliance rejected. When Compliance fails AND we
        have a draft, persist it as `auto_rejected` so the human can inspect
        the output + per-agent reasoning in the UI (feedback loop)."""
        if self.state.compliance and not self.state.compliance.approved:
            reason = self.state.compliance.rejection_reason or "compliance rejected"
            status = "rejected_by_compliance"

            # If we have a draft, save it with status='auto_rejected' so the user
            # can see the per-stage reasoning and edit/approve manually.
            draft_id: Optional[str] = None
            if self.state.draft:
                draft_id = self._write_daily_draft(
                    status="auto_rejected",
                    postiz_post_id=None,
                    scheduled_at=None,
                )
                # 2026-06-12 (Berkay): compliance ret sebebini DB'ye yaz —
                # "bu haber niye postlanmadı" UI'da/sorguda hep görünür olsun.
                if draft_id and reason:
                    try:
                        make_supabase().table("daily_drafts").update(
                            {"rejection_reason": reason}
                        ).eq("id", draft_id).execute()
                    except Exception as _re:
                        logger.warning(f"[Flow] compliance reason persist failed: {_re}")
                logger.info(f"[Flow] Compliance-rejected draft saved for human review: id={draft_id} reason={reason!r}")

            self.state.final_status = status
            logger.info(f"[Flow] SKIP — {reason}")
            self._finalize(status, daily_draft_id=draft_id,
                           draft_content=self.state.draft.content if self.state.draft else None)
        else:
            reason = (self.state.trend.skip_reason if self.state.trend else "no trend qualified") or "skip"
            status = "completed"
            self.state.final_status = status
            logger.info(f"[Flow] SKIP — {reason}")
            self._finalize(status)

    def _compute_confidence_score(
        self,
        persona_id: Optional[str],
        content_type: Optional[str],
    ) -> Optional[float]:
        """Phase 43.B.5 — composite confidence score at draft-creation time.

        Formula (decisions.md):
            confidence = 1.0 - 0.5 * trend_reject_rate_30d * weight
            weight     = min(1.0, sample_count / 30)
            clamped to [0.0, 1.0]

        At creation there are no iterations or edits yet, so the only live
        signal is the 30-day rejection rate for the same persona +
        content_type cluster. iterate_rounds / edit_count terms come into
        play later when the worker UPDATEs after a regen finishes.

        Returns None on DB failure or missing inputs — caller drops the
        field so the legacy column-less schema stays valid.
        """
        if not persona_id:
            return None
        try:
            sb = make_supabase()
            since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            q = (
                sb.table("daily_drafts")
                .select("status", count="exact")
                .eq("persona_id", persona_id)
                .gte("created_at", since)
            )
            if content_type:
                q = q.eq("content_type", content_type)
            res = q.execute()
            rows = res.data or []
            sample_count = len(rows)
            if sample_count == 0:
                # No history — fall back to a neutral prior so we don't
                # block edits/approves on a brand-new persona.
                return 0.75
            reject_states = {"auto_rejected", "rejected", "regen_failed"}
            rejects = sum(1 for r in rows if (r.get("status") or "").lower() in reject_states)
            reject_rate = rejects / sample_count
            weight = min(1.0, sample_count / 30.0)
            score = 1.0 - 0.5 * reject_rate * weight
            return max(0.0, min(1.0, round(score, 4)))
        except Exception as e:
            logger.warning(f"[Flow] confidence_score compute failed (non-fatal): {e}")
            return None

    def _gate_repair_rewrite(
        self, *, pd: "PlatformDraft", violations: str, raw_source: str,
    ) -> Optional[str]:
        """W1-1 (2026-06-11) — cron yolunda gate-blok onarımı.

        Approve yolundaki _gate_block_auto_rewrite'ın flow içi karşılığı:
        HARD_BLOCK yiyen platform draftı, ihlal listesi yazara geri verilerek
        BİR KEZ yeniden yazdırılır (retry cap 1; flow zaten writer'a sahip,
        HTTP üzerinden backend'e gitmez). Başarıda sanitize edilmiş yeni
        metin döner; her tür hatada None (çağıran draftı pending_review'a
        düşürür — eski davranış)."""
        try:
            from tools.typehype_client import generate_tweet_via_typehype
            from tools.cansu_voice import (
                build_cansu_directive, _lugat_for_platform, sanitize_draft,
            )
            plat = pd.platform
            plan = getattr(self.state, "plan", None)
            trend = getattr(self.state, "trend", None)
            ctx = "\n".join([
                build_cansu_directive(),
                _lugat_for_platform(plat),
                f"Trend konusu: {getattr(trend, 'topic', '') or ''}",
                "## GATE İHLALLERİ (bu yüzden reddedildi — düzelt)\n"
                f"{(violations or '')[:800]}\n"
                "Yukarıdaki ihlalleri içermeyen, YALNIZ kaynaktaki olgulara "
                "dayanan yeni bir metin yaz. Kaynakta olmayan tez/çıkarım/"
                "yorum cümlesi KURMA.",
                "## KAYNAK METİN (tüm iddialar buna bağlı olmalı)\n"
                + (raw_source or "").strip(),
            ])
            resp = generate_tweet_via_typehype(
                account_id=pd.account_id,
                etki=getattr(plan, "etki", None) or "konustursun",
                karakter=getattr(plan, "karakter", None) or "iceriden",
                uzunluk=self._UZUNLUK_BY_PLATFORM.get(plat.lower()) or "punch",  # type: ignore[arg-type]
                yapi="dogal",
                additional_context=ctx,
                is_ultra=False,
                content_type=self._CONTENT_TYPE_BY_PLATFORM.get(plat.lower(), "tweet"),  # type: ignore[arg-type]
                voice_mode="hybrid" if plat.lower() in ("linkedin", "devto", "youtube") else "first_person_witty",
                model_override=getattr(settings, "writer_model", None) or None,
                clean_source_input=True,
            )
            new_text = sanitize_draft((resp.get("content") or "").strip(), plat)
            if new_text and len(new_text) > 40:
                return new_text
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[gate-repair] {pd.platform} rewrite failed: {e}")
        return None

    def _write_daily_draft(
        self,
        status: str,
        postiz_post_id: Optional[str],
        scheduled_at: Optional[str],
        platform_draft: Optional["PlatformDraft"] = None,
        content_thread_id: Optional[str] = None,
        auto_published: bool = False,
    ) -> Optional[str]:
        """Insert a row into daily_drafts and return the new id (or None on error).

        Phase 20: when ``platform_draft`` is passed, write that platform's row
        (content, platform, account_id all come from PlatformDraft). When the
        argument is omitted (legacy callers like skip_complete on text-only
        compliance reject), falls back to state.draft / state.account_id with
        platform='twitter'.
        """
        if not self.state.draft and not platform_draft:
            return None
        sb = make_supabase()
        user_id = self._lookup_user_id()
        persona = self._resolve_persona()

        if platform_draft is not None:
            content = platform_draft.content
            platform = platform_draft.platform
            account_id = platform_draft.account_id
        else:
            content = self.state.draft.content if self.state.draft else ""
            platform = "twitter"
            account_id = self.state.account_id

        # Image linked only to platforms where a visual is meaningful for now
        # (instagram = required, twitter/linkedin = optional preview, devto =
        # could be used as article cover; for V1 we attach to all platforms).
        image_url = self.state.visual.image_url if self.state.visual else None
        image_asset_id = self.state.visual.asset_id if self.state.visual else None

        # Phase 23 — video assets attached to video platforms only.
        # 2026-06-07 (video↔content binding): store the sha256 of the
        # exact content the video was rendered against. The edit_draft
        # path + the approve_draft/approve_thread guards compare current
        # content's sha against this one; mismatch ⇒ video_stale=true
        # and approve refuses to publish.
        video_row: dict[str, Any] = {}
        if self.state.video and platform.lower() in _VIDEO_PLATFORMS:
            import hashlib as _hl_video
            rendered_sha = _hl_video.sha256(
                (platform_draft.content or "").encode("utf-8")
            ).hexdigest()
            video_row = {
                "video_url": self.state.video.video_url,
                "video_thumbnail_url": self.state.video.thumbnail_url,
                "video_duration_sec": int(self.state.video.duration_sec) or None,
                "video_pipeline_used": self.state.video.pipeline_used,
                "video_content_sha": rendered_sha,
                "video_stale": False,
            }
            # 2026-06-07 (video integrity check, post-SEV-1 follow-up P0):
            # ffprobe the asset before we mark it usable. If duration is
            # materially shorter than the content's TTS budget, OR audio
            # and video tracks disagree, OR the mp4 is malformed, mark
            # video_integrity_ok=false; the approve guard refuses to ship.
            try:
                from .tools.video_integrity import check_video_integrity  # type: ignore
            except Exception:
                try:
                    import sys as _sys
                    _sys.path.insert(0, "/opt/hype-crew")
                    from tools.video_integrity import check_video_integrity  # type: ignore
                except Exception as _ie:
                    check_video_integrity = None    # type: ignore
                    logger.warning(f"[Flow] video_integrity import failed; soft-pass: {_ie!r}")
            if check_video_integrity is not None and self.state.video.video_url:
                try:
                    # 2026-06-10 — urlretrieve TIMEOUT'SUZDU: storage stall'ı
                    # publish döngüsünü sonsuza dek asıyordu (stuck >2h reaped
                    # run'ların kök sebebi — IG ilk video platformu olduğu için
                    # hep instagram yazımında kesiliyordu: d2951392 vakası).
                    # httpx + hard timeout; indirme başarısızsa integrity
                    # soft-pass (mevcut except davranışı) ve run DEVAM eder.
                    import httpx as _hx
                    from pathlib import Path as _P
                    _probe_dir = _P("/tmp/video_integrity_probes")
                    _probe_dir.mkdir(exist_ok=True)
                    _local = str(_probe_dir / f"flow_probe_{rendered_sha[:12]}.mp4")
                    with _hx.Client(timeout=_hx.Timeout(90.0, connect=15.0)) as _dl:
                        _resp = _dl.get(self.state.video.video_url)
                        _resp.raise_for_status()
                        with open(_local, "wb") as _fh:
                            _fh.write(_resp.content)
                    # PART 3 wiring (2026-06-07): pass the precise TTS
                    # audio duration from the pipeline's StoredVideoAsset
                    # (HeyGen lip-syncs to the audio so this is what
                    # the operator should EXPECT the video to be). When
                    # unavailable, the integrity check falls back to
                    # the char estimate from content_for_tts.
                    _precise_tts = None
                    try:
                        _precise_tts = float(self.state.video.duration_sec or 0) or None
                    except Exception:
                        _precise_tts = None
                    result = check_video_integrity(
                        file_path=_local,
                        content_for_tts=platform_draft.content or "",
                        srt_path=None,
                        tts_audio_duration_s=_precise_tts,
                    )
                    video_row.update({
                        "video_duration_s": round(result.video_duration_s, 2),
                        "expected_duration_s": round(result.expected_duration_s, 2),
                        "video_integrity_ok": bool(result.ok),
                        "video_integrity_reason": result.reason or None,
                        "video_integrity_checked_at": datetime.now(timezone.utc).isoformat(),
                    })
                    if not result.ok:
                        logger.warning(
                            f"[Flow] INTEGRITY FAIL platform={platform} draft "
                            f"reason={result.reason}"
                        )
                    try:
                        import os as _os
                        _os.remove(_local)
                    except Exception:
                        pass
                except Exception as _re:
                    logger.warning(
                        f"[Flow] video_integrity probe raised; soft-pass: {_re!r}"
                    )

        # Phase 25.H — content_type + voice_mode from Strategist (auto-resolved
        # via voice_mode_for_content_type if Strategist didn't override).
        ct_row: dict[str, Any] = {}
        if self.state.plan:
            ct = getattr(self.state.plan, "content_type", None)
            vm = getattr(self.state.plan, "voice_mode", None)
            if not vm and ct:
                from schemas.plan import voice_mode_for_content_type
                vm = voice_mode_for_content_type(ct)
            if ct:
                ct_row["content_type"] = ct
            if vm:
                ct_row["voice_mode"] = vm

        # Phase 43.B.5 — composite confidence score (sample-weighted 30d
        # reject rate). Computed once per draft at creation; later regen
        # rounds can recompute via /iterate. Best-effort: if the column
        # doesn't exist on this instance yet we strip it on retry.
        confidence_row: dict[str, Any] = {}
        persona_id_for_conf = persona["id"] if persona else None
        content_type_for_conf = ct_row.get("content_type") if ct_row else None
        confidence_score = self._compute_confidence_score(
            persona_id=persona_id_for_conf,
            content_type=content_type_for_conf,
        )
        if confidence_score is not None:
            confidence_row["confidence_score"] = confidence_score

        # Phase 43.D — mark auto-published rows so the monthly Slack
        # quality audit can sample from them (Critic's freeze-on-≥3-fail
        # gate). Only set when the caller is on the auto_publish_enabled
        # path; pending_review writes pass through with default false.
        autopub_row: dict[str, Any] = {}
        if auto_published:
            autopub_row["auto_published"] = True

        # Phase 43.H.1 — propagate source_url so the URL pre-gate sees this
        # draft on next run. TrendScoutOutput is a Pydantic v2 model; setattr
        # of an undeclared field doesn't stick (silently dropped on subsequent
        # attribute reads). Cache lookup on a side-channel dict instead, and
        # fall back to the trends table when the cache is empty.
        # CrewAI Flow doesn't honour custom __init__, so cache lives as an
        # ad-hoc dict on the instance (lazy-create on first read).
        cache: dict[str, str] = self.state.trend_source_url_cache  # state'te (resume-güvenli)
        source_url_val: Optional[str] = None
        if self.state.trend is not None and self.state.trend.trend_id:
            source_url_val = cache.get(self.state.trend.trend_id)
            if not source_url_val:
                try:
                    lookup = (
                        sb.table("trends")
                        .select("url")
                        .eq("id", self.state.trend.trend_id)
                        .limit(1)
                        .execute()
                        .data
                    )
                    if isinstance(lookup, list) and lookup:
                        head = lookup[0]
                        if isinstance(head, dict):
                            u = head.get("url")
                            if isinstance(u, str) and u:
                                source_url_val = u
                                cache[self.state.trend.trend_id] = u  # cache = state dict → in-place yeter
                except Exception as e:
                    logger.warning(f"[Flow] source_url trends-table lookup failed: {e}")
        source_url_row: dict[str, Any] = {}
        if source_url_val:
            source_url_row["source_url"] = source_url_val

        row = {
            "user_id": user_id,
            "account_id": account_id,
            "trend_id": self.state.trend.trend_id if self.state.trend else None,
            "content": content,
            "platform": platform,
            "status": status,
            "source": "hype_auto",
            "trend_topic": self.state.trend.topic if self.state.trend else None,
            "insight": self.state.plan.angle if self.state.plan else None,
            "hype_run_id": self.state.run_id,
            "scheduled_at": scheduled_at,
            "postiz_post_id": postiz_post_id,
            "persona_id": persona["id"] if persona else None,
            "image_url": image_url,
            "image_asset_id": image_asset_id,
            "content_thread_id": content_thread_id,
            **ct_row,
            **video_row,
            **confidence_row,
            **autopub_row,
            **source_url_row,
        }

        # ── LangGraph Faz 2 — daily_drafts IDEMPOTENCY (code-level) ────────
        # Migration 025'in partial unique index'i (hype_run_id, platform,
        # content_type) WHERE deleted_at IS NULL var; PostgREST'ten temiz
        # upsert edilemediği için resume güvenliğini KODDA sağlıyoruz: bu run
        # için aynı (platform, content_type) zaten yazılmışsa INSERT yerine o
        # satırı UPDATE edip id'sini döndürürüz → resume'da çift draft YOK.
        #
        # NO-OP guarantee (normal ilk run): taze bir run'da hype_run_id+platform
        # +content_type ile eşleşen satır olmadığından SELECT boş döner →
        # davranış bugünküyle birebir (yeni INSERT). Yalnız run_id varken
        # çalışır; legacy/edge durumda run_id boşsa atlanır (eski davranış).
        existing_did: Optional[str] = None
        _run_id_for_idem = self.state.run_id

        def _idem_lookup() -> Optional[str]:
            """Run the idempotent SELECT for THIS run's (platform, content_type)
            partial-unique key and return the existing row id, or None.

            Reused by (a) the pre-check below and (b) the MED-3 23505 recovery
            in the INSERT except handler — a unique-violation means the
            conflicting row now exists, so re-running this exact lookup finds it
            and converts the lost race / resume re-run into the UPDATE path.
            Only meaningful when run_id is set; returns None otherwise."""
            if not _run_id_for_idem:
                return None
            _ct_val = ct_row.get("content_type")
            _q = (
                sb.table("daily_drafts").select("id")
                .eq("hype_run_id", _run_id_for_idem)
                .eq("platform", platform)
                .is_("deleted_at", "null")
            )
            # content_type partial-index ayağı: NULL ve değer ayrımını
            # index'le aynı şekilde ele al.
            if _ct_val is None:
                _q = _q.is_("content_type", "null")
            else:
                _q = _q.eq("content_type", _ct_val)
            _ex = _q.limit(1).execute()
            _ex_rows = _ex.data if isinstance(_ex.data, list) else []
            if _ex_rows and isinstance(_ex_rows[0], dict):
                _rid = _ex_rows[0].get("id")
                if isinstance(_rid, str):
                    return _rid
            return None

        if _run_id_for_idem:
            try:
                existing_did = _idem_lookup()
            except Exception as _ie:
                logger.warning(
                    f"[Flow] daily_drafts idempotency pre-check failed "
                    f"(insert'e düşülüyor): {_ie}"
                )

        if existing_did:
            logger.info(
                f"[Flow] daily_drafts IDEMPOTENT update: run={_run_id_for_idem} "
                f"platform={platform} content_type={ct_row.get('content_type')} "
                f"existing_id={existing_did} (resume — çift draft önlendi)"
            )
            try:
                # id/account_id/user_id gibi kimlik alanlarını UPDATE'e sokma.
                _update_row = {
                    k: v for k, v in row.items()
                    if k not in ("user_id", "account_id")
                }
                try:
                    sb.table("daily_drafts").update(_update_row).eq("id", existing_did).execute()
                except Exception as _ue:
                    _umsg = str(_ue)
                    _umsg_lower = _umsg.lower()
                    phase43_keys = ("confidence_score", "auto_published", "source_url")
                    if (
                        any(k in _umsg for k in phase43_keys)
                        or "PGRST204" in _umsg
                        or "column" in _umsg_lower
                    ):
                        _safe = {k: v for k, v in _update_row.items() if k not in phase43_keys}
                        sb.table("daily_drafts").update(_safe).eq("id", existing_did).execute()
                    else:
                        raise
                # visual asset link (insert yolundakiyle aynı, tek sefer).
                if (
                    self.state.visual
                    and self.state.visual.asset_id
                    and not getattr(self, "_visual_linked", False)
                ):
                    try:
                        sb.table("persona_assets").update(
                            {"daily_draft_id": existing_did}
                        ).eq("id", self.state.visual.asset_id).execute()
                        self._visual_linked = True  # type: ignore[attr-defined]
                    except Exception as link_e:
                        logger.warning(f"[Flow] visual asset link (idem) failed: {link_e}")
            except Exception as _ue2:
                logger.exception(f"[Flow] daily_drafts idempotent update failed: {_ue2}")
            return existing_did

        try:
            try:
                result = sb.table("daily_drafts").insert(row).execute()
            except Exception as inner_e:
                msg = str(inner_e)[:300]
                # Phase 43.D — also strip auto_published / autopub_row keys
                # that may be missing on instances that haven't run the
                # 43.C migration yet. We strip all Phase 43-era optional
                # columns together so a single retry handles whichever
                # combination is missing.
                phase43_keys = (
                    "confidence_score",
                    "auto_published",
                    "source_url",  # Phase 43.H.1 — strip if column not yet migrated
                )
                msg_lower = msg.lower()
                if (
                    any(k in msg for k in phase43_keys)
                    or "PGRST204" in msg
                    or "column" in msg_lower
                ):
                    logger.warning(
                        "[Flow] daily_drafts: Phase 43 column missing "
                        f"(msg={msg[:120]!r}); retrying without optional cols."
                    )
                    row_safe = {
                        k: v for k, v in row.items() if k not in phase43_keys
                    }
                    result = sb.table("daily_drafts").insert(row_safe).execute()
                else:
                    raise
            rows = result.data if isinstance(result.data, list) else []
            if rows and isinstance(rows[0], dict):
                rid = rows[0].get("id")
                # ── SHADOW GATE (advisory) — never blocks ────────────────
                # Logs a faithfulness verdict at generation time so the
                # graduation-readiness scoreboard has data. Manual
                # approval continues; publish-time fail-closed gate
                # unchanged.
                try:
                    if isinstance(rid, str):
                        _shadow_raw = (
                            self.state.trend_raw_content_cache or {}
                        ).get(
                            self.state.trend.trend_id if self.state.trend else None,
                            "",
                        ) or ""
                        if _shadow_raw and content:
                            import asyncio as _aio_sh
                            from tools.guarded_postiz import shadow_gate as _shadow_gate
                            async def _run_shadow():
                                return await _shadow_gate(
                                    draft_text=content,
                                    source_raw_content=_shadow_raw,
                                    draft_id=rid,
                                    account_id=account_id,
                                    trend_id=(self.state.trend.trend_id
                                              if self.state.trend else None),
                                    source_url=source_url_val,
                                    path_tag="shadow",
                                )
                            try:
                                _aio_sh.run(_run_shadow())
                            except RuntimeError:
                                _loop_sh = _aio_sh.new_event_loop()
                                try:
                                    _loop_sh.run_until_complete(_run_shadow())
                                finally:
                                    _loop_sh.close()
                except Exception as _se:
                    logger.warning(f"[Flow] shadow gate (advisory) failed: {_se!r}")
                if isinstance(rid, str):
                    # Link the visual asset to the FIRST draft we write (avoid
                    # double-linking the same asset to all platform rows).
                    if (
                        self.state.visual
                        and self.state.visual.asset_id
                        and not getattr(self, "_visual_linked", False)
                    ):
                        try:
                            sb.table("persona_assets").update(
                                {"daily_draft_id": rid}
                            ).eq("id", self.state.visual.asset_id).execute()
                            self._visual_linked = True  # type: ignore[attr-defined]
                        except Exception as link_e:
                            logger.warning(f"[Flow] visual asset link failed: {link_e}")
                    return rid
        except Exception as e:
            # ── MED-3 — unique-violation (23505) recovery ───────────────────
            # The (hype_run_id, platform, content_type) partial-unique index
            # (migration 026, NULLS NOT DISTINCT) can reject our INSERT when a
            # concurrent writer / advisory-lock race / resume re-run already
            # created the row between our pre-check SELECT and this INSERT.
            # That is NOT a real failure — the conflicting row IS exactly the
            # row we wanted. Re-run the SAME idempotent SELECT (it now finds
            # the committed row) and UPDATE→return its id, converting the lost
            # race into the idempotent-update path. Only attempt this when
            # run_id is set (the index requires hype_run_id IS NOT NULL anyway).
            _e_str = str(e)
            _is_23505 = (
                "23505" in _e_str
                or "duplicate key" in _e_str.lower()
                or "duplicate" in _e_str.lower()
            )
            if _is_23505 and _run_id_for_idem:
                try:
                    _conflict_did = _idem_lookup()
                except Exception as _le:
                    logger.warning(
                        f"[Flow] daily_drafts 23505 recovery lookup failed: {_le}"
                    )
                    _conflict_did = None
                if _conflict_did:
                    logger.warning(
                        f"[Flow] daily_drafts 23505 → IDEMPOTENT recovery: "
                        f"run={_run_id_for_idem} platform={platform} "
                        f"content_type={ct_row.get('content_type')} "
                        f"existing_id={_conflict_did} "
                        f"(unique-violation race/resume — çift draft önlendi)"
                    )
                    try:
                        _update_row = {
                            k: v for k, v in row.items()
                            if k not in ("user_id", "account_id")
                        }
                        try:
                            sb.table("daily_drafts").update(_update_row).eq(
                                "id", _conflict_did
                            ).execute()
                        except Exception as _ue:
                            _umsg = str(_ue)
                            _umsg_lower = _umsg.lower()
                            phase43_keys = (
                                "confidence_score", "auto_published", "source_url",
                            )
                            if (
                                any(k in _umsg for k in phase43_keys)
                                or "PGRST204" in _umsg
                                or "column" in _umsg_lower
                            ):
                                _safe = {
                                    k: v for k, v in _update_row.items()
                                    if k not in phase43_keys
                                }
                                sb.table("daily_drafts").update(_safe).eq(
                                    "id", _conflict_did
                                ).execute()
                            else:
                                raise
                    except Exception as _ue2:
                        logger.exception(
                            f"[Flow] daily_drafts 23505 recovery update failed: {_ue2}"
                        )
                    return _conflict_did
                # 23505 but couldn't locate the conflicting row — fall through
                # to the generic handler below (return None).
            logger.exception(f"[Flow] daily_drafts insert failed: {e}")
        return None

    @listen("fail_branch")
    def fail_complete(self) -> None:
        """Pipeline crashed — finalize as failed."""
        logger.error(f"[Flow] FAILED — {self.state.error}")
        self._finalize("failed")

    @listen("publish_branch")
    def publish_to_drafts(self) -> None:
        """Phase 20 — Multi-platform output.

        Phase 28.C — gate Postiz schedule behind `auto_publish_enabled`:
          - `auto_publish_enabled=false` (default during onboarding): write rows
            with status='pending_review', postiz_post_id=NULL. The user clicks
            Approve in the UI to trigger the real Postiz schedule from the
            backend route. No autonomous posting happens until then.
          - `auto_publish_enabled=true`: legacy behaviour — Postiz schedule call
            fires inside this method and rows are status='pending' (will publish
            at scheduled_at unless user rejects within the window).
        """
        if not self.state.draft or not self.state.platform_drafts:
            self._finalize("failed")
            return

        # 2026-06-08 — YouTube requires video. If video stage produced none
        # (worthy gate failed, budget exhausted, render error, or any other
        # reason), drop YT drafts so we never write text-only YouTube rows
        # that Postiz YT-publisher rejects with 400. Same applies to
        # YouTube Shorts and TikTok (vertical-video-only). Instagram Reels
        # falls back to image post via the IG path; LinkedIn supports
        # text-only natively. Reels rows live as IG draft variants so
        # they're handled by the regular IG flow.
        has_video_now = bool(self.state.video and self.state.video.video_url)
        if not has_video_now:
            _video_only = {"youtube", "youtube-shorts", "tiktok"}
            _drop = [
                p for p in self.state.platform_drafts
                if p.platform.lower() in _video_only
            ]
            if _drop:
                logger.info(
                    "[Flow] drop_video_only: no video produced, removing "
                    f"text-only drafts for {[p.platform for p in _drop]}"
                )
                self.state.platform_drafts = [
                    p for p in self.state.platform_drafts
                    if p.platform.lower() not in _video_only
                ]
        if not self.state.platform_drafts:
            logger.warning("[Flow] all platform_drafts dropped post-video-gate; nothing to publish")
            self._finalize("completed")
            return

        # Berkay 6 Haz 2026 Phase 1 — every cron auto-publish post must
        # physically route through GuardedPostizClient. The guarded
        # schedule_posts refuses without per-post PASS verdict tokens
        # from assert_publishable(), so a fabrication in this path is
        # impossible. The base PostizClient import is kept only for the
        # PlatformPost dataclass; never construct PostizClient directly.
        from tools.postiz_client import PlatformPost  # noqa: F401  PlatformPost only
        from tools.guarded_postiz import (
            GuardedPostizClient as _Pc,
            assert_publishable as _assert_publishable,
            GuardedPublishRefused as _GuardedPublishRefused,
        )

        scheduled_at_dt = datetime.now(timezone.utc) + timedelta(hours=settings.default_schedule_delay_hours)
        thread_id = self._content_thread_id()

        # Phase 28.C — read auto_publish_enabled flag fresh from DB. Default
        # OFF — we never auto-publish during the onboarding period.
        # Option C (2026-06-04) — also read allowed_publish_platforms:
        #   None        → legacy behavior, publish all platforms
        #   list[str]   → only publish drafts whose platform is in the list
        #   []          → publish nothing (per-account dry-publish)
        try:
            cfg_row = make_supabase().table("hype_account_config")\
                .select("auto_publish_enabled, allowed_publish_platforms")\
                .eq("account_id", self.state.account_id).limit(1).execute()
            first = (cfg_row.data or [None])[0]
            auto_publish = bool(first.get("auto_publish_enabled")) if isinstance(first, dict) else False
            raw_allowlist = first.get("allowed_publish_platforms") if isinstance(first, dict) else None
            if raw_allowlist is None:
                allowed_platforms: Optional[set[str]] = None
            elif isinstance(raw_allowlist, list):
                allowed_platforms = {str(p).strip().lower() for p in raw_allowlist if isinstance(p, (str, bytes))}
            else:
                logger.warning(
                    f"[Flow] allowed_publish_platforms has unexpected type "
                    f"({type(raw_allowlist).__name__}); treating as None (publish all)"
                )
                allowed_platforms = None
        except Exception as e:
            logger.warning(f"[Flow] auto_publish flag lookup failed (defaulting OFF): {e}")
            auto_publish = False
            allowed_platforms = None

        if not auto_publish:
            logger.info(
                f"[Flow] auto_publish_enabled=false — skipping Postiz, writing "
                f"{len(self.state.platform_drafts)} draft(s) as pending_review"
            )
            # Phase 28.C — inline pending_review path. Each platform_draft gets
            # a row in daily_drafts with status='pending_review', NO Postiz
            # schedule call is made. User clicks Approve in UI → backend
            # `/hype/drafts/:id/approve` fires the real Postiz schedule.
            # 2026-06-10 — ATOMİK davranış (n8n parite, C yaması): platform
            # yazımlarından HERHANGİ biri patlarsa bu run'ın o ana kadar
            # yazdığı satırlar telafi-silme ile kaldırılır → review kuyruğuna
            # asla "yarım platform seti" kartı düşmez (X-only artık vakaları).
            # Hang senaryosunu (exception yok) runner reaper'ın yetim-draft
            # temizliği kapatır.
            pr_primary_draft_id: Optional[str] = None
            _written_ids: list[str] = []
            try:
                for pd in self.state.platform_drafts:
                    pd.postiz_post_id = None
                    pd.scheduled_at = None
                    pr_did = self._write_daily_draft(
                        platform_draft=pd,
                        status="pending_review",
                        postiz_post_id=None,
                        scheduled_at=None,
                        content_thread_id=thread_id or None,
                    )
                    pd.daily_draft_id = pr_did
                    if pr_did:
                        _written_ids.append(pr_did)
                    if pr_primary_draft_id is None:
                        pr_primary_draft_id = pr_did
            except Exception as _we:
                logger.error(
                    f"[Flow] pending_review yazımı yarıda kesildi "
                    f"({type(_we).__name__}: {_we}) — {len(_written_ids)} "
                    f"yarım satır telafi-siliniyor"
                )
                if _written_ids:
                    try:
                        make_supabase().table("daily_drafts").update({
                            "deleted_at": datetime.now(timezone.utc).isoformat(),
                            "deleted_reason": "atomic publish rollback (partial write)",
                        }).in_("id", _written_ids).execute()
                    except Exception as _ce:
                        logger.warning(f"[Flow] telafi silme başarısız: {_ce}")
                raise

            first_pd_pr = self.state.platform_drafts[0]
            self.state.publish = PublisherOutput(
                postiz_post_id="PENDING_REVIEW",
                integration_id=first_pd_pr.integration_id,
                scheduled_at=scheduled_at_dt,
                platform=first_pd_pr.platform,
                dry_run=False,
            )
            logger.info(
                f"[Flow] PENDING_REVIEW — {len(self.state.platform_drafts)} draft(s) saved, "
                f"thread={thread_id} primary_draft={pr_primary_draft_id}. Awaiting user approval."
            )
            self._finalize("completed")
            return

        # Pre-upload visual assets to Postiz so per-platform posts can reference
        # them by id. We do this ONCE for the whole run and share uploads across
        # platforms.
        #   - IG rejects URL-only media (Phase 21.10) — image required.
        #   - Dev.to → optional hero image (main_image).
        #   - LinkedIn → optional inline image OR native video; video preferred
        #     when state.video exists.
        #   - YouTube / IG Reels / TikTok → video required (Postiz crashes
        #     without it).
        postiz = _Pc()
        uploaded_image: Optional[dict[str, str]] = None
        uploaded_video: Optional[dict[str, str]] = None

        def _wants(p_name: str) -> bool:
            return any(p.platform.lower() == p_name for p in self.state.platform_drafts)

        wants_instagram = _wants("instagram")
        wants_devto = _wants("devto")
        wants_linkedin = _wants("linkedin")
        wants_youtube = _wants("youtube") or _wants("youtube-shorts")
        wants_reels = _wants("instagram-reels")
        wants_tiktok = _wants("tiktok")
        wants_video_platform = wants_youtube or wants_reels or wants_tiktok
        has_visual_image = bool(self.state.visual and self.state.visual.image_url)
        has_video = bool(self.state.video and self.state.video.video_url)

        if wants_instagram and not has_visual_image and not has_video:
            # IG without media cannot be scheduled — drop IG draft.
            logger.warning(
                "[Flow] publish: Instagram target but no visual; dropping IG"
            )
            self.state.platform_drafts = [
                p for p in self.state.platform_drafts
                if p.platform.lower() != "instagram"
            ]
            wants_instagram = False

        # Upload IMAGE once when any platform wants it.
        needs_image_upload = (
            (wants_instagram and not has_video)
            or wants_devto
            or (wants_linkedin and not has_video)
        ) and has_visual_image
        if needs_image_upload:
            try:
                assert self.state.visual is not None  # has_visual_image guarantees
                uploaded_image = postiz.upload_image_url(self.state.visual.image_url)
                logger.info(
                    f"[Flow] visual image uploaded to Postiz: id={uploaded_image.get('id')} "
                    f"(targets: ig={wants_instagram} devto={wants_devto} linkedin={wants_linkedin})"
                )
            except Exception as e:
                logger.exception(f"[Flow] Postiz image upload failed: {e}")
                if wants_instagram and not has_video:
                    self.state.platform_drafts = [
                        p for p in self.state.platform_drafts
                        if p.platform.lower() != "instagram"
                    ]

        # Upload VIDEO once when any platform wants it (LinkedIn opt-in, YT/Reels required).
        needs_video_upload = has_video and (wants_video_platform or wants_linkedin or wants_instagram)
        if needs_video_upload:
            try:
                assert self.state.video is not None
                uploaded_video = postiz.upload_from_url(self.state.video.video_url)
                logger.info(
                    f"[Flow] video uploaded to Postiz: id={uploaded_video.get('id')} "
                    f"(targets: yt={wants_youtube} reels={wants_reels} tiktok={wants_tiktok} "
                    f"linkedin={wants_linkedin} ig={wants_instagram})"
                )
            except Exception as e:
                logger.exception(f"[Flow] Postiz video upload failed: {e}")
                # Drop platforms that hard-require video — otherwise Postiz settings validation 400s.
                hard_video = {"youtube", "youtube-shorts", "instagram-reels", "tiktok"}
                before = len(self.state.platform_drafts)
                self.state.platform_drafts = [
                    p for p in self.state.platform_drafts
                    if p.platform.lower() not in hard_video
                ]
                if len(self.state.platform_drafts) < before:
                    logger.warning(
                        "[Flow] dropped video-only platforms after upload failure"
                    )

        if not self.state.platform_drafts:
            self.state.error = "no platform drafts left after media-upload checks"
            self._finalize("failed")
            return

        # Build platform-post payload.
        #   - IG → video if available, else image
        #   - LinkedIn → video if available, else image
        #   - Dev.to → image only (article hero, not video)
        #   - YouTube / Reels / TikTok → video required
        VIDEO_PLATFORMS_LC = {"youtube", "youtube-shorts", "instagram-reels", "tiktok"}
        postiz_posts: list[PlatformPost] = []
        for pd in self.state.platform_drafts:
            media = None
            is_video_media = False
            platform_lc = pd.platform.lower()
            if platform_lc in VIDEO_PLATFORMS_LC and uploaded_video:
                media = [uploaded_video]
                is_video_media = True
            elif platform_lc in ("instagram", "linkedin"):
                if uploaded_video:
                    media = [uploaded_video]
                    is_video_media = True
                elif uploaded_image:
                    media = [uploaded_image]
            elif platform_lc == "devto" and uploaded_image:
                media = [uploaded_image]
            postiz_posts.append(PlatformPost(
                integration_id=pd.integration_id,
                provider=pd.platform,
                content=pd.content,
                title=pd.title,
                tags=pd.tags,
                media=media,
                is_video=is_video_media,
            ))

        # Option C (2026-06-04) — apply per-account auto-publish platform
        # allowlist. When `allowed_platforms` is a set, split platform_drafts +
        # postiz_posts in parallel:
        #   - allowed → proceed to postiz.schedule_posts
        #   - filtered out → write as pending_review (postiz_post_id=None) so
        #                    the draft is preserved and surfaced in the UI for
        #                    optional manual approval; never escapes silently.
        # When `allowed_platforms is None` → no filtering (legacy behavior).
        deferred_drafts: list = []
        # 2026-06-10 (otonomi D0-4) — modality unlock bayrakları artık
        # ENFORCE ediliyor: personas.{text,image,video}_autonomy_unlocked
        # false olan bucket'ın draftları otonom yayına ÇIKMAZ, Option C
        # deferred yoluyla pending_review'a düşer. Böylece
        # check_autonomy_gates'in RELOCK mekanizması (3 ardışık ret)
        # içerik-tipi bazında GERÇEK bir fren olur (örn. video sorunluysa
        # yalnız video insan onayına döner, text/image otonom sürer).
        _locked_buckets: set[str] = set()
        try:
            _pers = self._resolve_persona() or {}
            for _bucket in ("text", "image", "video"):
                if _pers.get(f"{_bucket}_autonomy_unlocked") is not True:
                    _locked_buckets.add(_bucket)
        except Exception as _pe:
            # Persona okunamazsa GÜVENLİ taraf: her şey kilitli say
            # (fail-closed) — draftlar pending_review'a düşer.
            logger.warning(f"[Flow] unlock-bayrak okuması başarısız (fail-closed): {_pe}")
            _locked_buckets = {"text", "image", "video"}

        def _draft_bucket(pd) -> str:
            if self.state.video and pd.platform.lower() in _VIDEO_PLATFORMS:
                return "video"
            if self.state.visual and getattr(self.state.visual, "image_url", None):
                return "image"
            return "text"

        if allowed_platforms is not None or _locked_buckets:
            allowed_postiz_posts: list[PlatformPost] = []
            allowed_drafts = []
            for pd, pp in zip(self.state.platform_drafts, postiz_posts):
                _bucket = _draft_bucket(pd)
                if _bucket in _locked_buckets:
                    logger.info(
                        f"[Flow] D0-4 modality kilidi: {pd.platform} draft'ı "
                        f"({_bucket} bucket kilitli) → pending_review"
                    )
                    deferred_drafts.append(pd)
                elif allowed_platforms is not None and pd.platform.lower() not in allowed_platforms:
                    deferred_drafts.append(pd)
                else:
                    allowed_drafts.append(pd)
                    allowed_postiz_posts.append(pp)
            logger.info(
                f"[Flow] Option C + modality filter: "
                f"allowed_platforms={sorted(allowed_platforms) if allowed_platforms is not None else 'ALL'} "
                f"locked_buckets={sorted(_locked_buckets) or '-'} "
                f"to_publish={[d.platform for d in allowed_drafts]} "
                f"deferred_to_pending_review={[d.platform for d in deferred_drafts]}"
            )
            # Persist deferred drafts immediately as pending_review (no Postiz ID)
            for pd in deferred_drafts:
                pd.postiz_post_id = None
                pd.scheduled_at = None
                pr_did = self._write_daily_draft(
                    platform_draft=pd,
                    status="pending_review",
                    postiz_post_id=None,
                    scheduled_at=None,
                    content_thread_id=thread_id or None,
                )
                pd.daily_draft_id = pr_did
            # Trim live state to only the allowed drafts for downstream
            # schedule_posts → post_ids zip-loop alignment.
            self.state.platform_drafts = allowed_drafts
            postiz_posts = allowed_postiz_posts
            if not postiz_posts:
                # Empty allowlist OR no drafts matched — finalize without any
                # Postiz call, but still record deferred drafts as approved-but-
                # held-back (they were already written above).
                logger.info(
                    f"[Flow] Option C — no platforms matched allowlist; "
                    f"deferred {len(deferred_drafts)} draft(s); skipping Postiz call"
                )
                first_pd = deferred_drafts[0] if deferred_drafts else None
                self.state.publish = PublisherOutput(
                    postiz_post_id="ALLOWLIST_EMPTY",
                    integration_id=first_pd.integration_id if first_pd else "",
                    scheduled_at=scheduled_at_dt,
                    platform=first_pd.platform if first_pd else "",
                    dry_run=False,
                )
                self._finalize(
                    "completed",
                    daily_draft_id=deferred_drafts[0].daily_draft_id if deferred_drafts else None,
                    postiz_post_id=None,
                    scheduled_at=scheduled_at_dt.isoformat(),
                    draft_content=self.state.draft.content,
                )
                return

        # Phase 1 fail-closed gate — every post in this cron batch is
        # individually checked. If ANY draft fails, the WHOLE batch is
        # held back as pending_review (operator can still approve per-
        # platform via the UI, which routes through the same gate).
        _gate_outcomes: list[Any] = []
        _gate_blocked: list[str] = []
        _raw_source_for_gate = (
            self.state.trend_raw_content_cache or {}
        ).get(
            getattr(self.state.trend, "trend_id", None)
            if self.state.trend else None,
            "",
        ) or ""
        import asyncio as _asyncio_gate

        def _run_gate(_text: str, _did: str):
            try:
                return _asyncio_gate.run(_assert_publishable(
                    draft_text=_text,
                    source_raw_content=_raw_source_for_gate,
                    path="cron_auto",
                    draft_id=_did,
                ))
            except RuntimeError:
                # Already inside an event loop — use a new loop in the
                # current thread for the gate run.
                _loop = _asyncio_gate.new_event_loop()
                try:
                    return _loop.run_until_complete(_assert_publishable(
                        draft_text=_text,
                        source_raw_content=_raw_source_for_gate,
                        path="cron_auto",
                        draft_id=_did,
                    ))
                finally:
                    _loop.close()

        def _run_async(_coro):
            # Netlik gate'i (async) için _run_gate ile aynı sync sarmalayıcı.
            try:
                return _asyncio_gate.run(_coro)
            except RuntimeError:
                _l2 = _asyncio_gate.new_event_loop()
                try:
                    return _l2.run_until_complete(_coro)
                finally:
                    _l2.close()

        _blocked_idx: set = set()
        for _i, (_pd_g, _pp_g) in enumerate(
            zip(self.state.platform_drafts, postiz_posts)
        ):
            _draft_id_for_gate = (
                getattr(_pd_g, "daily_draft_id", None)
                or f"flow-cron-{_i}"
            )
            _outcome = _run_gate(_pp_g.content, _draft_id_for_gate)
            # W1-1 (2026-06-11) — HARD_BLOCK'ta blokun sebebi yazara geri
            # verilip BİR KEZ yeniden yazdırılır; PASS'a dönerse yayın sürer.
            # (Anthropic vakası: gate 2 yorum cümlesini fabrikasyon saydı,
            # repair olmadığı için 5 draft + $3.5 video komple rehin kaldı.)
            if _outcome.is_block:
                _viol = (
                    getattr(_outcome, "reasoning", None)
                    or getattr(_outcome, "verdict", "")
                    or ""
                )
                logger.info(
                    f"[gate-repair] {_pd_g.platform} blocked — attempting "
                    f"one rewrite: {str(_viol)[:120]}"
                )
                _new_text = self._gate_repair_rewrite(
                    pd=_pd_g, violations=str(_viol),
                    raw_source=_raw_source_for_gate,
                )
                if _new_text:
                    _re_outcome = _run_gate(_new_text, _draft_id_for_gate)
                    if not _re_outcome.is_block:
                        logger.info(
                            f"[gate-repair] {_pd_g.platform} rewrite PASSED "
                            f"gate — publishing repaired text"
                        )
                        # 2026-06-11 (Hype müdür yakaladı): PlatformPost
                        # frozen dataclass — `.content =` FrozenInstanceError
                        # atıp run'ı tam onarım başarılı anında çökertiyordu.
                        # PlatformDraft (Pydantic) atanabilir; PlatformPost
                        # için yeni instance + listede değiştir.
                        import dataclasses as _dc
                        _pd_g.content = _new_text
                        _pp_g = _dc.replace(_pp_g, content=_new_text)
                        postiz_posts[_i] = _pp_g
                        _outcome = _re_outcome
                    else:
                        logger.warning(
                            f"[gate-repair] {_pd_g.platform} rewrite still "
                            f"blocked — deferring this platform only"
                        )
            # ── Netlik gate'i (12 Haz 2026, Berkay) ── faithfulness'ı GEÇEN
            # platform metni "normal biri anlar mı?" yargısından geçer; kalırsa
            # BİR KEZ sade-Türkçe yeniden yazılır. Yeniden yazım faithfulness'tan
            # DA geçmeli (uydurma sokmasın) — geçmezse orijinal kalır. FAIL-OPEN:
            # hata yayını durdurmaz; güvenlik faithfulness'ta.
            if not _outcome.is_block:
                try:
                    from tools.clarity_gate import check_clarity, clarity_rewrite
                    _cv = _run_async(check_clarity(_pp_g.content, _pd_g.platform))
                    if not _cv.get("clear", True):
                        logger.info(
                            f"[clarity] {_pd_g.platform} anlaşılmaz "
                            f"({_cv.get('reason','')[:80]}) — sadeleştiriliyor"
                        )
                        _ct = _run_async(clarity_rewrite(
                            _pp_g.content, source=_raw_source_for_gate,
                            platform=_pd_g.platform,
                        ))
                        if _ct and _ct.strip() and _ct.strip() != (_pp_g.content or "").strip():
                            _cg = _run_gate(_ct, _draft_id_for_gate)
                            if not _cg.is_block:
                                import dataclasses as _dc2
                                _pd_g.content = _ct
                                _pp_g = _dc2.replace(_pp_g, content=_ct)
                                postiz_posts[_i] = _pp_g
                                # 2026-06-12 (Berkay): KRİTİK — gate outcome'u da
                                # yenile. Yoksa _gate_outcomes'a ESKİ token eklenir,
                                # GuardedPostizClient "gated A, publishing B" deyip
                                # TÜM batch'i reddeder (publish FAILED). gate-repair
                                # bloğu zaten _outcome=_re_outcome yapıyor.
                                _outcome = _cg
                                logger.info(
                                    f"[clarity] {_pd_g.platform} sadeleştirildi "
                                    f"(faithfulness OK)"
                                )
                            else:
                                logger.info(
                                    f"[clarity] {_pd_g.platform} sade versiyon "
                                    f"faithfulness'a takıldı — orijinal kalır"
                                )
                except Exception as _ce:
                    logger.warning(
                        f"[clarity] {_pd_g.platform} hata (atlandı): "
                        f"{type(_ce).__name__}: {_ce}"
                    )
            _gate_outcomes.append(_outcome)
            if _outcome.is_block:
                _blocked_idx.add(_i)
                _gate_blocked.append(
                    f"{_pd_g.platform}({_draft_id_for_gate[:8]}): {_outcome.verdict}"
                )
        if _gate_blocked:
            # W1-1 (2026-06-11) — batch artık rehin alınmaz: YALNIZ bloklu
            # platform draftları pending_review'a düşer, geçenler yayınlanır.
            logger.warning(
                f"[Flow] faithfulness gate blocked (post-repair): "
                f"{_gate_blocked} — deferring ONLY those; "
                f"{len(self.state.platform_drafts) - len(_blocked_idx)} "
                f"draft(s) continue to publish"
            )
            for _bi in sorted(_blocked_idx):
                _pd_h = self.state.platform_drafts[_bi]
                # 2026-06-07 fix: was pd=_pd_h → TypeError, crashed the
                # auto-publish hold path exactly when the gate blocked a
                # fabrication, losing the drafts the gate just protected.
                pr_did_h = self._write_daily_draft(
                    platform_draft=_pd_h,
                    status="pending_review",
                    postiz_post_id=None,
                    scheduled_at=None,
                    content_thread_id=thread_id or None,
                )
                _pd_h.daily_draft_id = pr_did_h
            _keep = [
                _i for _i in range(len(self.state.platform_drafts))
                if _i not in _blocked_idx
            ]
            self.state.platform_drafts = [
                self.state.platform_drafts[_i] for _i in _keep
            ]
            postiz_posts = [postiz_posts[_i] for _i in _keep]
            _gate_outcomes = [_gate_outcomes[_i] for _i in _keep]
            if not self.state.platform_drafts:
                self.state.error = (
                    "faithfulness_gate_blocked: " + ", ".join(_gate_blocked)
                )
                self._finalize("blocked_by_gate")
                return

        # ── LangGraph Faz 2 — Postiz IDEMPOTENCY (çift LIVE post koruması) ──
        # Resume senaryosunda bu run zaten bir kısım platformu Postiz'e
        # schedule etmiş olabilir (daily_drafts.postiz_post_id dolu). schedule
        # API'sini bu platformlar için TEKRAR çağırmak = ikinci canlı post.
        # Bu yüzden invoke öncesi bu run'ın daha önce schedule ettiği platformu
        # (postiz_post_id IS NOT NULL, PENDING_* placeholder HARİÇ) tespit edip
        # schedule_posts'tan ÇIKARIRIZ; var olan id'yi yeniden kullanırız.
        #
        # NO-OP guarantee (normal ilk run): taze run'da bu run_id için hiçbir
        # satırda gerçek postiz_post_id yoktur → harita boş → tüm platformlar
        # schedule edilir, davranış bugünküyle birebir.
        _already_scheduled: dict[str, str] = {}  # platform_lc → postiz_post_id
        # ── BLOCKER-1 — Postiz write-ahead orphan tespiti ──────────────────
        # postiz_post_id == 'SCHEDULING' (write-ahead sentinel) demek: bu run
        # için bu platforma BİR Postiz schedule_posts çağrısı GİDİYORDU ama
        # gerçek postId yazılamadan crash oldu. Postiz idempotency-key/reference
        # DESTEKLEMEDİĞİ için (aşağıya bak) bu satırı güvenle gerçek bir post'a
        # eşleyemeyiz → kör tekrar schedule = ÇİFT CANLI POST riski. Bu yüzden
        # FAIL-CLOSED: orphan varsa run'ı failed işaretle + CRITICAL alarm.
        _scheduling_orphans: set[str] = set()  # platform_lc
        _run_id_for_postiz = self.state.run_id
        # Resume-safety (write-ahead + SCHEDULING orphan + idempotent skip) YALNIZ
        # LangGraph yolunda gerekli — CrewAI resume etmez (checkpoint yok). flag OFF'ta
        # bu bloklar atlanır → publish byte-for-byte ESKİ davranış → Faz 2 deploy'u
        # gerçekten INERT (canlı CrewAI publish yolu değişmez; rollback = flag off).
        # PER-ACCOUNT (runner.run_for_account ile AYNI karar): hype_account_config.
        # langgraph_enabled (DB-wins) → NULL ise env. Bu hesap LangGraph yolundaysa
        # write-ahead AKTİF; değilse byte-for-byte eski CrewAI publish (INERT).
        from config import effective_langgraph_enabled
        _lg_resume_safety = effective_langgraph_enabled(self.state.account_id)
        if _run_id_for_postiz and _lg_resume_safety:
            try:
                _prev = (
                    make_supabase().table("daily_drafts")
                    .select("platform, postiz_post_id")
                    .eq("hype_run_id", _run_id_for_postiz)
                    .not_.is_("postiz_post_id", "null")
                    .is_("deleted_at", "null")
                    .execute()
                )
                for _r in (_prev.data or []):
                    if not isinstance(_r, dict):
                        continue
                    _plat = _r.get("platform")
                    _pid = _r.get("postiz_post_id")
                    if not (isinstance(_plat, str) and isinstance(_pid, str) and _pid):
                        continue
                    if _pid == "SCHEDULING":
                        # Write-ahead sentinel — bir Postiz çağrısı gitmiş
                        # OLABİLİR ama id kaydedilmedi → fail-closed adayı.
                        _scheduling_orphans.add(_plat.lower())
                    elif not _pid.startswith("PENDING"):
                        # PENDING_* / PENDING_REVIEW placeholder'ları GERÇEK
                        # schedule değildir → atla (tekrar schedule edilmeli).
                        # SCHEDULING de değil → gerçek postId → reuse et.
                        _already_scheduled[_plat.lower()] = _pid
                if _already_scheduled:
                    logger.warning(
                        f"[Flow] Postiz IDEMPOTENT skip (resume): run={_run_id_for_postiz} "
                        f"zaten schedule edilmiş platformlar={list(_already_scheduled.keys())} "
                        f"— bunlar yeniden schedule EDİLMEYECEK (çift LIVE post önlendi)"
                    )
            except Exception as _pe:
                logger.warning(
                    f"[Flow] Postiz idempotency pre-check failed "
                    f"(tüm platformlar schedule edilecek): {_pe}"
                )

        # to-schedule alt kümesi (gate_outcomes ile hizayı koru) + tam-liste
        # için platform→id eşleme planı.
        _to_sched_posts: list = []
        _to_sched_outcomes: list = []
        _to_sched_pds: list = []  # write-ahead için karşılık gelen PlatformDraft'lar
        _sched_plan: list[tuple[int, Optional[str]]] = []  # (idx, reused_id|None)
        for _idx, (_pd_s, _pp_s) in enumerate(
            zip(self.state.platform_drafts, postiz_posts)
        ):
            _reuse = _already_scheduled.get(_pd_s.platform.lower())
            if _reuse:
                _sched_plan.append((_idx, _reuse))
            else:
                _sched_plan.append((_idx, None))
                _to_sched_posts.append(_pp_s)
                _to_sched_pds.append(_pd_s)
                # gate_outcomes schedule_posts'a postiz_posts ile birebir
                # geçtiğinden aynı alt-kümeyle filtrele.
                if _idx < len(_gate_outcomes):
                    _to_sched_outcomes.append(_gate_outcomes[_idx])

        # ── BLOCKER-1 — FAIL-CLOSED: SCHEDULING orphan tespiti ─────────────
        # Schedule edilecek bir platform 'SCHEDULING' sentinel'ine sahipse, bu
        # run için ona bir Postiz çağrısı ZATEN gitmiş OLABİLİR (write-ahead
        # yapılmış, çağrı yapılmış, ama gerçek postId yazılmadan crash). Postiz
        # idempotency-key / client-reference DESTEKLEMİYOR (postiz_client:
        # schedule_posts gövdesinde reference alanı yok; list_posts yalnız
        # tarih penceresi + integration ile döner → gönderdiğimiz post'u kesin
        # eşleyemeyiz). Bu yüzden FAIL-CLOSED: çift-post riskini almaktansa
        # run'ı durdur, operatör manuel reconcile etsin. Güvenli > tam.
        _orphan_hits = sorted(
            {
                _pd.platform.lower()
                for _pd in _to_sched_pds
                if _pd.platform.lower() in _scheduling_orphans
            }
        )
        if _orphan_hits:
            logger.error(
                f"[Flow] BLOCKER-1 FAIL-CLOSED: run={_run_id_for_postiz} "
                f"SCHEDULING orphan platform(lar)={_orphan_hits} — bir Postiz "
                f"çağrısı kaydedilmeden crash olmuş olabilir; KÖR yeniden "
                f"schedule edilMEYECEK (çift LIVE post riski). Run failed."
            )
            self.state.error = (
                "postiz_scheduling_orphan: "
                + ", ".join(_orphan_hits)
                + " — manuel reconcile gerek"
            )
            try:
                from tools.alerter import send_alert as _send_alert
                _send_alert(
                    "Postiz SCHEDULING orphan — manuel reconcile gerek, çift-post riski",
                    severity="critical",
                    platform=",".join(_orphan_hits),
                    reason=(
                        f"run={_run_id_for_postiz} resume sırasında postiz_post_id="
                        f"'SCHEDULING' kaldığı platform(lar) bulundu: {_orphan_hits}. "
                        "Postiz idempotency-key desteklemediği için kör yeniden "
                        "schedule fail-closed engellendi."
                    ),
                    action=(
                        "Postiz panelinde bu run'a ait planlı post var mı kontrol et; "
                        "varsa daily_drafts.postiz_post_id'yi gerçek id ile elle güncelle, "
                        "yoksa SCHEDULING satırını sil ve run'ı yeniden tetikle."
                    ),
                    extra={"hype_run_id": _run_id_for_postiz, "platforms": _orphan_hits},
                )
            except Exception as _ae:
                logger.warning(f"[Flow] orphan CRITICAL alert gönderilemedi: {_ae}")
            self._finalize("failed")
            return

        # ── BLOCKER-1 — WRITE-AHEAD: schedule_posts'tan ÖNCE sentinel rezerve et.
        # Schedule edilecek HER platform için daily_drafts satırını idempotent
        # _write_daily_draft ile 'SCHEDULING' sentinel postiz_post_id'siyle
        # oluştur. Crash schedule_posts ÇAĞRISI ile writeback ARASINDA olursa,
        # resume bu sentinel'i görüp yukarıdaki FAIL-CLOSED yoluna girer (kör
        # tekrar yok). Writeback (aşağıda) aynı (run,platform,content_type)
        # satırını gerçek postId'ye UPDATE eder → idempotent.
        # NO-OP (taze run): satır yoksa sentinel'le oluşturulur, sonra gerçek
        # id ile UPDATE edilir → net 1 satır/platform, bugünkü son durum.
        if _run_id_for_postiz and _lg_resume_safety and _to_sched_pds:
            for _wa_pd in _to_sched_pds:
                try:
                    self._write_daily_draft(
                        platform_draft=_wa_pd,
                        status="pending",
                        postiz_post_id="SCHEDULING",
                        scheduled_at=scheduled_at_dt.isoformat(),
                        content_thread_id=thread_id or None,
                        auto_published=True,
                    )
                except Exception as _wae:
                    # Write-ahead başarısızsa fail-closed: sentinel olmadan
                    # schedule edersek crash penceresi tekrar açılır.
                    logger.exception(
                        f"[Flow] BLOCKER-1 write-ahead başarısız "
                        f"(platform={_wa_pd.platform}); fail-closed: {_wae}"
                    )
                    self.state.error = (
                        f"postiz_writeahead_failed: {_wa_pd.platform}: "
                        f"{type(_wae).__name__}"
                    )
                    self._finalize("failed")
                    return

        if not _to_sched_posts:
            # Her platform zaten schedule edilmiş — Postiz çağrısı YOK.
            logger.info(
                "[Flow] Postiz: tüm platformlar zaten schedule edilmiş; "
                "schedule_posts atlanıyor (resume idempotent)"
            )
            resp = []
        else:
            try:
                resp = postiz.schedule_posts(
                    _to_sched_posts, scheduled_at_dt, gate_outcomes=_to_sched_outcomes,
                )
            except _GuardedPublishRefused as e:
                # The guarded client refused — that's a code bug (gate said PASS
                # but the wrapper still rejected). Hold the batch + scream.
                logger.exception(
                    f"[Flow] GuardedPostizClient REFUSED a PASS batch — code bug: {e}"
                )
                self.state.error = f"guarded_publish_refused: {e}"
                self._finalize("failed")
                return
            except Exception as e:
                logger.exception(f"[Flow] Postiz schedule failed: {e}")
                self.state.error = f"Postiz error: {type(e).__name__}: {str(e)[:200]}"
                self._finalize("failed")
                return

        # Postiz returns either a list of per-post ids OR a single object;
        # try several shapes. When platform-to-id mapping is impossible we use a
        # synthetic prefix so each row still has a unique key.
        #
        # 2026-06-11 (Berkay, ilk otonom yayın): Postiz /posts yanıtı
        # [{"postId": "...", "integration": "..."}] — anahtar `postId`. Parser
        # yalnız `id` arıyordu → gerçek ID alınamayıp PENDING_ ile dolduruluyordu;
        # her otonom post DB'de PENDING_ kalıp reconcile olamıyor, release_url
        # dolmuyordu (UI-approve yolu farklı olduğu için bugüne dek görünmedi).
        def _extract_pid(d: dict) -> Optional[str]:
            v = d.get("postId") or d.get("id") or d.get("post_id")
            return str(v) if v else None

        # Yalnız YENİ schedule edilen alt-küme için dönen id'ler.
        fresh_post_ids: list[str] = []
        if isinstance(resp, dict):
            top = _extract_pid(resp)
            if top:
                fresh_post_ids.append(top)
            for it in (resp.get("posts") or []):
                if isinstance(it, dict):
                    _pid = _extract_pid(it)
                    if _pid:
                        fresh_post_ids.append(_pid)
        elif isinstance(resp, list):
            for it in resp:
                if isinstance(it, dict):
                    _pid = _extract_pid(it)
                    if _pid:
                        fresh_post_ids.append(_pid)

        # LangGraph Faz 2 — tam-liste post_ids'yi _sched_plan'a göre birleştir:
        # skip edilen slot'lar (resume) var olan id'yi kullanır; yeni schedule
        # edilen slot'lar fresh_post_ids'i SIRAYLA tüketir. Böylece aşağıdaki
        # writeback zip'i self.state.platform_drafts ile birebir hizalı kalır.
        # NO-OP davranış (normal ilk run): _sched_plan tüm slotları None tutar →
        # tüm id'ler fresh_post_ids'ten gelir = bugünkü davranış.
        post_ids: list[str] = []
        _fresh_it = iter(fresh_post_ids)
        for _idx, _reused in _sched_plan:
            if _reused is not None:
                post_ids.append(_reused)
            else:
                _nxt = next(_fresh_it, None)
                post_ids.append(_nxt if _nxt else f"PENDING_{uuid.uuid4().hex[:10]}")

        # Pad with synthetic ids so each platform has one (defensive)
        while len(post_ids) < len(self.state.platform_drafts):
            post_ids.append(f"PENDING_{uuid.uuid4().hex[:10]}")

        primary_draft_id: Optional[str] = None
        primary_post_id: Optional[str] = None
        for pd, postiz_pid in zip(self.state.platform_drafts, post_ids):
            pd.postiz_post_id = postiz_pid
            pd.scheduled_at = scheduled_at_dt.isoformat()
            did = self._write_daily_draft(
                platform_draft=pd,
                status="pending",
                postiz_post_id=postiz_pid,
                scheduled_at=scheduled_at_dt.isoformat(),
                content_thread_id=thread_id or None,
                # Phase 43.D — Critic's freeze gate: only auto_published=true
                # rows feed the monthly quality audit's random sample, so the
                # ≥3/10 fail freeze trains on the exact posts that bypassed
                # human approval.
                auto_published=True,
            )
            pd.daily_draft_id = did
            if primary_draft_id is None:
                primary_draft_id = did
                primary_post_id = postiz_pid

        # PublisherOutput stays singular for legacy callers; references the
        # primary (first) platform post.
        first_pd = self.state.platform_drafts[0]
        self.state.publish = PublisherOutput(
            postiz_post_id=primary_post_id or "UNKNOWN",
            integration_id=first_pd.integration_id,
            scheduled_at=scheduled_at_dt,
            platform=first_pd.platform,
            dry_run=False,
        )

        logger.info(
            f"[Flow] PUBLISH — {len(self.state.platform_drafts)} platform(s) scheduled, "
            f"thread={thread_id} primary_draft={primary_draft_id}"
        )

        # 13 Haz 2026 (Berkay): haber yayınlandıktan SONRA o habere KONUSU BAĞLI
        # 1 SÖZLÜK + 1 SENCE? kartı zamanla. NON-FATAL — kart üretimi/yayını HABERİ
        # ASLA bloklamaz (try/except + ayrı event loop). Yayın flag'i kapalıysa
        # kartlar pending_review draft olur.
        try:
            import asyncio as _aio

            from tools.card_scheduler import schedule_companion_cards as _scc
            _tr = self.state.trend
            _src = getattr(_tr, "raw_content", None) or getattr(_tr, "full_source_text", None)
            _n = _aio.run(_scc(
                self.state.account_id,
                news_topic=_tr.topic,
                news_source=_src,
                trend_id=getattr(_tr, "trend_id", None),
                base_time_utc=scheduled_at_dt,
            ))
            logger.info(f"[Flow] companion kartlar: {_n} (SÖZLÜK+SENCE?)")
        except Exception as _ce:  # noqa: BLE001
            logger.warning(f"[Flow] companion kart hatası (haber etkilenmedi): {_ce}")

        self._finalize(
            "approved",
            daily_draft_id=primary_draft_id,
            postiz_post_id=primary_post_id,
            scheduled_at=scheduled_at_dt.isoformat(),
            draft_content=self.state.draft.content,
        )

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _lookup_user_id(self) -> Optional[str]:
        sb = make_supabase()
        r = sb.table("connected_accounts").select("user_id").eq("id", self.state.account_id).limit(1).execute()
        rows = r.data if isinstance(r.data, list) else []
        if rows and isinstance(rows[0], dict):
            uid = rows[0].get("user_id")
            if isinstance(uid, str):
                return uid
        return None

    def _finalize(
        self,
        status: str,
        daily_draft_id: Optional[str] = None,
        postiz_post_id: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        draft_content: Optional[str] = None,
        flow_status_label: Optional[str] = None,
    ) -> None:
        flow_state_dump: dict[str, Any] = {
            "trend": self.state.trend.model_dump(mode="json") if self.state.trend else None,
            "plan": self.state.plan.model_dump(mode="json") if self.state.plan else None,
            "draft": self.state.draft.model_dump(mode="json") if self.state.draft else None,
            "compliance": self.state.compliance.model_dump(mode="json") if self.state.compliance else None,
            "publish": self.state.publish.model_dump(mode="json") if self.state.publish else None,
            "label": flow_status_label or status,
            # 2026-06-07 P1: editor's-desk decision recorded on every finalize
            # so /control/karar-izi + analytics can answer "was the editor's
            # desk actually driving picks today?" instead of grep'ing logs.
            "editor_decision": self.state.editor_decision,
            "editor_decision_error": self.state.editor_decision_error,
        }
        # Şeffaflık: aday-eleme dökümü (Crew Akışı'nda "X/Y aday geçti").
        try:
            from tools.supabase_tools import consume_gate_breakdown
            _bd = consume_gate_breakdown(self.state.account_id)
            if _bd:
                flow_state_dump["gate_breakdown"] = _bd
        except Exception:
            pass
        finalize_run(
            run_id=self.state.run_id,
            status=status,
            draft_content=draft_content or (self.state.draft.content if self.state.draft else None),
            daily_draft_id=daily_draft_id,
            postiz_post_id=postiz_post_id,
            scheduled_at=scheduled_at,
            error=self.state.error,
            flow_state=flow_state_dump,
            started_at_ts=self.state.started_at_ts or None,
            trend_id=self.state.trend.trend_id if self.state.trend else None,
        )
        self.state.final_status = status
