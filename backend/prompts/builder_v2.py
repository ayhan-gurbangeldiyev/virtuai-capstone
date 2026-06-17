# ContentFactory - Prompt Builder v2
# New settings system: Etki, Karakter, Yapı, Uzunluk, Açılış, Bitiş, Derinlik
# Only for X (Twitter) platform. Other platforms use builder.py (v1)

from .etki import ETKILER
from .karakter_v2 import KARAKTERLER, KARAKTER_YAPI_UYUM
from .yapi import YAPILAR
from .acilis import ACILISLAR
from .bitis import BITISLER
from .derinlik import DERINLIKLER
from .smart_defaults import get_smart_defaults

from .system_identity import SYSTEM_IDENTITY
from .algorithm import (
    ALGORITHM_KNOWLEDGE,
    CONTENT_RULES,
)
from .quality import (
    QUALITY_CRITERIA,
    LENGTH_CONSTRAINTS,
    REPLY_MODES,
    ARTICLE_STYLES,
)


# ===================== HARD BLOCK =====================
HARD_BLOCK_V2 = """## MUTLAK YASAKLAR (İHLAL = GEÇERSİZ OUTPUT)

Aşağıdaki kelime ve kalıpları İÇEREN herhangi bir output reddedilir:
- "devrim" (devrim niteliğinde, devrim yaratıyor, devrim başlatıyor dahil)
- "çığır açan" / "oyun değiştirici" / "game changer"
- "hazır mısınız" / "hazır mıyız" / "hazır olun"
- "yeni bir dönem" / "yeni bir çağ" / "yeni bir sayfa"
- "kapıları açıyor" / "kapıları açacak" / "kapısını açıyor"
- "sınırları zorlayan" / "sınırları aşan"
- "inovasyon" / "transformasyon" / "paradigma"
- "düşünmek lazım" / "düşünmek gerek"
- "hadi bakalım" / "bir düşünün" / "merak etmeyin"
- "siz ne düşünüyorsunuz" (tam olarak bu kalıp)
- "muhteşem" / "harika" / "inanılmaz" / "olağanüstü"

Hashtag YASAK. Emoji YASAK (Shitpost etki hariç, onda max 1-2).

Bu listedeki hiçbir kelimeyi, hiçbir bağlamda, hiçbir şekilde kullanma.
Bunun yerine spesifik, somut, günlük dilde yaz."""


# ===================== HUMANIZER =====================
HUMANIZER = """## İNSAN GİBİ YAZ

Bu tweet bir insan yazdı gibi hissettirmeli. AI çıktısı gibi hissettirirse başarısız.

Kurallar:
- Gerçek bir insan Twitter'da nasıl yazarsa öyle yaz.
- Mükemmel gramer şart değil. Doğal Türkçe yaz, çeviri gibi olmasın.
- Klişe cümleler YASAK. "Bu sadece başlangıç", "Gelin birlikte keşfedelim" gibi AI kalıpları kullanma.
- Her tweet benzersiz olsun. Aynı cümle yapısını tekrarlama.
- Kısa cümleler, konuşma dili, net ifadeler.
- Tweet metnini tırnak içine alma. Başına "Tweet:" ekleme. Sadece tweet'in kendisini yaz.
- Alternatif versiyon sunma. "Veya:" diye ikinci seçenek yazma. TEK tweet yaz."""


# ===================== TASK DEFINITIONS =====================
TASK_DEFS_V2 = {
    "tweet": """## GÖREV: TWEET ÜRET

Verilen konuya göre tweet yaz.
Dikkat çekici başla, değer kat, güçlü bitir.
Thread ise her tweet bağımsız değer versin.""",

    "quote": """## GÖREV: QUOTE TWEET YAZ

Verilen orijinal tweet'e quote tweet yaz.
Sadece "katılıyorum" gibi boş yorumlar YASAK.
Kendi perspektifini ekle, değer kat.

Orijinal Tweet:
{original_tweet}""",

    "reply": """## GÖREV: REPLY YAZ

Verilen tweet'e reply yaz.
Konuşma başlatacak veya değer katacak şekilde yaz.
Authentic ol, yapay övgü/eleştiri yapma.

Reply Atacağın Tweet:
{original_tweet}""",

    "article": """## GÖREV: X ARTICLE YAZ

X/Twitter'ın uzun form Article formatında içerik üret.
Güçlü giriş, mantıklı akış, net takeaway'ler.""",
}


# ===================== ULTRA MODE =====================
ULTRA_PROMPT = """## ⚡ ULTRA MODE AKTİF

Bu içerik ULTRA modda üretiliyor. Maximum kalite.

Ek kurallar:
- Her kelime yerinde olmalı. Gereksiz hiçbir şey yok.
- Hook kalitesi maximum. İlk cümle mükemmel olmalı.
- Insight derinliği maximum. Yüzeysel bilgi yasak.
- Punchline kalitesi maximum. Son cümle akılda kalmalı.
- Bu tweet'i 10 kez yazsaydın, en iyisi bu olmalı.
- Orijinal ol. Daha önce söylenmemiş bir şey söyle veya bilinen bir şeyi hiç söylenmemiş bir şekilde söyle."""


# ===================== BUILDER FUNCTIONS =====================

def _build_etki_section(etki_id: str) -> str:
    """Build the Etki (goal/intent) prompt section."""
    etki = ETKILER.get(etki_id)
    if not etki:
        etki = ETKILER["patlassin"]
    return etki["prompt"]


def _build_karakter_section(karakter_id: str) -> str:
    """Build the Karakter (character/voice) prompt section."""
    karakter = KARAKTERLER.get(karakter_id)
    if not karakter:
        karakter = KARAKTERLER["uzman"]
    return karakter["prompt"]


def _build_yapi_section(yapi_id: str) -> str:
    """Build the Yapı (structure/tone) prompt section."""
    yapi = YAPILAR.get(yapi_id)
    if not yapi:
        yapi = YAPILAR["dogal"]
    return yapi["prompt"]


def _build_acilis_section(acilis_id: str) -> str:
    """Build the Açılış (hook) prompt section."""
    acilis = ACILISLAR.get(acilis_id)
    if not acilis:
        acilis = ACILISLAR["otomatik"]
    return acilis["prompt"]


def _build_bitis_section(bitis_id: str) -> str:
    """Build the Bitiş (CTA/ending) prompt section."""
    bitis = BITISLER.get(bitis_id)
    if not bitis:
        bitis = BITISLER["otomatik"]
    return bitis["prompt"]


def _build_derinlik_section(derinlik_id: str) -> str:
    """Build the Derinlik (knowledge depth) prompt section."""
    derinlik = DERINLIKLER.get(derinlik_id)
    if not derinlik:
        return ""
    return derinlik["prompt"]


def _build_length_section(uzunluk_id: str, content_type: str = "tweet") -> str:
    """Build AGGRESSIVE length constraint. This is a HARD limit, not guidance."""
    # Hard character limits per uzunluk
    HARD_LIMITS = {
        "tweet": {
            "micro": (50, 100, "TEK CÜMLE. Maximum 100 karakter. Bir nefeste okunacak kadar kısa."),
            "punch": (100, 280, "1-2 cümle. Maximum 280 karakter. Klasik tweet uzunluğu."),
            "spark": (280, 600, "Bir paragraf. Maximum 600 karakter."),
            "storm": (500, 1000, "Uzun tweet. Maximum 1000 karakter."),
            "thread": (800, 2500, "Thread formatı. 3-7 tweet, numaralandır (1/, 2/, 3/)."),
        },
        "reply": {
            "micro": (30, 100, "Kısa yanıt. Maximum 100 karakter."),
            "punch": (80, 280, "Normal yanıt. Maximum 280 karakter."),
            "spark": (200, 600, "Detaylı yanıt. Maximum 600 karakter."),
        },
        "quote": {
            "micro": (30, 100, "Kısa yorum. Maximum 100 karakter."),
            "punch": (80, 280, "Normal yorum. Maximum 280 karakter."),
            "spark": (200, 600, "Detaylı yorum. Maximum 600 karakter."),
        },
    }
    
    limits = HARD_LIMITS.get(content_type, HARD_LIMITS.get("tweet", {}))
    entry = limits.get(uzunluk_id)
    
    if not entry:
        return ""
    
    min_c, max_c, desc = entry
    
    return f"""## ⚠️ UZUNLUK LİMİTİ (KESİN KURAL)

**{desc}**

HARD LIMIT: {min_c}-{max_c} karakter. Bu aralığın DIŞINA ÇIKMA.
- {max_c} karakteri aşarsan output GEÇERSİZ sayılır.
- Sayma yöntemi: boşluklar ve noktalama dahil tüm karakterler.
- Kısa yaz. Fazla açıklama yapma. Her kelime kazanılmış olmalı.
- {max_c} karakter = MUTLAK ÜST SINIR. Yaklaş ama AŞMA."""


def _build_style_clone_section(style_prompt: str) -> str:
    """Build style clone section if a style profile is active."""
    if not style_prompt:
        return ""
    return f"""## 🎨 STİL PROFİLİ (EN YÜKSEK ÖNCELİK)

Aşağıdaki stil profiline SADIK KAL. Bu profil diğer tüm ayarlardan önce gelir.
Karakter ve Yapı ayarları bu stile uyarlanmalı, tersi değil.

{style_prompt}"""


def _build_example_tweets_section(example_tweets: list) -> str:
    """Build few-shot example tweets section."""
    if not example_tweets:
        return ""
    section = "## 📝 ÖRNEK TWEET'LER (Referans stil)\n\nBu tweet'lerin tonunu ve stilini referans al, ama birebir kopyalama:\n\n"
    for i, tweet in enumerate(example_tweets[:5], 1):
        section += f"{i}. {tweet}\n"
    return section


# ===================== MAIN BUILDER =====================

def build_final_prompt_v2(
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
    """
    Build the complete v2 prompt for X (Twitter) content generation.

    Prompt order (designed to avoid contradictions):
    1. HARD_BLOCK - Absolute restrictions (first thing model sees)
    2. HUMANIZER - Write like a human (second priority)
    3. SYSTEM_IDENTITY - Core AI identity
    4. ALGORITHM_KNOWLEDGE - X algorithm context
    5. ETKI - Goal/intent (strategic direction)
    6. TASK_DEFINITION - What to produce
    7. STYLE_CLONE - Style profile (highest content priority)
    8. EXAMPLE_TWEETS - Few-shot examples
    9. KARAKTER - Who is writing (voice)
    10. ACILIS - How to open (hook)
    11. YAPI - How to structure (format)
    12. DERINLIK - Knowledge perspective
    13. UZUNLUK - Length constraints
    14. BITIS - How to end (CTA)
    15. ULTRA - Ultra mode enhancements
    16. LANGUAGE - Language setting
    17. ADDITIONAL_CONTEXT - User's extra context
    18. TREND_CONTEXT - Trend information
    19. TOPIC - The actual topic
    20. QUALITY_CRITERIA - Quality checklist
    21. OUTPUT - Output instructions

    Returns:
        Complete prompt string
    """
    sections = []

    # 1. HARD BLOCK
    sections.append(HARD_BLOCK_V2)

    # 1.5 UZUNLUK (Length) — FIRST PRIORITY after hard block
    length_section = _build_length_section(uzunluk, content_type)
    if length_section:
        sections.append(length_section)

    # 2. HUMANIZER
    sections.append(HUMANIZER)

    # 3. SYSTEM IDENTITY
    sections.append(SYSTEM_IDENTITY)

    # 4. ALGORITHM KNOWLEDGE + CONTENT RULES
    sections.append(ALGORITHM_KNOWLEDGE)
    sections.append(CONTENT_RULES)

    # 5. ETKI (Goal)
    etki_section = _build_etki_section(etki)
    if etki_section:
        sections.append(etki_section)

    # 6. TASK DEFINITION
    task = TASK_DEFS_V2.get(content_type, TASK_DEFS_V2["tweet"])
    if original_tweet and "{original_tweet}" in task:
        task = task.format(original_tweet=original_tweet)
    sections.append(task)

    # 7. STYLE CLONE (highest content priority)
    style_section = _build_style_clone_section(style_prompt)
    if style_section:
        sections.append(style_section)

    # 8. EXAMPLE TWEETS
    examples_section = _build_example_tweets_section(example_tweets)
    if examples_section:
        sections.append(examples_section)

    # 9. KARAKTER (Voice)
    karakter_section = _build_karakter_section(karakter)
    if karakter_section:
        sections.append(karakter_section)

    # 10. ACILIS (Hook)
    acilis_section = _build_acilis_section(acilis)
    if acilis_section:
        sections.append(acilis_section)

    # 11. YAPI (Structure)
    yapi_section = _build_yapi_section(yapi)
    if yapi_section:
        sections.append(yapi_section)

    # 12. DERINLIK (Knowledge depth)
    derinlik_section = _build_derinlik_section(derinlik)
    if derinlik_section:
        sections.append(derinlik_section)

    # 13. (UZUNLUK moved to position 1.5)

    # 14. REPLY MODE (for replies)
    if content_type == "reply" and reply_mode:
        reply_modes = REPLY_MODES or {}
        rm = reply_modes.get(reply_mode, "")
        if rm:
            sections.append(f"## REPLY MODU\n\n{rm}")

    # 15. BITIS (Ending/CTA)
    bitis_section = _build_bitis_section(bitis)
    if bitis_section:
        sections.append(bitis_section)

    # 16. ULTRA MODE
    if is_ultra:
        sections.append(ULTRA_PROMPT)

    # 17. LANGUAGE
    lang_map = {
        "auto": "Konunun diline göre otomatik olarak Türkçe veya İngilizce yaz. Konu Türkçe ise Türkçe, İngilizce ise İngilizce.",
        "tr": "Kesinlikle TÜRKÇE yaz. Tüm içerik Türkçe olmalı.",
        "en": "Write in ENGLISH only. All content must be in English."
    }
    sections.append(f"## DİL\n\n{lang_map.get(language, lang_map['auto'])}")

    # 18. ADDITIONAL CONTEXT
    if additional_context:
        sections.append(f"## EK BAĞLAM\n\n{additional_context}")

    # 19. TREND CONTEXT
    if trend_context:
        sections.append(f"## TREND BAĞLAMI\n\n{trend_context}")

    # 20. TOPIC
    if topic:
        sections.append(f"## KONU\n\n{topic}")

    # 21. QUALITY CRITERIA
    sections.append(QUALITY_CRITERIA)

    # 22. OUTPUT INSTRUCTIONS (with length reminder)
    # Build length reminder
    CHAR_LIMITS_MAP = {
        "micro": 100, "punch": 280, "spark": 600, "storm": 1000, "thread": 2500,
    }
    char_limit = CHAR_LIMITS_MAP.get(uzunluk, 280)
    
    output_instruction = f"""## ÇIKTI

Sadece içeriğin kendisini yaz. Açıklama, meta bilgi, "İşte tweet:" gibi girişler yasak.
"Veya:", "Alternatif:" gibi ikinci seçenek sunma. TEK output yaz.
Thread ise numaralandır (1/, 2/, 3/). Tek içerik ise düz metin.
Tırnak işareti kullanma. Direkt tweet metnini yaz.

⚠️ HATIRLATMA: Maximum {char_limit} karakter. Bu limiti AŞMA."""
    sections.append(output_instruction)

    # Combine
    return "\n\n---\n\n".join(s for s in sections if s)


# ===================== VALIDATION =====================

def validate_settings(etki: str, karakter: str, yapi: str) -> dict:
    """Validate setting combination. Returns warnings if incompatible."""
    warnings = []

    # Check karakter-yapi compatibility
    compat = KARAKTER_YAPI_UYUM.get(karakter, {})
    if compat and not compat.get(yapi, True):
        warnings.append(
            f"'{KARAKTERLER.get(karakter, {}).get('name', karakter)}' karakteri ile "
            f"'{YAPILAR.get(yapi, {}).get('name', yapi)}' yapısı uyumsuz. "
            f"Çelişkili çıktılar üretebilir."
        )

    return {
        "valid": len(warnings) == 0,
        "warnings": warnings,
    }


# Export
__all__ = [
    'build_final_prompt_v2',
    'validate_settings',
    'get_smart_defaults',
    'ETKILER',
    'KARAKTERLER',
    'YAPILAR',
    'ACILISLAR',
    'BITISLER',
    'DERINLIKLER',
]
