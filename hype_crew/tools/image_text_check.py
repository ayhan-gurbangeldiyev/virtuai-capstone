"""Glow kart vision hakemi — başlık doğruluğu + logo fabrikasyonu denetimi.

2026-06-10 (Berkay): iki vaka tek günde — (1) "Alrdığını" başlık typo'su
(Nano Banana harf düşürdü), (2) "Cf" kalkanı (bilinmeyen ürün logosu
uyduruldu). Frame i2i yolu CLIP/estetik gate'ini bilinçli bypass ediyor
(o gate fotoğraflar için; düz grafik kartlarda false-fail) — ama yerine
hiçbir denetim yoktu. Otonom yayında kartlara kimse bakmayacak.

Bu hakem tek Flash-vision çağrısıyla üç şeyi yargılar:
  1. headline_ok    — karttaki başlık verilen metinle BİREBİR aynı mı
                      (harf düşmesi/diakritik bozulması dahil)
  2. no_fake_logo   — uydurma/yakıştırma logo-rozet-amblem var mı
  3. clean          — anlamsız/bozuk metin artıkları, ağır artefakt

Fail-open İLKESİ YOK: hakem hatasında 'error' döner ve çağıran karta
güvenmez (reroll/fallback) — görsel marka yüzü, şüphede yayınlanmaz.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger

_MODEL = "google/gemini-3-flash-preview"

_SYS = """Sen bir sosyal medya görsel kalite hakemisin. Sana bir kart görseli ve
kartta OLMASI GEREKEN başlık metni verilecek. Yalnızca JSON döndür:

{"headline_ok": true/false,      // karttaki başlık verilen metinle BİREBİR aynı mı
                                  // (eksik harf, ş→s gibi diakritik bozulması,
                                  // kelime farkı → false)
 "headline_seen": "<kartta gördüğün başlık>",
 "no_fake_logo": true/false,     // kartta GERÇEK olmayan, uydurulmuş bir marka
                                  // logosu/rozeti/amblemi/monogramı var mı?
                                  // Gerçek tanınmış logolar (OpenAI, Apple,
                                  // Claude, Google...) sorun DEĞİL → true.
                                  // İcat edilmiş kalkan/rozet/harf-amblemi → false
 "readable": true/false,         // başlık metni arka plan/glow'dan NET okunuyor mu;
                                  // kontrast yeterli mi (metin zemine karışmıyor,
                                  // soluk/seçilemez DEĞİL) → okunmuyorsa false
 "clean": true/false,            // anlamsız metin artıkları, bozuk eller/nesneler,
                                  // ağır görsel artefakt YOK mu
 "notes": "<tek cümle>"}"""


@dataclass
class CardVerdict:
    ok: bool
    headline_ok: bool
    no_fake_logo: bool
    clean: bool
    notes: str
    readable: bool = True
    error: Optional[str] = None


async def check_card(
    image_url: str, expected_headline: str, theme_key: str = "news"
) -> CardVerdict:
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        try:
            from config import settings
            api_key = settings.openrouter_api_key
        except Exception:
            pass
    if not api_key:
        return CardVerdict(False, False, False, False, "", error="no_api_key")

    # Tema bağlamı: pill etiketi + başlık metni rengi → hakem doğru zemini denetler.
    try:
        from .card_themes import get_theme
        _t = get_theme(theme_key)
        _ctx = (
            f"Bu bir '{_t.pill_label}' kartı (içerik tipi: {_t.key}). "
            f"Başlık metni {_t.text_color} renkte yazılmalı. "
        )
        if _t.hero_style == "symbolic":
            _ctx += "Bu kartta marka logosu OLMAMALI (sembolik görsel); logo varsa no_fake_logo=false. "
    except Exception:
        _ctx = ""

    # OpenAI-uyumlu vision mesajları (system + image_url içeren user bloğu).
    _messages = [
        {"role": "system", "content": _SYS},
        {"role": "user", "content": [
            {"type": "text",
             "text": f"{_ctx}Kartta olması gereken başlık:\n{expected_headline}"},
            {"type": "image_url",
             "image_url": {"url": image_url}},
        ]},
    ]

    # LiteLLM Router (flag-gated, fail-open). VISION call → router_chat_messages
    # (model_name="vision"). On any router error fall through to the existing
    # httpx path below (no behavior change when flag OFF / fail-closed semantics
    # preserved: router error → except → bare httpx → its own except → CardVerdict error).
    from .llm_router import router_enabled, router_chat_messages
    if router_enabled():
        try:
            text, _meta = await router_chat_messages(
                _messages, model_name="vision", temperature=0.0, max_tokens=300,
            )
            text = (text or "").strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                if text.endswith("```"):
                    text = "\n".join(text.split("\n")[:-1])
            parsed = json.loads(text.strip())
            _readable = bool(parsed.get("readable", True))
            v = CardVerdict(
                ok=(
                    bool(parsed.get("headline_ok"))
                    and bool(parsed.get("no_fake_logo"))
                    and bool(parsed.get("clean"))
                    and _readable
                ),
                headline_ok=bool(parsed.get("headline_ok")),
                no_fake_logo=bool(parsed.get("no_fake_logo")),
                clean=bool(parsed.get("clean")),
                notes=str(parsed.get("notes") or "")[:300],
                readable=_readable,
            )
            logger.info(
                f"[card-check] (router) ok={v.ok} headline={v.headline_ok} "
                f"logo={v.no_fake_logo} readable={v.readable} clean={v.clean} | {v.notes[:80]}"
            )
            return v
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[card-check] router atlandı: {e}")

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": _MODEL,
                    "temperature": 0.0,
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": _SYS},
                        {"role": "user", "content": [
                            {"type": "text",
                             "text": f"{_ctx}Kartta olması gereken başlık:\n{expected_headline}"},
                            {"type": "image_url",
                             "image_url": {"url": image_url}},
                        ]},
                    ],
                },
            )
            r.raise_for_status()
            text = (r.json()["choices"][0]["message"]["content"] or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])
        parsed = json.loads(text.strip())
        # readable yoksa True say (geriye-uyumlu — mor kartlar zaten yüksek kontrast).
        _readable = bool(parsed.get("readable", True))
        v = CardVerdict(
            ok=(
                bool(parsed.get("headline_ok"))
                and bool(parsed.get("no_fake_logo"))
                and bool(parsed.get("clean"))
                and _readable
            ),
            headline_ok=bool(parsed.get("headline_ok")),
            no_fake_logo=bool(parsed.get("no_fake_logo")),
            clean=bool(parsed.get("clean")),
            notes=str(parsed.get("notes") or "")[:300],
            readable=_readable,
        )
        logger.info(
            f"[card-check] ok={v.ok} headline={v.headline_ok} "
            f"logo={v.no_fake_logo} readable={v.readable} clean={v.clean} | {v.notes[:80]}"
        )
        return v
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-check] hakem hatası: {e}")
        return CardVerdict(False, False, False, False, "", error=str(e)[:200])
