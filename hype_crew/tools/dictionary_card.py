"""SÖZLÜK kart içerik üreticisi — AI terimi + sade açıklama (LLM + gate + dedup).

Haber-bağlı mod: news_topic/news_source verilirse terim o konuyla ilgili (açıklama
news_source'a karşı tutarlılık denetlenir). Evergreen mod: bağımsız AI terimi.
gate_dictionary REDDEDERSE yeniden dener (max_attempts). Hiç geçmezse None.
"""
from __future__ import annotations

import time
from typing import Optional

from loguru import logger

from .card_gates import chat_json, gate_dictionary

_GEN_SYS = """Sen Cansu'sun — yapay zekayı sıradan insana sade ve samimi anlatırsın.
Bir "SÖZLÜK" kartı için BİR yapay zeka terimi seç ve tek cümlelik açıklamasını yaz.

EN ÖNEMLİ KURAL — TERİM SEÇİMİ:
Terim, AI dünyasında GERÇEKTEN yaygın kullanılan, sıradan insanın bir yerde duyup
"bu ne demek ya?" dediği bir kavram olmalı. Herkesin merak ettiği, erişilebilir, gerçek.
UYDURMA/jenerik kategori ASLA (örn. "Yapay Zeka Bursu", "Dijital Beyin" gibi gerçek
terim olmayan şeyler YASAK).

İYİ terimler (gerçek, yaygın, "bu ne demek ya"):
- Token (parça), Halüsinasyon, Bağlam Penceresi, Parametre, Fine-tune (ince ayar),
  Prompt, Eğitim Verisi, Model, GPU, Açık Kaynak, Çıkarım (inference), Ağırlıklar.

KÖTÜ terimler (uydurma/jenerik — ASLA):
- "Yapay Zeka Bursu", "Dijital Zeka", "Akıllı Sistem", "Veri Okyanusu" — gerçek terim değil.

AÇIKLAMA KURALLARI:
- TEK ÇOK KISA cümle — EN FAZLA 8-9 KELİME (kartta tek-iki satıra sığmalı).
- Sade Türkçe, "sen" diline yakın; benzetme olabilir ama KISA tut. Ham İngilizce
  jargon KULLANMA (çevir: rate limit→kullanım sınırı). Akademik/kuru olma.
- DOĞRULUK ŞART: terimin GERÇEK özünü ver; yanıltıcı basitleştirme ya da
  insanlaştırma ("anlamak için" gibi) YASAK. Bir uzman okusa "yanlış değil" demeli.
  ÖRNEK — Token: KÖTÜ "kelimeleri anlamak için böldüğü parçalar" (yanıltıcı);
  İYİ "yapay zekanın metni işlerken böldüğü en küçük parça (kelime ya da parçası)".
Yalnızca JSON döndür: {"term": "...", "gloss": "..."}"""


async def generate_dictionary_card(
    *, news_topic: Optional[str] = None, news_source: Optional[str] = None,
    avoid_terms: Optional[list[str]] = None, max_attempts: int = 3,
) -> Optional[dict]:
    avoid = ", ".join(avoid_terms or [])
    for attempt in range(1, max_attempts + 1):
        if news_topic:
            user = f"Şu haberle İLGİLİ bir AI terimi + açıklaması üret.\nHaber konusu: {news_topic}"
            if news_source:
                user += f"\nDetay: {news_source[:1200]}"
        else:
            user = ("AI'da GERÇEKTEN yaygın, 'bu ne demek ya' dedirten bir terim seç + sade "
                    "açıklaması üret (evergreen). Uydurma/jenerik kategori YASAK.")
        if avoid:
            user += f"\n\nŞU terimleri KULLANMA (yakında kullanıldı): {avoid}"
        try:
            _t0 = time.perf_counter()
            gen, gmeta = await chat_json(_GEN_SYS, user, temperature=0.9, max_tokens=200)
            gen_ms = int((time.perf_counter() - _t0) * 1000)
            term = str(gen.get("term") or "").strip()
            gloss = str(gen.get("gloss") or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[dict-card] üretim hatası deneme {attempt}: {e}")
            continue
        if not term or not gloss:
            continue
        _g0 = time.perf_counter()
        v = await gate_dictionary(term, gloss, news_source=news_source)
        gate_ms = int((time.perf_counter() - _g0) * 1000)
        if v.ok:
            logger.info(f"[dict-card] OK deneme {attempt}: {term}")
            return {"kind": "dictionary", "term": term, "gloss": gloss,
                    "gate_reason": v.reason, "model": gmeta["model"],
                    "tokens": int(gmeta["tokens"]) + int(v.tokens), "attempts": attempt,
                    "gen_ms": gen_ms, "gate_ms": gate_ms}
        logger.info(f"[dict-card] gate reddi deneme {attempt}: {v.reason or v.error}")
    logger.warning("[dict-card] max deneme aşıldı — kart üretilemedi")
    return None
