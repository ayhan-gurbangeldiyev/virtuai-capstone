"""Planner agent — chooses the angle and V3 prompt builder parameters."""
from typing import Any
from crewai import Agent

from config import settings
from prompts import PLANNER_BACKSTORY
from tools.memory_tools import semantic_recall


def build_planner(account_config: dict[str, Any], memory_context: str) -> Agent:
    """Planner picks etki/karakter/uzunluk/hook based on trend + memory.

    Memory injection: full markdown context (voice + approved + rejected) into backstory.
    LLM: smart model (creative reasoning needed).
    """
    audience_description = (
        account_config.get("identity_card") or
        f"creator interested in {', '.join(account_config.get('topics_focus') or ['general topics'])}"
    )

    backstory = PLANNER_BACKSTORY.format(
        voice_description=account_config.get("voice_description") or "creator's authentic voice (style profile / brand voice applied downstream)",
        audience_description=audience_description,
        follower_goal=account_config.get("follower_goal") or "not specified",
        posting_cadence=account_config.get("posting_cadence", "daily"),
    )

    # Append live memory context
    backstory_with_memory = f"{backstory}\n\n# CURRENT MEMORY (read this BEFORE planning)\n\n{memory_context}"

    return Agent(
        role="Content Strategist",
        goal=(
            "Given the trend, pick the optimal angle + V3 parameters (etki/karakter/"
            "uzunluk/hook_type) that match this creator's voice AND will perform well."
        ),
        backstory=backstory_with_memory,
        tools=[semantic_recall],  # can look up similar past wins
        llm=settings.model_smart,
        verbose=True,
        allow_delegation=False,
        max_iter=6,
        respect_context_window=True,
    )
