"""Clarity gate — yayından önce "normal biri anlar mı?" kontrolü (12 Haz 2026).

Faithfulness gate kaynağa-sadıklığı denetler ama metin jargon-yüklü / literal
İngilizce-çeviri / "çok AI duruyor" olabilir (anlaşılmaz). Bu modül her platform
metnini SADE-ANLAŞILIRLIK açısından yargılar; kalırsa bir kez netlik-odaklı
yeniden yazar.

FAIL-OPEN: LLM hatası/belirsizlikte engellemez (clear=True döner) — netlik bir
kalite tercihidir, güvenlik değil; faithfulness gate güvenliği ayrıca tutar.
"""
import json
import logging
import re

import httpx
from config import settings

logger = logging.getLogger(__name__)

_JUDGE_SYS = (
    "Sen Cansu'nun editörüsün. Cansu Gen-Z için AI/tech haberi aktaran bir "
    "persona: casual ama DÜZGÜN yazan (normal büyük-küçük harf, doğru imla, "
    "kısa net cümleler), kuru, hype'sız, hafif alaycı; EMOJİ/ünlem-yağmuru/"
    "kurumsal-satış dili KULLANMAZ. Sana bir paylaşım "
    "metni verilir. İKİ şeyi birden denetle:\n"
    "1) NETLİK: AI/teknik bilmeyen normal biri TEK OKUMADA ne dendiğini anlar mı?\n"
    "2) DOĞALLIK: metin insan/Cansu gibi mi, yoksa 'AI/robot/kurumsal/reklam' gibi mi?\n\n"
    "KALIR (clear=false) eğer ŞUNLARDAN BİRİ varsa:\n"
    "- Literal İngilizce-çeviri / jargon yığını / anlaşılmaz melez "
    "('rate limit'leri biriktirip reset'),\n"
    "- AI/kurumsal/satış dili: 'güzel haberimiz var', 'kontrol sizin elinizde', "
    "'devreye alıyoruz', resmi 'siz' formu, ünlem yağmuru, EMOJİ, "
    "slogan/maxim kapanış, aşırı coşku/pazarlama,\n"
    "- Tamamen küçük harf akışı / virgülle uzun koşma cümle / bozuk imla,\n"
    "- 'Çok AI / yapay / klişe duruyor', ne dediği belirsiz.\n\n"
    "GEÇER (clear=true) eğer: akıcı + sade + DOĞAL; Cansu gibi casual/kuru; "
    "ne dediği net.\n\n"
    "SADECE JSON döndür: {\"clear\": true/false, \"reason\": \"kısa Türkçe sebep\"}"
)

_REWRITE_SYS = (
    "Sen Cansu'sun — AI/tech haberlerini Gen-Z için aktaran biri. Haberi "
    "herkesten önce görüp arkadaşına çaktıran, olayı çözmüş biri gibisin. "
    "Sana kaynağa-sadık ama jargon-yüklü/anlaşılmaz bir paylaşım metni verilir. "
    "Görevin: AYNI olguları koruyarak metni HEM net HEM KENDİ SESİNLE yeniden yaz.\n\n"
    "NETLİK: niş/İngilizce kavramı düz Türkçeyle AÇIKLA (örn. 'rate limit reset "
    "biriktirme' → 'kullanım hakkını biriktirip sonra kullanma'); jargon yığma; "
    "normal biri tek okumada anlasın.\n\n"
    "SES (Cansu): casual ama DÜZGÜN yazılmış Türkçe — normal büyük-küçük harf, "
    "doğru imla, kısa net cümleler (virgülle uzun zincir kurma); kuru, hype'a "
    "prim vermeyen, hafif alaycı. İKİNCİ TEKİL ŞAHIS ('sen' formu — "
    "'kullanabiliyorsun', 'takıldığında'); resmi 'siz' formu YASAK. "
    "'valla/ya/yani/aynen' ölçülü. Teknik terim gerekirse kalabilir ama cümle "
    "anlaşılır olsun.\n\n"
    "KESİN YASAK: emoji, em-dash (—), hashtag, ünlem yağmuru, kurumsal/satış dili "
    "('güzel haberimiz var', 'kontrol sizin elinizde', 'devreye alıyoruz'), "
    "slogan/maxim kapanış (son cümle genel hüküm olamaz), 'X değil Y' retoriği, "
    "resmi 'siz' formu.\n\n"
    "Yeni bilgi/sayı EKLEME — kaynakta olmayan hiçbir şeye çıkma. Uzunluğu ve "
    "platform formatını (kısa tweet / markdown makale) koru. SADECE yeni metni döndür."
)


async def _call(sys_prompt, user, *, max_tokens=400, temp=0.3):
    # LiteLLM Router dalı (flag-gated, fail-open). Bu helper hem JSON yargı
    # (check_clarity) hem DÜZ METİN (clarity_rewrite) için kullanılıyor → router_chat_json'ın
    # json_object zorlaması rewrite'ı bozar; çekirdek router_chat_messages (response_format YOK)
    # kullanılır, dönüş yine ham str. Kapalıyken aşağıdaki httpx yolu byte-identical çalışır.
    try:
        from .llm_router import router_enabled, router_chat_messages
        if router_enabled():
            try:
                txt, _meta = await router_chat_messages(
                    [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user},
                    ],
                    model_name="gate-fast", temperature=temp, max_tokens=max_tokens,
                )
                return (txt or "").strip()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[clarity] router atlandı, httpx'e düşülüyor: {e}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[clarity] router import hatası, httpx'e düşülüyor: {e}")

    key = (settings.openrouter_api_key or "").strip()
    if not key:
        return None
    model = getattr(
        settings, "model_fast", "openrouter/google/gemini-3-flash-preview"
    ).removeprefix("openrouter/")
    try:
        async with httpx.AsyncClient(timeout=40.0) as c:
            r = await c.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temp,
                    "max_tokens": max_tokens,
                },
            )
            r.raise_for_status()
            return (r.json()["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[clarity] LLM hata: {type(e).__name__}: {str(e)[:90]}")
        return None


# Resmi 'siz' formu KESİN yasak (Berkay). LLM yargısı 'siz'i bazen "net" bulup
# geçiriyordu (12 Haz 2026, Coinbase postu "sizin adınıza/kullanabiliyorsunuz"
# ile kaçtı) → deterministik dedektör: 'siz' zamiri + -siniz/-sınız/-sunuz/-sünüz
# fiil ekleri. Eşleşirse clarity_rewrite zorlanır ('sen' formuna çevirir).
_SIZ_RE = re.compile(
    r"\b(siz|sizin|size|sizi|sizler|sizlere|sizden|sizce)\b"
    r"|[a-zçğıöşü]{2,}(siniz|sınız|sunuz|sünüz)\b",
    re.IGNORECASE,
)


async def check_clarity(text: str, platform: str = "") -> dict:
    """{clear: bool, reason: str}. FAIL-OPEN: hata → clear=True (engelleme)."""
    if not (text or "").strip():
        return {"clear": True, "reason": "boş"}
    # Deterministik sert-kural: resmi 'siz' formu → her zaman sadeleştir.
    if _SIZ_RE.search(text):
        return {"clear": False, "reason": "resmi 'siz' formu kullanılmış (sen formu olmalı)"}
    out = await _call(
        _JUDGE_SYS, f"Platform: {platform}\nMetin:\n{text[:2000]}",
        max_tokens=120, temp=0,
    )
    if not out:
        return {"clear": True, "reason": "kontrol edilemedi (fail-open)"}
    try:
        s = out.strip()
        if s.startswith("```"):
            s = "\n".join(s.split("\n")[1:])
            if s.endswith("```"):
                s = s.rsplit("```", 1)[0]
            s = s.strip()
        d = json.loads(s)
        return {"clear": bool(d.get("clear", True)), "reason": str(d.get("reason", ""))[:160]}
    except Exception:
        return {"clear": True, "reason": "parse edilemedi (fail-open)"}


async def clarity_rewrite(text: str, source: str = "", platform: str = ""):
    """Netlik-odaklı yeniden yaz. Hata → None (çağıran orijinali korur)."""
    user = (
        f"Platform: {platform}\n\n"
        f"KAYNAK (olgular yalnız buradan, dışına ÇIKMA):\n{(source or '')[:1500]}\n\n"
        f"MEVCUT METİN (sadeleştir):\n{text}"
    )
    return await _call(_REWRITE_SYS, user, max_tokens=700, temp=0.4)
