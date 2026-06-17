"""Phase 34 — Brand extraction from trend topics for visual subject mapping.

Used by `flow.generate_visual` to detect brand/product mentions in trend topics
so that conceptual/hybrid visual modes can put the right logo into the frame
(e.g. WhatsApp news → WhatsApp logo + green UI, no Cansu face).

Detection is heuristic: case-insensitive substring match against a curated
brand list, longest-key-first to avoid "google" beating "google deepmind".

If no brand is found, callers fall back to the default scene description
(Cansu in scene or abstract conceptual).
"""
from __future__ import annotations

import re
from typing import Optional


# Curated brand list. Keys are lowercase match tokens; values are canonical
# brand names that go into the visual prompt's subject.
#
# Maintenance: add new tokens when a trend keeps surfacing without a brand match.
# Longer tokens listed first conceptually so that compound names beat prefixes;
# `_SORTED_KEYS` below enforces longest-first iteration regardless of dict order.
BRAND_NAMES: dict[str, str] = {
    # AI labs / orgs
    "google deepmind": "Google DeepMind",
    "stability ai": "Stability AI",
    "hugging face": "Hugging Face",
    "huggingface": "Hugging Face",
    "github copilot": "GitHub Copilot",
    "google ai": "Google AI",
    "meta ai": "Meta AI",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "deepmind": "Google DeepMind",
    "google": "Google",
    "meta": "Meta",
    "microsoft": "Microsoft",
    "xai": "xAI",
    "cohere": "Cohere",
    "mistral": "Mistral",
    "perplexity": "Perplexity",
    "midjourney": "Midjourney",
    "runway": "Runway",
    "elevenlabs": "ElevenLabs",
    # Models (treated as brand-products for visual purposes)
    "claude opus": "Claude",
    "claude sonnet": "Claude",
    "claude haiku": "Claude",
    "claude": "Claude",
    "gpt-5": "GPT-5",
    "gpt-4o": "GPT-4o",
    "gpt-4": "GPT-4",
    "gpt-3.5": "GPT-3.5",
    "chatgpt": "ChatGPT",
    "gemini": "Gemini",
    "llama": "Llama",
    "grok": "Grok",
    "stable diffusion": "Stable Diffusion",
    # Tools / dev apps
    "cursor": "Cursor",
    "windsurf": "Windsurf",
    "vercel": "Vercel",
    "supabase": "Supabase",
    "n8n": "n8n",
    "zapier": "Zapier",
    "notion": "Notion",
    "linear": "Linear",
    # Consumer apps / news brands
    "whatsapp": "WhatsApp",
    "instagram": "Instagram",
    "twitter": "Twitter",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "linkedin": "LinkedIn",
    "telegram": "Telegram",
    "discord": "Discord",
    "slack": "Slack",
    # Cloud platforms (Phase 42.B-10A — additive; longest-key-first ordering
    # is enforced by _SORTED_KEYS so insertion order is cosmetic)
    "aws bedrock": "AWS Bedrock",
    "google cloud": "Google Cloud",
    "bedrock": "AWS Bedrock",
    "amazon": "Amazon",
    "azure": "Azure",
    "gcp": "Google Cloud",
    "aws": "AWS",
    # Hardware / consumer companies
    "apple": "Apple",
    "samsung": "Samsung",
    "xiaomi": "Xiaomi",
    "huawei": "Huawei",
    "nvidia": "NVIDIA",
    "amd": "AMD",
    "intel": "Intel",
    "tesla": "Tesla",
    "spacex": "SpaceX",
    "spotify": "Spotify",
    "netflix": "Netflix",
}

# Longest-first ordering so compound tokens win.
_SORTED_KEYS = sorted(BRAND_NAMES.keys(), key=len, reverse=True)


def extract_brand_from_topic(trend_topic: Optional[str]) -> Optional[str]:
    """Return the first brand name detected in `trend_topic`, or None.

    Match is case-insensitive substring, word-boundary aware. Longest tokens
    are checked first (so 'google deepmind' beats 'google').
    """
    if not trend_topic:
        return None
    topic_lower = trend_topic.lower()
    for key in _SORTED_KEYS:
        # Use word boundaries when the key is purely alphabetic.
        # Compound keys (with spaces) only need substring matching.
        if " " in key or not key.isalpha():
            if key in topic_lower:
                return BRAND_NAMES[key]
        else:
            pattern = rf"\b{re.escape(key)}\b"
            if re.search(pattern, topic_lower):
                return BRAND_NAMES[key]
    return None


def extract_brands_from_topic(
    trend_topic: Optional[str],
    raw_content: Optional[str] = None,
) -> list[str]:
    """Return up to 3 canonical brand names detected in topic + raw_content.

    Phase 42.B addition. Does NOT replace `extract_brand_from_topic()` —
    that function remains the single-brand path used by all pre-42.B callers.

    Match rules:
    - Case-insensitive, word-boundary aware (compound keys use substring)
    - Longest keys checked first; matched spans are masked so 'Google
      DeepMind' suppresses a separate 'Google' match in the same span
    - Preserves first-appearance order in the combined text
    - Deduplicates by canonical name (so 'Claude Opus' + 'Claude' → ['Claude'])
    - Caps at 3 brands (prevents prompt bloat on multi-brand articles)
    - raw_content is truncated to the first 2000 chars to bound scan cost

    Args:
        trend_topic: Trend headline / topic line.
        raw_content: Optional fuller article body. Brands found here are
            kept in order of first appearance after topic brands.

    Returns:
        Ordered list of canonical brand names, max length 3.
        Empty list if no brand matched.

    Examples:
        >>> extract_brands_from_topic("OpenAI ships models on AWS Bedrock")
        ['OpenAI']  # AWS / Bedrock not in current brand dict
        >>> extract_brands_from_topic("Microsoft and OpenAI partnership")
        ['Microsoft', 'OpenAI']
        >>> extract_brands_from_topic("Google DeepMind releases Gemini")
        ['Google DeepMind', 'Gemini']  # 'Google' suppressed by longer key
    """
    parts = [t for t in (trend_topic, raw_content) if t]
    if not parts:
        return []
    text = " ".join(parts).lower()
    if len(text) > 2000:
        text = text[:2000]

    # Mask tracks which character spans have been consumed by longer matches
    masked: list[bool] = [False] * len(text)
    matches: list[tuple[int, str]] = []  # (start_pos, canonical_name)

    for key in _SORTED_KEYS:
        is_compound = " " in key or not key.isalpha()
        cursor = 0
        while cursor < len(text):
            if is_compound:
                idx = text.find(key, cursor)
                if idx < 0:
                    break
                end = idx + len(key)
            else:
                m = re.search(rf"\b{re.escape(key)}\b", text[cursor:])
                if not m:
                    break
                idx = cursor + m.start()
                end = cursor + m.end()

            # Skip if any char in this span is already masked by a longer match
            if any(masked[idx:end]):
                cursor = end
                continue

            matches.append((idx, BRAND_NAMES[key]))
            for i in range(idx, end):
                masked[i] = True
            cursor = end

    # Sort by position, dedupe canonical names preserving first-appearance order
    matches.sort(key=lambda x: x[0])
    seen: set[str] = set()
    out: list[str] = []
    for _, name in matches:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= 3:
            break
    return out


def build_brand_subject(brand: str, visual_mode: str) -> str:
    """Compose a scene description override for brand-led visuals.

    - conceptual: persona-free, brand baskın.
    - hybrid:     Cansu küçük overlay + brand ürün baskın.
    """
    if visual_mode == "conceptual":
        return (
            f"{brand} logo + product UI mockup on a modern device screen, "
            f"editorial product shot, abstract tech aesthetic, no people in frame."
        )
    if visual_mode == "hybrid":
        return (
            f"Foreground focus: {brand} logo and UI mockup; "
            f"Cansu small overlay in lower corner (max 20% of frame), "
            f"shallow depth of field, editorial product+person composition."
        )
    # face mode keeps default Cansu-centric scene
    return ""
