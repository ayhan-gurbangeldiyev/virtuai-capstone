"""Phase 35.1.E — Pronunciation resolver for Turkish TTS.

Three layers, all merged into the MiniMax `pronunciation_dict.tone` list:

1) STATIC_DICT — hand-curated, top ~50 brands/models/benchmarks.
2) Supabase `pronunciation_cache` — approved + recently used entries
   from previous runs (auto-populated by resolver).
3) Dynamic resolver — Gemini Flash call: from the current brief, extract
   any *new* foreign names not in (1)+(2) and propose Turkish phonetic
   bitişik spellings.

Output shape:
    {"tone": ["Anthropic/antropik", "GPT-5.5/cipiti beşbuçuk", ...]}
    → drop straight into MiniMax T2A body.

Design choices:
- Bitişik fonetik (no spaces) — Test results 30 May 2026 showed 3s
  speed-up over "ci pi ti" boşluklu format.
- Benchmark adı → TANIMLAMA (descriptive Turkish), not letter spelling.
- Resolver writes back to cache (approved=false) so user can review
  later via UI; auto-applies regardless of approval to keep pipeline
  unblocked.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Optional

from loguru import logger

from config import settings


# ---------------------------------------------------------------
# 1) STATIC DICT (hand-curated, voice_modes.py'ndaki rehberle uyumlu)
# ---------------------------------------------------------------
STATIC_PRONUNCIATION: dict[str, str] = {
    # Brand isimleri (Türkçe okunuş, bitişik)
    "Anthropic": "antropik",
    "Claude": "klod",
    "Claude Opus": "klod opus",
    "Claude Sonnet": "klod sone",
    "Claude Haiku": "klod hayku",
    # Berkay 6 Haz 2026: 3 OpenAI variants for A/B/C ear test.
    # Default (variant A) is IPA — see OPENAI_VARIANTS below for B/C.
    "OpenAI": "(ˈoʊpən eɪ aɪ)",  # variant A — IPA
    "ChatGPT": "çatcipiti",
    "Gemini": "cemini",
    "Google": "gugıl",
    "Google DeepMind": "gugıl dipmaynd",
    "DeepMind": "dipmaynd",
    "Microsoft": "maykrosoft",
    "Apple": "eppıl",
    "xAI": "eksey",
    # Capstone (4 Haz 2026) — Removed identity mappings (Mistral/Tesla/Meta/Grok):
    # key == intended pronunciation, zero TTS effect, dict slot waste.
    "Cohere": "kohir",
    "Perplexity": "perpleksiti",
    "Hugging Face": "haging feys",
    "HuggingFace": "haging feys",
    "Stability AI": "stabiliti yapay zeka",
    "NVIDIA": "envidya",
    "SpaceX": "speys eks",
    # Capstone (4 Haz 2026) — Cloud / partnership coverage gap (audit ship).
    # Previously absent → MiniMax read raw letters or fell to disabled resolver.
    "AWS": "ey dabıl yu es",
    "Azure": "ejur",
    "Bedrock": "bedrok",
    "SageMaker": "seyc meyker",
    "OpenRouter": "open rauter",
    # Model versiyonları (bitişik fonetik)
    "GPT-5.5": "cipiti beşbuçuk",
    "GPT-5": "cipiti beş",
    "GPT-4.5": "cipiti dörtbuçuk",
    "GPT-4o": "cipiti dört o",
    "GPT-4": "cipiti dört",
    "GPT-3.5": "cipiti üçbuçuk",
    "GPT": "cipiti",
    "Gemini 3.1 Pro": "cemini üçnoktabir pro",
    "Gemini 3.1": "cemini üçnoktabir",
    "Gemini 3": "cemini üç",
    "Gemini 2.5": "cemini ikibuçuk",
    "Gemini 2": "cemini iki",
    "Llama 4": "lama dört",
    "Llama 3": "lama üç",
    "Llama": "lama",
    # Benchmark / teknik test → TANIMLA (transliterate ETME)
    "SWE-Bench Pro": "yazılım mühendisliği kıyaslaması",
    "SWE-Bench": "yazılım mühendisliği kıyaslaması",
    "SWE Bench": "yazılım mühendisliği kıyaslaması",
    "MMLU": "çokalanlı bilgi testi",
    "HumanEval": "kodlama testi",
    "HellaSwag": "akıl yürütme testi",
    "GPQA": "uzman seviye soru testi",
    "Arena": "kullanıcı oylaması",
    "Chatbot Arena": "kullanıcı oylaması",
    "MATH": "matematik testi",
    "ARC": "soyut akıl yürütme testi",
    # Berkay 6 Haz 2026 — Letter-acronyms: IPA letter-names, NOT
    # translation. The prior `AI/yapay zeka` was translating, which made
    # Cansu sound like a textbook. Tech-fluent operators say the letters
    # in English. `API/uygulama arabirimi` similarly retired.
    "AI": "ey ay",
    "API": "ey pi ay",
    "ML": "em el",
    "NLP": "en pi ay",
    "CEO": "si i ou",
    "CTO": "si ti ou",
    "GPU": "ci pi yu",
    "CPU": "si pi yu",
    "SDK": "es di key",
    "URL": "yu ar el",
    # Capstone (4 Haz 2026) — Removed over-translations that made Cansu sound
    # like a textbook to her insider/dev audience:
    #   LLM → büyükdilmodeli      (invented compound)
    #   API → uygulama arabirimi  (devs say "API" naturally)
    #   RAG → bilgidesteklimodel  (invented compound)
    #   agentic → otonom          (Writer DNA uses 'agentic' intentionally)
    #   prompt engineering → komut mühendisliği (awkward; devs use English)
    # Teknik terim → Türkçe
    "context window": "bağlam penceresi",
    "fine-tuning": "ince ayar",
    "fine tuning": "ince ayar",
    "multimodal": "çok kipli",
    "embedding": "vektör temsili",
    "token": "kelime parçası",
    # Berkay 5 Haz 2026 — domain-specific model launches + English science
    # terms that recur in AI news. These previously fell through to MiniMax
    # which read them with Turkish phonetics ("life sciences" → "life
    # siyensıs" gibi). Listed here once → systematically resolved.
    "GPT-Rosalind": "cipiti rozalind",
    "Rosalind": "rozalind",
    "life sciences": "layf sayınsız",
    "drug discovery": "drag diskavıri",
    "purpose-built": "pörpıs bilt",
    "agentic": "ajantik",
    "agentic coding": "ajantik koding",
    "tool use": "tul yus",
    "agentic workflow": "ajantik workflo",
    "workflow": "workflo",
    "Copilot": "kopaylot",
    "Codex": "kodeks",
    "Scout": "skaut",
    "Whisper": "vispır",
    "Wizper": "vizpır",
    "Sonnet": "sone",
}


# Berkay 6 Haz 2026 — OpenAI pronunciation A/B/C: ear-test 3-second
# samples generated against each variant so the operator can pick by
# listening. The dict-active variant (A: IPA) is the production default;
# B/C are reserved for the sample comparison only.
OPENAI_VARIANTS: dict[str, str] = {
    "A_ipa": "(ˈoʊpən eɪ aɪ)",
    "B_ey_ay": "Open ey-ay",
    "C_letter_names": "Open A I",
}


def _dict_to_tone_list(d: dict[str, str]) -> list[str]:
    """Convert {"foo": "bar"} → ["foo/bar"] (MiniMax format)."""
    return [f"{k}/{v}" for k, v in d.items() if k and v]


# ---------------------------------------------------------------
# 2) Supabase cache layer (approved + recent)
# ---------------------------------------------------------------
async def fetch_cache_entries(
    foreign_terms: list[str],
    language: str = "tr",
) -> dict[str, str]:
    """Return {foreign_term: turkish_phonetic} for any cached terms found.

    Bumps hit_count + last_used_at as side effect.
    """
    if not foreign_terms:
        return {}
    try:
        from .supabase_client import make_supabase
    except Exception as e:
        logger.warning(f"pronunciation_resolver: supabase import fail ({e})")
        return {}
    sb = make_supabase()
    # Match by lower(foreign_term) to be tolerant of casing variations.
    rows = (
        sb.table("pronunciation_cache")
        .select("id, foreign_term, turkish_phonetic")
        .in_("foreign_term", foreign_terms)
        .eq("language", language)
        .execute()
    ).data or []
    out: dict[str, str] = {}
    hit_ids: list[str] = []
    for r in rows:
        ft = r.get("foreign_term")
        tp = r.get("turkish_phonetic")
        if ft and tp:
            out[ft] = tp
            hit_ids.append(r["id"])
    # Bump hit_count + last_used_at for the matched rows (best-effort).
    if hit_ids:
        try:
            sb.rpc("bump_pronunciation_cache_hits", {"row_ids": hit_ids}).execute()
        except Exception:
            # Fallback: per-row update (RPC may not exist yet).
            for rid in hit_ids:
                try:
                    sb.table("pronunciation_cache").update(
                        {"last_used_at": "now()"}
                    ).eq("id", rid).execute()
                except Exception:
                    pass
    return out


async def write_cache_entries(
    entries: dict[str, str],
    *,
    source: str = "resolver",
    language: str = "tr",
) -> None:
    """Upsert resolver-found terms into the cache (approved=False by default)."""
    if not entries:
        return
    try:
        from .supabase_client import make_supabase
    except Exception:
        return
    sb = make_supabase()
    rows = [
        {
            "foreign_term": k,
            "turkish_phonetic": v,
            "source": source,
            "language": language,
        }
        for k, v in entries.items()
        if k and v
    ]
    try:
        sb.table("pronunciation_cache").upsert(
            rows, on_conflict="foreign_term,language"
        ).execute()
    except Exception as e:
        logger.warning(f"pronunciation_resolver: cache write fail ({e})")


# ---------------------------------------------------------------
# 3) Dynamic resolver (Gemini Flash)
# ---------------------------------------------------------------
_RESOLVER_PROMPT_TR = """Aşağıdaki Türkçe haber metninden YABANCI brand/model/benchmark/teknik
isimlerini çıkar ve her birine Türkçe TTS motoru için BİTİŞİK fonetik
karşılık öner.

KURALLAR (kesin):
- Marka isimleri: "Anthropic" → "antropik", "Sonnet" → "sone"
- Model versiyonları: "4.5" → "dörtnoktabeş", "v6" → "altı"
- Kısaltmalar bitişik harfler: "GPT" → "cipiti", "TPU" → "tipiyu"
- Benchmark adlarını TANIMLA (transliterate ETME):
  "SWE-Bench 2.0" → "yazılım kıyaslaması iki sıfır"
  "MMLU Pro" → "çokalanlı bilgi testi pro"
- Sadece YABANCI olanları listele. Türkçe kelimeler ATLA.
- Boşluksuz bitişik hece yaz: "ci pi ti" değil, "cipiti".

Metin:
\"\"\"{TEXT}\"\"\"

Halihazırda bilinen ve listelemenize GEREK YOK:
{KNOWN_TERMS}

Çıktı sadece geçerli JSON. Başka açıklama yok:
{{
  "<original>": "<turkish_phonetic>",
  ...
}}

Eğer yabancı isim yoksa boş objeyle yanıtla: {{}}
"""


_JSON_RE = re.compile(r"\{[\s\S]*\}")


async def resolve_dynamic(
    text: str,
    *,
    known_terms: Optional[list[str]] = None,
    model: Optional[str] = None,
) -> dict[str, str]:
    """Call Gemini Flash (via OpenRouter) to extract + phoneticize foreign names.

    Returns {} on any failure (resolver is best-effort, never blocks pipeline).
    """
    text = (text or "").strip()
    if not text:
        return {}

    api_key = getattr(settings, "openrouter_api_key", None)
    if not api_key:
        logger.warning("pronunciation_resolver: OPENROUTER_API_KEY missing, skip")
        return {}

    model_id = model or getattr(
        settings, "model_smart", "google/gemini-3-flash-preview"
    )
    # CrewAI / litellm format uses "openrouter/<provider>/<name>" prefix.
    # OpenRouter direct REST API does NOT want that prefix — strip it.
    if isinstance(model_id, str) and model_id.startswith("openrouter/"):
        model_id = model_id[len("openrouter/") :]
    prompt = _RESOLVER_PROMPT_TR.format(
        TEXT=text[:4000],
        KNOWN_TERMS=", ".join(sorted(known_terms or [])[:80]) or "(yok)",
    )
    _SYS = (
        "You are a strict JSON-only Turkish phonetic "
        "transliteration assistant. Reply with ONLY a "
        "valid JSON object, nothing else."
    )

    # LiteLLM Router dalı (flag-gated, fail-open). model_smart kullanan JSON gate
    # (response_format json_object zaten vardı) → router_chat_json model_name="gate-smart"
    # birebir uygun. Parsed dict alınır, aşağıdaki MEVCUT clean-validate döngüsüne aynen
    # beslenir (parsed). Kapalı/hatalı iken aşağıdaki httpx yolu byte-identical çalışır.
    parsed: dict[str, str] = {}
    router_done = False
    try:
        from .llm_router import router_enabled, router_chat_json
        if router_enabled():
            try:
                parsed, _meta = await router_chat_json(
                    _SYS, prompt,
                    temperature=0.2, max_tokens=600, model_name="gate-smart",
                )
                if not isinstance(parsed, dict):
                    parsed = {}
                router_done = True
            except Exception as e:  # noqa: BLE001
                logger.warning(f"pronunciation_resolver: router atlandı, httpx'e düşülüyor ({e})")
                parsed = {}
                router_done = False
    except Exception as e:  # noqa: BLE001
        logger.warning(f"pronunciation_resolver: router import hatası, httpx'e düşülüyor ({e})")
        router_done = False

    if not router_done:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_id,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are a strict JSON-only Turkish phonetic "
                                    "transliteration assistant. Reply with ONLY a "
                                    "valid JSON object, nothing else."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.2,
                        "max_tokens": 600,
                        "response_format": {"type": "json_object"},
                    },
                )
                if r.status_code >= 400:
                    logger.warning(
                        f"pronunciation_resolver: openrouter {r.status_code} "
                        f"body: {r.text[:500]}"
                    )
                    return {}
                data = r.json()
        except Exception as e:
            logger.warning(f"pronunciation_resolver: openrouter fail ({type(e).__name__}: {e})")
            return {}

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            return {}

        try:
            parsed = json.loads(content)
        except Exception:
            m = _JSON_RE.search(content or "")
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    pass

    # Validate: keys + values are non-empty strings.
    clean: dict[str, str] = {}
    for k, v in (parsed or {}).items():
        if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
            clean[k.strip()] = v.strip()
    return clean


# ---------------------------------------------------------------
# Public API — main entry point
# ---------------------------------------------------------------
async def build_pronunciation_dict(
    text: str,
    *,
    language: str = "tr",
    use_resolver: bool = False,  # Capstone (3 Haz 2026): dynamic LLM resolver
                                  # DISABLED — runtime brand inference riski
                                  # var (boşluklu form üretiyor). Statik dict
                                  # %95 vakaları kapsar, geri kalanı TTS
                                  # context'ten çözer.
) -> dict[str, list[str]]:
    """Build the MiniMax `pronunciation_dict` payload for the given text.

    Layer priority (later overrides earlier):
      1) STATIC_PRONUNCIATION (hand-curated)
      2) Supabase pronunciation_cache (approved + recent)
      3) Gemini resolver (new foreign names — best-effort)

    Returns: {"tone": ["foo/bar", ...]} ready to drop into MiniMax body.
    Empty dict if nothing applicable.
    """
    merged: dict[str, str] = dict(STATIC_PRONUNCIATION)

    # 2) Cache — only fetch entries whose `foreign_term` appears in the text
    #    to keep the dict small (MiniMax has a soft limit on tone entries).
    text_lower = (text or "").lower()
    cache_candidates = [
        t for t in merged
        if t.lower() in text_lower and t not in merged.values()
    ]
    # Also widen with everything ever cached that appears in text — cheap query.
    try:
        from .supabase_client import make_supabase
        sb = make_supabase()
        all_cached = (
            sb.table("pronunciation_cache")
            .select("foreign_term")
            .eq("language", language)
            .execute()
        ).data or []
        cache_candidates.extend(
            r["foreign_term"]
            for r in all_cached
            if r.get("foreign_term", "").lower() in text_lower
        )
    except Exception:
        pass

    cache_hits = await fetch_cache_entries(
        list({c for c in cache_candidates}), language=language
    )
    # Capstone (4 Haz 2026) — STATIC dictionary now WINS over cache.
    # Reason: an unapproved resolver-generated row (e.g., AWS → "eydabılvıyüs")
    # could otherwise replace the hand-curated value. Only fill gaps from cache.
    for k, v in cache_hits.items():
        merged.setdefault(k, v)

    # 3) Resolver — only run if enabled + something looks foreign.
    if use_resolver:
        # Quick heuristic: text contains ASCII A-Z run of length ≥3 that isn't
        # already a known key → worth asking the LLM.
        unknown = bool(
            re.search(r"\b[A-Z][A-Za-z0-9.\-]{2,}\b", text or "")
        )
        if unknown:
            try:
                dyn = await resolve_dynamic(
                    text,
                    known_terms=list(merged.keys()),
                )
                # Filter: only entries that actually appear in text.
                fresh = {
                    k: v for k, v in dyn.items()
                    if k.lower() in text_lower and k not in merged
                }
                if fresh:
                    logger.info(
                        f"pronunciation_resolver: +{len(fresh)} new dynamic entries"
                    )
                    merged.update(fresh)
                    # Write back to cache async (best-effort, non-blocking).
                    asyncio.create_task(
                        write_cache_entries(fresh, source="resolver", language=language)
                    )
            except Exception as e:
                logger.warning(f"pronunciation_resolver: dynamic step fail ({e})")

    # Trim: only include entries whose key appears in the text. MiniMax doesn't
    # need the entire global dict — only what's actionable.
    applicable = {
        k: v for k, v in merged.items() if k.lower() in text_lower
    }

    if not applicable:
        return {}
    return {"tone": _dict_to_tone_list(applicable)}
