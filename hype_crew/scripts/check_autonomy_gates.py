"""Phase 43.D — Autonomy gate checker.

Runs daily at 03:00 UTC via systemd timer. For each active persona, the
gate logic decides whether the per-content_type autonomy unlock flags
(`personas.{text,image,video}_autonomy_unlocked`) should flip on or off.

Decision rules (per content_type bucket):

  · "text"  bucket — content_types in {first_person_witty / blog_post /
                     access_expansion / other}
  · "image" bucket — content_types in {model_launch / feature_major /
                     feature_minor / api_update / pricing / research /
                     security / partnership / product_launch}
  · "video" bucket — drafts with non-NULL video_url

Per bucket, count drafts created in the last 30 days for that persona:

   sample_count           ≥ {text: 30, image: 20, video: 10}
   reject_rate            < 0.05  (user-driven rejects ÷ sample_count)
   edit_rate              < 0.10  (user-driven edits ÷ sample_count)

If ALL three hold → unlock that bucket. If the bucket is already
unlocked and any predicate fails → keep unlocked but log degradation
(don't auto-lock; only the monthly quality audit or 3-consecutive-reject
guard does that).

3-consecutive-reject guard:
   Per bucket, look at the most recent 3 hype_feedback rows whose
   action='rejected'. If all 3 fall within the same content_type bucket
   AND they're newer than the last unlock event, RELOCK that bucket and
   set personas.last_consecutive_reject_at = now().

This script is read-mostly + at most one UPDATE per persona, so it's
safe to run more often than daily during early calibration.

CLI:
    python -m scripts.check_autonomy_gates                # all personas
    python -m scripts.check_autonomy_gates --dry-run      # log only
    python -m scripts.check_autonomy_gates --persona <id> # single
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from tools.supabase_client import make_supabase
except Exception:  # pragma: no cover — package-import fallback
    from hype_crew.tools.supabase_client import make_supabase  # type: ignore

logger = logging.getLogger("autonomy-gates")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)


# Phase 43.D — per-bucket gate thresholds. Numbers come from the
# 2026-06-02 debate (final-report.md): "text 30 / image 20 / video 10
# samples; <5% reject + <10% edit for 30 days".
SAMPLE_MIN = {"text": 30, "image": 20, "video": 10}
MAX_REJECT_RATE = 0.05
MAX_EDIT_RATE = 0.10
LOOKBACK_DAYS = 30
CONSECUTIVE_REJECT_WINDOW = 3


# decisions.md "Per-content_type autonomy thresholds" — the content_type
# enum is the schema-level grouping (Phase 25.B). We map each value into
# one of three buckets so the gate doesn't have to track 12 separate
# unlock flags.
TEXT_CONTENT_TYPES = {
    "first_person_witty", "blog_post", "access_expansion", "other",
    "research_summary", "opinion_piece",
}
IMAGE_CONTENT_TYPES = {
    "model_launch", "feature_major", "feature_minor", "api_update",
    "pricing", "research", "security", "partnership", "product_launch",
}


def _bucket_for(content_type: Optional[str], video_url: Optional[str]) -> Optional[str]:
    """Map a draft row into one of {'text','image','video'} or None."""
    if video_url:
        return "video"
    if not content_type:
        return None
    ct = content_type.lower()
    if ct in TEXT_CONTENT_TYPES:
        return "text"
    if ct in IMAGE_CONTENT_TYPES:
        return "image"
    return None  # legacy / unknown content_types don't participate in gating


@dataclass
class BucketStats:
    sample_count: int = 0
    rejects: int = 0
    edits: int = 0

    @property
    def reject_rate(self) -> float:
        return (self.rejects / self.sample_count) if self.sample_count else 0.0

    @property
    def edit_rate(self) -> float:
        return (self.edits / self.sample_count) if self.sample_count else 0.0


def _eval_persona(
    sb,
    persona: dict,
    *,
    dry_run: bool,
) -> dict:
    """Compute bucket stats + apply unlock / lock decisions for one persona."""
    persona_id = persona["id"]
    slug = persona.get("slug") or persona_id
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()

    # Pull all hype_auto drafts in window. Lightweight — Cansu is the only
    # active persona today and the table grows slowly.
    rows = (
        sb.table("daily_drafts")
        .select("id, content_type, video_url, status, created_at")
        .eq("persona_id", persona_id)
        .eq("source", "hype_auto")
        .gte("created_at", cutoff_iso)
        .execute()
    )
    drafts = rows.data or []

    # Pull user-driven actions (reject / edit) in the same window so we
    # can compute reject_rate / edit_rate per bucket. We attribute each
    # action to the draft's bucket via draft_id JOIN.
    draft_ids = [d["id"] for d in drafts if d.get("id")]
    actions_by_draft: dict[str, list[str]] = {}
    if draft_ids:
        # Supabase pg .in_() chunked at 200 to stay clear of URL limits.
        for i in range(0, len(draft_ids), 200):
            chunk = draft_ids[i:i + 200]
            try:
                a_rows = (
                    sb.table("hype_feedback")
                    .select("draft_id, action, created_at")
                    .in_("draft_id", chunk)
                    .gte("created_at", cutoff_iso)
                    .execute()
                )
                for a in (a_rows.data or []):
                    did = a.get("draft_id")
                    act = (a.get("action") or "").lower()
                    if did and act:
                        actions_by_draft.setdefault(did, []).append(act)
            except Exception as e:
                logger.warning(f"[{slug}] hype_feedback fetch failed: {e}")

    # Bucket the drafts + tally per-bucket reject / edit counts. A draft
    # is counted as 'rejected' if ANY hype_feedback action='rejected'
    # exists for it; same for 'edited'. Approves don't reduce the counts.
    stats: dict[str, BucketStats] = {
        "text": BucketStats(),
        "image": BucketStats(),
        "video": BucketStats(),
    }
    for d in drafts:
        bucket = _bucket_for(d.get("content_type"), d.get("video_url"))
        if not bucket:
            continue
        bs = stats[bucket]
        bs.sample_count += 1
        acts = actions_by_draft.get(d["id"], [])
        if "rejected" in acts:
            bs.rejects += 1
        if "edited" in acts:
            bs.edits += 1

    # Per-bucket unlock decision.
    decisions: dict[str, dict] = {}
    update_payload: dict = {}
    for bucket, bs in stats.items():
        already_unlocked = bool(persona.get(f"{bucket}_autonomy_unlocked"))
        passes_sample = bs.sample_count >= SAMPLE_MIN[bucket]
        passes_reject = bs.reject_rate < MAX_REJECT_RATE
        passes_edit = bs.edit_rate < MAX_EDIT_RATE
        will_unlock = passes_sample and passes_reject and passes_edit
        decisions[bucket] = {
            "sample_count": bs.sample_count,
            "reject_rate": round(bs.reject_rate, 4),
            "edit_rate": round(bs.edit_rate, 4),
            "passes_sample": passes_sample,
            "passes_reject": passes_reject,
            "passes_edit": passes_edit,
            "was_unlocked": already_unlocked,
            "will_unlock": will_unlock,
        }
        if will_unlock and not already_unlocked:
            update_payload[f"{bucket}_autonomy_unlocked"] = True
            logger.info(
                f"[{slug}] UNLOCK {bucket} — n={bs.sample_count} "
                f"reject={bs.reject_rate:.2%} edit={bs.edit_rate:.2%}"
            )
        elif not will_unlock and already_unlocked:
            # Degradation: we LOG but don't auto-lock here. Only the
            # monthly quality audit (Phase 43.D quality_audit.py) or the
            # 3-consecutive-reject guard below may relock.
            logger.warning(
                f"[{slug}] DEGRADED {bucket} (NOT auto-relocked) — "
                f"n={bs.sample_count} reject={bs.reject_rate:.2%} "
                f"edit={bs.edit_rate:.2%} (need <{MAX_REJECT_RATE:.0%} "
                f"and <{MAX_EDIT_RATE:.0%}, sample≥{SAMPLE_MIN[bucket]})"
            )

    # 3-consecutive-reject guard: re-lock any bucket whose most recent
    # CONSECUTIVE_REJECT_WINDOW user actions are ALL rejects of drafts
    # in that bucket.
    consecutive_relocks: dict[str, int] = {}
    if draft_ids:
        try:
            recent = (
                sb.table("hype_feedback")
                .select("draft_id, action, created_at")
                .in_("draft_id", draft_ids)
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
            recent_rows = recent.data or []
            # Build draft_id → bucket map for quick lookup
            bucket_for_draft = {
                d["id"]: _bucket_for(d.get("content_type"), d.get("video_url"))
                for d in drafts
            }
            # Walk newest-first. Stop at the first non-reject.
            tail: list[tuple[str, str]] = []
            for r in recent_rows:
                if (r.get("action") or "").lower() != "rejected":
                    break
                b = bucket_for_draft.get(r.get("draft_id"))
                if b:
                    tail.append((b, r.get("created_at") or ""))
                if len(tail) >= CONSECUTIVE_REJECT_WINDOW:
                    break
            if len(tail) >= CONSECUTIVE_REJECT_WINDOW:
                # All in same bucket?
                buckets = {b for b, _ in tail}
                if len(buckets) == 1:
                    locked_bucket = buckets.pop()
                    if persona.get(f"{locked_bucket}_autonomy_unlocked"):
                        update_payload[f"{locked_bucket}_autonomy_unlocked"] = False
                        consecutive_relocks[locked_bucket] = CONSECUTIVE_REJECT_WINDOW
                        update_payload["last_consecutive_reject_at"] = (
                            datetime.now(timezone.utc).isoformat()
                        )
                        logger.warning(
                            f"[{slug}] RELOCK {locked_bucket} — "
                            f"{CONSECUTIVE_REJECT_WINDOW} consecutive rejects"
                        )
        except Exception as e:
            logger.warning(f"[{slug}] consecutive-reject check failed: {e}")

    # Always update the heartbeat column even if nothing changed so the
    # UI can show "last gate check ran X minutes ago".
    update_payload["last_autonomy_check_at"] = datetime.now(timezone.utc).isoformat()

    if dry_run:
        logger.info(
            f"[{slug}] DRY RUN — would update: {sorted(update_payload.keys())}"
        )
    else:
        try:
            sb.table("personas").update(update_payload).eq(
                "id", persona_id
            ).execute()
        except Exception as e:
            logger.exception(f"[{slug}] persona UPDATE failed: {e}")

    return {
        "persona_id": persona_id,
        "slug": slug,
        "decisions": decisions,
        "consecutive_relocks": consecutive_relocks,
        "updated_fields": sorted(update_payload.keys()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--persona", help="single persona id (default: all active)")
    args = parser.parse_args()

    sb = make_supabase()
    q = (
        sb.table("personas")
        .select(
            "id, slug, text_autonomy_unlocked, image_autonomy_unlocked, "
            "video_autonomy_unlocked, last_autonomy_check_at, "
            "last_consecutive_reject_at, is_active"
        )
        .eq("is_active", True)
    )
    if args.persona:
        q = q.eq("id", args.persona)
    personas = q.execute().data or []

    if not personas:
        logger.info("no active personas to evaluate")
        return 0

    for p in personas:
        try:
            _eval_persona(sb, p, dry_run=args.dry_run)
        except Exception as e:
            logger.exception(f"persona {p.get('slug')} eval failed: {e}")
    logger.info(
        f"autonomy gates pass complete: personas_evaluated={len(personas)} "
        f"dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
