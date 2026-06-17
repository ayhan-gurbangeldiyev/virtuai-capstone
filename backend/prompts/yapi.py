# ContentFactory - Yapı (Structure/Tone) Definitions
# Controls HOW the tweet is structured and delivered
# This setting controls the writing structure. Karakter controls the voice, Etki controls the goal.

YAPILAR = {
    "dogal": {
        "id": "dogal",
        "name": "Doğal",
        "label": "Akıcı, samimi, konuşur gibi",
        "emoji": "🌊",

        "prompt": """## YAPI: DOĞAL

Düşündüğün gibi yaz. Yapıya zorlanma, akışına bırak.

Kurallar:
- Konuşma dili. Arkadaşına anlatır gibi, makale yazar gibi değil.
- Cümle fragments okay. "Garip." "Aynen öyle." "Neyse."
- Düşünce zıplamaları doğal. Her cümle bir öncekine bağlı olmak zorunda değil.
- Tamamlanmamış düşünceler okay. Her şeyin bir sonucu olmak zorunda değil.
- İç ses gibi yazabilirsin. "Aslında şimdi düşünüyorum da..."

Yapma:
- Template'e zorlanma. Thesis-Evidence-Insight gibi yapılar bu ton için değil.
- Her şeyi açıklama. Bazen gözlem yeterli.
- Profesyonel ses takma. Bu ton samimilik üzerine kurulu."""
    },

    "kurgulu": {
        "id": "kurgulu",
        "name": "Kurgulu",
        "label": "Yapılandırılmış, planlı, profesyonel",
        "emoji": "📐",

        "prompt": """## YAPI: KURGULU

Düşünülmüş, yapılandırılmış, her cümlesi planlı.

Kurallar:
- Net bir akış: Başlangıç → Gelişme → Sonuç. Her cümle bir sonrakini hazırlasın.
- İlk cümle ana iddiayı söylesin. Sonra destekle. Sonra sonuç çıkar.
- Her cümle bir amaca hizmet etsin. Gereksiz kelime, gereksiz cümle yok.
- Transition'lar smooth olsun. Cümleler birbirine doğal geçiş yapsın.
- Kapanış güçlü olsun. Akılda kalan bir son cümle.

Yapma:
- Soğuk ve akademik olma. Yapılandırılmış ama sıcak.
- Madde işareti listeleri yapma (thread hariç). Bu tweet, blog değil.
- Fazla uzatma. Yapı var ama gereksiz padding yok."""
    },

    "cesur": {
        "id": "cesur",
        "name": "Cesur",
        "label": "Provokatif, sınır zorlayan, vurucu",
        "emoji": "⚡",

        "prompt": """## YAPI: CESUR

Kimsenin söylemeye cesaret edemediğini söyle. Bold, edgy, impact.

Kurallar:
- İlk cümle şok edici olsun. "WTF" dedirtmeli.
- Giderek tırmandır. Her cümle bir öncekinden daha intense.
- Beklenmedik twist ile bitir. Okuyucu "oh" desin.
- Abartı okay ama inandırıcı kal. Absürt değil, zeki cesaret.
- Provokatif ol ama aptalca değil. Kışkırt ama düşündür.

Yapma:
- Sadece shock value için yazmak. Shock + insight = iyi. Sadece shock = troll.
- Offensive olma. Provokatif ve offensive farklı şeyler.
- Kontrolden çıkma. "Controlled chaos" = bu tonun özü. Kaos var ama bir akıl da var.

ÖNEMLİ UYARI: Bu yapı her karakterle uyumlu değil.
Uzman + Cesur ✅ (cesur uzman)
Otorite + Cesur ✅ (cesur lider)
İçeriden + Cesur ❌ (çelişir, içeriden cool ve sakin olmalı)
Mentalist + Cesur ❌ (çelişir, mentalist aydınlatıcı olmalı, kışkırtıcı değil)
Haberci + Cesur ❌ (çelişir, haberci tarafsız olmalı)"""
    },
}

# Export
__all__ = ['YAPILAR']
