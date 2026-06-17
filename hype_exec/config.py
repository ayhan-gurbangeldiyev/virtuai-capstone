"""Environment + settings loader for the Executive daemon."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Supabase
    supabase_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", ""))
    supabase_service_role_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
    supabase_db_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_DB_URL", ""))

    # Google Gemini (direct API via langchain-google-genai)
    google_api_key: str = field(default_factory=lambda: os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", ""))
    model_default: str = field(default_factory=lambda: os.environ.get("GEMINI_MODEL_DEFAULT", "gemini-3-flash-preview"))
    model_critical: str = field(default_factory=lambda: os.environ.get("GEMINI_MODEL_CRITICAL", "gemini-3.1-pro-preview"))

    # LangSmith (optional)
    langsmith_tracing: bool = field(default_factory=lambda: os.environ.get("LANGCHAIN_TRACING_V2", "false").lower() in ("1", "true", "yes"))
    langsmith_api_key: str = field(default_factory=lambda: os.environ.get("LANGCHAIN_API_KEY", ""))
    langsmith_project: str = field(default_factory=lambda: os.environ.get("LANGCHAIN_PROJECT", "hype-exec-prod"))

    # Daemon config
    health_port: int = field(default_factory=lambda: int(os.environ.get("HEALTH_PORT", "8090")))
    pool_min: int = field(default_factory=lambda: int(os.environ.get("POOL_MIN", "2")))
    pool_max: int = field(default_factory=lambda: int(os.environ.get("POOL_MAX", "10")))
    recursion_limit: int = field(default_factory=lambda: int(os.environ.get("RECURSION_LIMIT", "50")))
    tz_offset_hours: int = field(default_factory=lambda: int(os.environ.get("TZ_OFFSET_HOURS", "3")))

    # Account scope (single-tenant TypeHype for now)
    account_id: str = field(default_factory=lambda: os.environ.get("HYPE_ACCOUNT_ID", "2b731bf7-8c24-40c5-8237-d348ee822d51"))


settings = Settings()
