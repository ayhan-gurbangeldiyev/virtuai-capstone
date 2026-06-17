"""Curator news-filter — "haber mi, AI mı?" süzgeci (@upcornco escape hatch).

Trend engine bir "ne patlıyor" (çok-kaynaklı mega-trend) dedektörü; tek
kaynaklı, düşük-engagement bir haber tweet'i o funnel'da sistematik eleniyor.
Bu modül, güvenilir bir küratörün (şimdilik @upcornco) HER tweet'ini ayrı ayrı
"gerçek, taze bir AI HABERİ mi?" diye sınıflandırır. Geçenler trend_engine
tarafından force-seed edilir (bkz. TrendEngine._seed_curator_trends).

Tasarım kararları (operatör, 11 Haz 2026):
- Kapsam SADECE AI haberi (model/ürün/araştırma + AI-iş haberi: fiyat,
  platform değişimi, regülasyon, yatırım). AI olmayan her şey (fintech,
  consumer hardware, genel tech) elenir.
- FAIL-CLOSED: hata/belirsizlik → kapsama ALMA (kötü post yerine kaçan post).
"""
import json
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

# trend_engine ile aynı client/model — ekstra config yok.
_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
_MODEL = os.environ.get("MODEL_ANALYSIS", "gpt-4o-mini")


def _sanitize(text: str, max_len: int = 600) -> str:
    """Kontrol karakterlerini at, uzunluğu sınırla (prompt injection önlemi)."""
    if not text:
        return ""
    s = str(text)[:max_len]
    s = "".join(c for c in s if c == "\n" or (ord(c) >= 32 and ord(c) != 127))
    return s.strip()


# Belirsizlik/hata durumunda dönen güvenli (kapsama-ALMA) sonuç.
_FAIL_CLOSED = {
    "is_news": False,
    "is_ai": False,
    "category": "Other",
    "topic": "",
    "summary": "",
    "confidence": 0.0,
}


async def classify_curator_news(text: str, username: str = "upcornco") -> dict:
    """Tek bir küratör tweet'ini sınıflandır.

    Döner: {is_news, is_ai, category, topic, summary, confidence}
    Geçme kuralı (çağıran tarafça uygulanır):
        is_news AND is_ai AND confidence >= 0.5

    HER hata/bozuk-JSON → _FAIL_CLOSED (is_news=False, is_ai=False).
    """
    clean = _sanitize(text)
    if not clean:
        return dict(_FAIL_CLOSED)

    prompt = f"""Sen sert bir teknoloji haber editörüsün. Aşağıdaki @{username} \
tweet'ini değerlendir.

TWEET:
{clean}

İKİ SORU:
1. Bu GERÇEK, taze bir HABER mi? (ürün/model lansmanı, yeni özellik, fiyat \
değişimi, platform değişikliği, regülasyon, yatırım/satın alma, araştırma \
sonucu = HABER. Yorum/thread/anket/promo/etkinlik-çağrısı/retweet-benzeri = \
HABER DEĞİL.)
2. Konu YAPAY ZEKÂ ile ilgili mi? (AI modeli/ürünü/aracı/araştırması VEYA bir \
AI şirketinin haberi: OpenAI/Anthropic/Google AI/Meta AI vb. fiyat, platform, \
yatırım. SADECE-finans/bankacılık/fintech/ödeme-altyapısı, consumer hardware \
(oyun konsolu), genel tüketici-tech (abonelik zammı) = AI DEĞİL.)

ÖRNEKLER:
- "OpenAI, Anthropic ile rekabet için fiyatlarını düşürüyor" → is_news=true, is_ai=true (AI ürün fiyatı)
- "WhatsApp 3. parti yapay zekâlara izin verecek" → is_news=true, is_ai=true (AI platform değişimi)
- "Anthropic yeni modeli Fable 5'i tanıttı" → is_news=true, is_ai=true
- "Moka United fintech platformu RUUT'u tanıttı" → is_news=true, is_ai=FALSE (fintech)
- "YouTube Premium Türkiye fiyatlarına zam geldi" → is_news=true, is_ai=FALSE (genel tüketici-tech)
- "Xbox 25. yıla özel konsol tanıttı" → is_news=true, is_ai=FALSE (consumer hardware)
- "Girişimcilik programı yeni dönem başvuruları arıyor" → is_news=FALSE (promo)

SADECE JSON döndür:
{{
  "is_news": true/false,
  "is_ai": true/false,
  "category": "AI|Dev|Platform|Business|Finance|ConsumerTech|Other",
  "topic": "Türkçe, kısa ve net başlık (haberse; değilse boş)",
  "summary": "1-2 cümle Türkçe özet (haberse; değilse boş)",
  "confidence": 0.0-1.0
}}"""

    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": "Sen sert bir haber editörüsün. Sadece JSON döndür."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=250,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content.strip())
        out = {
            "is_news": bool(data.get("is_news", False)),
            "is_ai": bool(data.get("is_ai", False)),
            "category": str(data.get("category", "Other"))[:40],
            "topic": _sanitize(data.get("topic", ""), 200),
            "summary": _sanitize(data.get("summary", ""), 500),
            "confidence": float(data.get("confidence", 0.0) or 0.0),
        }
        return out
    except Exception as e:
        logger.warning(
            f"[curator_filter] classify FAILED (fail-closed): {type(e).__name__}: {str(e)[:200]}"
        )
        return dict(_FAIL_CLOSED)


def passes_curator_filter(result: dict) -> bool:
    """Geçme kuralı tek yerde: is_news AND is_ai AND confidence>=0.5."""
    return bool(
        result.get("is_news")
        and result.get("is_ai")
        and float(result.get("confidence", 0.0) or 0.0) >= 0.5
    )
