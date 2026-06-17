"""SÖZLÜK/SENCE? kart içeriği için kalite kapıları + ortak LLM JSON helper.

13 Haz 2026 (Berkay): kart içeriğini LLM üretir → bu kapılar denetler.
- SÖZLÜK açıklaması bir OLGU → yanlış/uydurma/jargon OLMAMALI (gate_dictionary).
- SENCE? görüş sorusu → AI-odaklı + "sen" formu + uygun + spekülasyon-değil (gate_question).

Kapılar FAIL-CLOSED: hata/şüphe → REDDET (kötü kart yayınlamaktansa kart olmasın).
LLM çağrısı OpenRouter gemini-flash (image_text_check.py / news_headline.py paterni).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger

_MODEL = "google/gemini-3-flash-preview"


def _api_key() -> str:
    k = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not k:
        try:
            from config import settings
            k = settings.openrouter_api_key
        except Exception:
            pass
    return k


async def chat_json(system: str, user: str, *, temperature: float = 0.0,
                    max_tokens: int = 500, model: Optional[str] = None) -> tuple[dict, dict]:
    """OpenRouter chat → (parsed_json, meta). meta = {model, tokens} (şeffaflık).
    Hata fırlatır (çağıran yakalar).

    litellm_router_enabled açıksa LiteLLM Router'dan geçer (uniform timeout+retry+
    cooldown + gerçek cost/latency); kapalıyken aşağıdaki çıplak httpx yolu (varsayılan)."""
    try:
        from .llm_router import router_enabled, router_chat_json
        if router_enabled():
            return await router_chat_json(system, user, temperature=temperature,
                                          max_tokens=max_tokens, model=model)
    except Exception as e:  # noqa: BLE001 — Router kurulamazsa çıplak yola düş (fail-open)
        from loguru import logger as _lg
        _lg.warning(f"[card_gates] LiteLLM Router atlandı, httpx'e düşülüyor: {e}")

    key = _api_key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY yok")
    mdl = model or _MODEL
    async with httpx.AsyncClient(timeout=45.0) as c:
        r = await c.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": mdl,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        r.raise_for_status()
        body = r.json()
        txt = (body["choices"][0]["message"]["content"] or "").strip()
    meta = {"model": mdl, "tokens": int((body.get("usage") or {}).get("total_tokens") or 0)}
    if txt.startswith("```"):
        txt = "\n".join(txt.split("\n")[1:])
        if txt.endswith("```"):
            txt = "\n".join(txt.split("\n")[:-1])
    return json.loads(txt.strip()), meta


@dataclass
class GateVerdict:
    ok: bool
    reason: str
    tokens: int = 0
    model: str = ""
    error: Optional[str] = None


_DICT_SYS = """Sen bir Türkçe AI-sözlük editörüsün. Sana bir AI terimi ve tek
cümlelik sade açıklaması verilecek. Açıklama SIRADAN insana hitap eden bir sosyal
medya kartında kullanılacak. Yalnızca JSON döndür:

{"correct": true/false,   // açıklama terimin GERÇEK özünü DOĞRU veriyor mu? Yanıltıcı
                          //   basitleştirme / insanlaştırma ("anlamak için") ya da eksik-
                          //   çarpık tanım = false. Bir uzman "yanlış değil" demeli.
                          //   (örn. Token: "kelimeleri anlamak için böldüğü parçalar" = false;
                          //    "metni işlerken böldüğü en küçük parça" = true.)
 "clear": true/false,     // sade Türkçe mi; ham İngilizce jargon ("rate limit",
                          //   "token" çevrilmeden) YOK mu; sıradan insan anlar mı?
 "voice": true/false,     // samimi, "sen" diline uygun, kuru/akademik DEĞİL mi?
 "curiosity": true/false, // terim AI'da GERÇEKTEN yaygın, 'bu ne demek ya' dedirten,
                          //   merak uyandıran GERÇEK bir kavram mı (Token, Halüsinasyon,
                          //   Parametre gibi)? UYDURMA/jenerik kategori ("Yapay Zeka
                          //   Bursu", "Dijital Zeka" gibi gerçek-olmayan) ise false.
 "reason": "<tek cümle>"}"""

_QUESTION_SYS = """Sen bir sosyal medya editörüsün. Sana Türkçe bir soru verilecek;
bu soru "SENCE?" adlı, izleyiciye yapay zeka hakkında AÇIK UÇLU görüş soran bir karta
girecek. Yalnızca JSON döndür:

{"ai_related": true/false,   // soru yapay zeka / AI ile mi ilgili?
 "open_opinion": true/false, // açık uçlu, kişisel görüş/deneyim soruyor mu ("sen"
                             //   formu); evet/hayır kapalı veya bilgi-sınavı DEĞİL mi?
 "appropriate": true/false,  // uygun mu; siyasi/tıbbi-tavsiye/saldırgan/spekülatif-
                             //   kehanet ("AGI ne zaman gelir") DEĞİL mi?
 "evocative": true/false,    // SENCE serisinin lügatına uygun mu: sıcak, "Sence yapay
                             //   zeka..." tarzı GÖRÜŞ/perspektif sorusu, herkesin fikri olur mu?
                             //   false ise: itiraf/günlük-konuşma ("azarladın mı") veya İngilizce
                             //   marka adıyla ("ChatGPT...") başlayan, ya da içe-dönük ("neyi
                             //   kanıtladın"), çok-derin (bilinç/ölüm), ya da random (hayal tatil).
 "akici": true/false,        // Türkçe AKICI/DOĞAL mı; yüksek sesle okununca takılmıyor mu?
                             //   Devrik/kayık kuruluş ya da "Sence"+kişisel-deneyim çakışması
                             //   ("Sence ... güveniyorsun?") varsa false.
 "reason": "<tek cümle>"}"""


async def gate_dictionary(term: str, gloss: str, news_source: Optional[str] = None) -> GateVerdict:
    """SÖZLÜK terim+açıklama kapısı. Olgu+netlik+ses. FAIL-CLOSED."""
    try:
        user = f"Terim: {term}\nAçıklama: {gloss}"
        if news_source:
            user += f"\n\nBağlam (bu habere bağlı üretildi, tutarlı olmalı):\n{news_source[:1500]}"
        v, meta = await chat_json(_DICT_SYS, user)
        ok = (bool(v.get("correct")) and bool(v.get("clear"))
              and bool(v.get("voice")) and bool(v.get("curiosity")))
        logger.info(f"[card-gate dict] ok={ok} term='{term}' | {str(v.get('reason'))[:80]}")
        return GateVerdict(ok, str(v.get("reason") or "")[:200], tokens=meta["tokens"], model=meta["model"])
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-gate dict] hata → REDDET: {e}")
        return GateVerdict(False, "", error=str(e)[:200])


async def gate_question(question: str) -> GateVerdict:
    """SENCE? soru kapısı. AI-odak+açık-görüş+uygunluk. FAIL-CLOSED."""
    try:
        v, meta = await chat_json(_QUESTION_SYS, f"Soru: {question}")
        ok = (bool(v.get("ai_related")) and bool(v.get("open_opinion"))
              and bool(v.get("appropriate")) and bool(v.get("evocative"))
              and bool(v.get("akici")))
        logger.info(f"[card-gate q] ok={ok} q='{question[:50]}' | {str(v.get('reason'))[:80]}")
        return GateVerdict(ok, str(v.get("reason") or "")[:200], tokens=meta["tokens"], model=meta["model"])
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-gate q] hata → REDDET: {e}")
        return GateVerdict(False, "", error=str(e)[:200])
