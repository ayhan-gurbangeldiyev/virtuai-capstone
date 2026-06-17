# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""Step 3 sample run — read-only validation of the home composer against
real production data.

Source of truth: projects/post-capstone/home-v1-implementation-plan.md and
projects/post-capstone/product-structure.md.

WHAT THIS SCRIPT DOES:
  - Reads last 7 days of persona_gate_log + daily_drafts(PUBLISHED) for a
    single account from production Supabase.
  - Selects 3 decision_pair candidates (days with ≥1 covered AND ≥1 skipped)
    and 3 closest_call candidates (days with 0 covered AND ≥1 skipped).
  - For each LLM candidate, calls Sonnet 4.6 via OpenRouter, parses the
    JSON, runs the 13-check validator, prints a fully-structured report.
  - Adds 2 deterministic status_only renderings (no LLM call) for
    completeness — total 8 samples.

WHAT THIS SCRIPT DOES NOT DO:
  - Never writes to Supabase. Never inserts, updates, or deletes any row.
  - Never deploys anywhere. Never restarts any service. Local-only.
  - Never caches sentences. Each run recomposes.
  - Never returns sentences to the home-summary endpoint. Step 3 wiring
    into routes/hype.py happens only after the 8-sample review passes.

USAGE:
    cd backend
    venv/bin/python scripts/home_composer_sample_run.py \\
        --account-id 2b731bf7-8c24-40c5-8237-d348ee822d51 \\
        --since-days 7

REQUIRES env:
    SUPABASE_URL, SUPABASE_KEY  (read-only operations only)
    OPENROUTER_API_KEY          (Sonnet 4.6 via OpenRouter)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

# ────────────────────────────────────────────────────────────────────────
# Env loading + clients
# ────────────────────────────────────────────────────────────────────────

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _BACKEND_DIR.parent

# Manual .env reader (avoids new dependencies).
def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)

_load_env(_BACKEND_DIR / ".env")
_load_env(_ROOT_DIR / ".env")

try:
    from supabase import create_client
except ImportError:
    print("FATAL: supabase-py not installed in venv", file=sys.stderr)
    sys.exit(1)
try:
    from openai import OpenAI
except ImportError:
    print("FATAL: openai SDK not installed (used for OpenRouter)", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
if not (SUPABASE_URL and SUPABASE_KEY):
    print("FATAL: SUPABASE_URL + SUPABASE_KEY required", file=sys.stderr)
    sys.exit(1)
if not OPENROUTER_KEY:
    print("FATAL: OPENROUTER_API_KEY required", file=sys.stderr)
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
llm = OpenAI(api_key=OPENROUTER_KEY, base_url="https://openrouter.ai/api/v1")
MODEL = "anthropic/claude-sonnet-4.6"
TEMPERATURE = 0.4
MAX_TOKENS = 350


# ────────────────────────────────────────────────────────────────────────
# Editorial hint translation — internal gate strings → operator-safe Turkish
# ────────────────────────────────────────────────────────────────────────

def translate_gate_reason(matched_reason: Optional[str]) -> str:
    """Convert raw persona_gate_log.matched_reason into operator-language.
    The LLM NEVER sees the raw string. Mapping is static and world-facing
    (does not anthropomorphize Cansu)."""
    if not matched_reason:
        return "Bu konu için net bir yapay zekâ sinyali bulunamadı."
    s = matched_reason.lower()
    if s.startswith("l1 tier_1_brand") or "tier_1_brand=" in s:
        return ("Haber, AI/teknoloji yayınlarında sık takip edilen bir marka "
                "veya konuya referans veriyor.")
    if s.startswith("l3 tier_1_brand_match"):
        return "İçerik birincil markalardan birini doğrudan kapsıyor."
    if "conditional_brand" in s and "required ai keyword" in s and "no required" not in s:
        return "İkincil bir marka açık bir AI sinyaliyle birlikte geçiyor."
    if "conditional_brand" in s and ("no required" in s or "no_ai_signal" in s):
        return "Marka geçiyor ama net bir yapay zekâ sinyali yok."
    if "l4 ambiguous" in s or s.startswith("l4 "):
        return "Haber, mevcut sinyalde net bir yapay zekâ açısı sunmuyor."
    if "blocked_keyword" in s:
        return ("Haber, Cansu'nun kapsamı dışında bir tüketici veya genel ürün "
                "konusu olarak görünüyor.")
    return "Bu konu için net bir yapay zekâ sinyali bulunamadı."


# ────────────────────────────────────────────────────────────────────────
# System prompt — frozen for review
# ────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TR = r"""Sen, Cansu Dut adlı otonom Türkçe içerik editörünün bugünkü editöryel
kararını operatöre anlatan bir yazma yardımcısısın.

GÖREVIN: Sana verilen "covered" (yazılan) ve "skipped" (geçilen) haberlerin
arasındaki editöryel farkı, operatörün her iki haberi açıp BAĞIMSIZ olarak
değerlendirebileceği bir dille yaz.

ÜRÜN İLKESI: Cümlenin geçmesi için operatör, iki haberi okuyup senin
yaptığın ayrımı kendisi değerlendirebilmelidir. Operatörün sadece Cansu'nun
iç sistemini bilirse anlamlı olan bir gerekçe YASAKTIR.

KESİN KURALLAR — bunlardan herhangi birine uymayan çıktı reddedilir:

1. covered.title ve (varsa) skipped.title cümlede HARFİYEN aynen geçer.
   Yeniden ifade etme, kısaltma, çeviri YOK.

2. "Çünkü" cümlesi iki haberin KENDİ özelliklerini karşılaştırır.
   Karşılaştırma her iki tarafı da somut olarak adlandırmalıdır;
   yalnızca covered tarafı için olumlu bir özellik söyleyip skipped
   tarafı için boş bırakmak YASAKTIR.
   KABUL: "X doğrudan yapay zekâ donanımına odaklanıyor; Y mevcut iPhone
           serisine yönelik daha genel bir tüketici güncellemesi olarak
           görünüyor."
   RED:   "Cansu'nun tarzı değil." (kişilik atfı)
   RED:   "Bu haber onun editöryel çizgisine daha uygun." (kendine atıf)
   RED:   "Daha alakalı / daha önemli / daha ilginç." (içerik taşımayan
           karşılaştırma)
   RED:   "X doğrudan AI donanımına odaklanıyor." (yalnızca tek tarafı
           söyleyen eksik karşılaştırma)

3. EVİDANS DİSİPLİNİ — en önemli kural. Yalnızca girdideki title,
   category, source_name, source_summary, editorial_hint ve context
   alanlarında geçen bilgilere dayanarak yaz. Girdide olmayan iddialar
   ekleme. Belirli bir sebep, mekanizma, ürün özelliği veya etki iddia
   etmek için o iddianın kaynağı girdide AÇIK olmalıdır.
   - Girdi güçlü ise net karşılaştırma kullan ("doğrudan", "açıkça").
   - Girdi zayıf ise (evidence_strength="weak") ihtiyatlı dil kullan:
     "mevcut sinyale göre…", "şu anki bilgiyle…", "okuduğu kadarıyla…",
     "daha çok … olarak görünüyor", "net bir yapay zekâ açısı göstermiyor".
   - evidence_strength="weak" iken nesne türüne ya da spesifik sebebe
     dair güçlü iddia KULLANMA. Aşağıdakiler girdide AÇIKÇA geçmiyorsa
     kullanılamaz: "şarj sorunu", "fiyat düzenlemesi", "güvenlik açığı",
     "lansman", "rapor", "değişiklik", "duyuru". Onun yerine "haber",
     "konu", "güncelleme" gibi nötr kelimeler tercih et.
   - Kuvvetli kelimelerden (kesin olarak, tamamen, oyunu değiştiriyor,
     sektörü dönüştürüyor, doğrudan kanıtlıyor) KAÇIN.

3a. İHTİYATLI DOĞRULUK İLKESİ: Vurucu ama desteklenmemiş bir cümle
    yerine her zaman ihtiyatlı ama doğru bir cümle tercih et. Home
    başlığı pazarlama metni DEĞİLDİR; editöryel kanıt yüzeyidir.
    Operatör senin cümleni iki haberi açıp doğrulayacak. Doğrulayamadığı
    bir iddia, daha sonra güveni tamamen yok eder.

4. Cümle 1–3 cümleden oluşur. Hedef 35–50 kelime; 60 kelime kesin üst sınır.

5. decision_pair modunda cümle bir karşıtlık ifadesi içermelidir:
   "çünkü", "ancak", "oysa", "buna karşılık" veya "; ... ise ..."
   yapısı. İki olgu yan yana konulamaz; bir ayrım yapılmalıdır.

6. Cansu'nun "kişiliği", "zevki", "tarzı", "hoşlandığı şeyler" hakkında
   YORUM YAPMA. Cansu bir editördür; karakter değil.

7. Cansu'nun geçmiş yayınlarına atıf yapma — YALNIZCA context içindeki
   cansu_recent_topics alanında somut olarak yer alıyorsa atıf yapabilirsin.

8. closest_call modu (covered yok, yalnızca skipped var):
   - Cümle "Cansu bugün yazmadı." ile başlar.
   - Devamında en yakın aday olan haberin başlığı ve editöryel çubuğu
     neden geçemediğine dair, haberin KENDİ özelliğine atıf yapan bir
     açıklama gelir.
   - "Sessiz kalmayı tercih etti", "yeterince ilginç bulmadı" gibi
     ifadeler kullanma.

9. Asla şu kelimeleri kullanma: Persona Gate, TrendScout, Visual Director,
   Content Strategist, Compliance, Postiz, Wiro, HeyGen, Nano Banana,
   LLM Judge, score, rubric, classifier, embedding, L1, L2, L3, L4.

10. ÇIKTI ALAN ADI YASAĞI: Cevabında girdi yapısının alan adlarını
    (source_summary, source_name, category, editorial_hint,
    evidence_strength, evidence_reason, matched_reason, gate_reason,
    hero_kind, cansu_recent_topics, trend_id, raw_content, payload,
    context, covered, skipped) ASLA referans olarak kullanma. Ne
    "source_summary'de açıklanan", ne "evidence_strength weak olduğu
    için", ne "editorial_hint'e göre" gibi ifadeler.
    Bilgiyi alan adı vermeden, doğrudan içerik üzerinden anlat.

11. KANONİK CÜMLE YAPISI (decision_pair için) — şablon değil, ürün
    sesidir; sapma bir editöryel tercih değil hatadır:

    Cümle TAM OLARAK şu yapıyla başlar:
        Cansu bugün "[covered.title]" hakkında yazdı; "[skipped.title]"
        hakkında yazmadı çünkü [iki haberin somut karşılaştırması].

    YASAK açılışlar: "Cansu, ..." (virgülle), "haberini seçti",
    "tercih etti", "kapsama aldı", "gündeme aldı", "öne çıkardı".

    closest_call için canonical yapı:
        Cansu bugün yazmadı. En yakın aday "[skipped.title]"…
        [haberin somut özelliğine atıf yapan açıklama].

ÇIKTI FORMATI — yalnızca aşağıdaki JSON nesnesi, başka hiçbir metin yok:
{
  "sentence": "tam paragraf (1–3 cümle, hedef 35–50 kelime, en fazla 60)",
  "reason": "iki haberi ayıran SOMUT farkı 3–8 kelimede özetleyen ifade —
             en az bir somut alan ismi içermeli (donanım, fiyat, güvenlik,
             model, API, araştırma, ürün, platform, rekabet, altyapı,
             kullanıcı, geliştirici, regülasyon, veri, performans vb.)"
}

İYİ ÖRNEK (decision_pair, kalibre edilmiş özgüven):
{
  "sentence": "Cansu bugün \"NVIDIA RTX Spark AI workstation\" hakkında yazdı; \"Apple iPhone 17 update\" hakkında yazmadı. NVIDIA'nın duyurusu doğrudan yapay zekâ iş istasyonu donanımına odaklanıyor; Apple'ın güncellemesi ise mevcut iPhone serisine yönelik daha genel bir tüketici ürünü güncellemesi olarak görünüyor.",
  "reason": "AI iş istasyonu donanımı vs tüketici ürünü güncellemesi"
}

İYİ ÖRNEK (closest_call):
{
  "sentence": "Cansu bugün yazmadı. En yakın aday \"Anthropic'in fiyat değişikliği\"ydi; ancak haber, model rekabetini etkileyen yeni bir hamleden çok, mevcut kullanıcı segmentini etkilemeyen rutin bir fiyat düzenlemesi olarak görünüyor.",
  "reason": "rutin fiyat düzenlemesi, stratejik kayma değil"
}

İYİ ÖRNEK (decision_pair, aynı kaynak iki haber):
{
  "sentence": "Cansu bugün \"Meta'nın güvenlik açığı raporu\" hakkında yazdı; \"Meta Reels yeni filtreleri\" hakkında yazmadı. Güvenlik açığı kullanıcıları ve düzenleyicileri ilgilendiren yapısal bir konu olarak görünüyor; Reels filtreleri ürün katmanında kalan kozmetik bir genişleme.",
  "reason": "yapısal güvenlik konusu vs kozmetik ürün genişlemesi"
}

KÖTÜ ÖRNEK (karakter atfı — RED):
{
  "sentence": "Cansu bugün NVIDIA hakkında yazdı çünkü Apple iPhone'u onun tarzı değil.",
  "reason": "Cansu'nun tarzı"
}

KÖTÜ ÖRNEK (boş karşılaştırma — RED):
{
  "sentence": "Cansu bugün \"NVIDIA RTX Spark AI workstation\" hakkında yazdı; \"Apple iPhone 17 update\" daha az alakalıydı.",
  "reason": "daha az alakalı"
}

KÖTÜ ÖRNEK (kendine atıf — RED):
{
  "sentence": "Cansu bugün \"NVIDIA RTX Spark AI workstation\" hakkında yazdı çünkü bu haber onun editöryel çizgisine daha uygun.",
  "reason": "editöryel çizgiye uygun"
}

KÖTÜ ÖRNEK (kanıtsız aşırı iddia — RED):
{
  "sentence": "Cansu bugün \"NVIDIA RTX Spark AI workstation\" hakkında yazdı; \"Apple iPhone 17 update\" hakkında yazmadı. NVIDIA'nın duyurusu yapay zekâ iş istasyonu kapasitelerini tamamen yeniden tanımlıyor ve sektörü değiştiriyor.",
  "reason": "AI sektörünü değiştiren duyuru"
}
"""


# ────────────────────────────────────────────────────────────────────────
# Validator — 13 mechanical checks
# ────────────────────────────────────────────────────────────────────────

BANNED_INTERNAL = [
    # Agent / system names
    "persona gate", "trendscout", "visual director", "content strategist",
    "compliance", "postiz", "wiro", "heygen", "nano banana", "llm judge",
    "score", "rubric", "classifier", "embedding",
    " l1 ", " l2 ", " l3 ", " l4 ",
    # Payload field names — model must paraphrase, never name the schema.
    "source_summary", "source_name", "editorial_hint", "evidence_strength",
    "evidence_reason", "matched_reason", "gate_reason", "hero_kind",
    "cansu_recent_topics", "today_skipped_count", "trend_id",
    "covered.title", "skipped.title", "covered_item", "skipped_item",
    "payload", "raw_content", "category_snapshot", "topic_snapshot",
    "source_snapshot",
]
BANNED_PERSONALITY = [
    "tarzı değil", "tarzında değil", "ilgi alanı dışında", "sevmedi",
    "sevmez", "hoşlanmaz", "hoşlanmadı", "kişiliğine", "zevkine",
    "tarzına", "ona göre değil", "cansu'nun tarzı", "ilginç bulmadı",
    "sessiz kalmayı tercih", "editöryel çizgisine", "editoryal çizgisine",
    "editöryel çizgi",
]
WEAK_REASON_PHRASES = [
    "daha alakalı", "daha az alakalı", "daha önemli", "daha ilginç",
    "daha uygun", "daha güçlü", "daha anlamlı", "daha dikkat çekici",
    "daha iyi", "yeterince alakalı değil", "yeterince önemli değil",
    "cansu için daha uygun",
]
UNSUPPORTED_CERTAINTY = [
    "kesin olarak", "tamamen", "net biçimde", "doğrudan kanıtlıyor",
    "oyunu değiştiriyor", "sektörü değiştiriyor", "sektörü dönüştürüyor",
    "dünyayı değiştiriyor",
]
ALLOWED_DOMAIN_NOUNS = {
    "donanım", "fiyat", "güvenlik", "model", "api", "araştırma", "ürün",
    "platform", "rekabet", "altyapı", "kullanıcı", "geliştirici",
    "regülasyon", "veri", "performans", "lansman", "ortaklık", "ölçek",
    "gizlilik", "uyumluluk", "açık kaynak", "kurumsal", "tüketici",
    "mobil", "bulut", "eğitim", "çıkarım", "ajan", "robot", "kapsam",
    "segment", "hamle", "strateji", "kazanım", "güncelleme", "duyuru",
    "rapor", "değişiklik", "düzenleme",
}
WEAK_EVIDENCE_STRONG_OBJECTS = [
    "duyuru", "rapor", "lansman", "değişiklik", "fiyat düzenlemesi",
]
CONTRAST_MARKERS = ["çünkü", "ancak", "oysa", "buna karşılık", " ise "]

# Common Turkish stopwords excluded from prefix-matching pools — they don't
# carry editorial signal and would create spurious matches against the
# external-referent / both-sides checks.
TURKISH_STOPWORDS = {
    "için", "olan", "olarak", "ile", "veya", "fakat", "ancak", "ama",
    "daha", "çok", "bir", "bu", "şu", "o", "şey", "kendi", "kendisi",
    "ve", "ya", "hem", "ne", "kim", "nasıl", "neden", "niçin", "hangi",
    "her", "tüm", "bütün", "biraz", "birkaç", "az", "hiç", "gibi",
    "kadar", "göre", "üzerine", "üzerinde", "olarak", "değil", "değildir",
    "olup", "olan", "olmaktan", "olan", "olabilir", "olmaz",
}


def _prefix_set(tokens: list[str] | set[str], n: int = 5) -> set[str]:
    """Normalize each token to its first n characters, filtering tokens
    that are too short to be meaningful or are Turkish stopwords. Used by
    checks 10 (external_referent) and 13 (both_sides) to match Turkish
    morphological variants (e.g. 'kesinti' / 'kesintisi' / 'kesintinin')
    without full lemmatization."""
    out: set[str] = set()
    for t in tokens:
        if len(t) < 4:
            continue
        if t in TURKISH_STOPWORDS:
            continue
        out.add(t[:n])
    return out


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zçğıöşü0-9]{2,}", text.lower())


def _contains_any(haystack: str, needles: list[str]) -> Optional[str]:
    h = haystack.lower()
    for n in needles:
        if n.lower() in h:
            return n
    return None


def validate(out: dict, payload: dict) -> list[CheckResult]:
    """Apply 13 checks. Returns the list of check results in order."""
    results: list[CheckResult] = []
    sentence = out.get("sentence", "") if isinstance(out, dict) else ""
    reason = out.get("reason", "") if isinstance(out, dict) else ""
    hero_kind = payload["hero_kind"]
    covered = payload.get("covered")
    skipped = payload["skipped"]
    evidence_strength = payload.get("evidence_strength", "strong")

    # 1. JSON parse — checked upstream by the caller; we only see the parsed dict.
    results.append(CheckResult("json",
        isinstance(out, dict) and isinstance(sentence, str) and isinstance(reason, str)))

    # 2. Verbatim covered title
    if hero_kind == "decision_pair":
        ok = covered is not None and covered["title"] in sentence
        results.append(CheckResult("covered_verbatim", ok,
            detail="" if ok else f"covered.title not substring of sentence"))
    else:
        results.append(CheckResult("covered_verbatim", True, detail="n/a (closest_call)"))

    # 3. Verbatim skipped title
    ok = skipped["title"] in sentence
    results.append(CheckResult("skipped_verbatim", ok,
        detail="" if ok else "skipped.title not substring of sentence"))

    # 4. Length
    words = sentence.split()
    n_words = len(words)
    n_sentences = len(re.findall(r"[.!?](\s|$)", sentence))
    ok = n_words <= 60 and n_sentences <= 3
    results.append(CheckResult("length", ok,
        detail=f"{n_words}w / {n_sentences}s"))

    # 5. Banned internal names
    bad = _contains_any(sentence + " " + reason, BANNED_INTERNAL)
    results.append(CheckResult("no_internal", bad is None,
        detail="" if bad is None else f"hit '{bad}'"))

    # 6. Anti-personality
    bad = _contains_any(sentence + " " + reason, BANNED_PERSONALITY)
    results.append(CheckResult("no_personality", bad is None,
        detail="" if bad is None else f"hit '{bad}'"))

    # 7. Weak-reason (with adjacent-noun heuristic)
    weak_hit = _contains_any(sentence + " " + reason, WEAK_REASON_PHRASES)
    has_noun_nearby = False
    if weak_hit:
        tokens = _tokenize(sentence + " " + reason)
        weak_tokens = set(_tokenize(weak_hit))
        for i, tok in enumerate(tokens):
            if tok in weak_tokens:
                window = tokens[max(0, i-4): i+5]
                if any(t in ALLOWED_DOMAIN_NOUNS for t in window):
                    has_noun_nearby = True
                    break
    ok = weak_hit is None or has_noun_nearby
    results.append(CheckResult("weak_reason", ok,
        detail="" if ok else f"weak phrase '{weak_hit}' with no concrete noun nearby"))

    # 8. Unsupported certainty
    bad = _contains_any(sentence, UNSUPPORTED_CERTAINTY)
    results.append(CheckResult("no_overclaim", bad is None,
        detail="" if bad is None else f"hit '{bad}'"))

    # 9. Reason concreteness
    reason_tokens = set(_tokenize(reason))
    has_concrete = bool(reason_tokens & ALLOWED_DOMAIN_NOUNS)
    if not has_concrete:
        # Allow if reason names a token from either item's category/source
        side_tokens: set[str] = set()
        for side in (covered, skipped):
            if not side:
                continue
            for k in ("category", "source_name"):
                v = side.get(k)
                if v:
                    side_tokens |= set(_tokenize(v))
        has_concrete = bool(reason_tokens & side_tokens)
    results.append(CheckResult("reason_concrete", has_concrete,
        detail="" if has_concrete else "reason has no domain noun nor side-token"))

    # 10. External referent — at least one ≥4-char token in sentence beyond
    # the verbatim title interpolation, drawn from any title/category/
    # source_name/source_summary/cansu_recent_topics field. Uses 5-char
    # prefix matching to tolerate Turkish morphology (e.g. 'kesinti' /
    # 'kesintisi' / 'kesintinin' all share the prefix 'kesin').
    ext_tokens: set[str] = set()
    for side in (covered, skipped):
        if not side:
            continue
        for k in ("category", "source_name", "source_summary"):
            v = side.get(k)
            if v:
                ext_tokens |= set(_tokenize(v))
    for t in payload.get("context", {}).get("cansu_recent_topics", []):
        ext_tokens |= set(_tokenize(t))
    # Subtract verbatim title tokens (those are interpolated and don't count).
    title_tokens: set[str] = set()
    for side in (covered, skipped):
        if side:
            title_tokens |= set(_tokenize(side["title"]))
    ext_tokens -= title_tokens
    ext_prefixes = _prefix_set(ext_tokens)
    sent_prefixes = _prefix_set(_tokenize(sentence)) - _prefix_set(title_tokens)
    overlap = ext_prefixes & sent_prefixes
    results.append(CheckResult("external_referent", bool(overlap),
        detail=f"prefix matches: {sorted(list(overlap))[:5]}" if overlap else "no external prefix match in sentence"))

    # 11. Contrast marker (decision_pair only)
    if hero_kind == "decision_pair":
        ok = any(m in sentence.lower() for m in CONTRAST_MARKERS)
        results.append(CheckResult("contrast_marker", ok,
            detail="" if ok else "no çünkü/ancak/oysa/buna karşılık/; … ise … found"))
    else:
        results.append(CheckResult("contrast_marker", True, detail="n/a (closest_call)"))

    # 12. Weak-evidence object-type caution
    if evidence_strength == "weak":
        # Strong object words allowed ONLY if they appear in title/category/hint.
        allowed_pool = set()
        for side in (covered, skipped):
            if not side:
                continue
            for k in ("title", "category", "editorial_hint"):
                v = side.get(k)
                if v:
                    allowed_pool |= set(_tokenize(v))
        violations = []
        for obj in WEAK_EVIDENCE_STRONG_OBJECTS:
            if obj in sentence.lower():
                obj_tokens = set(_tokenize(obj))
                if not obj_tokens & allowed_pool:
                    violations.append(obj)
        ok = not violations
        results.append(CheckResult("weak_evidence_caution", ok,
            detail="" if ok else f"strong object words without source: {violations}"))
    else:
        results.append(CheckResult("weak_evidence_caution", True, detail="n/a (strong evidence)"))

    # 13. Both-sides comparison (decision_pair only) — uses the same prefix
    # matcher as check 10 so Turkish morphology doesn't trip the check.
    if hero_kind == "decision_pair" and covered is not None:
        def _side_tokens(side: dict) -> set[str]:
            toks: set[str] = set()
            for k in ("category", "source_name", "source_summary", "editorial_hint"):
                v = side.get(k)
                if v:
                    toks |= set(_tokenize(v))
            return toks
        c_prefixes = _prefix_set(_side_tokens(covered) - title_tokens)
        s_prefixes = _prefix_set(_side_tokens(skipped) - title_tokens)
        sent_post_titles = _prefix_set(_tokenize(sentence)) - _prefix_set(title_tokens)
        c_match = bool(c_prefixes & sent_post_titles)
        s_match = bool(s_prefixes & sent_post_titles)
        ok = c_match and s_match
        results.append(CheckResult("both_sides", ok,
            detail=f"covered_side={c_match} skipped_side={s_match}"))
    else:
        results.append(CheckResult("both_sides", True, detail="n/a (closest_call)"))

    return results


def all_passed(results: list[CheckResult]) -> bool:
    return all(r.passed for r in results)


# ────────────────────────────────────────────────────────────────────────
# Data loading
# ────────────────────────────────────────────────────────────────────────

def _today_utc_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

def _format_relative_tr(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        mins = int(delta.total_seconds() / 60)
        if mins < 1: return "az önce"
        if mins < 60: return f"{mins} dakika önce"
        if mins < 60*24: return f"{mins // 60} saat önce"
        return f"{mins // (60*24)} gün önce"
    except Exception:
        return ""


def load_window(account_id: str, since_days: int) -> dict:
    """Pulls last N days of gate log + published drafts for the account.
    Returns dict with both lists. READ ONLY."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    gate = (sb.table("persona_gate_log")
        .select("trend_id, decision, topic_snapshot, category_snapshot, "
                "source_snapshot, matched_reason, created_at, account_id")
        .eq("account_id", account_id)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .execute()).data or []
    drafts = (sb.table("daily_drafts")
        .select("trend_id, trend_topic, platform, release_url, scheduled_at, "
                "postiz_state, account_id")
        .eq("account_id", account_id)
        .eq("postiz_state", "PUBLISHED")
        .gte("scheduled_at", cutoff)
        .order("scheduled_at", desc=True)
        .execute()).data or []
    # Enrich both with trends.url + raw_content (source_summary).
    trend_ids = list({r.get("trend_id") for r in gate + drafts if r.get("trend_id")})
    trends_map: dict = {}
    if trend_ids:
        for i in range(0, len(trend_ids), 100):
            chunk = trend_ids[i: i+100]
            tr = (sb.table("trends")
                .select("id, url, source_name, raw_content")
                .in_("id", chunk).execute()).data or []
            for t in tr:
                trends_map[t["id"]] = t
    return {"gate": gate, "drafts": drafts, "trends": trends_map}


def _day_key(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return ""


def _build_side_payload(row: dict, trends_map: dict, is_covered: bool) -> dict:
    """Build the covered/skipped payload from a gate row + trends enrichment."""
    tid = row.get("trend_id")
    t = trends_map.get(tid) or {}
    raw = (t.get("raw_content") or "").strip()
    summary = (raw[:300] + "…") if len(raw) > 300 else (raw or None)
    payload: dict = {
        "title": (row.get("topic_snapshot") or row.get("trend_topic") or "").strip(),
        "category": (row.get("category_snapshot") or "").strip() or None,
        "source_name": (row.get("source_snapshot") or t.get("source_name") or "").strip() or None,
        "source_summary": summary,
        "editorial_hint": translate_gate_reason(row.get("matched_reason")),
        "trend_id": tid,
    }
    if is_covered:
        payload["platform"] = row.get("platform")
    return payload


def select_samples(window: dict, n_dp: int = 3, n_cc: int = 3) -> dict:
    """Pick decision_pair and closest_call candidates from the window.
    Groups by UTC day; ranks days by recency."""
    gate_by_day: dict[str, list[dict]] = {}
    drafts_by_day: dict[str, list[dict]] = {}
    for r in window["gate"]:
        gate_by_day.setdefault(_day_key(r.get("created_at") or ""), []).append(r)
    for r in window["drafts"]:
        drafts_by_day.setdefault(_day_key(r.get("scheduled_at") or ""), []).append(r)

    dp: list[tuple[dict, dict]] = []
    cc: list[dict] = []
    # Iterate most recent days first
    for day in sorted(set(gate_by_day) | set(drafts_by_day), reverse=True):
        gates = gate_by_day.get(day, [])
        # Build covered (one per published trend; dedup by trend_id)
        seen: set = set()
        covered_today: list[dict] = []
        for d in drafts_by_day.get(day, []):
            tid = d.get("trend_id")
            if tid and tid in seen:
                continue
            if tid:
                seen.add(tid)
            # Look up the gate-accept row for this trend, if it exists
            accept_row = next(
                (g for g in gates if g.get("trend_id") == tid and g.get("decision") == "accept"),
                None)
            covered_today.append(_build_side_payload(
                {**(accept_row or {}), "trend_topic": d.get("trend_topic"),
                 "platform": d.get("platform")},
                window["trends"], is_covered=True))
        skipped_today = [
            _build_side_payload(g, window["trends"], is_covered=False)
            for g in gates if g.get("decision") == "reject"]
        if covered_today and skipped_today and len(dp) < n_dp:
            # Pick the same-category pair if possible, else fall back
            best = None; best_score = -1
            for c in covered_today:
                for s in skipped_today:
                    score = 1
                    if c.get("category") and c["category"] == s.get("category"):
                        score += 3
                    if score > best_score:
                        best_score = score; best = (c, s)
            if best:
                dp.append(best)
        elif skipped_today and not covered_today and len(cc) < n_cc:
            cc.append(skipped_today[0])
        if len(dp) >= n_dp and len(cc) >= n_cc:
            break

    return {"decision_pair": dp, "closest_call": cc}


# ────────────────────────────────────────────────────────────────────────
# LLM call
# ────────────────────────────────────────────────────────────────────────

SUMMARY_MIN_LEN = 140
TRUNCATION_MARKERS = ("…", "...", "..…")


def _side_evidence(side: Optional[dict]) -> str:
    """Classify one side's evidence quality. Used to derive overall strength
    and to surface evidence_reason in the report.

    Returns one of:
      summary_present   — non-null, ≥140 chars, no truncation marker
      summary_truncated — ends with … / ...
      summary_short     — non-null but < 140 chars
      summary_missing   — null / empty
    """
    if side is None:
        return "summary_missing"
    s = (side.get("source_summary") or "").strip()
    if not s:
        return "summary_missing"
    if s.endswith(TRUNCATION_MARKERS):
        return "summary_truncated"
    if len(s) < SUMMARY_MIN_LEN:
        return "summary_short"
    return "summary_present"


def _evidence_strength(payload: dict) -> tuple[str, list[str]]:
    """Returns (strength, per-side reasons). Strength = 'strong' only when
    EVERY non-null side has 'summary_present'. Any other condition (missing,
    truncated, short) downgrades to 'weak' — this is the Sample-2 lesson:
    a non-null but truncated summary is functionally weak evidence and lets
    the composer invent specific causes."""
    reasons: list[str] = []
    sides = [payload.get("covered"), payload.get("skipped")]
    for side in sides:
        if side is None:  # null covered is normal for closest_call; skip
            continue
        reasons.append(_side_evidence(side))
    strength = "strong" if all(r == "summary_present" for r in reasons) else "weak"
    return strength, reasons


def call_composer(payload: dict) -> tuple[Optional[dict], str]:
    """Single Sonnet call. Returns (parsed_json_or_None, raw_text)."""
    user_msg = json.dumps(payload, ensure_ascii=False, indent=2)
    resp = llm.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_TR},
            {"role": "user", "content": user_msg},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    # Strip ``` fences if present.
    raw = text
    if text.startswith("```"):
        # remove first fence line
        text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = "\n".join(text.split("\n")[:-1])
        text = text.strip()
    try:
        return json.loads(text), raw
    except Exception:
        return None, raw


# ────────────────────────────────────────────────────────────────────────
# Reporting
# ────────────────────────────────────────────────────────────────────────

def _print_side(label: str, side: Optional[dict]) -> None:
    if side is None:
        print(f"  {label}: (null)")
        return
    print(f"  {label}:")
    print(f"    title:           {side['title']!r}")
    print(f"    category:        {side.get('category')!r}")
    print(f"    source_name:     {side.get('source_name')!r}")
    src = side.get("source_summary")
    if src:
        print(f"    source_summary:  ({len(src)} chars) {src!r}")
    else:
        print(f"    source_summary:  None")
    print(f"    editorial_hint:  {side.get('editorial_hint')!r}")
    print(f"    trend_id:        {side.get('trend_id')}")
    if "platform" in side:
        print(f"    platform:        {side.get('platform')!r}")


def print_sample(idx: int, kind: str, payload: Optional[dict],
                 out: Optional[dict], raw: str,
                 results: list[CheckResult]) -> None:
    print("─" * 70)
    print(f"Sample {idx} — {kind}")
    print("─" * 70)
    if payload is not None:
        _print_side("covered", payload.get("covered"))
        _print_side("skipped", payload.get("skipped"))
        ctx = payload.get("context", {})
        print(f"  context:")
        print(f"    cansu_recent_topics: {ctx.get('cansu_recent_topics', [])}")
        print(f"    today_skipped_count: {ctx.get('today_skipped_count', 0)}")
        print(f"    evidence_strength:   {payload.get('evidence_strength')!r}")
        print(f"    evidence_reason:     {payload.get('evidence_reason')!r}")
    if out is None and payload is not None:
        print(f"  generated:")
        print(f"    PARSE FAIL — raw output below")
        print(f"    raw: {raw[:300]}")
    elif payload is not None:
        sent = out.get("sentence", "")
        print(f"  generated:")
        print(f"    sentence: {sent!r}")
        print(f"    reason:   {out.get('reason')!r}")
        print(f"    word_count: {len(sent.split())}")
        print(f"    model: {MODEL}  temp: {TEMPERATURE}")
    if results:
        print(f"  validation:")
        for r in results:
            tag = "PASS" if r.passed else "FAIL"
            print(f"    check {r.name:24s}: {tag}  {r.detail}")
        print(f"    retry_used: no")
        print(f"    fallback_used: no")
    print(f"  PM judgment:  [ filled in chat report ]")
    print(f"  Notes:        [ filled in chat report ]")
    print(f"  skeptical-reader test: [ filled in chat report ]")
    print()


def print_status_only(idx: int, reason: str) -> None:
    sentences = {
        "no_decisions": "Cansu bugün için henüz bir değerlendirme yapmadı.",
        "scaffold":     "Cansu bugünün haberlerini hâlâ inceliyor.",
        "cold_install": "Cansu henüz haber değerlendirmeye başlamadı.",
        "system_dark":  "Sistem son bir saattir kendini kontrol etmedi.",
    }
    print("─" * 70)
    print(f"Sample {idx} — status_only ({reason})")
    print("─" * 70)
    print(f"  generated (deterministic, no LLM call):")
    print(f"    sentence: {sentences[reason]!r}")
    print(f"  validation: skipped (deterministic fallback)")
    print(f"  PM judgment:  [ filled in chat report ]")
    print()


# ────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-id", required=True)
    ap.add_argument("--since-days", type=int, default=7)
    args = ap.parse_args()

    print(f"# Step 3 sample run — account={args.account_id} window={args.since_days}d")
    print(f"# model={MODEL} temp={TEMPERATURE} max_tokens={MAX_TOKENS}")
    print()

    window = load_window(args.account_id, args.since_days)
    print(f"# window: gate_rows={len(window['gate'])} "
          f"drafts_rows={len(window['drafts'])} "
          f"trends_enriched={len(window['trends'])}")
    print()

    picked = select_samples(window, n_dp=3, n_cc=3)
    print(f"# selected: decision_pair={len(picked['decision_pair'])} "
          f"closest_call={len(picked['closest_call'])}")
    print()

    idx = 0
    # 3 decision_pair samples
    for c, s in picked["decision_pair"]:
        idx += 1
        payload = {
            "hero_kind": "decision_pair",
            "covered": c, "skipped": s,
            "context": {"cansu_recent_topics": [], "today_skipped_count": 0},
        }
        strength, reasons = _evidence_strength(payload)
        payload["evidence_strength"] = strength
        payload["evidence_reason"] = reasons
        out, raw = call_composer(payload)
        results = validate(out or {}, payload) if out is not None else []
        print_sample(idx, "decision_pair", payload, out, raw, results)

    # 3 closest_call samples
    for s in picked["closest_call"]:
        idx += 1
        payload = {
            "hero_kind": "closest_call",
            "covered": None, "skipped": s,
            "context": {"cansu_recent_topics": [], "today_skipped_count": 0},
        }
        strength, reasons = _evidence_strength(payload)
        payload["evidence_strength"] = strength
        payload["evidence_reason"] = reasons
        out, raw = call_composer(payload)
        results = validate(out or {}, payload) if out is not None else []
        print_sample(idx, "closest_call", payload, out, raw, results)

    # 2 deterministic status_only samples
    idx += 1; print_status_only(idx, "no_decisions")
    idx += 1; print_status_only(idx, "system_dark")

    print("# END")
    return 0


if __name__ == "__main__":
    sys.exit(main())
