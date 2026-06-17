"""SENCE? kart içerik üreticisi — AI-odaklı açık uçlu "sen" sorusu (LLM + gate + dedup).

Haber-bağlı mod: news_topic verilirse soru o konuya değer. Evergreen mod: bağımsız.
gate_question REDDEDERSE yeniden dener. Hiç geçmezse None.
"""
from __future__ import annotations

import time
from typing import Optional

from loguru import logger

from .card_gates import chat_json, gate_question

_GEN_SYS = """Sen Cansu'sun. "SENCE?" serisi için izleyiciyle "birlikte düşünelim"
diyen sıcak bir GÖRÜŞ sorusu yaz. SENCE = "sen ne düşünüyorsun" → fikir/perspektif
sorusu (deneyim-itirafı ya da evet-hayır DEĞİL).

ŞEKİL (serinin lügatı — buna SADIK kal):
- ZORUNLU: Soru "Sence" kelimesiyle BAŞLAR. Tercih edilen kalıp: "Sence yapay zeka
  en çok hangi/kime/neyi ...?" (örnek: "Sence yapay zeka en çok hangi işimizi
  kolaylaştırdı?"). "Sence" ile başlamayan soru KABUL EDİLMEZ.
- "yapay zeka" de — "ChatGPT / AI" gibi İngilizce marka adı KULLANMA.
- Görüş / hafif hayal-gücü / perspektif sorusu: "en çok hangi...", "en çok kime...",
  "ilk neyi...". Herkesin bir fikri olur, yorumda paylaşır.
- TEK cümle, sıcak ve sade — EN FAZLA 8-10 kelime.
- TÜRKÇE AKICI VE DOĞAL OLMALI. Yüksek sesle okununca takılmamalı; devrik/kayık/
  kulağı tırmalayan kuruluş YASAK.
- "Sence"den sonra YAPAY ZEKA HAKKINDA bir görüş sorusu gelir. "Sence ... sen
  ...-yor musun?" gibi görüş + kişisel-deneyim KARIŞIMI kayık olur — YAPMA.
  KÖTÜ: "Sence yapay zekaya en çok hangi konuda güveniyorsun?" (Sence+güveniyorsun
  çakışması, kayık). İYİ: "Sence yapay zeka en çok hangi konuda güvenilir?"

DENGE:
- Ne çok DERİN/felsefi (bilinç, ruh, ölüm, "anlamı ne") — ağır kaçar.
- Ne RANDOM/absürt ("hayal tatil nasıl olurdu") — alakasız kaçar.
- Ne İTİRAF/günlük-konuşma ("ChatGPT'ye kızıp azarladın mı", "en utanç verici
  soru") — format dışı, fazla samimi kaçar.
- Hedef: ortada — sıcak, merak uyandıran, fikir soran.

ONAYLI ÖRNEK HAVUZU (kalibre bu — bu kalitede ve bu çeşitlilikte üret):
- "Sence yapay zeka en çok hangi işimizi kolaylaştırdı?"
- "Sence yapay zeka bir gün gerçek bir arkadaş olabilir mi?"
- "Sence yapay zeka hangi meslekte insanın yerini asla tutamaz?"
- "Sence yapay zeka en çok hangi konuda güvenilir?"
- "Sence yapay zeka seni gerçekten tanıyor mu, yoksa tahmin mi ediyor?"
- "Sence yapay zeka yaratıcı mı, yoksa sadece kopyalıyor mu?"
- "Sence yapay zeka en çok hangi alışkanlığımızı değiştirdi?"
- "Sence yapay zeka olmadan hayat zorlaşır mı?"
- "Sence yapay zeka en çok kimin hayatını değiştirdi?"
- "Sence yapay zeka insana en çok hangi konuda benziyor?"

YAPI ÇEŞİTLİLİĞİ (hep "en çok hangi X" KALIBINA sıkışma — yukarıdaki gibi karıştır):
- "Sence yapay zeka ... mı, yoksa ... mı?" (ikili karşıtlık)
- "Sence yapay zeka bir gün ... olabilir mi?" (olasılık)
- "Sence yapay zeka olmadan ... ?" (yokluk senaryosu)
- "Sence yapay zeka en çok hangi/kime/neyi ...?" (klasik)
Açı havuzu: kolaylık, arkadaşlık, meslek, güven, seni-tanıma, yaratıcılık,
alışkanlık, bağımlılık, etki, benzerlik (+ yeni açılar bul).

KÖTÜ örnekler (ASLA):
- "ChatGPT'ye kızıp azarladığın oldu mu?"  (itiraf + İngilizce marka, format dışı)
- "Yapay zekaya en son neyi kanıtlamaya çalıştın?"  (içe-dönük)
- "Yapay zekanın tasarlayacağı hayal tatil nasıl olurdu?"  (random)
- "Yapay zeka bilinç kazanırsa ne hissederdin?"  (çok derin)

Uygun: siyaset YOK, tıbbi tavsiye YOK, kehanet YOK.
Yalnızca JSON döndür: {"question": "..."}"""


async def generate_question_card(
    *, news_topic: Optional[str] = None,
    avoid_questions: Optional[list[str]] = None, max_attempts: int = 3,
) -> Optional[dict]:
    avoid = " | ".join(avoid_questions or [])
    for attempt in range(1, max_attempts + 1):
        if news_topic:
            user = ("Şu haberle bağlantılı, 'Sence' ile başlayan sıcak bir görüş sorusu üret "
                    f"('Sence yapay zeka...' tarzı).\nHaber konusu: {news_topic}")
        else:
            user = ("Onaylı örnek havuzu kalibresinde, sıcak ve AKICI bir SENCE? görüş sorusu üret "
                    "(evergreen) — 'Sence yapay zeka...' ile başlasın; yapıyı çeşitlendir (hep "
                    "'en çok hangi X' olmasın: 'mı yoksa mı', 'olabilir mi', 'olmadan' de). "
                    "İtiraf/İngilizce-marka/random/çok-derin/kayık-Türkçe DEĞİL.")
        if avoid:
            user += f"\n\nŞU sorulara BENZEME (yakında kullanıldı): {avoid}"
        try:
            _t0 = time.perf_counter()
            gen, gmeta = await chat_json(_GEN_SYS, user, temperature=0.9, max_tokens=120)
            gen_ms = int((time.perf_counter() - _t0) * 1000)
            q = str(gen.get("question") or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[q-card] üretim hatası deneme {attempt}: {e}")
            continue
        if not q:
            continue
        # Deterministik şekil kontrolü: SENCE sorusu "Sence" ile BAŞLAMALI (Berkay
        # kuralı — serinin lügatı). LLM kaçırırsa yeniden üret.
        if not q.lower().lstrip("\"' ").startswith("sence"):
            logger.info(f"[q-card] 'Sence' ile başlamıyor, yeniden deneme {attempt}: {q[:50]}")
            continue
        _g0 = time.perf_counter()
        v = await gate_question(q)
        gate_ms = int((time.perf_counter() - _g0) * 1000)
        if v.ok:
            logger.info(f"[q-card] OK deneme {attempt}: {q[:50]}")
            return {"kind": "question", "question": q,
                    "gate_reason": v.reason, "model": gmeta["model"],
                    "tokens": int(gmeta["tokens"]) + int(v.tokens), "attempts": attempt,
                    "gen_ms": gen_ms, "gate_ms": gate_ms}
        logger.info(f"[q-card] gate reddi deneme {attempt}: {v.reason or v.error}")
    logger.warning("[q-card] max deneme aşıldı — soru üretilemedi")
    return None
