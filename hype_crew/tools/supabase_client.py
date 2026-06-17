"""Shared Supabase client — single instance per process (fresh per crew run).

We instantiate per-process (not module-level singleton) to keep "fresh isolated
session" pattern from the autonomy architecture: each systemd timer fire =
new Python process = new Supabase client = zero state leak between runs.
"""
from supabase import Client, create_client

from config import settings


def make_supabase() -> Client:
    """Create a new Supabase service-role client. Call once per crew run."""
    return create_client(settings.supabase_url, settings.supabase_service_key)
