# ContentFactory - Etki (Goal/Intent) Definitions
# Controls WHAT the tweet aims to achieve algorithmically
# This setting controls the strategic goal. Other settings (Karakter, Yapı) handle voice and structure.

ETKILER = {
    "patlassin": {
        "id": "patlassin",
        "name": "Patlasın",
        "label": "Viral, maximum erişim",
        "emoji": "🔥",
        "description": "Paylaşılsın, kaydedilsin, konuşulsun. Maximum viral potansiyel.",

        "prompt": """## HEDEF: PATLASIN 🔥

Bu tweet'in tek amacı PATLAMAK. Maximum etkileşim.

Strateji:
- İlk cümle scroll durdurucu olmalı. Okuyucu 3 saniye içinde ya durur ya kaydırır.
- Beklenmedik bir açı bul. Herkesin söylediğini söyleme, herkesin düşünmediğini söyle.
- Self-contained yaz. Tweet'in içinde her şey olsun, dışarı link istemesin.
- Okuyucu bitirdiğinde ya kaydetmek ya paylaşmak ya yorum yazmak istesin.

Algoritma hedefleri:
- Dwell time: Okuyucu duraksasın, tekrar okusun (10x ağırlık)
- Bookmark: "Bunu kaydetmeliyim" dedirtsin (~10x ağırlık)
- Reply: Yorum yazdırsın (13.5x ağırlık)

DİKKAT: Provokatif ol ama sınırı aşma. Report = -369 ceza, tek bir report viral potansiyeli öldürür."""
    },

    "konustursun": {
        "id": "konustursun",
        "name": "Konuştursun",
        "label": "Tartışma başlatsın, reply çeksin",
        "emoji": "💬",
        "description": "İnsanlar yorum yazsın, fikrini söylesin. Konuşma başlatsın.",

        "prompt": """## HEDEF: KONUŞTURSUN 💬

Bu tweet'in amacı KONUŞMA başlatmak. İnsanlar yorum yazmak istesin.

Strateji:
- Net bir pozisyon al. Ortada durma, bir taraf seç.
- Kışkırtıcı ama zeki ol. Troll değil, düşündüren biri ol.
- İnsanların "hayır ama..." ya da "evet çünkü..." demek isteyeceği bir iddia at.
- Açık uçlu bırak. Her şeyi söyleme, boşluk bırak ki insanlar tamamlasın.

Algoritma hedefleri:
- Reply: EN DEĞERLİ metrik, 13.5x ağırlık. Her reply tweet'i yukarı taşır.
- Reply'a cevap verme: 75x ağırlık. Gelen yorumlara cevap vermek altın.
- Dwell time: Tartışma okutturur (10x)

Bitiş stratejisi: Mümkünse soru veya meydan okuma ile bitir. Ama zoraki soru ekleme, doğal akışa uymazsa punch ile bitir."""
    },

    "ogretsin": {
        "id": "ogretsin",
        "name": "Öğretsin",
        "label": "Bilgi versin, kaydedilsin",
        "emoji": "🧠",
        "description": "Okuyucu bir şey öğrensin. Kaydetmeye değer içerik.",

        "prompt": """## HEDEF: ÖĞRETSİN 🧠

Bu tweet'in amacı DEĞER vermek. Okuyucu "bunu bilmiyordum" desin.

Strateji:
- Bir şey öğret ama sıkıcı olma. Bilgiyi ilginç bir şekilde sun.
- Spesifik ol. Genel laflar değil, somut bilgi ver. Rakam, örnek, karşılaştırma.
- "Bunu kaydetmeliyim" dedirt. Bookmark'a alınacak kalitede yaz.
- Okuyucu tweet'i okuduktan sonra profili ziyaret etmek istesin.

Algoritma hedefleri:
- Bookmark: ~10x ağırlık. Kaydetmeye değer bilgi = algoritma ödülü.
- Profile click: 12x ağırlık. "Kim bu bilen adam?" dedirt.
- Dwell time: Bilgi yoğun içerik uzun okunur (10x)

Ton: Öğretici ama yukarıdan bakan değil. "Bak ne buldum, sana da göstereyim" havası."""
    },

    "iz_biraksin": {
        "id": "iz_biraksin",
        "name": "İz Bıraksın",
        "label": "Düşündürsün, aklından çıkmasın",
        "emoji": "✨",
        "description": "Derin etki. Okuyucu saatlerce düşünsün.",

        "prompt": """## HEDEF: İZ BIRAKSIN ✨

Bu tweet'in amacı AKILDA KALMAK. Okuyucu saatlerce düşünsün.

Strateji:
- Yüzeyde kalma, derine in. Herkesin gördüğünü değil, kimsenin fark etmediğini yaz.
- İnsan gerçekliğine dokun. İnsanların yaşadığı ama dile getirmediği bir şeyi söyle.
- Basit ama derin ol. En etkili cümleler kısa olanlardır.
- Okuyucu "bunu bir daha okumam lazım" desin.

Algoritma hedefleri:
- Dwell time: Tekrar okuma = uzun dwell (10x ağırlık)
- Reply: Derin içerik tartışma tetikler (13.5x)
- Bookmark: Düşündüren şeyler kaydedilir (~10x)

DİKKAT: Felsefe dersi verme, aforizma yazma. Günlük dilden, gerçek hayattan, somut gözlemlerden yola çık. Soyut değil, somut derinlik."""
    },

    "shitpost": {
        "id": "shitpost",
        "name": "Shitpost",
        "label": "Komik, ironik, absürt",
        "emoji": "💀",
        "description": "Güldürsün. Absürt, ironik, beklenmedik humor.",

        "prompt": """## HEDEF: SHITPOST 💀

Bu tweet'in amacı GÜLDÜRMEk. Absürt, ironik, beklenmedik.

Strateji:
- Fazla düşünme, fazla kurgulama. Shitpost doğal ve anlık hissettirmeli.
- İroni ve absürdizm kullan. Ciddi bir formatla saçma bir şey anlat, ya da saçma bir formatla ciddi bir şey anlat.
- Herkesin yaşadığı ama kimsenin dile getirmediği absürtlükleri yakala.
- "Gerçekten bunu yazdı mı" tepkisini al.

Referans tarz: Twitter'daki shitpost kültürü. Kısa, keskin, beklenmedik.

Algoritma hedefleri:
- Reply: Gülen insanlar yorum yazar, etiketler (13.5x)
- Repost: Komik şeyler paylaşılır (1x ama reach artırır)
- Dwell time: "Bir daha okuyayım" etkisi (10x)

Kurallar:
- Emoji kullanabilirsin (max 1-2, shitpost'a uygun)
- Küçük harf okay, büyük harf bağırma okay
- Noktalama esnek
- AMA: Irkçılık, cinsiyetçilik, nefret söylemi kesinlikle YASAK. Komedi zeka gerektirir, aşağılama değil."""
    },
}

# Export
__all__ = ['ETKILER']
