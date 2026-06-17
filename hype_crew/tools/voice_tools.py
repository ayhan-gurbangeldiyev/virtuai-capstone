"""Voice tools — load creator's authentic samples + LLM-based voice alignment score.

Used by Writer (read voice examples) and Compliance (score alignment).
"""
from typing import Optional

try:
    from crewai.tools import tool
except ImportError:
    def tool(*args, **kwargs):  # noqa: ARG001
        def _decorate(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return _decorate

from .supabase_client import make_supabase
from .memory_tools import load_memory_dict


@tool("load_voice_examples")
def load_voice_examples(account_id: str, limit: int = 20) -> list[str]:
    """Return the creator's authentic voice samples (markdown content strings).

    Source priority:
    1. hype_memory entries with type='voice_examples' (curated seed + edits)
    2. Recent approved_drafts (also voice signal)
    """
    mem = load_memory_dict(
        account_id,
        limits={"voice_examples": limit, "approved_drafts": limit // 2},
    )

    voice = [r["content"] for r in mem.get("voice_examples", [])]
    approved = [r["content"] for r in mem.get("approved_drafts", [])]
    combined = voice + approved
    return combined[:limit] if combined else []


@tool("brand_voice_score")
def brand_voice_score(
    content: str,
    voice_description: str,
    sample_count: int = 5,
    account_id: Optional[str] = None,
) -> dict:
    """LLM-as-critic: how well does `content` match creator's voice?

    Returns 0-100 score + short justification. Uses HYPE_MODEL_FAST
    (defaults to google/gemini-3-flash-preview after Phase 18.9 — ~30x
    cheaper than gpt-4o-mini with comparable or better Turkish quality).

    NOTE: This is the only tool that hits LLM (besides the agents themselves).
    Compliance uses this to backstop voice drift.
    """
    from openai import OpenAI
    from config import settings

    # Pull recent approved samples as anchor (if available)
    samples_text = ""
    if account_id:
        mem = load_memory_dict(account_id, limits={"voice_examples": sample_count})
        samples = [r["content"] for r in mem.get("voice_examples", [])][:sample_count]
        if samples:
            samples_text = "\n\nReference samples (authentic creator voice):\n" + "\n---\n".join(samples)

    client = OpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    system = (
        "You are a voice critic. Score how closely a draft tweet matches a creator's "
        "described voice and reference samples. Reply ONLY with valid JSON: "
        '{"score": <0-100 int>, "reasoning": "<short>"}'
    )
    user = (
        f"Creator's voice description: {voice_description}\n"
        f"{samples_text}\n\n"
        f"Draft to score:\n{content}\n\n"
        "Return JSON only."
    )

    # CrewAI/litellm uses the "openrouter/<provider>/<model>" prefix to
    # disambiguate providers, but when we call the OpenAI SDK directly
    # against OpenRouter's base_url the model name has to be the bare
    # "<provider>/<model>" form. Strip the prefix only for this client.
    model_id = settings.model_fast
    if model_id.startswith("openrouter/"):
        model_id = model_id[len("openrouter/"):]

    # LiteLLM Router (flag-gated, fail-open). When enabled, route through the
    # Router for uniform timeout/retry/cooldown + cost telemetry; on any error
    # fall through to the existing bare OpenAI sync path below.
    from .llm_router import router_enabled, router_chat_json_sync
    if router_enabled():
        try:
            data, _meta = router_chat_json_sync(
                system, user, temperature=0.2, max_tokens=200, model_name="gate-fast",
            )
            score = max(0, min(100, int(data.get("score", 50))))
            return {
                "score": score,
                "reasoning": data.get("reasoning", "")[:200],
                "model": _meta.get("model") or model_id,
            }
        except Exception as e:
            from loguru import logger
            logger.warning(f"[voice_score] router atlandı: {e}")

    try:
        resp = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        import json
        data = json.loads(resp.choices[0].message.content)
        score = max(0, min(100, int(data.get("score", 50))))
        return {
            "score": score,
            "reasoning": data.get("reasoning", "")[:200],
            "model": model_id,
        }
    except Exception as e:
        # Fail-open: assume neutral score so we don't block on LLM glitches
        return {
            "score": 50,
            "reasoning": f"voice_score_error: {type(e).__name__}",
            "model": settings.model_fast,
            "error": str(e)[:200],
        }
