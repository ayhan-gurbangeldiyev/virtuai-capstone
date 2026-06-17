"""Hype Crew agent prompt backstories — 2 prompts only.

Writer / Compliance / Publisher prompts removed:
- Writer logic lives in TypeHype's build_final_prompt_v3 (called via internal endpoint)
- Compliance is rule-based (Python code in tools/), no LLM agent needed
- Publisher is a direct Postiz HTTP call from Flow, no LLM
"""
from .constants import HARD_RULES, FORMATTING_RULES, HOOK_TYPES, MEMORY_PROTOCOL
from .trendscout_prompt import TRENDSCOUT_BACKSTORY
from .planner_prompt import PLANNER_BACKSTORY

__all__ = [
    "HARD_RULES", "FORMATTING_RULES", "HOOK_TYPES", "MEMORY_PROTOCOL",
    "TRENDSCOUT_BACKSTORY", "PLANNER_BACKSTORY",
]
