"""TrendScout agent — picks one trend per run from Supabase."""
from typing import Any
from crewai import Agent

from config import settings
from prompts import TRENDSCOUT_BACKSTORY
from tools import query_trends, mark_trend_processed


def build_trendscout(account_config: dict[str, Any]) -> Agent:
    """Construct the Trend Scout agent for a specific account.

    Memory: only `trend_log` scope (track what's been processed).
    LLM: fast model (filter logic, no creative work).
    """
    backstory = TRENDSCOUT_BACKSTORY.format(
        voice_description=account_config.get("voice_description") or "creator's authentic voice (style profile / brand voice applied downstream)",
        topics_focus=", ".join(account_config.get("topics_focus") or []) or "general",
        watch_accounts=", ".join(account_config.get("watch_accounts") or []) or "none specified",
        forbidden_topics=", ".join(account_config.get("forbidden_topics") or []) or "none",
        reactive_triggers=", ".join(account_config.get("reactive_triggers") or []) or "launch, breaking, milestone",
    )

    return Agent(
        role="Trend Scout",
        goal=(
            "Query the Supabase trends table, pick ONE high-value trend the creator "
            "should write about. Reject everything off-niche or low-quality."
        ),
        backstory=backstory,
        tools=[query_trends, mark_trend_processed],
        llm=settings.model_fast,
        verbose=True,
        allow_delegation=False,
        max_iter=8,
        respect_context_window=True,
    )
