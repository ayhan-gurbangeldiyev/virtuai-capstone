# ContentFactory - Bitiş (CTA/Ending) Definitions
# Controls HOW the tweet ends
# Default is "otomatik" - AI picks the best ending strategy

BITISLER = {
    "otomatik": {
        "id": "otomatik",
        "name": "Otomatik",
        "label": "AI en uygun bitişi seçer",
        "emoji": "🎲",

        "prompt": """## BİTİŞ: OTOMATİK

Tweet'in bitişini konuya ve diğer ayarlara göre sen belirle.
Bazen soru ile bitir (reply tetikler), bazen punch ile bitir (impact bırakır), bazen açık uçlu bırak.
Doğal hissettir. Zorlama CTA ekleme."""
    },

    "soru": {
        "id": "soru",
        "name": "Soru",
        "label": "Soru ile bitir, reply tetikle",
        "emoji": "❓",

        "prompt": """## BİTİŞ: SORU

Tweet'i bir soru ile bitir. İnsanlar cevap yazmak istesin.

Kurallar:
- Soru doğal olsun. Tweet'in akışından çıksın, yapıştırılmış gibi olmasın.
- Açık uçlu soru. Evet/hayır ile cevaplanmasın.
- Gerçekten merak ediyor gibi sor. "Siz ne düşünüyorsunuz?" gibi klişeler YASAK.
- Spesifik soru sor. "Ne düşünüyorsunuz?" değil, "[spesifik konu] hakkında sizin deneyiminiz ne?"

Neden etkili: Reply = 13.5x algoritma ağırlığı. İyi soru = çok reply = viral."""
    },

    "dogal": {
        "id": "dogal",
        "name": "Doğal",
        "label": "CTA olmadan, punch ile bitir",
        "emoji": "🎤",

        "prompt": """## BİTİŞ: DOĞAL

Tweet'i doğal bir şekilde bitir. Soru yok, CTA yok. Punch ile kapat.

Kurallar:
- Son cümle en güçlü cümle olsun. Mic drop etkisi.
- "Hepsi bu." "Nokta." gibi gereksiz kapanışlar ekleme. Sadece içerikle bitir.
- Akılda kalan son cümle. Okuyucu bu cümleyi hatırlasın.
- Bazen eksik bırakmak bile etkili. Her şeyi söylemek zorunda değilsin.

Neden etkili: En iyi tweet'lerin çoğu CTA'sız biter. Güçlü punch = bookmark + dwell time."""
    },
}

# Export
__all__ = ['BITISLER']
