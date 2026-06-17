# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
# ContentFactory - Prompt Builder v2 LITE
# Lightweight prompt approach: ~800-1200 chars instead of ~14,000
# Each setting maps to 1-2 sentences, not paragraphs
# Only for X (Twitter) platform

from .smart_defaults import get_smart_defaults
from .karakter_v2 import KARAKTER_YAPI_UYUM

# ===================== COMPACT MAPS =====================

ETKI_LITE = {
    "patlassin": "Maximum viral. Scroll durdurucu ilk cümle. Kaydetmeye ve paylaşmaya değer yaz. Beklenmedik açıyla gir.",
    "konustursun": "Konuşma başlat. Net pozisyon al, tartışma tetikle. Okuyucu yorum yazmak istesin. Açık uçlu bırak.",
    "ogretsin": "Değer ver. Okuyucu yeni bir şey öğrensin. Spesifik bilgi, rakam, somut örnek. Kaydetmeye değer.",
    "iz_biraksin": "Aklından çıkmasın. Yüzeyde kalma, derine in. İnsanların yaşayıp dile getirmediği şeyleri söyle. Basit ama derin.",
    "shitpost": "Güldür. Absürt, ironik, beklenmedik humor. Fazla düşünme, doğal ve anlık hissettir. Shitpost kültürü.",
}

KARAKTER_LITE = {
    "uzman": "Bilen, deneyimli biri gibi yaz. Kendinden emin, spesifik, somut.",
    "otorite": "Kesin konuş, tartışmaya yer bırakma. Kanıt ve veriyle destekle.",
    "iceriden": "Perde arkasını gören biri gibi yaz. İçeriden bilgi paylaş, merak uyandır.",
    "mentalist": "İnsan davranışını oku. Herkesin yaptığı ama fark etmediği kalıpları göster.",
    "haberci": "Muhabir gibi. Hızlı, net, faktüel. İlk cümlede ana bilgi.",
}

YAPI_LITE = {
    "dogal": "Akıcı, samimi, konuşur gibi. Arkadaşına anlatır gibi yaz.",
    "kurgulu": "Yapılandırılmış, planlı. Net akış: iddia → destek → sonuç.",
    "cesur": "Provokatif, vurucu. Kimsenin söylemeye cesaret edemediğini söyle. Shock + insight.",
}

ACILIS_LITE = {
    "otomatik": "",
    "zit_gorus": "Herkesin inandığının tersiyle başla.",
    "merak": "Merak uyandırarak başla. 'Bir şeyi fark ettim...' tarzı.",
    "hikaye": "Kısa bir anekdot veya gözlemle başla.",
    "tartisma": "Tartışma başlatacak bir iddia veya soruyla başla.",
}

BITIS_LITE = {
    "otomatik": "",
    "soru": "Soru ile bitir ama klişe olmasın. 'Siz ne düşünüyorsunuz?' YASAK. Spesifik soru sor.",
    "dogal": "CTA olmadan, güçlü son cümle ile bitir. Mic drop.",
}

DERINLIK_LITE = {
    "standart": "",
    "karsi_gorus": "Popüler görüşün tersini savun. Constructive contrarian.",
    "perde_arkasi": "İçeriden bilgi perspektifinden yaz.",
    "uzmanlik": "Uzman seviyesinde derinlik. Nuance ve trade-off göster.",
}

UZUNLUK_DESC = {
    "micro": "MAX 100 karakter. Tek cümle.",
    "punch": "MAX 280 karakter. 1-2 cümle.",
    "spark": "MAX 600 karakter. Bir paragraf.",
    "storm": "MAX 1000 karakter. Uzun tweet.",
    "thread": "Thread formatı: 3-7 tweet, numaralandır (1/, 2/, 3/).",
}

UZUNLUK_LIMITS = {
    "micro": 100, "punch": 280, "spark": 600, "storm": 1000, "thread": 2500,
}

LANG_LITE = {
    "auto": "Konunun diline göre Türkçe veya İngilizce yaz.",
    "tr": "Türkçe yaz.",
    "en": "Write in English.",
}


# ===================== HARD BLOCK (compact) =====================

HARD_BLOCK_LITE = """YASAKLAR: Hashtag YASAK. Emoji YASAK (shitpost hariç, onda max 1-2).
Şu kelimeleri KULLANMA: devrim, çığır açan, hazır mısınız, yeni bir dönem, kapıları açıyor, inovasyon, paradigma, muhteşem, harika, inanılmaz, olağanüstü, hadi bakalım, düşünmek lazım.
Tweet metnini tırnak içine alma. "Tweet:" ekleme. Alternatif/"veya" ile ikinci versiyon YAZMA. TEK tweet yaz."""


# ===================== TASK DEFS (compact) =====================

TASK_LITE = {
    "tweet": "Verilen konuya göre tweet yaz.",
    "quote": "Orijinal tweet'e quote tweet yaz. Kendi perspektifini ekle.\n\nOrijinal Tweet:\n{original_tweet}",
    "reply": "Bu tweet'e reply yaz. Konuşma başlat veya değer kat.\n\nReply Atacağın Tweet:\n{original_tweet}",
    "article": "X/Twitter Article formatında uzun form içerik üret.",
}


# ===================== ULTRA (compact) =====================

ULTRA_LITE = "ULTRA MODE: Maximum kalite. Her kelime yerinde. Orijinal insight. Bu tweet'i 10 kez yazsaydın en iyisi bu olmalı."


# ===================== MAIN BUILDER =====================

def build_final_prompt_v2_lite(
    content_type: str = "tweet",
    topic: str = None,
    etki: str = "patlassin",
    karakter: str = "uzman",
    yapi: str = "dogal",
    uzunluk: str = "punch",
    acilis: str = "otomatik",
    bitis: str = "otomatik",
    derinlik: str = "standart",
    language: str = "auto",
    is_ultra: bool = False,
    original_tweet: str = None,
    reply_mode: str = None,
    article_style: str = None,
    additional_context: str = None,
    style_prompt: str = None,
    example_tweets: list = None,
    trend_context: str = None,
) -> str:
    """Build lightweight v2 prompt. Same interface as build_final_prompt_v2."""
    
    lines = []
    
    # 1. Hard block (always first)
    lines.append(HARD_BLOCK_LITE)
    
    # 2. Length (critical, right after block)
    length_desc = UZUNLUK_DESC.get(uzunluk, UZUNLUK_DESC["punch"])
    lines.append(f"UZUNLUK: {length_desc}")
    
    # 3. Language
    lang = LANG_LITE.get(language, LANG_LITE["auto"])
    lines.append(lang)
    
    # 4. Core identity (1 line)
    lines.append("İnsan gibi yaz. AI çıktısı gibi hissettirme. Doğal, kısa, net.")
    
    # 5. Task
    task = TASK_LITE.get(content_type, TASK_LITE["tweet"])
    if original_tweet and "{original_tweet}" in task:
        task = task.format(original_tweet=original_tweet)
    lines.append(task)
    
    # 6. Etki (goal)
    etki_text = ETKI_LITE.get(etki, ETKI_LITE["patlassin"])
    lines.append(f"HEDEF: {etki_text}")
    
    # 7. Karakter (voice) 
    karakter_text = KARAKTER_LITE.get(karakter, "")
    if karakter_text:
        lines.append(f"SES: {karakter_text}")
    
    # 8. Yapı (structure)
    yapi_text = YAPI_LITE.get(yapi, "")
    if yapi_text:
        lines.append(f"YAPI: {yapi_text}")
    
    # 9. Açılış (hook) — only if not otomatik
    acilis_text = ACILIS_LITE.get(acilis, "")
    if acilis_text:
        lines.append(f"AÇILIŞ: {acilis_text}")
    
    # 10. Bitiş (ending) — only if not otomatik
    bitis_text = BITIS_LITE.get(bitis, "")
    if bitis_text:
        lines.append(f"BİTİŞ: {bitis_text}")
    
    # 11. Derinlik — only if not standart
    derinlik_text = DERINLIK_LITE.get(derinlik, "")
    if derinlik_text:
        lines.append(f"DERİNLİK: {derinlik_text}")
    
    # 12. Style clone (if active)
    if style_prompt:
        lines.append(f"STİL PROFİLİ (buna sadık kal): {style_prompt}")
    
    # 13. Example tweets (if any)
    if example_tweets:
        examples = "\n".join(f"- {t}" for t in example_tweets[:3])
        lines.append(f"REFERANS TWEET'LER (stili referans al, kopyalama):\n{examples}")
    
    # 14. Ultra mode
    if is_ultra:
        lines.append(ULTRA_LITE)
    
    # 15. Context
    if additional_context:
        lines.append(f"EK BAĞLAM: {additional_context}")
    
    if trend_context:
        lines.append(f"TREND: {trend_context}")
    
    # 16. Topic (last, so it's fresh in model's memory)
    if topic:
        lines.append(f"KONU: {topic}")
    
    return "\n\n".join(lines)


# ===================== RE-EXPORT for compatibility =====================

def validate_settings(etki: str, karakter: str, yapi: str) -> dict:
    """Validate setting combination."""
    warnings = []
    compat = KARAKTER_YAPI_UYUM.get(karakter, {})
    if compat and not compat.get(yapi, True):
        warnings.append(f"Uyumsuz kombinasyon: {karakter} + {yapi}")
    return {"valid": len(warnings) == 0, "warnings": warnings}


# Convenience: import heavy prompt modules for settings endpoints
from .etki import ETKILER
from .karakter_v2 import KARAKTERLER
from .yapi import YAPILAR
from .acilis import ACILISLAR
from .bitis import BITISLER
from .derinlik import DERINLIKLER


__all__ = [
    'build_final_prompt_v2_lite',
    'validate_settings',
    'get_smart_defaults',
    'ETKILER', 'KARAKTERLER', 'YAPILAR',
    'ACILISLAR', 'BITISLER', 'DERINLIKLER',
    'UZUNLUK_LIMITS',
]
