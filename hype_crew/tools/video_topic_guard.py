"""Video render ÖNCESİ konu-tutarlılık kapısı — "video haberle aynı olayı mı anlatıyor?"

2026-06-11 (Berkay: "bir daha hata görmek istemiyorum bu konuda, crew resmen
sallamış"). Vaka: kaynak kirlenmesi yüzünden caption "Advanced AI Framework"
yazarken video script "Claude Fable 5 duyuruldu" anlattı — $3.5'lık render
YANLIŞ habere harcandı, otonom yayında kimse fark etmeyecekti.

Kök neden trend_engine'de düzeltildi (related-tweet artık story_dedup eşiğiyle),
ama bu modül SON SAVUNMA: HeyGen'e tek dolar gitmeden önce, video anlatımının
post caption'ı (operatörün yanında gördüğü yer-gerçeği) ile AYNI OLAYI anlatıp
anlatmadığı tek Flash çağrısıyla yargılanır. Uymuyorsa render YOK → image-only
post ayakta kalır (video opsiyoneldir, yanlış video değildir).

İLKE: metin birebir aynı olmak zorunda DEĞİL (caption kısa-vurucu, video tam
anlatım) — yalnız AYNI OLAY/HİKÂYE olmalı. story_dedup hakemiyle aynı mantık.

FAIL-CLOSED: hakem hatasında (1 retry sonrası) render ENGELLENİR — "emin
değilsek pahalı yanlış video basma" güvenli tarafı. Flash kesintisi en fazla
videoları image-only'ye düşürür, asla yanlış video yayınlatmaz.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger

_MODEL = "google/gemini-3-flash-preview"

_SYS = """Sen bir haber masası editörüsün. Sana bir sosyal medya POST metni ile
o posta eşlik edecek VİDEO anlatım metni verilecek. Tek soru: ikisi de AYNI
OLAYIN (aynı duyuru / lansman / haber) anlatımı mı?

KURAL:
- Metinlerin BİREBİR aynı olması GEREKMEZ — post kısa ve vurucu, video tam
  anlatım olabilir. Önemli olan AYNI OLAYI anlatmaları.
- Aynı olayın farklı yönleri (tanıtım / benchmark / erişim-fiyat / güvenlik)
  AYNI hikâyedir → match: true.
- Aynı şirketin BAĞIMSIZ olayları (yeni model vs ortaklık vs fon programı vs
  güvenlik çerçevesi) FARKLI hikâyedir → match: false.

ÖRNEK match:false → Post: "Anthropic, Advanced AI Framework'te hükümetlere
frontier modelleri bloklama yetkisi öneriyor." Video: "Anthropic, Claude Fable
5 modelini duyurdu." → İkisi farklı olay (güvenlik çerçevesi vs model lansmanı).

Yalnızca JSON döndür:
{"match": true/false,
 "video_konusu": "<videonun anlattığı olay, kısa>",
 "post_konusu": "<postun anlattığı olay, kısa>",
 "reason": "<tek cümle>"}"""


@dataclass
class ScriptVerdict:
    match: bool
    video_konusu: str
    post_konusu: str
    reason: str
    error: Optional[str] = None


def _api_key() -> str:
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        try:
            from config import settings
            key = (settings.openrouter_api_key or "").strip()
        except Exception:
            pass
    return key


def check_script_matches_caption(
    *, script: str, caption: str, topic: str = "",
) -> ScriptVerdict:
    """Video anlatımı (script) post caption'ı ile aynı olayı mı anlatıyor?

    match=True → render serbest. match=False VEYA error → çağıran render
    YAPMAMALI (fail-closed). 1 retry içerir; kalıcı hatada match=False döner.
    """
    key = _api_key()
    if not key:
        # Anahtar yoksa kapıyı çalıştıramayız — güvenli taraf: engelle.
        return ScriptVerdict(False, "", "", "no_api_key", error="no_api_key")

    user_msg = (
        f"POST metni:\n{(caption or '').strip()[:1200]}\n\n"
        f"VİDEO anlatımı:\n{(script or '').strip()[:1800]}"
    )
    if topic:
        user_msg = f"Haber başlığı: {topic}\n\n" + user_msg

    # LiteLLM Router (flag-gated, fail-open). On any router error we fall
    # through to the existing httpx.Client retry loop below (no behavior change
    # when flag OFF or router fails).
    from .llm_router import router_enabled, router_chat_json_sync
    if router_enabled():
        try:
            parsed, _meta = router_chat_json_sync(
                _SYS, user_msg, temperature=0.0, max_tokens=300, model_name="gate-fast",
            )
            v = ScriptVerdict(
                match=bool(parsed.get("match")),
                video_konusu=str(parsed.get("video_konusu") or "")[:200],
                post_konusu=str(parsed.get("post_konusu") or "")[:200],
                reason=str(parsed.get("reason") or "")[:300],
            )
            logger.info(
                f"[video-guard] (router) match={v.match} | video='{v.video_konusu[:60]}' "
                f"post='{v.post_konusu[:60]}' | {v.reason[:80]}"
            )
            return v
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[video-guard] router atlandı: {e}")

    last_err: Optional[str] = None
    for attempt in (1, 2):
        try:
            with httpx.Client(timeout=45.0) as client:
                r = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": _MODEL,
                        "temperature": 0.0,
                        "max_tokens": 300,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": _SYS},
                            {"role": "user", "content": user_msg},
                        ],
                    },
                )
                r.raise_for_status()
                text = (r.json()["choices"][0]["message"]["content"] or "").strip()
            parsed = json.loads(text)
            v = ScriptVerdict(
                match=bool(parsed.get("match")),
                video_konusu=str(parsed.get("video_konusu") or "")[:200],
                post_konusu=str(parsed.get("post_konusu") or "")[:200],
                reason=str(parsed.get("reason") or "")[:300],
            )
            logger.info(
                f"[video-guard] match={v.match} | video='{v.video_konusu[:60]}' "
                f"post='{v.post_konusu[:60]}' | {v.reason[:80]}"
            )
            return v
        except Exception as e:  # noqa: BLE001
            last_err = str(e)[:200]
            logger.warning(f"[video-guard] hakem hatası (deneme {attempt}): {last_err}")

    # Kalıcı hata → fail-closed: render engellenir.
    return ScriptVerdict(False, "", "", f"judge_error: {last_err}", error=last_err)
