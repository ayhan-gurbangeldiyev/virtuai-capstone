"""Story-level dedup — aynı HİKÂYEnin farklı tweet'lerini tek trende birleştir.

2026-06-10 (A yaması, Berkay'ın n8n parite kararı). Bağlam: eski n8n
workflow'u RSS resmi blog okuyordu → hikâye başına TEK kanonik URL vardı ve
URL dedup'ı hikâye dedup'ı gibi davranıyordu. Şimdiki girdi X firehose'u:
aynı lansman 5-10 tweet = 5-10 URL = (eski davranışta) 5-10 ayrı "trend" →
duplicate run'lar, çoklu yazar+görsel+video maliyeti (Claude Fable 5 vakası:
aynı haber için 3 ayrı run).

Mekanizma — iki kademe, ucuz olan önce:
  1. Deterministik şüphe: konu+içerik token imzaları (diacritic fold,
     stopword filtreli) son 72h trendleriyle karşılaştırılır. Güçlü örtüşme
     yoksa hiç LLM çağrılmaz (vakaların büyük çoğunluğu).
  2. Şüphede gpt-4o-mini hakem: "bu ikisi aynı haber mi?" (binde-bir dolar,
     temperature=0). Hakem hatasında GÜVENLİ taraf: birleştirme YAPMA
     (yanlış merge, kaçan duplicate'ten daha kötü — farklı haberi yutar).

Eşleşme bulunursa çağıran (trend_engine) yeni satır AÇMAZ; tweet'i mevcut
trende source_tweets olarak ekler. hype_crew o trendi zaten işlediyse
trend-id dedup'ı yeni tweet'in re-post tetiklemesini de engeller.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

# Türkçe + İngilizce, haber başlıklarında imza değeri taşımayan kelimeler.
_STOPWORDS = {
    # tr
    "ve", "ile", "için", "yeni", "bir", "bu", "da", "de", "mi", "daha",
    "olan", "olarak", "sonra", "önce", "gibi", "kadar", "çok", "en",
    "duyurdu", "duyuruldu", "tanıttı", "tanıtıldı", "açıkladı", "geldi",
    "geliyor", "başlıyor", "başladı", "yayınladı", "yayınlandı", "oldu",
    "piyasada", "özellikleri", "özelliği", "güncelledi", "güncellendi",
    # en
    "the", "and", "for", "with", "new", "its", "has", "are", "was",
    "announced", "announces", "launches", "launched", "released",
    "releases", "introduces", "introducing", "update", "updated",
    "now", "today", "out",
}
# NOT: marka adları (anthropic/claude/openai…) BİLEREK stopword DEĞİL — bunlar
# story-merge'in imzasıdır ("claude"+"fable" çifti aynı lansmanı yakalar). Aynı
# şirketin farklı haberlerinin yanlış kaynak/duplicate sayılmasını engelleyen şey
# stopword değil, EŞİK: tek ortak token asla yetmez (related-tweet'te ≥4 içerik
# token'ı + jaccard≥0.2; merge'de ≥2 konu token'ı + jaccard≥0.3).

_WORD_RE = re.compile(r"[a-z0-9çğıöşü]+")


def _fold(text: str) -> str:
    text = (text or "").lower()
    # Türkçe karakterler korunur, diğer aksanlar düzleştirilir
    return unicodedata.normalize("NFC", text)


def story_tokens(text: str, *, max_chars: int = 400) -> set[str]:
    """Konu/içerikten imza token seti. Kısa ve stopword tokenlar elenir."""
    toks = set(_WORD_RE.findall(_fold(text[:max_chars])))
    return {t for t in toks if len(t) >= 3 and t not in _STOPWORDS}


def deterministic_overlap(sig_a: set[str], sig_b: set[str]) -> tuple[int, float]:
    """(ortak token sayısı, jaccard) döner."""
    if not sig_a or not sig_b:
        return (0, 0.0)
    inter = sig_a & sig_b
    union = sig_a | sig_b
    return (len(inter), len(inter) / len(union))


# Şüphe iki kanaldan tetiklenir (gerçek Fable-5 üçlüsüyle kalibre edildi):
#   1. KONU imzaları: konular kısa olduğu için jaccard anlamlı — en az 2
#      ortak token + jaccard >= 0.3 ("claude"+"fable" çifti tipik vaka).
#      Tek ortak token ("openai" gibi) şüphe SAYILMAZ — aynı şirketin
#      farklı haberleri normaldir.
#   2. KONU+İÇERİK imzaları: konular bambaşka kelimelenmişse içerik
#      yakalar — ama içerik token havuzu büyük olduğundan eşik yüksek
#      (>= 4 ortak ve jaccard >= 0.2).
def is_suspect(
    topic_new: set[str], topic_old: set[str],
    full_new: set[str], full_old: set[str],
) -> bool:
    t_inter, t_jac = deterministic_overlap(topic_new, topic_old)
    if t_inter >= 2 and t_jac >= 0.3:
        return True
    f_inter, f_jac = deterministic_overlap(full_new, full_old)
    return f_inter >= 4 and f_jac >= 0.2


def confirm_same_story_llm(
    topic_a: str, content_a: str, topic_b: str, content_b: str,
) -> Optional[bool]:
    """gpt-4o-mini hakem. True/False; hata/parse sorununda None (merge yapma)."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        resp = client.chat.completions.create(
            model=os.environ.get("MODEL_ANALYSIS", "gpt-4o-mini"),
            temperature=0.0,
            max_tokens=120,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "Sen bir haber masası editörüsün. Sana iki haber adayı "
                    "verilecek. Soru: ikisi de AYNI OLAYIN (aynı duyuru/lansman/"
                    "vaka) haberi mi?\n\n"
                    "KURAL: Bir lansmanın FARKLI YÖNLERİ (tanıtım, benchmark/"
                    "performans sonuçları, erişim/fiyat, güvenlik özellikleri) "
                    "hep AYNI hikâyedir — okuyucu için tek haber: 'X çıktı'. "
                    "Aynı şirketin BAĞIMSIZ olayları (yeni model vs ortaklık "
                    "anlaşması vs dava vs veri merkezi yatırımı) FARKLI "
                    "hikâyedir.\n\n"
                    "ÖRNEKLER:\n"
                    "- 'Claude Fable 5 tanıtıldı' + 'Fable 5 benchmark "
                    "sonuçları SOTA' → same_story: true (aynı lansmanın iki "
                    "yönü)\n"
                    "- 'Claude Fable 5 tanıtıldı' + 'Fable 5 herkese açık, "
                    "Mythos 5 kısıtlı' → same_story: true (aynı lansmanın "
                    "erişim detayı)\n"
                    "- 'Claude Fable 5 tanıtıldı' + 'Anthropic Pentagon ile "
                    "anlaşma imzaladı' → same_story: false (bağımsız olaylar)\n\n"
                    'Yalnızca JSON döndür: {"same_story": true/false}'
                )},
                {"role": "user", "content": (
                    f"A) {topic_a}\n{(content_a or '')[:500]}\n\n"
                    f"B) {topic_b}\n{(content_b or '')[:500]}"
                )},
            ],
        )
        parsed = json.loads(resp.choices[0].message.content or "{}")
        val = parsed.get("same_story")
        return bool(val) if isinstance(val, bool) else None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[story_dedup] LLM hakem hatası (merge yapılmayacak): {e}")
        return None


def find_same_story(
    topic: str,
    raw_content: str,
    candidates: list[dict],
    *,
    use_llm: bool = True,
) -> Optional[dict]:
    """Yeni adayı son trendlerle karşılaştır; aynı hikâyeyse o trend satırını döndür.

    candidates: trends satırları (id, topic, raw_content?, source_tweets?...).
    Deterministik şüphe yoksa LLM hiç çağrılmaz. Şüphelilerde en güçlü örtüşen
    önce sorulur; ilk True'da döner.
    """
    topic_new = story_tokens(topic)
    full_new = story_tokens(f"{topic} {raw_content or ''}")
    if not topic_new and not full_new:
        return None

    scored: list[tuple[float, int, dict]] = []
    for cand in candidates:
        cand_topic = cand.get("topic") or ""
        topic_old = story_tokens(cand_topic)
        full_old = story_tokens(f"{cand_topic} {cand.get('raw_content') or ''}")
        if is_suspect(topic_new, topic_old, full_new, full_old):
            inter, jac = deterministic_overlap(topic_new, topic_old)
            scored.append((jac, inter, cand))

    if not scored:
        return None
    scored.sort(key=lambda r: (-r[0], -r[1]))

    for jac, inter, cand in scored[:3]:  # en fazla 3 hakem çağrısı
        if not use_llm:
            return cand
        verdict = confirm_same_story_llm(
            topic, raw_content or "",
            cand.get("topic") or "", cand.get("raw_content") or "",
        )
        if verdict is True:
            logger.info(
                f"[story_dedup] '{topic[:50]}' ≈ '{(cand.get('topic') or '')[:50]}' "
                f"(jaccard={jac:.2f}, ortak={inter}) → MERGE"
            )
            return cand
        if verdict is False:
            continue
        # None (hakem hatası) → güvenli taraf: bu adayı atla
    return None
