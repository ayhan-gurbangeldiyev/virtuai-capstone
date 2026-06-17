"""Phase 26 — Executive Board user-facing API.

  GET    /exec/decisions                   — list (filter: status, role, days, account_id)
  POST   /exec/decisions/{id}/approve      — flip awaiting_approval → approved_pending_resume
  POST   /exec/decisions/{id}/reject       — flip awaiting_approval → rejected_pending_resume
  POST   /exec/decisions/{id}/revert       — undo auto_executed decision (re-apply old_value)
  GET    /exec/memos                       — per-role memo timeline
  GET    /exec/meetings                    — meeting log with transcripts

Auth: require_auth + account ownership via connected_accounts.user_id.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from middleware.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exec", tags=["exec"])


def get_supabase():
    from server import supabase
    return supabase


def _verify_account_ownership(account_id: str, user_id: str) -> None:
    """Phase 28.M — workspace-aware: owner OR accepted collaborator."""
    from services.access_control import accessible_owner_ids
    sb = get_supabase()
    row = (
        sb.table("connected_accounts")
        .select("id")
        .eq("id", account_id)
        .in_("user_id", accessible_owner_ids(user_id))
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "account not found or unauthorized")


def _verify_decision_ownership(decision_id: str, user_id: str) -> dict:
    sb = get_supabase()
    row = sb.table("executive_decisions").select("*").eq("id", decision_id).limit(1).execute()
    if not row.data:
        raise HTTPException(404, "decision not found")
    d = row.data[0]
    _verify_account_ownership(d["account_id"], user_id)
    return d


# ─── Decisions ─────────────────────────────────────────────────────────────


@router.get("/decisions")
async def list_decisions(
    account_id: str = Query(...),
    status: Optional[Literal[
        "awaiting_approval", "approved_pending_resume", "rejected_pending_resume",
        "auto_executed", "executed", "rejected", "reverted", "expired", "failed",
    ]] = None,
    role: Optional[Literal["CEO", "CPO", "CBPO", "CFO", "CRO"]] = None,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(require_auth),
):
    _verify_account_ownership(account_id, user.id)
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = sb.table("executive_decisions").select("*")\
        .eq("account_id", account_id)\
        .gte("created_at", since)\
        .order("created_at", desc=True)\
        .limit(limit)
    if status:
        q = q.eq("status", status)
    if role:
        q = q.eq("role_responsible", role)
    rows = q.execute()
    return {"items": rows.data or [], "count": len(rows.data or [])}


@router.post("/decisions/{decision_id}/approve")
async def approve_decision(decision_id: str, user=Depends(require_auth)):
    d = _verify_decision_ownership(decision_id, user.id)
    if d["status"] != "awaiting_approval":
        raise HTTPException(400, f"decision not pending (status={d['status']})")
    sb = get_supabase()
    sb.table("executive_decisions").update({
        "status": "approved_pending_resume",
        "approved_by": user.id,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", decision_id).execute()
    logger.info(f"[exec] decision {decision_id} approved by {user.id}")
    return {"status": "approved_pending_resume", "id": decision_id}


@router.post("/decisions/{decision_id}/reject")
async def reject_decision(decision_id: str, user=Depends(require_auth)):
    d = _verify_decision_ownership(decision_id, user.id)
    if d["status"] != "awaiting_approval":
        raise HTTPException(400, f"decision not pending (status={d['status']})")
    sb = get_supabase()
    sb.table("executive_decisions").update({
        "status": "rejected_pending_resume",
        "approved_by": user.id,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", decision_id).execute()
    logger.info(f"[exec] decision {decision_id} rejected by {user.id}")
    return {"status": "rejected_pending_resume", "id": decision_id}


@router.post("/decisions/{decision_id}/revert")
async def revert_decision(decision_id: str, user=Depends(require_auth)):
    d = _verify_decision_ownership(decision_id, user.id)
    if d["status"] not in ("auto_executed", "executed"):
        raise HTTPException(400, f"only auto_executed/executed decisions can be reverted (status={d['status']})")
    if not d.get("old_value"):
        raise HTTPException(400, "decision has no old_value to revert to")

    sb = get_supabase()
    target_table = d.get("target_table")
    if target_table == "hype_account_config":
        sb.table("hype_account_config").update({
            **(d["old_value"] or {}),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("account_id", d["account_id"]).execute()
    else:
        raise HTTPException(400, f"revert not implemented for target_table={target_table}")
    sb.table("executive_decisions").update({
        "status": "reverted",
        "reverted_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", decision_id).execute()
    logger.info(f"[exec] decision {decision_id} reverted by {user.id}")
    return {"status": "reverted", "id": decision_id}


# ─── Memos ─────────────────────────────────────────────────────────────────


@router.get("/memos")
async def list_memos(
    account_id: str = Query(...),
    role: Optional[Literal["CEO", "CPO", "CBPO", "CFO", "CRO"]] = None,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(require_auth),
):
    _verify_account_ownership(account_id, user.id)
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = sb.table("executive_memos").select("*")\
        .eq("account_id", account_id)\
        .gte("created_at", since)\
        .order("created_at", desc=True)\
        .limit(limit)
    if role:
        q = q.eq("author_role", role)
    rows = q.execute()
    return {"items": rows.data or [], "count": len(rows.data or [])}


# ─── Meetings ──────────────────────────────────────────────────────────────


@router.get("/meetings")
async def list_meetings(
    account_id: str = Query(...),
    kind: Optional[Literal["hourly_heartbeat", "daily_standup", "weekly_review", "event_triggered"]] = None,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(require_auth),
):
    _verify_account_ownership(account_id, user.id)
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = sb.table("executive_meetings").select("*")\
        .eq("account_id", account_id)\
        .gte("started_at", since)\
        .order("started_at", desc=True)\
        .limit(limit)
    if kind:
        q = q.eq("kind", kind)
    rows = q.execute()
    return {"items": rows.data or [], "count": len(rows.data or [])}


@router.get("/summary")
async def exec_summary(account_id: str = Query(...), user=Depends(require_auth)):
    """Snapshot for the Executive Board tab — pending count, last meeting, recent cost."""
    _verify_account_ownership(account_id, user.id)
    sb = get_supabase()
    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    pending = sb.table("executive_decisions").select("id", count="exact")\
        .eq("account_id", account_id).eq("status", "awaiting_approval").execute()
    auto_24h = sb.table("executive_decisions").select("id", count="exact")\
        .eq("account_id", account_id).eq("status", "auto_executed")\
        .gte("created_at", since_24h).execute()
    last_meeting = sb.table("executive_meetings").select("id,kind,started_at,total_cost_usd")\
        .eq("account_id", account_id).order("started_at", desc=True).limit(1).execute()
    week_cost = sb.table("executive_meetings").select("total_cost_usd")\
        .eq("account_id", account_id).gte("started_at", since_7d).execute()
    weekly_total = sum(float(r.get("total_cost_usd") or 0) for r in (week_cost.data or []))

    return {
        "pending_approval": pending.count or 0,
        "auto_executed_24h": auto_24h.count or 0,
        "last_meeting": (last_meeting.data or [None])[0],
        "weekly_cost_usd": round(weekly_total, 4),
    }
