"""Faithfulness gate — block writer fabrications BEFORE publish.

Three tiers, cheap → expensive, mirroring the compliance/runner.py cascade
pattern. The gate is fail-closed: any hard block → draft holds at
status='pending_review', never auto-publishes.

  Tier 0 — NER entity grounding (cheap, deterministic):
    Extract ORG / PRODUCT / PERSON entities from the draft + the source.
    Any draft entity not present in source (with alias / case normalization)
    is a fabrication. This single check would have caught "Starlink" on the
    Google/SpaceX $920M compute deal instantly.

  Tier 1 — claim entailment (medium, LLM):
    Decompose the draft into atomic factual statements (excluding pure
    opinion/stance clauses — "bence X", "asıl önemli olan Y"). Score each
    on whether it's directly inferable from raw_content. If the share of
    grounded factual claims drops below `claim_grounding_floor` (default
    0.9), block.

  Tier 2 — "fabricated thesis" judge (LLM, gray-zone only):
    Asks: does the draft assert a central thesis / hidden angle /
    "the real story is..." NOT supported by the source? Runs only when
    T0 and T1 didn't already hard-block.

Reuses llm_judge.py's strict-JSON PASS/FAIL pattern.

Usage:
    from tools.faithfulness_gate import run_faithfulness_gate
    verdict = await run_faithfulness_gate(
        draft_text=tweet,
        source_raw_content=trend.raw_content,
        source_url=trend.url,
    )
    if verdict.is_block:
        # keep as pending_review, log the reason
        ...
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


JUDGE_MODEL = "google/gemini-3-flash-preview"
ENTAILMENT_MODEL = "google/gemini-3-flash-preview"

# ──────────────────────────────────────────────────────────────────────
# GLiNER — real NER for T0. Replaces curated-alias entity extraction
# while keeping the curated map as a NORMALIZER (product→maker collapse
# and Turkish-suffix strip).
# ──────────────────────────────────────────────────────────────────────

GLINER_MODEL_ID = "urchade/gliner_multi"   # pinned; CPU-friendly multilingual

# Labels chosen empirically on the Apple-Intelligence/Gemini case: this
# combination reliably surfaces Turkish AI-news entities including new
# AI product names (Apple Intelligence, Google Gemini, Codex, Mythos)
# that aren't in any curated alias map.
GLINER_LABELS = [
    "company name",         # Apple, Google, Meta, SpaceX, Anthropic
    "AI assistant",         # Siri, AI asistanı, ChatGPT
    "AI model name",        # Claude Opus 4.8, Gemini, Apple Intelligence
    "AI feature name",      # Memory, Computer Use, Computer Vision
    "person name",          # Sam Altman, Demis Hassabis
    "CVE id",
    "benchmark name",       # MMLU, SWE-Bench
]
GLINER_THRESHOLD = 0.45     # tuned empirically: catches AI products, drops
                            # noise like "ürün ekibinin" / "guncelleme"

# Token-set fuzzy threshold for matching draft entities to source entities.
# 0.85 = "near-exact match modulo word-order and case" — set this way so
# "Google Gemini" matches "Gemini App" but NOT "Apple Intelligence".
FUZZY_MATCH_THRESHOLD = 85

# Single-word tokens GLiNER sometimes returns that are not actually
# proper-noun entities. Filtered out post-extraction so noise doesn't
# pollute the entity set. Add words here when iterating.
_GLINER_NOISE_STOPLIST = {
    # Generic
    "ai", "yapay zeka", "model", "modeller", "asistan", "asistani",
    "ai asistani", "araç", "hizmet", "uygulama", "uygulamalar",
    "platform", "platformlar", "sistem", "ozellik", "özellik",
    "guncelleme", "güncelleme", "yeni", "olay",
    # Common nouns
    "flow", "tartisma", "tartışma", "haber", "rapor",
    "fiyat", "fiyati", "ürün", "urun", "ekibi", "ekibinin",
    "urun ekibinin", "ürün ekibinin",
    "yatirimci", "yatirimcilar", "yatırımcılar",
    "gelistirme", "geliştirme", "gelistirme ozelligi",
    "kullanici", "kullanicilar", "kullanıcılar",
    "muhendis", "mühendis", "muhendisler",
    "operatör", "operatorler",
    "marka", "markalar",
    "gelistirici", "geliştirici", "gelistiriciler", "geliştiriciler",
    "rakip", "rakipler", "rakipleri",
    "tüketici", "tuketici", "tüketiciler",
    "musteri", "müşteri", "müşteriler",
    "ekip", "ekipler", "topluluk", "topluluklar",
    # 2026-06-08 — generic workforce/role common nouns GLiNER over-extracts.
    # Cross-lingual FP: Turkish "çalışan" never matches an English source's
    # "workers" → false T0 block. These are roles, not named entities.
    "çalışan", "calisan", "çalışanlar", "calisanlar", "çalışanları",
    "personel", "görevli", "gorevli", "insan", "insanlar", "kişi", "kisi",
    # 2026-06-08 (gate refine) — common nouns GLiNER over-extracts.
    # None of these are named entities in AI-news context; they are
    # features, UI elements, or generic abstractions. Without these,
    # drafts like "context kaybolmuyor" (Claude Cowork case c600d372)
    # false-block because GLiNER picks "context" as an entity.
    "context", "feature", "update", "data", "file", "tab",
    "version", "mode", "session", "thread", "output", "input",
    "draft", "message", "transition", "loop", "cost", "trigger",
    "limit", "queue", "channel", "stream", "memory", "history",
    "view", "page", "screen", "tool", "tools",
    # Turkish equivalents
    "bağlam", "baglam", "sekme", "dosya", "çıktı", "cikti",
    "mesaj", "geçiş", "gecis", "taslak", "ekran", "akış", "akis",
    "döngü", "dongu", "maliyet", "modu", "modlar",
    # Common verbs/process words that GLiNER occasionally picks up
    "kayıp", "kayip", "geçiş", "gecis",
    # 2026-06-08 — internet-traffic terminology, generic web infrastructure
    # words. Caught in Cloudflare bot draft where "botlardan" / "scraper"
    # were flagged as entities (they're generic web nouns).
    "bot", "botlar", "botlardan", "botların",
    "scraper", "scraperlar", "crawler", "crawlerlar",
    "spam", "trafik", "trafiği", "trafikten",
    "kullanıcı", "kullanici", "ziyaretçi", "ziyaretci",
    "isteği", "istek", "istekler",
}


def _is_noise_entity(canonical: str) -> bool:
    """Drop short or stoplist-matched extractions."""
    if not canonical or len(canonical) < 3:
        return True
    if canonical in _GLINER_NOISE_STOPLIST:
        return True
    # Pure-numeric (let currency canon handle these)
    if canonical.replace(" ", "").replace("$", "").replace(".", "").replace(",", "").isdigit():
        return True
    return False


_GLINER_INSTANCE = None    # module-level singleton (same pattern as CLIP)
_GLINER_LOAD_LOCK_TRIED = False


def _get_gliner():
    """Lazy-load GLiNER on first call. In PRODUCTION this MUST succeed —
    the curated dict alone cannot catch entity substitutions like
    Apple Intelligence vs Gemini (gold-26). In dev / CI without the
    optional deps, the gate degrades to the curated map and the caller
    is expected to know.

    To force-fail when load is missing in production set the env var
    `FAITHFULNESS_NER_REQUIRED=true`. The gate will raise (loud — caller
    must surface) instead of silently degrading. CI / production should
    set this.
    """
    global _GLINER_INSTANCE, _GLINER_LOAD_LOCK_TRIED
    if _GLINER_INSTANCE is not None:
        return _GLINER_INSTANCE
    if _GLINER_LOAD_LOCK_TRIED:
        return None     # don't keep retrying every call
    _GLINER_LOAD_LOCK_TRIED = True

    import os as _os
    required = (_os.environ.get("FAITHFULNESS_NER_REQUIRED") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    try:
        from gliner import GLiNER       # type: ignore
        logger.info(f"[gliner] loading {GLINER_MODEL_ID} (first-call)…")
        _GLINER_INSTANCE = GLiNER.from_pretrained(GLINER_MODEL_ID)
        logger.info("[gliner] loaded")
        return _GLINER_INSTANCE
    except Exception as e:
        msg = (
            f"[gliner] load failed; CURATED-DICT FALLBACK in effect. "
            f"Gate recall WILL drop on novel entity substitutions "
            f"(gold-26 / Apple Intelligence-vs-Gemini class). Underlying "
            f"error: {type(e).__name__}: {e}"
        )
        if required:
            logger.error(msg)
            raise RuntimeError(
                "FAITHFULNESS_NER_REQUIRED=true but GLiNER could not load. "
                "Install gliner + rapidfuzz from hype_crew/requirements.txt "
                "and re-run."
            ) from e
        logger.warning(msg)
        return None


def _gliner_extract(text: str) -> list[dict]:
    """Returns list of {entity, label, score}. Empty list on no-text or
    GLiNER unavailable."""
    if not text or not text.strip():
        return []
    model = _get_gliner()
    if model is None:
        return []
    try:
        return model.predict_entities(text, GLINER_LABELS, threshold=GLINER_THRESHOLD)
    except Exception as e:
        logger.warning(f"[gliner] predict failed: {e!r}")
        return []


# ──────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FaithfulnessVerdict:
    overall: str                 # 'PASS' | 'SOFT_FAIL' | 'HARD_BLOCK'
    tier0_entities_missing: list[str]
    tier0_blocked: bool
    tier1_claim_pass_ratio: Optional[float]
    tier1_ungrounded_claims: list[str]
    tier1_blocked: bool
    tier2_verdict: Optional[str]    # 'PASS' / 'FAIL' / 'SKIPPED'
    tier2_ungrounded_angles: list[str]
    tier2_blocked: bool
    reasoning: str
    cost_usd: float = 0.0

    @property
    def is_block(self) -> bool:
        return self.overall == "HARD_BLOCK"


# ──────────────────────────────────────────────────────────────────────
# Tier 0 — NER entity grounding (deterministic, cheap)
# ──────────────────────────────────────────────────────────────────────

# Curated brand / product / person dictionary the AI-news beat uses. Each
# canonical form maps to a set of aliases that should be treated as the
# same entity. Used both for extraction and for source-side matching.
_ENTITY_ALIASES: dict[str, set[str]] = {
    "openai":      {"openai", "open ai", "open-ai"},
    "anthropic":   {"anthropic"},
    "google":      {"google", "google deepmind", "deepmind"},
    "microsoft":   {"microsoft", "ms"},
    "apple":       {"apple"},
    "meta":        {"meta", "facebook", "instagram", "whatsapp",
                    "meta ai", "metaai", "meta-ai"},
    "nvidia":      {"nvidia", "envidia"},
    "amazon":      {"amazon", "aws", "amazon bedrock", "bedrock"},
    "spacex":      {"spacex", "space x"},
    "tesla":       {"tesla"},
    "starlink":    {"starlink"},
    "xai":         {"xai", "x ai"},
    "chatgpt":     {"chatgpt"},
    "claude":      {"claude", "claude opus", "claude sonnet", "claude haiku",
                    "opus 4", "opus 4.7", "opus 4.8", "claude mythos", "mythos"},
    "gemini":      {"gemini", "gemini app", "geminiapp"},
    "copilot":     {"copilot"},
    "codex":       {"codex"},
    "scout":      {"scout"},
    "gpt":         {"gpt"},
    "gpt-5":       {"gpt-5", "gpt5"},
    "gpt-5.5":     {"gpt-5.5", "gpt5.5", "gpt 5.5"},
    "gpt-rosalind": {"gpt-rosalind", "rosalind"},
    "llama":       {"llama", "llama 3", "llama-3"},
    "mistral":     {"mistral"},
    "cohere":      {"cohere"},
    "perplexity":  {"perplexity"},
    "sam altman":  {"sam altman", "altman"},
    "elon musk":   {"elon musk", "musk"},
    "togg":        {"togg"},
    "windows":     {"windows"},
    "creator studio": {"creator studio", "creatorstudio"},
    "mgsm":        {"mgsm"},
    "cve":         {"cve"},
    "synthid":     {"synthid"},
    "limitless":   {"limitless"},
    "youtube":     {"youtube", "yt"},
    "tiktok":      {"tiktok", "tik tok"},
    "twitter":     {"twitter"},
    "snapchat":    {"snapchat", "snap"},
    "linkedin":    {"linkedin"},
    "reddit":      {"reddit"},
    "pinterest":   {"pinterest"},
    "discord":     {"discord"},
    "twitch":      {"twitch"},
    "github":      {"github"},
    "palantir":    {"palantir"},
    "deepseek":    {"deepseek", "deep seek"},
    "huawei":      {"huawei"},
    "alphafold":   {"alphafold", "alpha fold"},
    "crispr":      {"crispr"},
    "demis hassabis": {"demis hassabis", "hassabis"},
    # ── 2026-06-08 acronym aliases (PART 2 of gate fix) ──
    # Well-known agency / regulation / standard acronyms that AI news
    # routinely uses. The Perplexity-25M draft (a8bac287) FP-blocked
    # on "SBA" because the source said "U.S. Small Business
    # Administration" verbatim with no alias mapping. Same class
    # for: NIST, FDA, FTC, EU AI Act, GDPR, DARPA, NHTSA, etc.
    "sba":            {"sba", "small business administration",
                       "u.s. small business administration",
                       # Turkish equivalents (TR news drafts use these)
                       "abd küçük işletmeler idaresi",
                       "küçük işletmeler idaresi",
                       "abd kucuk isletmeler idaresi",
                       "kucuk isletmeler idaresi"},
    "nist":           {"nist", "national institute of standards and technology"},
    "fda":            {"fda", "food and drug administration"},
    "ftc":            {"ftc", "federal trade commission"},
    "doj":            {"doj", "department of justice"},
    "dod":            {"dod", "department of defense"},
    "nhtsa":          {"nhtsa", "national highway traffic safety administration"},
    "nsa":            {"nsa", "national security agency"},
    "cia":            {"cia", "central intelligence agency"},
    "fbi":            {"fbi", "federal bureau of investigation"},
    "darpa":          {"darpa", "defense advanced research projects agency"},
    "cisa":           {"cisa", "cybersecurity and infrastructure security agency"},
    "irs":            {"irs", "internal revenue service"},
    "uspto":          {"uspto", "u.s. patent and trademark office"},
    "sec":            {"sec", "securities and exchange commission"},
    "eu ai act":      {"eu ai act", "european union ai act", "ai act"},
    "gdpr":           {"gdpr", "general data protection regulation"},
    "ccpa":           {"ccpa", "california consumer privacy act"},
    "hipaa":          {"hipaa", "health insurance portability and accountability act"},
    "iso":            {"iso", "international organization for standardization"},
    "ieee":           {"ieee", "institute of electrical and electronics engineers"},
    "w3c":            {"w3c", "world wide web consortium"},
    "iso 27001":      {"iso 27001", "iso/iec 27001"},
    "soc 2":          {"soc 2", "soc2"},
    "wto":            {"wto", "world trade organization"},
    "imf":            {"imf", "international monetary fund"},
    "un":             {"un", "united nations"},
    "g7":             {"g7"},
    "g20":            {"g20"},
    "asml":           {"asml"},
    "tsmc":           {"tsmc", "taiwan semiconductor manufacturing"},
    "samsung":        {"samsung", "samsung electronics"},
    "intel":          {"intel"},
    "amd":            {"amd", "advanced micro devices"},
    "nvidia":         {"nvidia"},
    "snowflake":      {"snowflake"},
    "databricks":     {"databricks"},
    "salesforce":     {"salesforce"},
    "shopify":        {"shopify"},
    "stripe":         {"stripe"},
    "uber":           {"uber"},
    "airbnb":         {"airbnb"},
    "amazon":         {"amazon", "amzn"},
    "aws":            {"aws", "amazon web services"},
    "azure":          {"azure", "microsoft azure"},
    "gcp":            {"gcp", "google cloud platform", "google cloud"},
    "github copilot": {"github copilot", "copilot"},
}


# Product → maker: when a maker's product is in source, the maker counts as
# grounded too. So a draft saying "Anthropic" is GROUNDED when the source
# says "Claude Opus 4.8". This kills the bulk of T0 false positives.
_PRODUCT_TO_MAKER: dict[str, str] = {
    "claude":      "anthropic",
    "chatgpt":     "openai",
    "gpt":         "openai",
    "gpt-5":       "openai",
    "gpt-5.5":     "openai",
    "codex":       "openai",
    "gemini":      "google",
    "synthid":     "google",
    "copilot":     "microsoft",
    "windows":     "microsoft",
    "llama":       "meta",
    "starlink":    "spacex",
    "scout":       "meta",
    "limitless":   "meta",
}


# Source URL account → canonical entity. Many sources are tweet URLs whose
# raw_content omits the publishing organization's name even though the
# account identity is obvious. e.g. https://x.com/AnthropicAI/... → anthropic.
_URL_ACCOUNT_TO_ENTITY: dict[str, str] = {
    "anthropicai":     "anthropic",
    "claudeai":        "anthropic",
    "openai":          "openai",
    "openaidevs":      "openai",
    "googledeepmind":  "google",
    "google":          "google",
    "googleai":        "google",
    "metaai":          "meta",
    "spacex":          "spacex",
    "elonmusk":        "elon musk",
    "tesla":           "tesla",
    "microsoft":       "microsoft",
    "msftai":          "microsoft",
    "apple":           "apple",
    "geminiapp":       "google",
    # ── 2026-06-08 STAGE 1 sources (PART C diagnosis cure) ──
    # New X handles added in supply expansion migration 018. Without
    # these, drafts sourced from them FP-blocked at tier0 because the
    # brand entity isn't always verbatim in the source text (the
    # speaker IS the brand). Each maps to the canonical entity the
    # writer naturally uses.
    "perplexity_ai":   "perplexity",
    "perplexityai":    "perplexity",
    "sama":            "openai",        # Sam Altman speaks for OpenAI
    "mistralai":       "mistral",
    "karpathy":        "anthropic",     # joined Anthropic 2026-05-19
    "levelsio":        "indie hacker",
    "jeremyphoward":   "fast.ai",
    "hardmaru":        "sakana",        # Sakana AI CEO
    # Existing ai_news_en commentators that were silently FP-blocking:
    "_akhaliq":        "huggingface",
    "swyx":            "smol.ai",
    "officialloganK":  "google",        # Logan Kilpatrick, ex-OpenAI now Google
    "officiallogank":  "google",
    "alexalbert__":    "anthropic",
    "btibor91":        "openai",        # heavy OpenAI tracker
    "kimmonismus":     "openai",        # ditto
    "emollick":        "wharton",
    "simonw":          "datasette",
    "suhail":          "mighty",        # Suhail Doshi
    "deedydas":        "menlo ventures",
    "therundownai":    "the rundown",
}


def _entities_from_url(source_url: Optional[str]) -> set[str]:
    """Pull a canonical entity from the publishing account. e.g.
    x.com/AnthropicAI/status/123 → {"anthropic"}."""
    if not source_url:
        return set()
    m = re.search(r"x\.com/([^/]+)/", source_url, re.IGNORECASE)
    if not m:
        m = re.search(r"twitter\.com/([^/]+)/", source_url, re.IGNORECASE)
    if not m:
        return set()
    acct = m.group(1).lower()
    return {ent for key, ent in _URL_ACCOUNT_TO_ENTITY.items() if key in acct}


# Reverse map: any alias → its canonical entity key
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canon, aliases in _ENTITY_ALIASES.items():
    for a in aliases:
        _ALIAS_TO_CANONICAL[a.lower()] = canon


def _normalize_for_match(text: str) -> str:
    """Lowercase + strip Turkish-specific diacritics for forgiving match."""
    if not text:
        return ""
    folded = (
        text.replace("ı", "i").replace("İ", "i")
            .replace("ş", "s").replace("Ş", "s")
            .replace("ğ", "g").replace("Ğ", "g")
            .replace("ü", "u").replace("Ü", "u")
            .replace("ö", "o").replace("Ö", "o")
            .replace("ç", "c").replace("Ç", "c")
    )
    s = unicodedata.normalize("NFKD", folded).encode("ascii", "ignore").decode("ascii")
    return s.lower()


def _extract_known_entities(text: str) -> set[str]:
    """Match the curated alias set against the text. Returns canonical keys."""
    if not text:
        return set()
    norm = _normalize_for_match(text)
    hits: set[str] = set()
    for alias, canon in _ALIAS_TO_CANONICAL.items():
        # word-boundary check (alphanumeric or hyphen on either side fails)
        if re.search(rf"(?<![a-z0-9-]){re.escape(alias)}(?![a-z0-9-])", norm):
            hits.add(canon)
    return hits


# Specific numeric / CVE / benchmark patterns that frequently surface as
# fabricated specifics. Each pattern is extracted from the draft; the
# normalized-numeric token form is what gets matched against the source.
_SPECIFIC_PATTERNS = [
    # CVE IDs — case-insensitive verbatim
    re.compile(r"cve-\d{4}-\d+", re.IGNORECASE),
    # Benchmark names — case-insensitive verbatim
    re.compile(r"\b(?:MGSM|HumanEval|MMLU|GPQA|HellaSwag|SWE-Bench|SWE Bench)\b", re.IGNORECASE),
    # GPU / hardware model identifiers a tweet would only mention if literally in source
    re.compile(r"\b(?:H100|H200|A100|B200|GB200|TPU\s?v[34567])\b", re.IGNORECASE),
]


# Currency / numeric canonicalization.
#
# The job: "$920M" / "920 milyon dolar" / "920M$" should all collapse to
# the same token so a draft using one form matches a source using another.
# Same for "%23" / "23 percent", "2.5x" / "2,5 kat", and bare large numbers
# expressed as "10 binden fazla" vs "10000".
#
# Output token form: __USD_920000000__, __PCT_23__, __MULT_2.5__, __NUM_10000__.

_UNIT_MULT: dict[str, int] = {
    "":  1,
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
    "bin":   1_000,
    "milyon": 1_000_000,
    "milyar": 1_000_000_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "thousand": 1_000,
}


def _to_int(num_str: str, unit: str) -> int:
    n = float(num_str.replace(",", "."))
    return int(round(n * _UNIT_MULT[unit.lower()]))


def _canonicalize_numerics(text: str) -> str:
    """Rewrite numeric variants to canonical tokens so $920M ↔ "920 milyon
    dolar" ↔ "920M$" all collapse to __USD_920000000__. Applied to both
    source and draft before T0 grounding.

    2026-06-08 (PART 3 of gate fix): symmetric treatment of
    thousand-separators and bare-K/M/B suffixes. Without this, the
    Perplexity draft a8bac287 FP-blocked because source's "100,000"
    stayed verbatim while draft's "100 bin" canonicalized to
    __NUM_100000__ — two different tokens for the same number.
    """
    if not text:
        return ""
    s = text

    # ─ PRE: strip thousand-separators (1,234,567 → 1234567) ────────────
    # Pattern: 1-3 digits then 1+ groups of (comma + exactly 3 digits).
    # Unambiguous because EU decimal-comma is single digit after comma
    # ("2,5"), never 3-digit groups. Years like "1,000" rare in news.
    s = re.sub(
        r"(\d{1,3})((?:,\d{3})+)(?!\d)",
        lambda m: m.group(1) + m.group(2).replace(",", ""),
        s,
    )

    # ─ Money ────────────────────────────────────────────────────────────
    # "$920M" / "$920m" / "$ 920 M"
    s = re.sub(
        r"\$\s*(\d+(?:[.,]\d+)?)\s*([KMBkmb])\b",
        lambda m: f" __USD_{_to_int(m.group(1), m.group(2))}__ ",
        s,
    )
    # "$135" / "$135.50" — bare $ amount (no unit suffix)
    s = re.sub(
        r"\$\s*(\d+(?:[.,]\d+)?)\b(?![KMBkmb])",
        lambda m: f" __USD_{_to_int(m.group(1), '')}__ ",
        s,
    )
    # "920 milyon dolar" / "920 milyon dolarlık" / "920 milyon $"
    s = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*(milyon|milyar|bin|million|billion|thousand)\s*(?:dolar(?:lık|ı|a|dan)?|usd|\$|us\$)",
        lambda m: f" __USD_{_to_int(m.group(1), m.group(2))}__ ",
        s, flags=re.IGNORECASE,
    )
    # "135 dolar" / "135 dolarlık" — bare dolar w/o unit-word
    s = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*dolar(?:lık|ı|a|dan)?\b",
        lambda m: f" __USD_{_to_int(m.group(1), '')}__ ",
        s, flags=re.IGNORECASE,
    )

    # ─ Percent ─────────────────────────────────────────────────────────
    # "%23" / "% 23.5"  (Turkish prefix form)
    s = re.sub(
        r"%\s*(\d+(?:[.,]\d+)?)",
        lambda m: f" __PCT_{m.group(1).replace(',', '.')}__ ",
        s,
    )
    # "23%" / "23.5 %"  (English SUFFIX form — symmetric with "%23". Without
    # this the source's "87% less time" stayed verbatim while the Turkish
    # draft's "%87" / "yüzde 87" canonicalized → __PCT_87__ false-blocked as
    # ungrounded even though it IS in the source. 2026-06-08 cross-lingual fix.)
    s = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*%",
        lambda m: f" __PCT_{m.group(1).replace(',', '.')}__ ",
        s,
    )
    # "23 percent" / "23 yüzde" / "yüzde 23"
    s = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*(?:percent|yuzde|yüzde)\b",
        lambda m: f" __PCT_{m.group(1).replace(',', '.')}__ ",
        s, flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(?:yuzde|yüzde)\s*(\d+(?:[.,]\d+)?)",
        lambda m: f" __PCT_{m.group(1).replace(',', '.')}__ ",
        s, flags=re.IGNORECASE,
    )

    # ─ Multiplier (Nx / N kat) ─────────────────────────────────────────
    s = re.sub(
        r"\b(\d+(?:[.,]\d+)?)\s*kat\b",
        lambda m: f" __MULT_{m.group(1).replace(',', '.')}__ ",
        s, flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\b(\d+(?:[.,]\d+)?)\s*x\b",
        lambda m: f" __MULT_{m.group(1).replace(',', '.')}__ ",
        s, flags=re.IGNORECASE,
    )

    # ─ Bare large numbers w/ unit-words (no currency) ──────────────────
    # "10 binden fazla" / "32 milyon" / "240 milyon kullanıcı"
    s = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*(milyon|milyar|bin|million|billion|thousand)\b",
        lambda m: f" __NUM_{_to_int(m.group(1), m.group(2))}__ ",
        s, flags=re.IGNORECASE,
    )

    # ─ Bare K/M/B suffix without currency (PART 3, 2026-06-08) ─────────
    # "100K shares" / "5M users" / "2.5B requests" → __NUM_…__
    # Skip cases already captured by earlier USD rule (would have
    # become __USD_…__ already).
    s = re.sub(
        r"(?<![_\w\$])(\d+(?:\.\d+)?)([KMBkmb])\b",
        lambda m: f" __NUM_{_to_int(m.group(1), m.group(2))}__ ",
        s,
    )

    # ─ Standalone large integer ≥ 10000 (PART 3, 2026-06-08) ────────────
    # Without this, source-side "100,000" (after thousand-strip → "100000")
    # would stay verbatim while draft-side "100 bin" canonicalized.
    # Threshold 5+ digits avoids hitting years (2024, 2026) or small
    # quantities. Excludes digits already inside __TOK_<n>__ wrappers.
    s = re.sub(
        r"(?<![_\w])(\d{5,})(?![_\d])",
        lambda m: f" __NUM_{int(m.group(1))}__ ",
        s,
    )

    return s


def _extract_specific_facts(text: str) -> set[str]:
    """Return canonicalized specific-fact tokens.

    Two flavors:
      - verbatim patterns (CVE id, benchmark name, GPU model)
      - numeric tokens emitted by _canonicalize_numerics
        (__USD_…__, __PCT_…__, __MULT_…__, __NUM_…__)
    """
    if not text:
        return set()
    facts: set[str] = set()
    for pat in _SPECIFIC_PATTERNS:
        for m in pat.findall(text):
            facts.add(m.lower())
    canon = _canonicalize_numerics(text)
    for tok in re.findall(r"__(?:USD|PCT|MULT|NUM)_[\d.]+__", canon):
        facts.add(tok.lower())
    return facts


def _expand_with_makers(entities: set[str]) -> set[str]:
    """If a product entity is present, also mark its maker as grounded.
    Source has "claude opus 4.8" → makers also include "anthropic"."""
    out = set(entities)
    for e in entities:
        maker = _PRODUCT_TO_MAKER.get(e)
        if maker:
            out.add(maker)
    return out


def _expand_with_aliases(entities: set[str]) -> set[str]:
    """For source-side: if a canonical entity is present, also add ALL
    aliases of that canonical to the grounded set. So a source that
    surfaces canonical "google" makes "google deepmind", "deepmind"
    grounded too — they're all known surface forms of the same thing.
    This kills the FP class where the draft uses the more specific
    alias and the source uses the generic name."""
    out = set(entities)
    for canon in entities:
        if canon in _ENTITY_ALIASES:
            out |= _ENTITY_ALIASES[canon]
    return out


# ──────────────────────────────────────────────────────────────────────
# Entity canonicalization — collapses surface forms so fuzzy match works:
#   "OpenAI'ın"  → "openai"        (Turkish apostrophe-suffix strip)
#   "Google DeepMind" → "google"   (alias collapse)
#   "Claude Opus 4.8" → "anthropic"   (product → maker)
# ──────────────────────────────────────────────────────────────────────


def _canonicalize_entity(raw: str) -> str:
    """Lower + diacritic fold + Turkish apostrophe-suffix strip.

    Preserves the entity as extracted (does NOT collapse "Apple
    Intelligence" → "apple"). Alias-collapse + product→maker happen
    ONLY on the source side (via _extract_known_entities + curated map
    supplements + _expand_with_makers), so the draft check stays strict
    on the specific entity surface form.
    """
    if not raw:
        return ""
    s = _normalize_for_match(raw)
    # Strip Turkish "X'Y" suffix-marker on entity names
    s = re.sub(r"'(?:[a-z]{0,5})$", "", s)
    s = re.sub(r"'\s*[a-z]{0,5}\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Comparison / contrast / hypothetical / market-reference markers. When a
# draft entity is missing from source BUT the surrounding clause is in
# one of these contexts, treat as a comparator (not a grounding violation).
# This kills the FP-7 (Meta Ray-Ban contextual comparison) class.
_COMPARISON_MARKERS = re.compile(
    r"\b(?:"
    r"gibi|tarzında|tarzı|karşı|karşısında|karşılaşt|kıyasla|nazaran|"
    r"başarısından\s+sonra|ardından|öncesi|sonrasında|"
    r"benzeri|benzer\s+şekilde|"
    r"ile\s+(?:arasında|kıyasla|karşılaştırıldığında)|"
    r"e?\s+rağmen|ile\s+\w+ken|ile\s+\w+mişken|"
    r"\w+ken|\w+mişken|\w+iyorken"
    r")\b",
    re.IGNORECASE,
)


def _is_comparator_context(text: str, entity_norm: str) -> bool:
    """Returns True if the entity appears within a comparison/contrast
    clause (e.g. "Meta Ray-Ban ile sokakları ele geçirmişken, Apple…").
    Uses a windowed substring check — looks for the entity occurrence
    in the original text and tests its surrounding 80-char window for
    one of the comparison markers."""
    if not entity_norm:
        return False
    text_norm_full = _normalize_for_match(text)
    idx = text_norm_full.find(entity_norm)
    if idx < 0:
        return False
    window_start = max(0, idx - 40)
    window_end = min(len(text_norm_full), idx + len(entity_norm) + 80)
    window = text_norm_full[window_start:window_end]
    return bool(_COMPARISON_MARKERS.search(window))


def _extract_entities_normalized(text: str, source_url: Optional[str] = None) -> set[str]:
    """Run GLiNER → canonicalize → return as a set of canonical strings.

    Also union with curated-alias hits (the alias map still operates as a
    fallback recognizer for entities that appear as Turkish-suffixed
    forms, and for the source-URL-account hint). The combined set is the
    "entity universe" for grounding."""
    out: set[str] = set()
    for e in _gliner_extract(text):
        raw = (e.get("text") or "").strip()
        if not raw:
            continue
        canon = _canonicalize_entity(raw)
        if _is_noise_entity(canon):
            continue
        out.add(canon)
    # Fallback / supplemental — curated alias hits cover Turkish-suffix
    # forms that GLiNER may chop at the apostrophe.
    out |= _extract_known_entities(text)
    if source_url:
        out |= _entities_from_url(source_url)
    out.discard("")
    return out


def _fuzzy_in_set(needle: str, haystack: set[str]) -> bool:
    """Strict near-match. True if any haystack entry matches needle at
    `token_sort_ratio >= FUZZY_MATCH_THRESHOLD` — close form, not subset.

    `token_sort_ratio` reorders tokens then runs full Levenshtein, so:

       "google gemini"        vs "gemini"            → ~70 (BLOCK)
       "google gemini"        vs "google gemini app" → ~95 (PASS)
       "apple intelligence"   vs "apple"             → ~43 (BLOCK)
       "anthropic"            vs "anthropic"         → 100 (PASS)
       "openai'in"            vs "openai"            → ~95 (PASS)

    Plus: substring of multi-token entity counts as a match (e.g. needle
    "gemini" → haystack has "google gemini" → matches). Falls back to
    plain membership when rapidfuzz isn't available.
    """
    if not needle:
        return True
    if needle in haystack:
        return True
    try:
        from rapidfuzz import fuzz                # type: ignore
    except Exception:
        return False
    # Multi-token needle: ALL meaningful tokens must be in source set
    # (either as standalone canonical or as sub-token of some haystack
    # entry). This makes "google deepmind" match when source has
    # "google" AND "deepmind" individually (e.g. via alias map after
    # _expand_with_makers).
    needle_tokens = [t for t in needle.split() if len(t) >= 3]
    if len(needle_tokens) >= 2:
        haystack_tokens = set()
        for h in haystack:
            haystack_tokens.update(h.split())
        if all(t in haystack_tokens for t in needle_tokens):
            return True

    for h in haystack:
        if not h:
            continue
        if fuzz.token_sort_ratio(needle, h) >= FUZZY_MATCH_THRESHOLD:
            return True
        # Multi-word needle that appears verbatim as a subspan in
        # haystack (e.g. needle "apple tv" in haystack "apple tv plus")
        if " " in needle and needle in h:
            return True
        # Single proper-noun needle that appears verbatim as a TOKEN
        # in a multi-word haystack entry — only when the needle is
        # ≥ 5 chars (avoids matching "ai"/"meta"/"flow" as substrings)
        if " " not in needle and len(needle) >= 5:
            for tok in h.split():
                if tok == needle:
                    return True
    return False


def tier0_entity_grounding(
    draft_text: str,
    source_raw_content: str,
    *,
    source_url: Optional[str] = None,
) -> tuple[bool, list[str]]:
    """Deterministic GLiNER-backed entity + specific-fact grounding check.

    Pipeline:
      1. GLiNER extracts entities from draft and source (with curated
         alias-map supplement for Turkish-suffix coverage and URL hint).
      2. Each entity is canonicalized (diacritic fold, apostrophe-suffix
         strip, alias collapse, product→maker).
      3. A draft entity is grounded if a fuzzy match (token_set_ratio
         ≥ 85) exists in the source entity set. Currency/numeric specifics
         still flow through the canonical-token check.
      4. A draft entity missing from source is ALLOWED only when it
         appears in a comparison/contrast/hypothetical context (so the
         FP-7 "Meta Ray-Ban ile sokakları ele geçirmişken" pattern
         passes without breaking entity grounding for direct claims).

    Returns (blocked, list_of_ungrounded_entities).
    """
    draft_entities = _extract_entities_normalized(draft_text)
    source_entities = _extract_entities_normalized(source_raw_content, source_url=source_url)
    # Source-side: expand with maker + aliases-for-canonicals so a source
    # that surfaces "Google" also covers "Google DeepMind"/"DeepMind"
    # claims by the draft (they're all known surface forms of the same
    # canonical).
    source_entities = _expand_with_makers(source_entities)
    source_entities = _expand_with_aliases(source_entities)

    # Pre-compute normalized source text for verbatim-substring fallback.
    # If the draft entity literally appears in the source text (after
    # diacritic fold + lowercase), it is grounded — even when GLiNER
    # didn't extract it. This kills the "starship v3" / "claude mythos"
    # FP class where the entity is named in source but GLiNER skipped it.
    source_text_norm = _normalize_for_match(source_raw_content)

    entity_missing: list[str] = []
    for d_norm in sorted(draft_entities):
        if _fuzzy_in_set(d_norm, source_entities):
            continue
        if d_norm and d_norm in source_text_norm:
            continue
        # Multi-token needle: every token (≥3 chars) literally in
        # source text is good enough. e.g. needle "anthropic recursive
        # self-improvement": source has "recursive self-improvement"
        # verbatim + "claude" (canonical maker for anthropic). All
        # tokens covered → grounded.
        toks = [t for t in d_norm.split() if len(t) >= 3]
        if len(toks) >= 2:
            covered = all(t in source_text_norm or
                          _fuzzy_in_set(t, source_entities)
                          for t in toks)
            if covered:
                continue
        # Allow comparison context (FP-7 class).
        if _is_comparator_context(draft_text, d_norm):
            continue
        entity_missing.append(d_norm)

    # Specific facts (currency/percent/CVE/benchmark) — unchanged
    draft_facts = _extract_specific_facts(draft_text)
    source_facts = _extract_specific_facts(source_raw_content)
    source_norm = _normalize_for_match(source_raw_content)
    fact_missing = sorted([
        f for f in draft_facts
        if f not in source_facts and f not in source_norm
    ])

    all_missing = entity_missing + fact_missing
    return (bool(all_missing), all_missing)


# ──────────────────────────────────────────────────────────────────────
# Tier 1 — claim entailment (LLM, medium cost)
# ──────────────────────────────────────────────────────────────────────

TIER1_SYSTEM_PROMPT = """Sen bir kaynağa-bağlılık (faithfulness) hakemisin.

Sana iki metin verilecek:
  (A) KAYNAK METİN — orijinal haber tweet/article.
  (B) ÜRETİLEN TASLAK — Cansu Dut adlı persona'nın yazdığı Türkçe X postu.

GÖREVİN — İKİ AŞAMA:

AŞAMA 1: Taslağı cümle bazında parçala ve her cümleyi TİP olarak etiketle:
  - FACT: somut bir entity / sayı / tarih / ortaklık / olay / sebep-sonuç
    iddiası (kanıt gerektirir).
    Örnek: "Google SpaceX ile 920 milyon dolar anlaşma imzaladı",
    "CVE-2026-48095 açığı var", "OpenAI Microsoft tekelini bitirdi",
    "Bu özellik MMLU'da %94 skor aldı".
  - STANCE: değerlendirme, yorum, çerçeveleme, perspektif. Sıklıkla şu
    işaretleyicilerle gelir: "bence", "asıl iş", "asıl mesele", "asıl
    hikaye", "kimse söylemiyor ama", "perde-arkası", "burada
    görünmeyen", "ben bu hamleyi şöyle okuyorum", "şu açıdan bakınca",
    "demek ki…", "yani…", "operatörler için anlamlı", "yatırımcılar
    için yeni bilgi", "rakipler düşünmek zorunda", "sektör için sinyal",
    "bunu hafife almak yanlış olur", "ekosistemde tartışma başlatır",
    "klasik X tuzağı", "pattern'i yayılıyor", "pazar için anlamlı",
    "X dünyası bitiyor olabilir" (sonu "olabilir/galiba/sanırım" ile
    biten hedge'ler).
  - HEDGE: "olabilir", "galiba", "sanırım", "muhtemelen", "tahmin
    ediyorum" ile biten cümleler — STANCE gibi muamele gör.
  - META: "İlginç bir hamle.", "Yorum yarın.", "Detayı haberde.",
    "Bugünün haberi:" gibi içerikten boşaltılmış işaret cümleleri.

ÖNEMLİ:
- Sadece FACT tipindeki cümleleri yargıla. STANCE / HEDGE / META
  cümleleri ÇIKARMAdan listele ama "verdict": "stance" ver ve
  GROUNDING'İ KONTROL ETME — pass_ratio hesabına dahil ETME.
- Bir STANCE cümlesinin İÇİNDE bir FACT varsa (örn. "Microsoft
  Anthropic'le anlaşma yaptı, asıl iş bu" → "anlaşma yaptı" FACT
  kısmıdır, "asıl iş bu" STANCE) — sadece FACT parçasını yargıla.

GENEL-BİLGİ (general knowledge) framing — KAYNAK GEREKMİYOR:
Yaygın olarak bilinen, alanın temel bilgisi olan ifadeler (Cansu'nun
takipçilerinin zaten bildiği şeyler) FACT değil, çerçeveleme olarak
sayılır. ARAMA kaynak GEREKLİ DEĞİL:
  ✅ "kimyacılar molekül analizine zaman harcar"
       (NMR/kimya alanında genel bilinen — kaynak söylemese de OK)
  ✅ "API entegrasyonu copy-paste döngüsü yaratır"
       (geliştirici-tarafı genel-bilgi)
  ✅ "site analitiği insan trafiğine göre ayarlanır"
       (web ekosistemi temel bilgisi)
Eğer cümle, alanın temel bilinen bilgisini KARAR-vermeden aktarıyorsa
"verdict": "stance" ver (genel çerçeveleme). YENİ sayı/zaman/ölçek
iddiası varsa o kısmı FACT yap.

İNTERPRETASYON — KAYNAK GEREKMİYOR ama smuggling YASAK:
Cansu'nun KAYNAKTAKİ olaya getirdiği OKUYUŞ/anlam/ima — FACT değil,
yorumdur. Kaynak grounding GEREKLİ DEĞİL.
  ✅ "AI burada metin üretmiyor — saha kararları alıyor."
       (Hiroki örneği: AI tarımda nasıl kullanılıyor? Bu, kaynakta
        anlatılan kullanımın okuyuşu — "metin üretmek" vs "saha
        kararları" kaynakta yok ama OLAYIN OKUNUŞU değil)
  ✅ "Bu, tamamlamadan çözmeye geçiş."
       (kaynaktaki kapasite atlamasının okunuşu)
  ✅ "Trafik rakamları artık eskisi kadar anlamlı değil."
       (kaynaktaki bot oranı verisinin consequence-okuması)

SMUGGLING (kaçırma) KURALI — KRİTİK:
Bir STANCE/INTERPRETIVE cümle İÇİNDE yeni bir FACT iddiası
taşıyorsa, FACT'i AYRIŞTIR ve claims listesine tip="FACT" olarak
ekle. Yorum, yeni-fact taşımak için bir araç olarak KULLANILAMAZ.
  ❌ "Bu hamle, OpenAI'ın gelirinin 3 kat arttığı anlamına geliyor."
       → STANCE: "Bu hamle … anlamına geliyor" (yorum)
       → FACT (kaynakta OLMALI): "OpenAI'ın gelirinin 3 kat arttı"
       → FACT yoksa kaynakta → verdict="ungrounded", pass_ratio'ya DAHİL.
  ❌ "Apple bu modeli askeri amaçla geliştirdi."
       → tek FACT iddiası (motiv); kaynakta yok → ungrounded.
  ❌ "Anthropic gizlice AGI'ye ulaştı."
       → FACT iddiası (olay); kaynakta yok → ungrounded.
  ❌ "Cansu için asıl önemli olan: Sam Altman istifa etti."
       → STANCE framing + FACT smuggle ("istifa etti"). FACT'i
         ayrıştır ve kaynakta var mı diye bak.

SPEKÜLASYON İŞARETİ (soft — grounding'i ETKİLEMEZ, sadece raporlanır):
Her cümle için ek bir "speculative" bayrağı ver. Şu durumlarda true:
  - Kaynakta OLMAYAN politik/jeopolitik tahmin/yorum ("Çin'e gün doğdu",
    "fişi hükümetlerde", "bu hamle ABD'yi öne geçirir", "düzenleyiciler
    buna izin vermez").
  - Kaynakta OLMAYAN pazar/rekabet kehaneti ("X bu pazarı ele geçirir",
    "Y kazanır/biter", "rakipler dağılır").
  - Kaynakta OLMAYAN nedensellik/sonuç zinciri (olayın kaynakta yazmayan
    bir sebebe/sonuca bağlanması).
Aksi halde false. NOT: Bu bayrak yalnız STANCE/HEDGE/META cümleleri için
anlamlı; FACT cümlelerinde de işaretleyebilirsin ama pass_ratio'yu DEĞİŞTİRME.
Bu işaret yayını ENGELLEMEZ; sadece insan gözlemi için kaydedilir.

AŞAMA 2: Her FACT için verdict:
  - "grounded": Kaynak DOĞRUDAN veya açık biçimde implikasyon olarak
    destekliyor. Aynı entity'nin maker/üreticisinden bahsetmek
    (kaynak "Claude Opus 4.8" → draft "Anthropic") GROUNDED'tır.
    Para biriminin sembolü farklı olabilir ($920M ≡ "920 milyon dolar").
    DİL FARKI GROUNDING'İ BOZMAZ: kaynak çoğunlukla İngilizce, taslak
    Türkçe. İddianın ÇEVİRİSEL karşılığı kaynaktaysa GROUNDED say
    ("Our most powerful on-device AI model runs on iPhone 17 Pro" ≡
    "En güçlü on-device AI modeli iPhone 17 Pro'da çalışıyor").
    Her FACT için yargıdan önce kaynağı İKİ DİLDE de tara; İngilizce
    kaynak cümlesini bulamadın diye Türkçe iddiayı ungrounded YAPMA,
    önce çevirisini ara.
  - "ungrounded": Kaynakta yok ya da kaynağı genişleterek/abartarak
    uyduruyor (genelleme dahil — kaynak "bir özellik" diyorsa "tüm
    pazar" yazmak ungrounded'dır).

ÖRNEKLER (KALİBRASYON):

Örnek 1 — STANCE faithful olarak kabul:
  Kaynak: "Apple iPhone 18 Pro'da bölgesel batarya stratejisi uyguluyor."
  Taslak: "Apple iPhone 18 Pro'da bölgesel batarya stratejisine geçiyor.
           Tek SKU dünyası bitiyor olabilir."
  Yargı: cümle 1 FACT grounded; cümle 2 STANCE (hedge "olabilir") — değerlendirilmez.
  pass_ratio = 1.0 (1/1 FACT)

Örnek 2 — STANCE faithful olarak kabul:
  Kaynak: "Anthropic Claude Opus 4.8'i duyurdu."
  Taslak: "Anthropic Claude Opus 4.8'i çıkardı. Bence ekibin disiplini
           hissediliyor."
  Yargı: cümle 1 FACT grounded (Anthropic ← Claude Opus üreticisi);
         cümle 2 STANCE. pass_ratio = 1.0.

Örnek 3 — gerçek fabrication:
  Kaynak: "Google SpaceX ile 920 milyon dolarlık compute anlaşması."
  Taslak: "Google'ın SpaceX ile $920M anlaşması — asıl hikaye Starlink
           üzerinden veri merkezlerine fiziksel bağlantı."
  Yargı: cümle 1 FACT grounded; "asıl hikaye…" STANCE değil — somut
         bir iddia (Starlink + fiziksel bağlantı). Kaynakta YOK →
         ungrounded. pass_ratio = 0.5.

Çıktı KESİNLİKLE şu JSON formatında olmalı, başka metin yok:

{
  "claims": [
    {"claim": "...", "type": "FACT" | "STANCE" | "HEDGE" | "META",
     "verdict": "grounded" | "ungrounded" | "stance",
     "speculative": true | false,
     "evidence_or_gap": "..."}
  ],
  "pass_ratio": <0.0-1.0 arası, grounded FACT sayısı / toplam FACT sayısı;
                hiç FACT yoksa 1.0>
}"""


async def tier1_claim_entailment(
    draft_text: str,
    source_raw_content: str,
    *,
    claim_grounding_floor: float = 0.9,
) -> tuple[bool, Optional[float], list[str], float]:
    """LLM-based atomic-claim entailment.

    Returns (blocked, pass_ratio, ungrounded_claims, cost_estimate).
    blocked = pass_ratio < claim_grounding_floor.
    """
    try:
        from openai import AsyncOpenAI
        from config import settings
    except Exception as e:
        logger.warning(f"tier1_claim_entailment: import failed: {e}")
        return (False, None, [], 0.0)

    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    user = (
        f"(A) KAYNAK METİN:\n{source_raw_content}\n\n"
        f"(B) ÜRETİLEN TASLAK:\n{draft_text}"
    )

    # LiteLLM Router (flag-gated, fail-open). Async JSON gate → router_chat_json
    # (gate-fast). On any router error we fall through to the AsyncOpenAI path
    # below (no behavior change when flag OFF).
    from .llm_router import router_enabled, router_chat_json
    if router_enabled():
        try:
            parsed, _meta = await router_chat_json(
                TIER1_SYSTEM_PROMPT, user, temperature=0.0, max_tokens=1500,
                model_name="gate-fast",
            )
            claims = parsed.get("claims") or []
            if not claims:
                return (False, 1.0, [], 0.001)
            pass_ratio = float(parsed.get("pass_ratio") or 0.0)
            ungrounded = [
                f"{c.get('claim','')} → {c.get('evidence_or_gap','')}"
                for c in claims
                if c.get("verdict") == "ungrounded"
            ]
            _log_speculation_flags(claims, draft_text)
            blocked = pass_ratio < claim_grounding_floor
            return (blocked, pass_ratio, ungrounded, 0.002)
        except Exception as e:
            logger.warning(f"tier1_claim_entailment: router atlandı: {e}")

    try:
        resp = await client.chat.completions.create(
            model=ENTAILMENT_MODEL,
            temperature=0.0,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": TIER1_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        if not getattr(resp, "choices", None):
            logger.warning(
                "tier1_claim_entailment: boş/None choices (OpenRouter "
                "rate-limit/err) — grounding atlandı (fail-soft)"
            )
            return (False, None, [], 0.0)
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])
            text = text.strip()
        parsed = json.loads(text)
    except Exception as e:
        logger.exception(f"tier1_claim_entailment: LLM/parse failed: {e}")
        return (False, None, [], 0.0)

    claims = parsed.get("claims") or []
    if not claims:
        # No factual claims surfaced — nothing to ground. Don't block on this.
        return (False, 1.0, [], 0.001)
    pass_ratio = float(parsed.get("pass_ratio") or 0.0)
    ungrounded = [
        f"{c.get('claim','')} → {c.get('evidence_or_gap','')}"
        for c in claims
        if c.get("verdict") == "ungrounded"
    ]
    _log_speculation_flags(claims, draft_text)
    blocked = pass_ratio < claim_grounding_floor
    return (blocked, pass_ratio, ungrounded, 0.002)


def _log_speculation_flags(claims: list, draft_text: str) -> None:
    """SOFT spekülasyon gözlemi (2026-06-14). Tier 1 hakimi politik/jeopolitik/
    pazar tahmini veya kaynakta-olmayan nedensellik için 'speculative': true
    işaretler. Bu YALNIZCA loglanır — yayını ENGELLEMEZ, pass_ratio'yu
    değiştirmez (false-pos riski; Faz A 'önce yumuşak' kararı). Gözlemle;
    gerçek-pozitif netleşince block'a çekme kararı insan verir.
    """
    try:
        spec = [
            str(c.get("claim", ""))[:140]
            for c in (claims or [])
            if c.get("speculative") is True
        ]
        if spec:
            logger.warning(
                f"[faithfulness] SPEKÜLASYON-FLAG ({len(spec)}): "
                f"{' ; '.join(spec)} | draft='{draft_text[:80]}'"
            )
    except Exception as e:  # noqa: BLE001 — gözlem hiçbir koşulda akışı bozmaz
        logger.debug(f"[faithfulness] speculation-flag log atlandı: {e}")


# ──────────────────────────────────────────────────────────────────────
# Arbiter — blok temyiz hakimi (2026-06-10, Berkay: "çok sert bloklama
# olmamalı; iyice uydurduysa müdahale etmeli").
#
# Tier 0 deterministik katmanın FP sınıfları (NER span varyansı, Türkçe
# ek almış entity, çeviri karşılığı) ve Tier 1'in cross-lingual kaçırması
# bugüne dek doğrudan HARD_BLOCK'a düşüyordu — temyiz yoktu. Arbiter,
# YALNIZCA blok çıktığında çalışır (draftların küçük yüzdesi), ihlalleri
# tek tek sınıflar:
#   fp          → yanlış alarm, blok kalkar (PASS, reasoning'e not düşer)
#   minor       → yeni olgu eklemeyen kusur, blok kalkar (PASS_WITH_NOTE
#                 semantiği — reasoning'de işaretli, kalibrasyona girer)
#   fabrication → blok KALIR; ihlal listesi onaylanmış kalemlere
#                 filtrelenir ki rewrite döngüsü gerçek soruna nişan alsın
# Arbiter hatası/timeout → orijinal blok korunur (fail-closed).
# Kill-switch: FAITHFULNESS_ARBITER_DISABLED=1
# ──────────────────────────────────────────────────────────────────────

ARBITER_SYSTEM_PROMPT = """Sen bir fact-check TEMYİZ hakimisin. Birinci
katman (deterministik NER + claim-entailment) bir taslağı blokladı; işin
her ihlali tek tek inceleyip GERÇEK uydurma ile yanlış alarmı ayırmak.

Girdi: (A) KAYNAK METİN, (B) ÜRETİLEN TASLAK, (C) İHLAL LİSTESİ.

Her ihlal için sınıf:
  - "fp" (yanlış alarm): unsur ASLINDA kaynakta var — yazım varyantı,
    Türkçe ek almış hali ("Apple Intelligence'ın"), kısaltma/açılım,
    ÇEVİRİ karşılığı (kaynak çoğunlukla İngilizce, taslak Türkçe —
    iki dilde de ara), ya da unsur bir olgu iddiası değil yorum /
    genel-bilgi çerçevelemesi.
  - "minor": kaynakta birebir yok ama YENİ somut olgu da eklemiyor —
    yuvarlama, hafif genelleme, zararsız parafraz. Yayın güvenliğini
    bozmaz.
  - "fabrication": kaynakta olmayan YENİ entity / sayı / tarih / olay /
    ortaklık / sebep iddiası, ya da kaynaktaki bir olguyla ÇELİŞKİ.
    ŞÜPHEDEYSEN fabrication de — yayın güvenliği her zaman önce gelir.

"item" alanına ihlali AYNEN (verbatim) kopyala.

JSON çıktı (yalnızca JSON):
{"violations": [{"item": "<ihlal verbatim>", "class": "fp|minor|fabrication",
  "why": "<tek cümle>"}],
 "overall": "fp|minor|fabrication"}
overall = en kötü sınıf (fabrication > minor > fp)."""


async def arbiter_review(
    draft_text: str,
    source_raw_content: str,
    violations: list[str],
) -> tuple[str, list[dict], float]:
    """Blok temyizi. Returns (overall_class, per_violation, cost).

    overall_class ∈ {"fp", "minor", "fabrication", "error"} — "error"
    çağıranın orijinal bloğu koruması demektir (fail-closed).
    """
    if not violations:
        return ("error", [], 0.0)
    try:
        from openai import AsyncOpenAI
        from config import settings
    except Exception as e:
        logger.warning(f"arbiter_review: import failed: {e}")
        return ("error", [], 0.0)

    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    user = (
        f"(A) KAYNAK METİN:\n{source_raw_content}\n\n"
        f"(B) ÜRETİLEN TASLAK:\n{draft_text}\n\n"
        "(C) İHLAL LİSTESİ:\n- " + "\n- ".join(violations)
    )

    # LiteLLM Router (flag-gated, fail-open). Async JSON gate → router_chat_json
    # (gate-fast). On any router error fall through to the AsyncOpenAI path
    # below. Bozuk/missing overall → ("error", ...) = blok korunur (fail-closed).
    from .llm_router import router_enabled, router_chat_json
    if router_enabled():
        try:
            parsed, _meta = await router_chat_json(
                ARBITER_SYSTEM_PROMPT, user, temperature=0.0, max_tokens=1000,
                model_name="gate-fast",
            )
            items = parsed.get("violations") or []
            overall = (parsed.get("overall") or "").strip().lower()
            if overall not in ("fp", "minor", "fabrication"):
                return ("error", [], 0.002)
            return (overall, items, 0.002)
        except Exception as e:
            logger.warning(f"arbiter_review: router atlandı: {e}")

    try:
        resp = await client.chat.completions.create(
            model=ENTAILMENT_MODEL,
            temperature=0.0,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": ARBITER_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        if not getattr(resp, "choices", None):
            logger.warning(
                "arbiter_review: boş/None choices (rate-limit/err) — temyiz "
                "atlandı, blok korunur (fail-closed)"
            )
            return ("error", [], 0.0)
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])
            text = text.strip()
        parsed = json.loads(text)
    except Exception as e:
        logger.exception(f"arbiter_review: LLM/parse failed: {e}")
        return ("error", [], 0.0)

    items = parsed.get("violations") or []
    overall = (parsed.get("overall") or "").strip().lower()
    if overall not in ("fp", "minor", "fabrication"):
        # Bozuk çıktı — fail-closed.
        return ("error", [], 0.002)
    return (overall, items, 0.002)


# ──────────────────────────────────────────────────────────────────────
# Tier 2 — fabricated-thesis judge (LLM, gray-zone only)
# ──────────────────────────────────────────────────────────────────────

TIER2_SYSTEM_PROMPT = """You are a strict source-fidelity reviewer.

Input: a Turkish AI-news tweet draft (B) and the original source text (A).

Question: does the draft's CENTRAL THESIS introduce a NEW SPECIFIC entity
or a CAUSAL CLAIM that the source does NOT support?

FAIL when ANY of these apply:
  (1) The framing introduces a concrete NEW entity, product, organization,
      person, or event NOT in the source (e.g. "Starlink", "YouTube",
      "Pentagon", a specific competitor not named in source).
  (2) The framing asserts a specific causal claim ("X caused Y", "this
      means Z threshold was crossed", "X bitti / Y öldü") not supported
      by the source.
  (3) The framing makes a market-scale impact claim ("BÜTÜN endüstri
      için exit signal", "pazarın %X'i tehlikede", "[sector] dünyası
      bitiyor", "[sector]'ı işsiz bıraktı", "sektörün de-facto
      standardı") that is not directly stated by the source.

(3) is the overreach case: a strong directional claim about a whole
market/sector/category is FAIL unless the source itself makes that
claim. The line: source says "Meta tests a feature" → draft saying
"BÜTÜN performance marketing endüstrisi için exit signal" = FAIL
because the source does not assert sector-wide impact.

PASS in all other cases. Specifically PASS when:
  - The framing is a sharp interpretation BUILT ON the source's facts
    (no new entities), even if punchy or opinionated.
  - The framing is a market/sector commentary that adds NO new entity
    ("operator için anlamlı", "pattern yayılıyor", "devlerin bile içeride
    yetmiyor", "ekosistemde tartışma başlatır").
  - The framing is a hedge or stance marker ("olabilir", "galiba",
    "klasik X tuzağı") on a grounded fact.
  - The framing critiques or contrasts using only source entities.
  - **The framing is an interpretation of WHAT THE SOURCE DESCRIBES** —
    a re-reading of the same event in different terms. This is the
    "beat" Cansu's voice is explicitly designed to add:
      * MECHANISM reading: "this is how X works" / "the move is in Y"
      * CONSEQUENCE reading: "this means Z is no longer true"
      * CAPABILITY-SHIFT reading: "this is X-to-Y transition" /
        "this isn't A anymore, it's B"
    PASS as long as the reading stays on the SAME event/capability the
    source describes (no new entity, no new specific number, no new
    motiv/cause). The reading IS Cansu's value; allowing it is the
    whole point.

KRİTİK PERMISSION — INTERPRETIVE BEAT (allow Cansu's READING):
The source describes an event/capability. The draft adds ONE sentence
re-framing that same event in different terms. This is NOT a new
thesis — it's a reading of what already happened in the source.
ALLOW even when the reading uses different vocabulary than the source.

  ✅ ALLOW: "Bu, tamamlamadan çözmeye geçiş."
       Source: Claude's open-ended coding success rate 26% → 76%.
       Draft re-frames the capability jump as a category shift.
       No new entity, no new number, no new motiv. ALLOW.

  ✅ ALLOW: "AI burada metin üretmiyor — saha kararları alıyor."
       Source: Hiroki manages his Japanese farm using ChatGPT + Codex.
       Draft re-frames what AI is DOING in this case. Not a new fact
       about ChatGPT; a reading of the use-case. ALLOW.

  ✅ ALLOW: "Trafik rakamları artık eskisi kadar anlamlı değil."
       Source: 57.4% of internet traffic is bots; humans first time
       in minority.
       Draft draws the CONSEQUENCE on web-analytics meaning. The
       consequence flows directly from the source fact. No new entity,
       no new number. ALLOW.

  ✅ ALLOW: "Dil üretmekten çıkıp domain-specific reasoning'e geçiş."
       Source: Opus 4.7 solves molecule structure from NMR data.
       Draft re-frames the capability as a category shift in what
       LLMs do. Same event, different lens. ALLOW.

  ✅ ALLOW: "Context kaybolmuyor, geçiş maliyeti sıfır."
       Source: Claude desktop app retains conversation state.
       Draft reads the SAME feature in two beats (no context loss,
       zero switching cost). Both flow directly from "retained state".
       "Geçiş maliyeti sıfır" is a consequence reading. ALLOW.

❌ NOT ALLOWED (still BLOCK) — fact-disguised-as-reading:
The "interpretive beat" exemption does NOT cover:
  - New numbers / sizes / percentages that source doesn't have.
  - New named entities (orgs, products, people) not in source.
  - New events / actions / cause-effect chains that source doesn't
    assert.
  - Motiv claims ("X bunu Y amacıyla yaptı") not in source.

Examples of FAIL (new entity smuggled in via framing):
  - Source: "Google bought $920M of compute from SpaceX."
    Draft: "the real story is Google's Starlink physical connection."
    → FAIL. Starlink is a NEW entity not in source.
  - Source: "Claude Opus 4.8 with sharper judgment."
    Draft: "everyone thinks X but real story is recursive self-improvement
    threshold crossed."
    → FAIL. Specific causal claim ("threshold crossed") not in source —
    and the source EXPLICITLY denies it.
  - Source: "Meta tests Reels 'Series' feature for topic-grouping."
    Draft: "Meta Series ile YouTube'a doğrudan saldırı başlattı."
    → FAIL. YouTube is a NEW entity; "doğrudan saldırı" is an
    unsupported causal claim.
  - Source: "Meta launches a new AI assistant that turns dashboards into chat."
    Draft: "Bu, BÜTÜN performance marketing endüstrisi için exit signal."
    → FAIL. Sector-scale impact ("BÜTÜN endüstri için exit signal")
    not asserted by source.
  - Source: "Anthropic Mythos found 10K+ vulnerabilities."
    Draft: "Mythos güvenlik araştırmacılarının %40'ını işsiz bıraktı."
    → FAIL. Sector-impact + specific number ("%40'ını işsiz bıraktı")
    not in source.
  - Source: "SynthID watermark expands to more partners."
    Draft: "SynthID sektörün de-facto standardını kurdu."
    → FAIL. "De-facto standart" is a market-scale assertion not in source.

Examples of PASS (sharp framing, no new entity):
  - Source: "Google bought $920M of compute from SpaceX."
    Draft: "Google AI talebinin altında ezilmeye başladı: $920M compute
    aldı. Devlerin bile içeride yetmiyor."
    → PASS. "Devlerin bile içeride yetmiyor" is a stance built on the
    grounded fact, no new entity.
  - Source: "Apple uses regional battery strategy for iPhone 18 Pro."
    Draft: "Apple iPhone 18 Pro'da bölgesel batarya stratejisine geçiyor.
    Bu, ürün ekibinin son aylardır işaret ettiği yöne uyuyor."
    → PASS. "Ürün ekibinin son aylardır işaret ettiği yöne uyuyor" is a
    SOFT INFERENCE / commentary on the company's product direction; it
    does not introduce a new entity or specific causal claim. Phrases
    like "ürün ekibinin yön gösterdiği uyuyor", "ekibin disiplini
    hissediliyor", "son aylardır beklenen adım", "vizyonla tutarlı",
    "uzun süredir konuşulan plan" are stance/inference, NOT FAIL.
  - Source: "Google releases 32M lab-grown male mosquitoes."
    Draft: "DeepMind tarafı için anlamlı bir gelişme: Google sivrisinek
    salacak."
    → PASS. "DeepMind" is an ALIAS of an in-source entity (Google) — a
    known sub-brand of Google. Drafts may refer to an in-source company
    using its alias / sub-brand / product name; do not flag.
  - Source: "Google launches feature X via Gemini App."
    Draft: "Google DeepMind tarafı için anlamlı: Gemini App ile feature
    X geliyor."
    → PASS. Same: "Google DeepMind" is referenced as the agent — both
    Google and DeepMind are valid in-context.
  - Source: "Meta AI bot helped Instagram account takeovers via the
    support flow."
    Draft: "Meta AI destek botu, hesap ele geçirmede araç oldu. Klasik
    'AI'ın yetkisi insandan fazla' tuzağı."
    → PASS. The framing is a critique pattern, introduces no new entity.
  - Source: "Google DeepMind expands Singapore partnership: science,
    pandemic prep, healthcare."
    Draft: "Devlet + AI lab ortaklığı pattern'i yayılıyor."
    → PASS. Sector commentary, no new entity.
  - Source: "Apple uses regional battery strategy for iPhone 18 Pro."
    Draft: "Apple iPhone 18 Pro'da bölgesel strateji. Tek SKU dünyası
    bitiyor olabilir."
    → PASS. Hedged stance ("olabilir") on a grounded fact.
  - Source: "Anthropic says recursive self-improvement NOT on horizon."
    Draft: "Anthropic'in dürüst kabulü: RSI henüz ufukta değil. Hype
    değil, gerçekçilik."
    → PASS. Same direction as source.
  - Source: "OpenAI frontier models and Codex are now generally available
    on AWS, on Amazon Bedrock."
    Draft: "Herkes OpenAI modellerini sadece Microsoftun elinde sanıyordu.
    AWS Bedrock hamlesiyle o tekel tamamen bitti."
    → PASS. "Microsoft tekeli bitti" is the DIRECT logical entailment of
    "now generally available on AWS" — bringing the implied prior state
    ("OpenAI was exclusive to Microsoft Azure") into the framing is a
    sharp interpretation, NOT a new fact: it is the inverse of the
    source's positive claim. Implied-prior-state entailments are PASS
    even when the implied entity (here "Microsoft") is not literally
    in source.
  - Source: "Apple smart glasses postponed to end of 2027."
    Draft: "Meta Ray-Ban ile sokakları ele geçirmişken, Apple akıllı
    gözlük projesini 2027'ye erteledi."
    → PASS. Meta + Ray-Ban appear in a comparator clause
    ("ile … geçirmişken") — the draft is contrasting Apple's delay
    against a competitor reference. Comparator entities are not
    grounding violations; they're context for the actual claim about
    Apple. (T0's comparison-context allowance handles this; T2 should
    also recognize the pattern.)

Return strict JSON, no other text:
{
  "verdict": "PASS" | "FAIL",
  "reasoning": "1-2 sentences citing the specific NEW entity or causal
                claim if FAIL; or why no new entity / claim if PASS",
  "ungrounded_angles": ["list of each ungrounded framing — only the
                        new-entity or unsupported-causal ones"]
}"""


async def tier2_thesis_judge(
    draft_text: str,
    source_raw_content: str,
) -> tuple[bool, str, list[str], float]:
    try:
        from openai import AsyncOpenAI
        from config import settings
    except Exception as e:
        logger.warning(f"tier2_thesis_judge: import failed: {e}")
        return (False, "SKIPPED", [], 0.0)

    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    user = f"(A) SOURCE:\n{source_raw_content}\n\n(B) DRAFT:\n{draft_text}"

    # LiteLLM Router (flag-gated, fail-open). Async JSON gate → router_chat_json
    # (gate-fast). On any router error fall through to the AsyncOpenAI path below.
    from .llm_router import router_enabled, router_chat_json
    if router_enabled():
        try:
            parsed, _meta = await router_chat_json(
                TIER2_SYSTEM_PROMPT, user, temperature=0.0, max_tokens=600,
                model_name="gate-fast",
            )
            verdict = parsed.get("verdict", "PASS")
            return (
                verdict == "FAIL",
                verdict,
                list(parsed.get("ungrounded_angles") or []),
                0.001,
            )
        except Exception as e:
            logger.warning(f"tier2_thesis_judge: router atlandı: {e}")

    try:
        resp = await client.chat.completions.create(
            model=JUDGE_MODEL,
            temperature=0.0,
            max_tokens=600,
            messages=[
                {"role": "system", "content": TIER2_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        if not getattr(resp, "choices", None):
            logger.warning(
                "tier2_thesis_judge: boş/None choices (rate-limit/err) — "
                "atlandı (fail-soft SKIPPED)"
            )
            return (False, "SKIPPED", [], 0.0)
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])
            text = text.strip()
        parsed = json.loads(text)
    except Exception as e:
        logger.exception(f"tier2_thesis_judge: failed: {e}")
        return (False, "SKIPPED", [], 0.0)

    verdict = parsed.get("verdict", "PASS")
    return (
        verdict == "FAIL",
        verdict,
        list(parsed.get("ungrounded_angles") or []),
        0.001,
    )


# ──────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────

async def run_faithfulness_gate(
    *,
    draft_text: str,
    source_raw_content: str,
    source_url: Optional[str] = None,
    claim_grounding_floor: float = 0.9,
) -> FaithfulnessVerdict:
    """Run all three tiers, return a structured verdict.

    Fail-closed: any tier hard-blocks → overall=HARD_BLOCK.
    Tier 2 is skipped when T0 + T1 are clean (cheap optimization).
    """
    cost = 0.0

    # Tier 0 — deterministic NER + specific-fact match
    t0_blocked, t0_missing = tier0_entity_grounding(
        draft_text, source_raw_content or "", source_url=source_url,
    )

    # Tier 1 — claim entailment
    t1_blocked, t1_ratio, t1_ungrounded, t1_cost = await tier1_claim_entailment(
        draft_text, source_raw_content or "",
        claim_grounding_floor=claim_grounding_floor,
    )
    cost += t1_cost

    # Arbiter — temyiz (2026-06-10). Yalnız blokta çalışır; fp/minor →
    # blok kalkar, fabrication → blok kalır + ihlal listesi onaylanmış
    # kalemlere filtrelenir (rewrite feedback'i keskinleşir). "error" →
    # orijinal blok korunur (fail-closed).
    arbiter_note: Optional[str] = None
    if (t0_blocked or t1_blocked) and not os.environ.get(
        "FAITHFULNESS_ARBITER_DISABLED"
    ):
        _viol = (
            [f"kaynakta geçmeyen unsur: {e}" for e in t0_missing]
            + [f"desteksiz iddia: {c}" for c in t1_ungrounded]
        )
        a_overall, a_items, a_cost = await arbiter_review(
            draft_text, source_raw_content or "", _viol,
        )
        cost += a_cost
        if a_overall in ("fp", "minor"):
            _why = "; ".join(
                f"{(it.get('item') or '')[:60]}→{it.get('class')}: {it.get('why', '')}"
                for it in a_items
            )[:400]
            arbiter_note = (
                f"ARBITER_{'FP_OVERRULE' if a_overall == 'fp' else 'MINOR_PASS'}: "
                f"t0={t0_missing} t1={len(t1_ungrounded)} claims | {_why}"
            )
            logger.info(f"[arbiter] blok kaldırıldı ({a_overall}): {_why[:200]}")
            t0_blocked = False
            t1_blocked = False
        elif a_overall == "fabrication":
            _confirmed = {
                (it.get("item") or "")
                for it in a_items
                if it.get("class") == "fabrication"
            }
            if _confirmed:
                _t0_f = [
                    e for e in t0_missing
                    if any(e in c for c in _confirmed)
                ]
                _t1_f = [
                    u for u in t1_ungrounded
                    if any(u[:60] in c or c in u for c in _confirmed)
                ]
                # Filtre boş kalırsa (eşleşme tutmadı) orijinal listeyi koru.
                t0_missing = _t0_f or t0_missing
                t1_ungrounded = _t1_f or t1_ungrounded
            arbiter_note = "ARBITER_CONFIRMED_FABRICATION"
            logger.info(
                f"[arbiter] fabrication onaylandı: t0={t0_missing} "
                f"t1={t1_ungrounded}"
            )
        else:
            arbiter_note = "ARBITER_ERROR (orijinal blok korundu)"
            logger.warning("[arbiter] hata — fail-closed, blok korunuyor")

    # Tier 2 — only if everything else passed; otherwise we already block
    if not (t0_blocked or t1_blocked):
        t2_blocked, t2_verdict, t2_angles, t2_cost = await tier2_thesis_judge(
            draft_text, source_raw_content or "",
        )
        cost += t2_cost
    else:
        t2_blocked, t2_verdict, t2_angles = (False, "SKIPPED", [])

    blocked = t0_blocked or t1_blocked or t2_blocked
    overall = "HARD_BLOCK" if blocked else "PASS"

    reasoning_parts: list[str] = []
    if t0_blocked:
        reasoning_parts.append(
            f"Tier 0: ungrounded entities/specifics: {t0_missing}"
        )
    if t1_blocked:
        reasoning_parts.append(
            f"Tier 1: claim grounding ratio {t1_ratio:.2f} below floor {claim_grounding_floor}; "
            f"ungrounded: {t1_ungrounded}"
        )
    if t2_blocked:
        reasoning_parts.append(
            f"Tier 2: fabricated thesis(es) detected: {t2_angles}"
        )
    if not reasoning_parts:
        reasoning_parts.append("All tiers PASS")
    if arbiter_note:
        reasoning_parts.append(arbiter_note)
    reasoning = " | ".join(reasoning_parts)

    return FaithfulnessVerdict(
        overall=overall,
        tier0_entities_missing=t0_missing,
        tier0_blocked=t0_blocked,
        tier1_claim_pass_ratio=t1_ratio,
        tier1_ungrounded_claims=t1_ungrounded,
        tier1_blocked=t1_blocked,
        tier2_verdict=t2_verdict,
        tier2_ungrounded_angles=t2_angles,
        tier2_blocked=t2_blocked,
        reasoning=reasoning,
        cost_usd=cost,
    )
