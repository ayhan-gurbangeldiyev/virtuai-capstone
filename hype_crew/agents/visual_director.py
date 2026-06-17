"""Visual Director — 5th CrewAI agent.

Picks scene + outfit + mood for the draft, calls generate_visual_image tool which
runs Wiro generation + 4-layer compliance gate, returns VisualDirectorOutput.

Only activated when persona.visual_enabled = True. Otherwise the Crew skips this
agent's task entirely (PR 4.3 wiring).
"""
from typing import Any
from crewai import Agent

from config import settings
from prompts.visual_director_prompt import VISUAL_DIRECTOR_BACKSTORY
from tools.visual_director_tools import generate_visual_image


def build_visual_director(persona_config: dict[str, Any]) -> Agent:
    """Visual Director agent. Smart model (creative scene selection)."""
    backstory = VISUAL_DIRECTOR_BACKSTORY.format(
        persona_display_name=persona_config.get("display_name", "Cansu Dut"),
        topics_focus=", ".join(persona_config.get("topics_focus") or []),
        forbidden_topics=", ".join(persona_config.get("forbidden_topics") or []),
    )

    return Agent(
        role="Visual Director",
        goal=(
            "Pick a scene + outfit + mood that fits the draft, then call "
            "generate_visual_image tool to produce an iPhone-11-aesthetic image "
            "and run compliance. Return the populated VisualDirectorOutput."
        ),
        backstory=backstory,
        tools=[generate_visual_image],
        llm=settings.model_smart,
        verbose=True,
        allow_delegation=False,
        max_iter=4,
        respect_context_window=True,
    )
