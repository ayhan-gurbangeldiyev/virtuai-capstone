"""Lightweight Supabase REST client (service-role) for executive tables."""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from ..config import settings


@lru_cache(maxsize=1)
def make_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
