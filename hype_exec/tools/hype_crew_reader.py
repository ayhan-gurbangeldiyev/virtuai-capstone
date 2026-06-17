"""Read-only queries against Hype Crew tables to build meeting agendas."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from .supabase_client import make_supabase


def _iso(hours_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def get_today_runs(account_id: str, hours: int = 24) -> dict[str, Any]:
    sb = make_supabase()
    rows = sb.table("hype_runs").select(
        "id,status,total_cost_usd,total_tokens,started_at,completed_at,error"
    ).eq("account_id", account_id).gte("started_at", _iso(hours)).execute()
    data = rows.data or []
    statuses = [r.get("status") for r in data]
    return {
        "total": len(data),
        "completed": sum(1 for s in statuses if s == "completed"),
        "failed": sum(1 for s in statuses if s == "failed"),
        "rejected_by_compliance": sum(1 for s in statuses if s == "rejected_by_compliance"),
        "executive_freeze": sum(1 for s in statuses if s == "executive_freeze"),
        "total_cost_usd": round(sum(float(r.get("total_cost_usd") or 0) for r in data), 4),
        "recent_errors": [r.get("error") for r in data if r.get("status") == "failed"][-3:],
    }


def get_pending_drafts(account_id: str, limit: int = 10) -> list[dict[str, Any]]:
    sb = make_supabase()
    rows = sb.table("daily_drafts").select(
        "id,platform,trend_topic,content,status,created_at"
    ).eq("account_id", account_id).eq("source", "hype_auto").eq("status", "pending")\
        .order("created_at", desc=True).limit(limit).execute()
    return rows.data or []


def get_failure_streak(account_id: str, n: int = 10) -> dict[str, Any]:
    sb = make_supabase()
    rows = sb.table("hype_runs").select("status,started_at,error")\
        .eq("account_id", account_id).order("started_at", desc=True).limit(n).execute()
    data = rows.data or []
    streak = 0
    for r in data:
        if r.get("status") == "failed":
            streak += 1
        else:
            break
    return {"window": n, "consecutive_failed": streak, "recent_errors": [r.get("error") for r in data[:3]]}


def get_engagement_summary(account_id: str, days: int = 7) -> dict[str, Any]:
    sb = make_supabase()
    rows = sb.table("hype_memory").select("content,metadata,importance_score,created_at")\
        .eq("account_id", account_id).eq("memory_type", "performance_log")\
        .gte("created_at", _iso(days * 24)).order("created_at", desc=True).limit(50).execute()
    data = rows.data or []
    if not data:
        return {"samples": 0, "avg_importance": None, "top_3": []}
    importances = [float(r.get("importance_score") or 0) for r in data]
    return {
        "samples": len(data),
        "avg_importance": round(sum(importances) / len(importances), 3),
        "top_3": [{"content": r.get("content")[:160], "score": float(r.get("importance_score") or 0)} for r in sorted(data, key=lambda x: -(x.get("importance_score") or 0))[:3]],
    }


def get_account_config(account_id: str) -> dict[str, Any]:
    sb = make_supabase()
    row = sb.table("hype_account_config").select("*").eq("account_id", account_id).limit(1).execute()
    return (row.data or [{}])[0]


def get_compliance_window(account_id: str, hours: int = 48) -> dict[str, Any]:
    """Recent compliance verdicts from persona_assets joined via daily_drafts."""
    sb = make_supabase()
    rows = sb.table("persona_assets").select(
        "id,compliance_passed,clip_persona_similarity,aesthetic_score,llm_judge_verdict,visual_mode,created_at"
    ).gte("created_at", _iso(hours)).order("created_at", desc=True).limit(50).execute()
    data = rows.data or []
    if not data:
        return {"samples": 0, "pass_rate": None}
    passes = sum(1 for r in data if r.get("compliance_passed"))
    verdicts = {}
    for r in data:
        v = r.get("llm_judge_verdict") or "n/a"
        verdicts[v] = verdicts.get(v, 0) + 1
    return {
        "samples": len(data),
        "pass_rate": round(passes / len(data), 3),
        "verdict_breakdown": verdicts,
        "low_clip_count": sum(1 for r in data if (r.get("clip_persona_similarity") or 1) < 0.55),
    }


def build_agenda(account_id: str, *, kind: str) -> dict[str, Any]:
    """Compose an agenda dict for the requested meeting kind.

    kind ∈ {hourly_heartbeat, daily_standup, weekly_review, event_triggered}
    """
    try:
        if kind == "hourly_heartbeat":
            return {
                "kind": kind,
                "runs_last_24h": get_today_runs(account_id, hours=24),
                "failure_streak": get_failure_streak(account_id, n=10),
                "compliance_48h": get_compliance_window(account_id, hours=48),
            }
        if kind == "daily_standup":
            return {
                "kind": kind,
                "runs_last_24h": get_today_runs(account_id, hours=24),
                "pending_drafts": get_pending_drafts(account_id, limit=10),
                "compliance_48h": get_compliance_window(account_id, hours=48),
                "engagement_7d": get_engagement_summary(account_id, days=7),
                "config_snapshot": get_account_config(account_id),
            }
        if kind == "weekly_review":
            return {
                "kind": kind,
                "runs_last_7d": get_today_runs(account_id, hours=24 * 7),
                "engagement_7d": get_engagement_summary(account_id, days=7),
                "compliance_7d": get_compliance_window(account_id, hours=24 * 7),
                "config_snapshot": get_account_config(account_id),
            }
        # event_triggered → caller passes its own agenda
        return {"kind": kind}
    except Exception as e:
        logger.exception(f"build_agenda failed for kind={kind}: {e}")
        return {"kind": kind, "agenda_build_error": str(e)}
