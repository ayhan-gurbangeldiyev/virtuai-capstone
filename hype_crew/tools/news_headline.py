"""One-sentence Turkish news headline generator (grounded, non-hallucinating).

Produces the headline sentence stamped onto the Cansu news card. The headline
MUST be factually accurate and grounded ONLY in the provided source content —
no invented numbers, claims, or details (aligns with the pipeline's
"block false facts" gate philosophy). Used by the frame i2i visual path.
"""
from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger

from config import settings

_SYS_PROMPT = (
    "Sen deneyimli bir Türk haber editörüsün. Sana bir haberin konusu ve kaynak "
    "içeriği verilir. Görevin: SADECE verilen içerikteki bilgilere dayanarak TEK, "
    "kısa, nötr ve OLGUSAL DOĞRU bir Türkçe haber başlığı cümlesi yazmak.\n"
    "KURALLAR:\n"
    "- NETLİK (EN ÖNEMLİ): başlık, yapay zekâ/teknik bilmeyen NORMAL bir "
    "okuyucunun TEK OKUMADA anladığı SADE Türkçe olmalı. İngilizce bir "
    "kavramı KELİMESİ KELİMESİNE çevirme — örn. 'rate limit reset' → 'hız "
    "sınırı sıfırlaması' gibi tuhaf, anlaşılmaz literal çeviri YASAK. Kavramı "
    "düz Türkçeyle AÇIKLA (örn. 'kullanım hakkını biriktirip sonra kullanma'). "
    "Jargon yığma; cümle okununca NE DENDİĞİ NET anlaşılsın.\n"
    "- En fazla ~75 karakter, tek cümle.\n"
    "- TÜRKÇE YAZIM KURALI (kritik): cümle düzeni kullan — YALNIZCA ilk "
    "kelime ve özel adlar (OpenAI, Apple, Siri gibi) büyük harfle başlar. "
    "Her Kelimeyi Büyük Harfle Başlatma (Title Case YASAK).\n"
    "  DOĞRU: 'OpenAI bazı kullanıcı hesaplarının yanlışlıkla askıya "
    "alındığını duyurdu.'\n"
    "  YANLIŞ: 'OpenAI Bazı Kullanıcı Hesaplarının Yanlışlıkla Askıya "
    "Alındığını Duyurdu.'\n"
    "- İçerikte OLMAYAN hiçbir sayı, oran, iddia veya detay EKLEME.\n"
    "- Abartma, yorum, spekülasyon, çağrı (CTA) yok; sadece olguyu aktar.\n"
    "- Doğru Türkçe imla (ı, ş, ğ, ü, ö, ç).\n"
    "- SADECE başlık cümlesini döndür: tırnak yok, açıklama yok, etiket yok."
)


def _clean(text: str) -> str:
    text = (text or "").strip().strip('"').strip("'").strip()
    # collapse to a single line
    text = " ".join(text.split())
    return text


def _ensure_period(text: str) -> str:
    """Headline must end with sentence punctuation (Berkay: foto'da nokta olsun)."""
    text = (text or "").strip()
    if text and text[-1] not in ".!?…":
        text += "."
    return text


async def generate_news_headline_async(
    *,
    topic: str,
    source_text: Optional[str] = None,
    max_chars: int = 90,
) -> str:
    """Return a grounded one-sentence Turkish headline.

    Falls back to the topic itself on any error (never raises). source_text
    should be the real article/tweet body (trends.raw_content) or the
    fact-gated draft — the LLM is grounded on it and must not add facts.
    """
    topic = (topic or "").strip()
    source = (source_text or "").strip()
    if not source:
        # No grounding material -> safest is the topic verbatim (no invention).
        return _ensure_period(topic[:max_chars])

    api_key = (settings.openrouter_api_key or "").strip()
    if not api_key:
        logger.warning("[news_headline] OPENROUTER_API_KEY missing — using topic")
        return _ensure_period(topic[:max_chars])

    model = getattr(settings, "model_fast", "openrouter/google/gemini-3-flash-preview")
    actual_model = model.removeprefix("openrouter/")
    user_prompt = (
        f"Konu: {topic}\n\n"
        f"Kaynak içerik:\n{source[:1800]}\n\n"
        "Başlık cümlesi:"
    )

    # LiteLLM Router dalı (flag-gated, fail-open). Bu site JSON değil DÜZ METİN
    # döndürür → router_chat_json'ın json_object zorlaması başlığı bozar; bu yüzden
    # çekirdek router_chat_messages kullanılır (response_format YOK). Kapalıyken
    # aşağıdaki httpx yolu byte-identical çalışır.
    try:
        from .llm_router import router_enabled, router_chat_messages
        if router_enabled():
            try:
                txt, _meta = await router_chat_messages(
                    [
                        {"role": "system", "content": _SYS_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    model_name="gate-fast", temperature=0.2, max_tokens=60,
                )
                text = _clean(txt)
                if not text:
                    return _ensure_period(topic[:max_chars])
                if len(text) > max_chars:
                    logger.info(f"[news_headline] headline too long ({len(text)}c) — using topic")
                    return _ensure_period(topic[:max_chars])
                text = _ensure_period(text)
                logger.info(f"[news_headline] '{text}'")
                return text
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[news_headline] router atlandı, httpx'e düşülüyor: {e}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[news_headline] router import hatası, httpx'e düşülüyor: {e}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": actual_model,
                    "messages": [
                        {"role": "system", "content": _SYS_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 60,
                },
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"[news_headline] LLM call failed ({type(e).__name__}: {str(e)[:100]}) — using topic"
        )
        return _ensure_period(topic[:max_chars])

    text = _clean((data.get("choices") or [{}])[0].get("message", {}).get("content", ""))
    if not text:
        return _ensure_period(topic[:max_chars])
    if len(text) > max_chars:
        # Prefer the topic over a mid-word truncation that could distort meaning.
        logger.info(f"[news_headline] headline too long ({len(text)}c) — using topic")
        return _ensure_period(topic[:max_chars])
    text = _ensure_period(text)
    logger.info(f"[news_headline] '{text}'")
    return text
