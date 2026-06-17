"""Home v1 hero composer — Sonnet 4.6 prose generation for decision_pair
and closest_call hero kinds.

Source of truth: projects/post-capstone/product-structure.md and
projects/post-capstone/home-v1-implementation-plan.md.

INVOCATION:
    from services.home_composer import compose_hero, build_payload

    payload = build_payload(hero_kind, covered, skipped, recent_topics)
    sentence, reason, used_fallback = compose_hero(payload)

WIRING:
    routes/hype.py:get_home_summary calls this module when
    HOME_COMPOSER_ENABLED=true. Falls back to deterministic Step 2
    templates when the flag is off, when the LLM call fails twice, or
    when the API is unreachable.

CACHE:
    In-memory TTL cache (10 min default) keyed on:
      decision_pair: {account_id}:decision_pair:{covered_tid}:{skipped_tid}
      closest_call:  {account_id}:closest_call:{skipped_tid}
    Process-local; deploy/restart busts the cache; multiple workers may
    compose slightly different sentences. v1 acceptable per locked product
    principle (cache is stability/cost protection, not source of truth).

RUNTIME GUARANTEES:
    - Never raises. Any unexpected error path falls back to (None, None, True).
    - Never writes to Supabase. Never calls Postiz. Only OpenRouter outbound.
    - Never imports from routes.*; safe to call from any route handler.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────

MODEL = "anthropic/claude-sonnet-4.6"
TEMPERATURE = 0.4
MAX_TOKENS = 350
CACHE_TTL_SECONDS = 600  # 10 minutes per locked v1 spec
SUMMARY_MIN_LEN = 140
TRUNCATION_MARKERS = ("…", "...", "..…")


def is_enabled() -> bool:
    """Feature flag — HOME_COMPOSER_ENABLED env. Defaults to false so
    Step 3 stays opt-in and the deterministic Step 2 template renders
    until you explicitly enable composition."""
    return os.environ.get("HOME_COMPOSER_ENABLED", "false").lower() in (
        "1", "true", "yes"
    )


# ────────────────────────────────────────────────────────────────────────
# Editorial-hint translation (gate_log internal → operator-safe Turkish)
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
# System prompt — frozen; matches the sample-run script verbatim
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
    Örneğin "source_summary'de açıklanan mekanizma" yerine "mevcut
    bilgilere göre …" veya "habere göre …" yaz.

11a. KAYITLI GEREKÇE KURALI (Phase 2): Eğer girdide `recorded_reason`
    alanı doluysa, çıktının "çünkü …" cümlesi YALNIZCA bu gerekçeyi
    paraphrase ederek aktarabilir. Yeni bir editöryel argüman, yeni bir
    karşılaştırma boyutu veya recorded_reason'da olmayan bir iddia
    EKLEYEMEZ. Recorded_reason'da geçen sayısal değerler (örn. "son 7
    günde 5 kez işlenmişti") aynen aktarılmalıdır. Eğer recorded_reason
    boşsa, "çünkü …" cümlesi yazılmaz; sadece iki başlık verilir.

11. KANONİK CÜMLE YAPISI (decision_pair için) — şablon değil, ürün
    sesidir; sapma bir editöryel tercih değil hatadır:

    Cümle TAM OLARAK şu yapıyla başlar:

        Cansu bugün "[covered.title]" hakkında yazdı; "[skipped.title]"
        hakkında yazmadı çünkü [iki haberin somut karşılaştırması].

    Veya çok benzer alternatif:

        Cansu bugün "[covered.title]" hakkında yazdı; "[skipped.title]"
        hakkında yazmadı. [İki haberin somut karşılaştırması].

    YASAK açılışlar (bunları KULLANMA):
    - "Cansu, ..." (virgülle başlayan açılış)
    - "haberini seçti"
    - "tercih etti"
    - "kapsama aldı / gündeme aldı / öne çıkardı"

    closest_call için canonical yapı:

        Cansu bugün yazmadı. En yakın aday "[skipped.title]"…
        [haberin somut özelliğine atıf yapan açıklama].

ÇIKTI FORMATI — yalnızca aşağıdaki JSON nesnesi, başka hiçbir metin yok:
{
  "sentence": "tam paragraf (1–3 cümle, hedef 35–50 kelime, en fazla 60).
              decision_pair'da kural 11'deki kanonik açılışla başlar.",
  "reason": "iki haberi ayıran SOMUT farkı 3–8 kelimede özetleyen ifade.
             ZORUNLU: aşağıdaki listedeki en az BİR somut alan ismini
             içermek zorundadır. İçermezse cevabın reddedilir.

             İzin verilen alan isimleri:
               donanım, fiyat, güvenlik, model, API, araştırma, ürün,
               platform, rekabet, altyapı, kullanıcı, geliştirici,
               regülasyon, veri, performans, lansman, ortaklık, ölçek,
               gizlilik, uyumluluk, açık kaynak, kurumsal, tüketici,
               mobil, bulut, eğitim, çıkarım, ajan, robot, kapsam,
               segment, hamle, strateji, kazanım, güncelleme, duyuru,
               rapor, değişiklik, düzenleme.

             İYİ reason örnekleri (alan ismi belirgin):
               - 'AI donanım kapasitesi vs tüketici güncellemesi'
               - 'yapısal güvenlik konusu vs kozmetik ürün genişlemesi'
               - 'rutin fiyat düzenlemesi, stratejik kayma değil'
               - 'yeni model mimarisi vs şirket içi düzenleme'

             KÖTÜ reason örnekleri (somut isim yok — REDDEDİLİR):
               - 'daha alakalı'
               - 'AI bağlantısı'
               - 'farklı odak'
               - 'editöryel öncelik'"
}

İYİ ÖRNEK 4 (decision_pair, model vs şirket haberi):
{
  "sentence": "Cansu bugün \"Google Gemini 3.0 modeli duyuruldu\" hakkında yazdı; \"OpenAI iş güncellemesi\" hakkında yazmadı çünkü Gemini 3.0 yeni bir model mimarisi ve API erişimi getirirken, OpenAI haberi şirket içi düzenlemeleri konu alıyor.",
  "reason": "yeni model mimarisi ve API vs şirket içi düzenleme"
}

İYİ ÖRNEK 5 (closest_call, gizlilik raporu):
{
  "sentence": "Cansu bugün yazmadı. En yakın aday \"Anthropic gizlilik raporu yayımlandı\" haberiydi; ancak rapor mevcut gizlilik politikalarının özetini sunuyor, kullanıcı verisini etkileyen somut bir değişiklik içermiyor.",
  "reason": "gizlilik politika özeti, kullanıcı verisi değişikliği değil"
}

İYİ ÖRNEK 6 (decision_pair, kanonik açılış + concrete reason):
{
  "sentence": "Cansu bugün \"AWS Bedrock'a yeni model ortaklığı eklendi\" hakkında yazdı; \"Microsoft kurumsal eğitim güncellemesi\" hakkında yazmadı çünkü Bedrock ortaklığı bulut altyapısında yeni bir geliştirici erişim noktası yaratıyor, oysa Microsoft duyurusu mevcut kurumsal eğitim programının bir genişlemesi.",
  "reason": "bulut altyapısında yeni geliştirici erişimi vs kurumsal eğitim genişlemesi"
}
"""

STRICT_ADDENDUM = """
Önceki cevabın doğrulamayı geçemedi. Lütfen iki haberin SOMUT
özelliklerini karşılaştır. Cansu'nun karakterine DEĞİL, haberlerin kendi
özelliklerine atıf yap. Şablon değil, editöryel argüman yaz.
Girdide olmayan iddialar ekleme.
"""


# ────────────────────────────────────────────────────────────────────────
# Evidence classifier
# ────────────────────────────────────────────────────────────────────────

def side_evidence(side: Optional[dict]) -> str:
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


def evidence_strength(payload: dict) -> tuple[str, list[str]]:
    """Strong only when every non-null side is summary_present."""
    reasons: list[str] = []
    for side in (payload.get("covered"), payload.get("skipped")):
        if side is None:
            continue
        reasons.append(side_evidence(side))
    strength = "strong" if all(r == "summary_present" for r in reasons) else "weak"
    return strength, reasons


# ────────────────────────────────────────────────────────────────────────
# Validator (13 checks; identical to the sample-run script)
# ────────────────────────────────────────────────────────────────────────

BANNED_INTERNAL = [
    # Agent / system names
    "persona gate", "trendscout", "visual director", "content strategist",
    "compliance", "postiz", "wiro", "heygen", "nano banana", "llm judge",
    "score", "rubric", "classifier", "embedding",
    " l1 ", " l2 ", " l3 ", " l4 ",
    # Payload field names — model must paraphrase, never name the schema.
    # Detected during smoke test: "source_summary'de açıklanan" leaked.
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
TURKISH_STOPWORDS = {
    "için", "olan", "olarak", "ile", "veya", "fakat", "ancak", "ama",
    "daha", "çok", "bir", "bu", "şu", "şey", "kendi", "kendisi",
    "ve", "ya", "hem", "ne", "kim", "nasıl", "neden", "niçin", "hangi",
    "her", "tüm", "bütün", "biraz", "birkaç", "az", "hiç", "gibi",
    "kadar", "göre", "üzerine", "üzerinde", "değil", "değildir",
    "olup", "olmaktan", "olabilir", "olmaz",
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zçğıöşü0-9]{2,}", text.lower())


def _prefix_set(tokens, n: int = 5) -> set[str]:
    out: set[str] = set()
    for t in tokens:
        if len(t) < 4 or t in TURKISH_STOPWORDS:
            continue
        out.add(t[:n])
    return out


def _contains_any(hay: str, needles: list[str]) -> Optional[str]:
    h = hay.lower()
    for n in needles:
        if n.lower() in h:
            return n
    return None


def validate(out: dict, payload: dict) -> list[CheckResult]:
    """Apply 13 checks. Same logic as the sample-run script."""
    results: list[CheckResult] = []
    sentence = out.get("sentence", "") if isinstance(out, dict) else ""
    reason = out.get("reason", "") if isinstance(out, dict) else ""
    hero_kind = payload["hero_kind"]
    covered = payload.get("covered")
    skipped = payload["skipped"]
    evd = payload.get("evidence_strength", "strong")

    results.append(CheckResult("json",
        isinstance(out, dict) and isinstance(sentence, str) and isinstance(reason, str)))

    if hero_kind == "decision_pair":
        ok = covered is not None and covered["title"] in sentence
        results.append(CheckResult("covered_verbatim", ok))
    else:
        results.append(CheckResult("covered_verbatim", True, "n/a"))

    results.append(CheckResult("skipped_verbatim", skipped["title"] in sentence))

    n_words = len(sentence.split())
    n_sent = len(re.findall(r"[.!?](\s|$)", sentence))
    results.append(CheckResult("length", n_words <= 60 and n_sent <= 3,
                               f"{n_words}w/{n_sent}s"))

    bad = _contains_any(sentence + " " + reason, BANNED_INTERNAL)
    results.append(CheckResult("no_internal", bad is None,
                               "" if bad is None else f"hit '{bad}'"))
    bad = _contains_any(sentence + " " + reason, BANNED_PERSONALITY)
    results.append(CheckResult("no_personality", bad is None,
                               "" if bad is None else f"hit '{bad}'"))

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
    results.append(CheckResult("weak_reason", weak_hit is None or has_noun_nearby))

    bad = _contains_any(sentence, UNSUPPORTED_CERTAINTY)
    results.append(CheckResult("no_overclaim", bad is None,
                               "" if bad is None else f"hit '{bad}'"))

    reason_tokens = set(_tokenize(reason))
    has_concrete = bool(reason_tokens & ALLOWED_DOMAIN_NOUNS)
    if not has_concrete:
        side_tokens: set[str] = set()
        for side in (covered, skipped):
            if not side: continue
            for k in ("category", "source_name"):
                v = side.get(k)
                if v: side_tokens |= set(_tokenize(v))
        has_concrete = bool(reason_tokens & side_tokens)
    results.append(CheckResult("reason_concrete", has_concrete))

    ext_tokens: set[str] = set()
    title_tokens: set[str] = set()
    for side in (covered, skipped):
        if not side: continue
        for k in ("category", "source_name", "source_summary"):
            v = side.get(k)
            if v: ext_tokens |= set(_tokenize(v))
        title_tokens |= set(_tokenize(side["title"]))
    for t in payload.get("context", {}).get("cansu_recent_topics", []):
        ext_tokens |= set(_tokenize(t))
    ext_tokens -= title_tokens
    ext_pref = _prefix_set(ext_tokens)
    sent_pref = _prefix_set(_tokenize(sentence)) - _prefix_set(title_tokens)
    overlap = ext_pref & sent_pref
    results.append(CheckResult("external_referent", bool(overlap),
                               f"matched: {sorted(list(overlap))[:5]}"))

    if hero_kind == "decision_pair":
        ok = any(m in sentence.lower() for m in CONTRAST_MARKERS)
        results.append(CheckResult("contrast_marker", ok))
    else:
        results.append(CheckResult("contrast_marker", True, "n/a"))

    if evd == "weak":
        allowed_pool: set[str] = set()
        for side in (covered, skipped):
            if not side: continue
            for k in ("title", "category", "editorial_hint"):
                v = side.get(k)
                if v: allowed_pool |= set(_tokenize(v))
        violations = []
        for obj in WEAK_EVIDENCE_STRONG_OBJECTS:
            if obj in sentence.lower():
                if not set(_tokenize(obj)) & allowed_pool:
                    violations.append(obj)
        results.append(CheckResult("weak_evidence_caution", not violations,
                                   f"violations={violations}" if violations else ""))
    else:
        results.append(CheckResult("weak_evidence_caution", True, "n/a"))

    if hero_kind == "decision_pair" and covered is not None:
        def _stoks(side: dict) -> set[str]:
            toks: set[str] = set()
            for k in ("category", "source_name", "source_summary", "editorial_hint"):
                v = side.get(k)
                if v: toks |= set(_tokenize(v))
            return toks
        c_pref = _prefix_set(_stoks(covered) - title_tokens)
        s_pref = _prefix_set(_stoks(skipped) - title_tokens)
        sp = _prefix_set(_tokenize(sentence)) - _prefix_set(title_tokens)
        c_m = bool(c_pref & sp); s_m = bool(s_pref & sp)
        results.append(CheckResult("both_sides", c_m and s_m,
                                   f"covered={c_m} skipped={s_m}"))
    else:
        results.append(CheckResult("both_sides", True, "n/a"))

    return results


def all_passed(results: list[CheckResult]) -> bool:
    return all(r.passed for r in results)


# ────────────────────────────────────────────────────────────────────────
# OpenRouter / Sonnet wrapper
# ────────────────────────────────────────────────────────────────────────

_llm_client = None


def _get_llm():
    global _llm_client
    if _llm_client is None:
        try:
            from openai import OpenAI
        except ImportError:
            return None
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            return None
        _llm_client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
    return _llm_client


def _call_sonnet(payload: dict, addendum: str = "") -> Optional[dict]:
    """One LLM call. Returns parsed JSON dict or None on any failure."""
    client = _get_llm()
    if client is None:
        return None
    system = SYSTEM_PROMPT_TR + (addendum or "")
    try:
        resp = client.chat.completions.create(
            model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])
            text = text.strip()
        return json.loads(text)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[home-composer] LLM call failed: {type(e).__name__}: {str(e)[:160]}")
        return None


# ────────────────────────────────────────────────────────────────────────
# In-memory TTL cache
# ────────────────────────────────────────────────────────────────────────

_CACHE: dict[str, tuple[float, dict]] = {}


def _cache_key(account_id: str, payload: dict) -> str:
    kind = payload["hero_kind"]
    skipped_tid = (payload["skipped"] or {}).get("trend_id") or "no_skipped_tid"
    if kind == "decision_pair":
        covered_tid = (payload.get("covered") or {}).get("trend_id") or "no_covered_tid"
        return f"{account_id}:decision_pair:{covered_tid}:{skipped_tid}"
    return f"{account_id}:closest_call:{skipped_tid}"


def _cache_get(key: str) -> Optional[dict]:
    hit = _CACHE.get(key)
    if hit is None: return None
    expires_at, value = hit
    if time.time() > expires_at:
        _CACHE.pop(key, None); return None
    return value


def _cache_put(key: str, value: dict) -> None:
    _CACHE[key] = (time.time() + CACHE_TTL_SECONDS, value)


# ────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────

def build_payload(
    hero_kind: str,
    covered: Optional[dict],
    skipped: dict,
    cansu_recent_topics: Optional[list[str]] = None,
    recorded_reason: Optional[str] = None,
) -> dict:
    """Construct the payload the composer accepts. Caller is responsible
    for ensuring covered/skipped dicts contain title/category/source_name/
    source_summary/editorial_hint/trend_id keys (build_side_from_row
    helper below covers the common case).

    Phase 2 — `recorded_reason` (when provided) is the verbatim recorded
    differentiator from the within-beat selection_delta. When present, the
    composer is constrained to paraphrase it and may NOT invent a new
    comparative claim. When absent, the composer falls back to a neutral
    'no recorded reason' sentence (no editorial invention)."""
    payload: dict = {
        "hero_kind": hero_kind,
        "covered": covered,
        "skipped": skipped,
        "recorded_reason": recorded_reason,
        "context": {
            "cansu_recent_topics": cansu_recent_topics or [],
            "today_skipped_count": 0,
        },
    }
    strength, reasons = evidence_strength(payload)
    payload["evidence_strength"] = strength
    payload["evidence_reason"] = reasons
    return payload


def build_side_from_row(
    *,
    title: str,
    category: Optional[str],
    source_name: Optional[str],
    source_summary: Optional[str],
    matched_reason: Optional[str],
    trend_id: Optional[str],
    platform: Optional[str] = None,
) -> dict:
    """Shape a covered/skipped dict from raw row fields. Translates the
    internal matched_reason into operator-safe editorial_hint."""
    side: dict = {
        "title": (title or "").strip(),
        "category": (category or "").strip() or None,
        "source_name": (source_name or "").strip() or None,
        "source_summary": (source_summary or "").strip() or None,
        "editorial_hint": translate_gate_reason(matched_reason),
        "trend_id": trend_id,
    }
    if platform:
        side["platform"] = platform
    return side


@dataclass
class ComposeResult:
    sentence: Optional[str]
    reason: Optional[str]
    cache_hit: bool
    used_fallback: bool
    retry_used: bool
    validation: list[CheckResult]
    evidence_strength: str
    evidence_reason: list[str]


def compose_hero(account_id: str, payload: dict) -> ComposeResult:
    """One composer call with up-to-one retry on validation failure.
    On second failure (or any unexpected error), used_fallback=True and
    the caller should render the Step-2 deterministic template.

    Cache: hits return immediately without an LLM call. Misses populate
    on validated PASS only (failed-then-fallback results are NOT cached
    — we'd rather retry next pageview than serve a stale fallback)."""
    key = _cache_key(account_id, payload)
    cached = _cache_get(key)
    if cached is not None:
        return ComposeResult(
            sentence=cached["sentence"], reason=cached["reason"],
            cache_hit=True, used_fallback=False, retry_used=False,
            validation=[], evidence_strength=payload["evidence_strength"],
            evidence_reason=payload["evidence_reason"],
        )

    # First attempt
    out = _call_sonnet(payload)
    if out is not None:
        v1 = validate(out, payload)
        if all_passed(v1):
            _cache_put(key, {"sentence": out["sentence"], "reason": out["reason"]})
            return ComposeResult(
                sentence=out["sentence"], reason=out["reason"],
                cache_hit=False, used_fallback=False, retry_used=False,
                validation=v1, evidence_strength=payload["evidence_strength"],
                evidence_reason=payload["evidence_reason"],
            )
        first_results = v1
    else:
        first_results = []

    # Retry with strict addendum
    out2 = _call_sonnet(payload, addendum="\n" + STRICT_ADDENDUM)
    if out2 is not None:
        v2 = validate(out2, payload)
        if all_passed(v2):
            _cache_put(key, {"sentence": out2["sentence"], "reason": out2["reason"]})
            return ComposeResult(
                sentence=out2["sentence"], reason=out2["reason"],
                cache_hit=False, used_fallback=False, retry_used=True,
                validation=v2, evidence_strength=payload["evidence_strength"],
                evidence_reason=payload["evidence_reason"],
            )
        second_results = v2
    else:
        second_results = []

    # Both attempts failed — fall through to deterministic template
    logger.warning(
        f"[home-composer] fallback for key={key} "
        f"first_failed={[r.name for r in first_results if not r.passed]} "
        f"second_failed={[r.name for r in second_results if not r.passed]}"
    )
    try:
        from tools.alerter import send_alert
        send_alert(
            title="Home composer fell back to template",
            severity="WARN",
            reason=f"key={key} both attempts failed validation or API",
            action="Inspect the input payload and tune prompt/validation if pattern repeats.",
        )
    except Exception:  # noqa: BLE001
        pass

    return ComposeResult(
        sentence=None, reason=None,
        cache_hit=False, used_fallback=True, retry_used=True,
        validation=second_results or first_results,
        evidence_strength=payload["evidence_strength"],
        evidence_reason=payload["evidence_reason"],
    )


def cache_stats() -> dict:
    """Diagnostic — process-local cache size + TTL window."""
    now = time.time()
    live = sum(1 for _, (exp, _) in _CACHE.items() if exp > now)
    return {"entries_total": len(_CACHE), "entries_live": live,
            "ttl_seconds": CACHE_TTL_SECONDS}


def clear_cache() -> None:
    """For tests + smoke runs."""
    _CACHE.clear()
