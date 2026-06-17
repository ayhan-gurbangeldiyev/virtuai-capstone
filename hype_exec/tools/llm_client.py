"""Google Gemini LangChain client wrapper (direct API).

Uses langchain-google-genai's ChatGoogleGenerativeAI against Google AI Studio
endpoints. Structured output via `with_structured_output(method="json_schema")`.

Direct Gemini API benefits over OpenRouter:
  - No middleman markup (raw pricing: 2.5-flash $0.30/$2.50 per M tokens)
  - Implicit context caching kicks in automatically (~75% savings on stable
    prefix when system prompt is reused across calls)
  - 1M token context window
"""
from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import settings


def make_llm(*, model: str | None = None, temperature: float = 0.3, timeout: int = 60) -> ChatGoogleGenerativeAI:
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY (or GEMINI_API_KEY) is not set")
    return ChatGoogleGenerativeAI(
        model=model or settings.model_default,
        google_api_key=settings.google_api_key,
        temperature=temperature,
        timeout=timeout,
        max_retries=2,
    )


def make_llm_critical() -> ChatGoogleGenerativeAI:
    """For CEO escalations / weekly strategy. Gemini Pro, lower temperature."""
    return make_llm(model=settings.model_critical, temperature=0.2, timeout=120)
