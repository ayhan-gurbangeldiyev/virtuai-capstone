# ContentFactory - Açılış (Hook) Definitions
# Controls HOW the tweet opens - the first sentence strategy
# Default is "otomatik" - AI picks the best hook for the topic

ACILISLAR = {
    "otomatik": {
        "id": "otomatik",
        "name": "Otomatik",
        "label": "AI en uygun açılışı seçer",
        "emoji": "🎲",

        "prompt": """## AÇILIŞ: OTOMATİK

İlk cümle scroll-stopper olmalı. Konuya ve diğer ayarlara göre en uygun açılışı sen seç.
Her seferinde FARKLI bir açılış yap. Aynı kalıbı tekrarlama.
İlk 3 saniye kuralı: Okuyucu ya durur ya kaydırır. O 3 saniyeyi kazan."""
    },

    "zit_gorus": {
        "id": "zit_gorus",
        "name": "Zıt Görüş",
        "label": "Herkesin inandığının tersini söyle",
        "emoji": "🔄",

        "prompt": """## AÇILIŞ: ZIT GÖRÜŞ

Tweet'e herkesin kabul ettiği bir şeyin TAM TERSİYLE başla.

Örnekler (birebir kopyalama, kendi cümleni kur):
- "Herkes [X] diyor. Tam tersi."
- "[Yaygın inanış] diye biliniyor. Yanlış."
- "[Popüler görüş]? Hayır."

Neden etkili: Merak + tartışma tetikler. Okuyucu "neden yanlış?" diye okumaya devam eder.
Her seferinde FARKLI bir giriş cümlesi kur. Kalıba takılma."""
    },

    "merak": {
        "id": "merak",
        "name": "Merak",
        "label": "Merak uyandır, okuttur",
        "emoji": "🔍",

        "prompt": """## AÇILIŞ: MERAK

Tweet'e merak uyandıran bir cümleyle başla. Okuyucu "ne oldu?" desin.

Örnekler (birebir kopyalama, kendi cümleni kur):
- "Bir şeyi değiştirdim ve her şey değişti."
- "Kimse bundan bahsetmiyor ama..."
- "Bunu fark ettiğimde..."

Neden etkili: Curiosity gap. Okuyucu cevabı öğrenmek için devam eder = dwell time.
Ama tease'i deliver et. Boş merak = clickbait. Merak + bilgi = iyi tweet.
Her seferinde FARKLI bir giriş cümlesi kur."""
    },

    "hikaye": {
        "id": "hikaye",
        "name": "Hikaye",
        "label": "Kişisel anekdot veya gözlemle başla",
        "emoji": "📖",

        "prompt": """## AÇILIŞ: HİKAYE

Tweet'e kısa bir hikaye, anekdot veya gözlemle başla.

Örnekler (birebir kopyalama, kendi cümleni kur):
- "Dün bir şey oldu."
- "Geçen hafta bir toplantıdaydım..."
- "Kahvaltıda fark ettim ki..."
- "3 yıl önce bir hata yaptım."

Neden etkili: İnsanlar hikayelere bağlanır. Hikaye = dwell time + empati + reply.
Ama kısa tut. Bu tweet, roman değil. 1-2 cümle hikaye, sonra punchline veya insight.
Her seferinde FARKLI bir giriş cümlesi kur."""
    },

    "tartisma": {
        "id": "tartisma",
        "name": "Tartışma",
        "label": "Tartışma başlatıcı iddia veya soru",
        "emoji": "⚔️",

        "prompt": """## AÇILIŞ: TARTIŞMA

Tweet'e tartışma başlatacak bir iddia veya soruyla başla.

Örnekler (birebir kopyalama, kendi cümleni kur):
- "İki kamp var ve bir taraf tamamen yanılıyor."
- "Bunu söyleyince insanlar kızıyor ama..."
- "[Tartışmalı iddia]. Değiştirin fikrimi."

Neden etkili: Polarize edici açılış reply tetikler (13.5x). İnsanlar katılır veya karşı çıkar.
Ama toxic olma. Tartışma ≠ kavga. Constructive disagreement istiyoruz.
Her seferinde FARKLI bir giriş cümlesi kur."""
    },
}

# Export
__all__ = ['ACILISLAR']
