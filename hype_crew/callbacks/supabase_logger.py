"""Observability — persist run + each agent stage to Supabase.

Design note (post Bug-1 fix):
- No ContextVar (CrewAI Flow async context boundary breaks ContextVar propagation).
- All functions take `run_id` explicitly. Flow holds run_id in `self.state.run_id`
  and passes it where needed.
- task_callback removed; Flow.run_crew batch-writes hype_stages after kickoff.
"""
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from tools.supabase_client import make_supabase


# ─── OpenRouter pricing (blended input+output, USD per 1M tokens) ────────────
# These are *rough* blended rates used for tracking only. We don't separate
# input vs output cost — typical agent runs are ~80% input prompt tokens, so
# the blended figure is close enough for budget alerts.
MODEL_COSTS_PER_MTOKEN = {
    # Google Gemini
    "openrouter/google/gemini-3-flash-preview": 0.15,  # $0.075 in / $0.30 out
    "google/gemini-3-flash-preview": 0.15,
    "openrouter/google/gemini-pro-1.5": 1.50,
    # OpenAI
    "openrouter/openai/gpt-4o-mini": 0.30,             # $0.15 in / $0.60 out
    "openrouter/openai/gpt-4o": 3.50,                  # $2.50 in / $10 out (was 5.00 — overstated)
    "openai/gpt-4o-mini": 0.30,
    "openai/gpt-4o": 3.50,
    # Anthropic
    "openrouter/anthropic/claude-3-haiku": 0.50,
    "openrouter/anthropic/claude-3-5-sonnet": 6.00,
    # 2026-06-08 — Sonnet 4.6 wired as the new WRITER model. Rate is
    # the OpenRouter blended estimate ($3 in / $15 out → blended ~8.40
    # for typical 80/20 input-heavy agent runs).
    "openrouter/anthropic/claude-sonnet-4.6": 8.40,
    "anthropic/claude-sonnet-4.6": 8.40,
}


def _estimate_cost(model: str, tokens: int) -> float:
    # Fallback at Gemini's rate (cheapest mainstream), not $1/M — most unknown
    # models on OpenRouter are at or below Gemini Flash pricing, and an
    # over-cautious fallback inflated weekly totals 6× in early testing.
    rate = MODEL_COSTS_PER_MTOKEN.get(model, 0.15)
    return round((tokens / 1_000_000) * rate, 6)


# ─── Lifecycle ──────────────────────────────────────────────────────────────


def init_run(
    account_id: str,
    trend_id: Optional[str] = None,
    triggered_by: str = "cron",
    dry_run: bool = True,
    run_id: Optional[str] = None,
) -> str:
    """Create a hype_runs row at the start of a Flow. Returns run_id.

    Called from Flow.initialize. Caller stores run_id in flow.state.run_id.

    LangGraph Faz 2 (stable thread_id): when `run_id` is provided, that value
    IS the hype_runs PK (so it can double as the LangGraph thread_id and
    correlate across processes on resume). This path is IDEMPOTENT:
      - if no row with that id exists yet → INSERT with that explicit id;
      - if a row already exists (RESUME case) → do NOT insert a duplicate;
        UPDATE status='running' and return the same id.
    The legacy callers (no `run_id` arg) are byte-for-byte unaffected: the DB
    mints the id exactly as before.
    """
    sb = make_supabase()

    # ── Resume path: caller-supplied stable id (= LangGraph thread_id) ──
    if run_id:
        try:
            existing = (
                sb.table("hype_runs").select("id").eq("id", run_id)
                .limit(1).execute()
            )
            has_row = bool(existing.data) and isinstance(existing.data, list)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[Hype] init_run pre-check failed ({run_id}); assuming fresh: {e}")
            has_row = False

        if has_row:
            # RESUME — row already exists; re-mark running, never duplicate.
            try:
                sb.table("hype_runs").update({"status": "running"}).eq("id", run_id).execute()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[Hype] init_run resume status-update failed ({run_id}): {e}")
            logger.info(f"[Hype] Run RESUMED (existing row): {run_id} account={account_id}")
            return run_id

        # Fresh run with a pre-minted id.
        row = {
            "id": run_id,
            "account_id": account_id,
            "trend_id": trend_id,
            "triggered_by": triggered_by,
            "status": "running",
            "dry_run": dry_run,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            sb.table("hype_runs").insert(row).execute()
        except Exception as e:  # noqa: BLE001
            # Race: another process inserted the same id between our pre-check
            # and insert. Treat as resume (idempotent) rather than crashing.
            logger.warning(
                f"[Hype] init_run explicit-id insert conflict ({run_id}); "
                f"treating as resume: {e}"
            )
            try:
                sb.table("hype_runs").update({"status": "running"}).eq("id", run_id).execute()
            except Exception:
                pass
        logger.info(f"[Hype] Run started (explicit id): {run_id} account={account_id} dry_run={dry_run}")
        return run_id

    # ── Legacy path (unchanged): DB mints the id ──
    row = {
        "account_id": account_id,
        "trend_id": trend_id,
        "triggered_by": triggered_by,
        "status": "running",
        "dry_run": dry_run,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    result = sb.table("hype_runs").insert(row).execute()
    rows = result.data if isinstance(result.data, list) else []
    run_id = ""
    if rows and isinstance(rows[0], dict):
        rid = rows[0].get("id")
        if isinstance(rid, str):
            run_id = rid
    logger.info(f"[Hype] Run started: {run_id} account={account_id} dry_run={dry_run}")
    return run_id


def log_stage(
    run_id: str,
    agent_name: str,
    stage_order: int,
    output: Any = None,
    model_used: str = "",
    tokens_used: int = 0,
    duration_ms: Optional[int] = None,
    status: str = "success",
    error: Optional[str] = None,
) -> None:
    """Insert one hype_stages row. Called from Flow.run_crew after crew kickoff.

    `output` is serialized to JSON-able dict. Pydantic models or dicts both fine.
    """
    if not run_id:
        logger.warning(f"[Hype] log_stage called with empty run_id; skipping ({agent_name})")
        return

    # Normalize output to JSON-able
    output_dump: Any
    if output is None:
        output_dump = None
    elif hasattr(output, "model_dump"):
        try:
            output_dump = output.model_dump(mode="json")
        except Exception:
            output_dump = str(output)[:2000]
    elif isinstance(output, (dict, list, str, int, float, bool)):
        output_dump = output
    else:
        output_dump = str(output)[:2000]

    sb = make_supabase()
    try:
        # UPSERT(run_id, stage_order) — LangGraph resume aynı stage'i tekrar loglarsa
        # INSERT yerine UPDATE (çift stage satırı yok, UI temiz). uq_hype_stages_run_order
        # (migration 025) bu on_conflict'i destekler. CrewAI yolu: stage'ler tekil →
        # davranış değişmez (her zaman yeni satır gibi).
        sb.table("hype_stages").upsert({
            "run_id": run_id,
            "agent_name": agent_name,
            "stage_order": stage_order,
            "output": output_dump,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="run_id,stage_order").execute()
        logger.info(f"[Hype] Stage {stage_order}: {agent_name} ({tokens_used} tokens, {model_used})")
    except Exception as e:
        logger.error(f"[Hype] Failed to log stage {stage_order}: {e}")


def finalize_run(
    run_id: str,
    status: str = "completed",
    draft_content: Optional[str] = None,
    daily_draft_id: Optional[str] = None,
    postiz_post_id: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    error: Optional[str] = None,
    flow_state: Optional[dict] = None,
    started_at_ts: Optional[float] = None,
    trend_id: Optional[str] = None,
) -> None:
    """Update hype_runs at end of Flow. run_id passed explicitly (no ContextVar)."""
    if not run_id:
        logger.warning("[Hype] finalize_run called with empty run_id; skipping")
        return

    sb = make_supabase()
    # Aggregate tokens + cost from logged stages
    stages = sb.table("hype_stages").select("tokens_used, model_used").eq("run_id", run_id).execute()
    stage_rows = [s for s in (stages.data if isinstance(stages.data, list) else []) if isinstance(s, dict)]

    def _as_int(v: Any) -> int:
        try:
            return int(v) if v is not None else 0
        except (TypeError, ValueError):
            return 0

    def _as_str(v: Any) -> str:
        return v if isinstance(v, str) else ""

    total_tokens = sum(_as_int(s.get("tokens_used")) for s in stage_rows)
    total_cost = sum(_estimate_cost(_as_str(s.get("model_used")), _as_int(s.get("tokens_used"))) for s in stage_rows)

    update: dict[str, Any] = {
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
    }
    if draft_content is not None:
        update["draft_content"] = draft_content
    if daily_draft_id:
        update["daily_draft_id"] = daily_draft_id
    # Only persist trend_id if it looks like a real UUID AND isn't an obvious
    # placeholder. TrendScout sometimes returns "none" / null UUID when no
    # trend qualifies; the trends FK constraint rejects both.
    ZERO_UUID = "00000000-0000-0000-0000-000000000000"
    if trend_id and trend_id.lower() not in ("none", "null", "", ZERO_UUID):
        try:
            import uuid as _uuid
            _uuid.UUID(trend_id)
            update["trend_id"] = trend_id
        except (ValueError, AttributeError):
            pass
    if postiz_post_id:
        update["postiz_post_id"] = postiz_post_id
    if scheduled_at:
        update["scheduled_at"] = scheduled_at
    if error:
        update["error"] = error[:2000]
    if flow_state:
        try:
            update["flow_state"] = json.loads(json.dumps(flow_state, default=str))
        except Exception:
            update["flow_state"] = {"_serialization_error": True}

    try:
        sb.table("hype_runs").update(update).eq("id", run_id).execute()
        elapsed = time.time() - started_at_ts if started_at_ts else None
        elapsed_str = f"{elapsed:.1f}s" if elapsed is not None else "?"
        logger.info(
            f"[Hype] Run finalized: {run_id} status={status} "
            f"tokens={total_tokens} cost=${total_cost} elapsed={elapsed_str}"
        )
    except Exception as e:
        logger.error(f"[Hype] Failed to finalize run {run_id}: {e}")
