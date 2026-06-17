"""Phase 28.M — Transparent shared-workspace access control.

Returns the set of `user_id`s whose data a requesting user can see.
Always includes the requesting user; adds any workspace owners they are
an accepted, non-revoked collaborator on (Phase 28.G workspace_collaborators).

Used by every backend filter/list endpoint instead of `.eq("user_id", user.id)`:
    accessible = accessible_owner_ids(user.id)
    sb.table("...").select("*").in_("user_id", accessible).execute()

RLS already permits collaborator reads (Phase 28.G policies). This helper just
widens the application-layer filter so the data actually surfaces.
"""
from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)


def accessible_owner_ids(user_id: str, supabase=None) -> list[str]:
    """Return the requesting user_id plus every workspace owner_user_id they
    are an accepted collaborator on.

    Caller passes `supabase` (service-role client) explicitly OR the helper
    lazy-imports it from `server` if omitted. Lazy import avoids circular
    deps because `server` imports route modules.

    On any DB error the helper falls back to `[user_id]` — fail-safe to the
    user's own scope rather than crashing the request.
    """
    ids: set[str] = {user_id}
    if not user_id:
        return []

    if supabase is None:
        from server import supabase as _sb  # local import to avoid cycle
        supabase = _sb

    try:
        rows = (
            supabase.table("workspace_collaborators")
            .select("owner_user_id")
            .eq("user_id", user_id)
            .not_.is_("accepted_at", "null")
            .is_("revoked_at", "null")
            .execute()
        )
        for r in (rows.data or []):
            owner = r.get("owner_user_id")
            if owner:
                ids.add(owner)
    except Exception as exc:
        logger.warning(
            f"[access_control] workspace_collaborators lookup failed for "
            f"user_id={user_id}: {exc!s} — falling back to self-only scope"
        )

    return list(ids)
