"""Layer 4: LLM-judge for gray-zone images (Gemini 3 Flash vision via OpenRouter).

ONLY triggered when L1/L2/L3 return mixed verdicts (e.g. CLIP NEEDS_REVIEW, or one
of the layers FAIL while others PASS). Saves tokens by not running this on every
generation.

Input:
    - image bytes
    - layer summary (CLIP score, aesthetic score, OCR forbidden hits)

Output:
    - 'PASS' | 'NEEDS_REVIEW' | 'FAIL'
    - reasoning (string, 1-2 sentences)
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from loguru import logger
from openai import AsyncOpenAI

from config import settings

JUDGE_MODEL = "google/gemini-3-flash-preview"

# Phase 42.B-12B — visual_mode-aware judge prompts.
# Prior to 42B-12B a single Cansu-portrait prompt was applied to every image
# regardless of visual_mode, which silently auto-failed any brand-news /
# conceptual visual that landed in the aesthetic gray zone. The 'face' entry
# below is byte-identical to the pre-42B-12B prompt; 'conceptual' is new,
# 'hybrid' is aliased to 'conceptual' (Phase 39 collapsed hybrid routing).
_FACE_JUDGE_PROMPT = """\
You are a visual compliance reviewer for an AI persona content pipeline.

Your job: verify a generated image looks like an authentic candid iPhone snapshot
of a real Turkish woman, NOT like an AI-generated portrait, NOT like a stock photo,
NOT like a fashion shoot.

The persona ("Cansu Dut") posts as a self-disclosed AI persona, but each image
should still look photographically real — not glossy, not symmetric, not waxy-skin,
not influencer-styled.

Return strict JSON:
{
  "verdict": "PASS" | "NEEDS_REVIEW" | "FAIL",
  "reasoning": "1-2 sentence summary",
  "tells": ["list", "of", "any", "AI tells", "spotted"]
}

PASS criteria: looks like a real iPhone candid moment, no obvious AI tells, identity
consistent with the anchor profile (Turkish woman, mid-20s, brown wavy hair).

NEEDS_REVIEW criteria: subtle AI tells (slightly waxy skin, dead-doll eyes, symmetric
face, perfect studio lighting), but no clear failure. Human reviewer should look.

FAIL criteria: obvious AI rendering, plastic skin, unrealistic anatomy, brand logos,
text watermark, political content, religious imagery, or completely wrong person.
"""

_CONCEPTUAL_JUDGE_PROMPT = """\
You are a visual compliance reviewer for an AI persona content pipeline.

The image you are reviewing is a CONCEPTUAL BRAND VISUAL produced for news /
brand-coverage content. By design, this image SHOULD NOT contain people and
SHOULD show brand-context elements (logos, product mockups, abstract tech
imagery). Apply BRAND-VISUAL criteria, not portrait/identity criteria.

Return strict JSON:
{
  "verdict": "PASS" | "NEEDS_REVIEW" | "FAIL",
  "reasoning": "1-2 sentence summary",
  "tells": ["list", "of", "issues", "spotted"]
}

PASS criteria:
- No people anywhere in the frame
- Brand or topic visually recognizable (logo, wordmark, product mockup)
- Editorial product-shot or conceptual-tech composition
- Symbolic UI / abstract shapes instead of readable fake text
- Clean magazine-quality lighting and composition

NEEDS_REVIEW criteria:
- Brand recognizability is weak but defensible
- Minor UI/text artifacts (a few characters of fake-looking text) without
  being prominent
- Composition slightly off but not broken
- Aesthetic feels generic but not embarrassing

FAIL criteria:
- ANY person, face, or human silhouette visible (this is the hardest rule)
- Catastrophic fake-text clutter (readable paragraphs of nonsense, garbled
  UI labels covering the frame)
- Melted, distorted, or unrecognizable brand logos
- Political content, religious imagery, hate symbols, NSFW
- Brand of a competitor accidentally rendered instead of the requested brand
- Image is unrelated to a brand/tech context (e.g. a generic landscape)
"""

JUDGE_SYSTEM_PROMPTS: dict[str, str] = {
    "face": _FACE_JUDGE_PROMPT,
    "conceptual": _CONCEPTUAL_JUDGE_PROMPT,
    # Phase 39 collapsed hybrid routing into conceptual; alias keeps the
    # type-system value alive without code duplication. If 'hybrid' resurfaces
    # as a first-class composition mode, replace with a dedicated prompt.
    "hybrid": _CONCEPTUAL_JUDGE_PROMPT,
}


@dataclass(frozen=True)
class LlmJudgeResult:
    verdict: str           # 'PASS' | 'NEEDS_REVIEW' | 'FAIL'
    reasoning: str
    tells: list[str]
    cost_usd: float
    raw_response: str


async def judge_image(
    *,
    image_bytes: bytes,
    image_mime: str,
    context_summary: str,
    visual_mode: str = "face",
) -> LlmJudgeResult:
    """Ask Gemini vision to judge the generated image.

    Phase 42.B-12B — `visual_mode` selects the appropriate judge prompt:
      face       → portrait/identity criteria (default, unchanged)
      conceptual → brand-visual criteria (no-people-expected)
      hybrid     → aliased to conceptual (Phase 39 collapse)
    Unknown values fall back to the face prompt.
    """
    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    image_url = f"data:{image_mime};base64,{image_b64}"

    user_content = [
        {
            "type": "text",
            "text": f"Layer summary from upstream compliance gates:\n{context_summary}\n\n"
                    "Now look at the image and give your verdict in strict JSON.",
        },
        {"type": "image_url", "image_url": {"url": image_url}},
    ]

    _system_prompt = JUDGE_SYSTEM_PROMPTS.get(visual_mode, JUDGE_SYSTEM_PROMPTS["face"])

    # LiteLLM Router (flag-gated, fail-open). VISION call → router_chat_messages
    # (model_name="vision"). On any router error fall through to the AsyncOpenAI
    # path below (no behavior change when flag OFF).
    from ..llm_router import router_enabled, router_chat_messages
    if router_enabled():
        try:
            raw, _meta = await router_chat_messages(
                [
                    {"role": "system", "content": _system_prompt},
                    {"role": "user", "content": user_content},
                ],
                model_name="vision", temperature=0.1, max_tokens=400,
            )
            raw = raw or ""
            logger.debug(f"llm judge raw (router): {raw[:200]}")
            import json as _json
            try:
                text = raw.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()
                parsed = _json.loads(text)
                verdict = parsed.get("verdict", "NEEDS_REVIEW")
                reasoning = parsed.get("reasoning", "")
                tells = parsed.get("tells", []) or []
            except Exception as e:
                logger.warning(f"llm judge parse failed (router): {e}; raw: {raw[:200]}")
                verdict = "NEEDS_REVIEW"
                reasoning = "parse_failed"
                tells = []
            return LlmJudgeResult(
                verdict=verdict,
                reasoning=reasoning,
                tells=tells,
                cost_usd=float(_meta.get("cost_usd") or 0.0),
                raw_response=raw,
            )
        except Exception as e:
            logger.warning(f"llm judge: router atlandı: {e}")

    resp = await client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPTS.get(visual_mode, JUDGE_SYSTEM_PROMPTS["face"])},
            {"role": "user", "content": user_content},
        ],
        max_tokens=400,
        temperature=0.1,
    )
    raw = resp.choices[0].message.content or ""
    logger.debug(f"llm judge raw: {raw[:200]}")

    # Parse JSON loosely
    import json
    try:
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)
        verdict = parsed.get("verdict", "NEEDS_REVIEW")
        reasoning = parsed.get("reasoning", "")
        tells = parsed.get("tells", []) or []
    except Exception as e:
        logger.warning(f"llm judge parse failed: {e}; raw: {raw[:200]}")
        verdict = "NEEDS_REVIEW"
        reasoning = "parse_failed"
        tells = []

    # Estimate cost (gemini-3-flash pricing rough: input ~$0.075/M, output $0.30/M)
    usage = resp.usage
    cost = 0.0
    if usage:
        cost = (
            (usage.prompt_tokens or 0) * 0.075 / 1_000_000
            + (usage.completion_tokens or 0) * 0.30 / 1_000_000
        )

    return LlmJudgeResult(
        verdict=verdict,
        reasoning=reasoning,
        tells=tells,
        cost_usd=cost,
        raw_response=raw,
    )
