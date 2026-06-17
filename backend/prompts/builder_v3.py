# ContentFactory - Prompt Builder v3
# 5-section architecture: GÖREV → SES → KURALLAR → ÖRNEKLER → SON KONTROL
# Designed for single-pass quality over constraint overload

from .personas import PERSONAS
from .tones import TONES
from .knowledge import KNOWLEDGE_MODES
from .quality import LENGTH_CONSTRAINTS, REPLY_MODES, ARTICLE_STYLES, APEX_MODE

from .linkedin import LINKEDIN_SYSTEM_PROMPT
from .instagram import INSTAGRAM_SYSTEM_PROMPT
from .blog import BLOG_SYSTEM_PROMPT
from .youtube import YOUTUBE_SYSTEM_PROMPT
from .tiktok import TIKTOK_SYSTEM_PROMPT

# ─────────────────────────────────────────────
# SECTION 1: GÖREV (Task)
# ─────────────────────────────────────────────

_TASK_TEMPLATES = {
    "tweet": "Verilen konuya göre tweet yaz. Scroll durdurucu açılış, net mesaj, değer katan içerik.",
    "quote": "Aşağıdaki tweet'e quote tweet yaz. Boş övgü yasak — kendi perspektifini ekle, değer kat.\n\nOrijinal tweet:\n{original_tweet}",
    "reply": "Aşağıdaki tweet'e reply yaz. Bağlama uygun, değer katan, doğal bir yanıt.\n\nReply atacağın tweet:\n{original_tweet}",
    "article": "X/Twitter Article formatında uzun form içerik yaz. Güçlü başlık, hooklu giriş, bölümlenmiş yapı, takeaway'li kapanış.",
    "linkedin": "LinkedIn için profesyonel içerik yaz. İlk 2-3 satır hook, kısa paragraflar, net insight.",
    "instagram": "Instagram için caption yaz. Hook ile başla, kısa paragraflar, engagement odaklı.",
    "blog": "Blog yazısı yaz. SEO uyumlu yapı, örneklerle desteklenmiş, actionable sonuç.",
    "youtube": "YouTube için içerik yaz. CTR optimize başlık, retention odaklı yapı.",
    "tiktok": "TikTok için kısa form video scripti yaz. İlk 1-3 saniye hook, hızlı tempo, loop-friendly.",
}


_DIRECTION_RULES = {
    "support": "⚠️ YÖN: Bu tweet'e KATIL ve DESTEKLE. Üstüne koy, güçlendir, ek perspektif sun. Karşı çıkma.",
    "oppose": "⚠️ YÖN: Bu tweet'e KARŞI ÇIK. Zıt görüş belirt, argümanı çürüt veya sorgula. Ama saygılı kal, trolleme.",
    "add": "⚠️ YÖN: Bu tweet'in ÜSTÜNE BİLGİ EKLE. Yeni bir perspektif, veri, örnek veya bağlam sun. Tekrar etme, değer kat.",
    "roast": "⚠️ YÖN: Bu tweet'le DALGA GEÇ. İronik, komik, zekice yaklaş. Kırıcı değil eğlenceli ol. Shitpost energy.",
}


def _build_gorev(content_type: str, topic: str = None, original_tweet: str = None,
                 reply_mode: str = None, article_style: str = None,
                 references: list = None, additional_context: str = None,
                 direction: str = None, direction_custom: str = None) -> str:
    """Section 1: GÖREV — ne üretilecek."""
    task = _TASK_TEMPLATES.get(content_type, _TASK_TEMPLATES["tweet"])
    if original_tweet and "{original_tweet}" in task:
        task = task.format(original_tweet=original_tweet)

    parts = [f"## GÖREV\n\n{task}"]

    # Direction (quote/reply yönlendirme)
    if content_type in ("quote", "reply"):
        if direction_custom:
            parts.append(f"⚠️ YÖN (kullanıcı talimatı): {direction_custom}")
        elif direction and direction in _DIRECTION_RULES:
            parts.append(_DIRECTION_RULES[direction])

    if reply_mode and reply_mode in REPLY_MODES:
        rm = REPLY_MODES[reply_mode]
        parts.append(f"Reply modu: {rm['name']} — {rm['approach']}")

    if article_style and article_style in ARTICLE_STYLES:
        ast = ARTICLE_STYLES[article_style]
        parts.append(f"Makale stili: {ast['name']} — {ast['structure']}")

    if references:
        parts.append("Referanslar:\n" + "\n".join(f"• {r}" for r in references))

    if additional_context:
        parts.append(f"Ek bağlam: {additional_context}")

    if topic:
        parts.append(f"Konu: {topic}")

    return "\n\n".join(parts)


# ─────────────────────────────────────────────
# SECTION 2: SES (Voice = Style > Persona > Tone)
# ─────────────────────────────────────────────

_PLATFORM_PROMPTS = {
    "linkedin": LINKEDIN_SYSTEM_PROMPT,
    "instagram": INSTAGRAM_SYSTEM_PROMPT,
    "blog": BLOG_SYSTEM_PROMPT,
    "youtube": YOUTUBE_SYSTEM_PROMPT,
    "tiktok": TIKTOK_SYSTEM_PROMPT,
}

def _extract_persona_essence(persona_id: str) -> str:
    """Persona'nın özünü 3-5 cümleye sıkıştır.
    2026-06-08: 'otorite' deleted from PERSONAS (was pushing contrarian
    voice into every draft). Fallback is now 'uzman'."""
    if not persona_id:
        return ""
    p = PERSONAS.get(persona_id) or PERSONAS.get("uzman") or PERSONAS.get("saf")
    if not p:
        return ""
    identity = p.get("identity", "").strip()
    voice = p.get("voice_characteristics", [])
    voice_str = ", ".join(voice[:3]) if voice else ""
    avoid = p.get("avoid", [])
    avoid_str = ", ".join(avoid[:3]) if avoid else ""

    lines = [f"Persona: {p['name']} — {p['description']}"]
    if identity:
        # Take first 2 sentences of identity
        sentences = [s.strip() for s in identity.replace("\n", " ").split(".") if s.strip()]
        lines.append(". ".join(sentences[:2]) + ".")
    if voice_str:
        lines.append(f"Ses: {voice_str}.")
    if avoid_str:
        lines.append(f"Kaçın: {avoid_str}.")
    return "\n".join(lines)


def _extract_tone_essence(tone_id: str) -> str:
    """Ton'un özünü 2-3 cümleye sıkıştır."""
    t = TONES.get(tone_id, TONES.get("natural"))
    if not t:
        return ""
    core = t.get("core_principle", "").strip().replace("\n", " ")
    # Take first sentence of core principle
    sentences = [s.strip() for s in core.split(".") if s.strip()]
    first = ". ".join(sentences[:2]) + "." if sentences else ""

    dos = t.get("dos_and_donts", {}).get("do", [])[:3]
    donts = t.get("dos_and_donts", {}).get("dont", [])[:3]

    lines = [f"Ton: {t['name']} — {t['description']}"]
    if first:
        lines.append(first)
    if dos:
        lines.append("Yap: " + ", ".join(dos) + ".")
    if donts:
        lines.append("Yapma: " + ", ".join(donts) + ".")
    return "\n".join(lines)



BASE_PROHIBITIONS = """
### Kırılmaz Yasaklar
- AI kalıpları YASAK: "Unutmayın ki", "Sonuç olarak", "İşte size", "Siz ne düşünüyorsunuz?"
- Emoji, hashtag, üç nokta (...), clickbait ("İşin sırrı...") YASAK
- Tespitini yap ve BIRAK. Açıklama, özet, soru ile bitirme.
"""

# ═══════════════════════════════════════════
# TONE VOICE GUIDES — Her ton için "nasıl yaz" kılavuzu
# ═══════════════════════════════════════════

TONE_VOICE_GUIDES = {
    "witty": {
        "label": "Esprili",
        "voice": "Keskin ironi, beklenmedik final, deadpan humor. Espriyi yap ve orada bırak, açıklama. Okuyucu 2 saniye düşünsün, sonra gülsün.",
        "hook": "İronik zıtlık veya absürt bir gözlemle aç. Herkesin bildiği bir şeyi ters çevir.",
        "example_energy": "Twitter'daki 'ölüm' esprileri. Kuru, zeki, acımasız.",
    },
    "aggressive": {
        "label": "Agresif",
        "voice": "Direkt, korkusuz, tartışma başlat. Hot take formatı. Özür dileme, yumuşatma, 'ama tabii herkesin fikri farklı olabilir' ekleme.",
        "hook": "Sarsıcı bir iddia veya meydan okumayla aç. Popüler bir görüşe direkt karşı çık.",
        "example_energy": "Tartışma başlatan, insanların RT yapıp 'buna katılmıyorum ama...' dediği tweetler.",
    },
    "informative": {
        "label": "Bilgi Verici",
        "voice": "Veriyle konuş, insight ver. 'Bunu bilmiyordunuz' hissi yarat. Otorite ol ama ukala olma.",
        "hook": "Şaşırtıcı bir istatistik, az bilinen bir gerçek veya yaygın bir yanılgıyı yıkan bir cümleyle aç.",
        "example_energy": "'TIL (Today I Learned)' hissi. Okuyucu kaydedip paylaşmak istesin.",
    },
    "friendly": {
        "label": "Samimi",
        "voice": "1. tekil şahıs, kişisel deneyim, arkadaşına anlatıyormuş gibi. Samimi ama yüzeysel değil.",
        "hook": "Kişisel bir anekdot veya 'dün başıma şu geldi' formatıyla aç. Okuyucu kendini bulsun.",
        "example_energy": "Kahve sohbetindeki o zeki arkadaş. Rahat ama derin.",
    },
    "inspirational": {
        "label": "İlham Verici",
        "voice": "Vizyon çiz, büyük düşün. Motivasyonel klişeler YASAK. Gerçek deneyimden gelen bilgelik.",
        "hook": "'Ya şöyle olsaydı' veya geleceğe dair cesur bir öngörüyle aç.",
        "example_energy": "Steve Jobs keynote'u, motivasyonel poster değil. Büyük resmi gör, küçük adımı söyle.",
    },
}

# ═══════════════════════════════════════════
# CONTENT ARCHITECTURE — Twitter Ustalığı Kuralları
# ═══════════════════════════════════════════

CONTENT_ARCHITECTURE = """
### İçerik Mimarisi

**RİTİM:** Setup → satır boşluğu → Punchline. Blok metin yazma, nefes ver.
**SENTEZ:** Birden fazla ton varsa TEK ruh hali yarat (agresif+esprili = sarcastic). Bipolar olma.
**SHOW DON'T TELL:** Tespitini yap ve BIRAK. "Yani kısacası" diye açıklama.
**ORGANİKLİK:** İnsan gibi yaz — mükemmel akademik cümle değil, akıcı doğal cümle. Yazarın
kendi büyük/küçük harf tarzını (style profile veya brand voice'tan) izle. Eğer yazarın tarzı
belirtilmemişse sentence-case (normal Türkçe yazım) kullan. Tüm tweeti küçük harfle yazmayı
DEFAULT olarak ALMA — sadece yazarın stil profili açıkça küçük harf istiyorsa öyle yaz.
"""

# ═══════════════════════════════════════════
# FEW-SHOT EXAMPLES — Her ton için viral tweet örnekleri
# AI kuraldan çok örnekten öğrenir. Bunları kopyalama ama ritimlerini taklit et.
# ═══════════════════════════════════════════

FEW_SHOT_EXAMPLES = {
    "witty": [
        "herkes yapay zekadan iş kaybetmekten korkuyor\n\nkardeşim sen zaten 4 saat Excel'e bakıp 2 satır yazıyorsun, yapay zeka seni değil sen yapay zekayı kurtarırsın",
        "startup kurucuları \"başarısızlık öğreticidir\" diyor\n\nöğretici olan senin 3. pivot'un değil, yatırımcının yüz ifadesi",
        "linkedinde \"open to work\" yazanların %90'ı aslında open to compliment",
    ],
    "aggressive": [
        "herkes AI wrapper yapıp \"SaaS kurdum\" diyor\n\nbir API key'i .env'e yazmak seni founder yapmıyor",
        "\"network'ün net worth'ündür\" diyen adamın network'ü 3 tane LinkedIn motivasyon hesabı",
        "Turkish startup ekosistemi: aynı 50 kişi birbirinin eventine gidip \"ekosistem büyüyor\" diyor",
    ],
    "informative": [
        "OpenAI'ın yıllık geliri 2 milyar doları geçti ama hala kar etmiyor\n\nbu detayı atlayan herkes 2000'lerin dotcom balonunu da atlamış demektir",
        "RAG sistemlerinde chunk size 512 token üstüne çıkınca retrieval kalitesi %40 düşüyor\n\nkoca dokümanı olduğu gibi embedding'e atıp \"çalışmıyor\" diyenler burada mı",
        "Türkiye'de SaaS churn rate ortalaması %8-12\n\nABD'de bu %5. Fark onboarding'de, üründe değil",
    ],
    "friendly": [
        "geçen hafta müşteriyle toplantıdaydım, adam \"biz aslında ne istediğimizi bilmiyoruz\" dedi\n\nen dürüst brief buydu. keşke herkes böyle başlasa",
        "junior developer'ken her PR'da kalp krizi geçirirdim\n\nşimdi senior'ım, hala geçiriyorum ama artık bunu normalize ettim",
        "bir projede en çok zaman alan şey kod yazmak değil\n\nherkesin \"bence şöyle olmalı\"sını dinleyip ortak bir \"tamam şöyle yapalım\"a ulaşmak",
    ],
    "inspirational": [
        "herkes product-market fit arıyor\n\nasıl zor olan founder-problem fit. senin gerçekten umursadığın bir problem mi bu, yoksa pazar büyük diye mi girdin",
        "10 yıl önce \"mobil first\" dediler herkes güldü\n\nşimdi \"AI first\" diyenlere de gülüyorlar. pattern aynı, sadece gülenlerin ömrü kısalıyor",
        "en iyi kariyer hamlelerim hep \"mantıksız\" denen şeylerdi\n\nspreadsheet'ler güvenli hissettirir ama hayat spreadsheet'te yaşanmıyor",
    ],
}


def _build_brand_voice_section(brand_voice: dict = None) -> str:
    """Brand Voice DNA from Creator Hub profile. Background layer, overridden by persona/tone."""
    if not brand_voice:
        return BASE_PROHIBITIONS
    tones = brand_voice.get("tones", {})
    principles = brand_voice.get("principles", [])
    avoid = brand_voice.get("avoid", [])
    sample_voice = brand_voice.get("sample_voice", "")
    active_tones = {k: v for k, v in tones.items() if v > 0}
    if not active_tones and not principles and not avoid and not sample_voice:
        return ""
    parts = ["### Marka DNA (Arka Plan)"]
    parts.append("Bu kullanıcının genel yazım eğilimidir. Persona ve Ton seçimleri bunu override edebilir.")
    if active_tones:
        sorted_tones = sorted(active_tones.items(), key=lambda x: -x[1])
        dominant = sorted_tones[:2]
        minor = sorted_tones[2:]

        # Dominant tonların voice guide'larını ekle
        for key, val in dominant:
            guide = TONE_VOICE_GUIDES.get(key)
            if guide:
                parts.append(f"\n**ANA TON: %{val} {guide['label']}**")
                parts.append(f"Ses: {guide['voice']}")
                parts.append(f"Hook: {guide['hook']}")

        # Sentez ipucu (2+ dominant ton varsa)
        if len(dominant) >= 2:
            k1, v1 = dominant[0]
            k2, v2 = dominant[1]
            l1 = TONE_VOICE_GUIDES.get(k1, {}).get("label", k1)
            l2 = TONE_VOICE_GUIDES.get(k2, {}).get("label", k2)
            parts.append(f"\nSENTEZ: {l1} + {l2} tonlarını ayrı cümleler olarak değil, TEK bir ruh halinde birleştir.")

        if minor:
            min_parts = [f"%{v} {TONE_VOICE_GUIDES.get(k, {}).get('label', k)}" for k, v in minor if v >= 10]
            if min_parts:
                parts.append(f"Hafif dokunuş: {', '.join(min_parts)}")

    # Target Audience
    audience = brand_voice.get("target_audience")
    if audience:
        audience_guides = {
            "beginners": "HEDEF KİTLE: Yeni başlayanlar. Basit dil, sıfır jargon, açıklayıcı ama patronluk taslama.",
            "professionals": "HEDEF KİTLE: Sektör profesyonelleri. Mesleki derinlik, teknik terimler kullanabilirsin, 101 seviyesi değil.",
            "clevel": "HEDEF KİTLE: C-Level yöneticiler. Stratejik ve vizyoner dil, ROI/impact odaklı, kısa ve özlü.",
            "founders": "HEDEF KİTLE: Girişimciler ve yatırımcılar. Büyüme metrikleri, pazar dinamikleri, cesur öngörüler.",
        }
        guide = audience_guides.get(audience)
        if guide:
            parts.append(f"\n{guide}")

    # Content Architecture (her zaman)
    parts.append(CONTENT_ARCHITECTURE)
    # Pre-defined chip key → label mapping
    principle_labels = {
        "concise": "Kısa ve Öz", "data-driven": "Veri Odaklı", "question-hook": "Soru ile Başla",
        "storytelling": "Hikayeleştirici", "actionable": "Uygulanabilir Tavsiye", "personal": "Kişisel Deneyim",
        "contrarian": "Karşıt Görüş", "educational": "Öğretici", "thread-style": "Thread Formatı", "visual-first": "Görsel Ağırlıklı",
    }
    avoid_labels = {
        "emoji-spam": "Emoji Spam", "clickbait": "Tıklama Tuzağı", "corporate": "Kurumsal Dil",
        "slang": "Aşırı Argo", "generic": "Genel Geçer Klişe", "self-promo": "Sürekli Reklam",
        "negativity": "Negatif Ton", "jargon": "Teknik Jargon", "long-winded": "Gereksiz Uzun", "hashtag-spam": "Hashtag Spam",
    }
    if principles:
        p_labels = [principle_labels.get(p, p) for p in principles[:5]]
        parts.append(f"İLKELER: {', '.join(p_labels)}")
    if avoid:
        a_labels = [avoid_labels.get(a, a) for a in avoid[:5]]
        parts.append(f"YASAKLAR: {', '.join(a_labels)}")

    # Few-shot örnekler (dominant tonlara göre)
    if active_tones:
        sorted_for_examples = sorted(active_tones.items(), key=lambda x: -x[1])
        examples = []
        for key, _ in sorted_for_examples[:2]:
            examples.extend(FEW_SHOT_EXAMPLES.get(key, []))
        if examples:
            parts.append("\nÖRNEK TWEETLER (bu ritimde yaz, kopyalama):")
            for i, ex in enumerate(examples[:3], 1):
                parts.append(f"  {i}. {ex}")

    parts.append(BASE_PROHIBITIONS)
    return chr(10).join(parts)


def _build_ses(persona: str, tone: str, style_prompt: str = None,
               platform: str = "twitter", content_type: str = "tweet",
               brand_voice: dict = None,
               voice_mode: str = None) -> str:
    """Section 2: SES — nasıl seslenecek. Öncelik: stil > tonal_çerçeve > persona > ton.

    Phase 25.C: `voice_mode` (first_person_witty / third_person_neutral / hybrid)
    appends a "Tonal Çerçeve" block AFTER style DNA but BEFORE persona — Style
    Lab clone style still wins on word choice; voice_mode shapes WHO is talking
    (1st vs 3rd person) and ABOUT WHAT (personal reaction vs neutral reporting).
    """
    parts = ["## SES\n"]

    # Platform-specific voice (non-Twitter platforms have their own system prompts)
    platform_key = content_type if content_type in _PLATFORM_PROMPTS else platform
    if platform_key in _PLATFORM_PROMPTS:
        # Phase 37 — Inject more of each platform's system prompt (was 8 lines,
        # too thin for tone differentiation; LinkedIn.py = 250w but only first
        # 8 lines reached LLM → Twitter/IG/LinkedIn ended up identical tone).
        # Now ~30 lines, keeps platform conventions (structure, banned
        # phrases, hashtag rules) intact.
        prompt = _PLATFORM_PROMPTS[platform_key]
        lines = [l.strip() for l in prompt.strip().split("\n") if l.strip() and not l.startswith("#")]
        platform_essence = "\n".join(lines[:30])
        if platform_essence:
            parts.append(f"### Platform Sesi\n{platform_essence}")

    # Style DNA (highest priority)
    if style_prompt:
        parts.append(f"### Stil DNA (EN YÜKSEK ÖNCELİK)\n{style_prompt}\n\nBu kişinin ağzından çıkmış gibi yaz. Kelime seçimi, cümle yapısı, ritim hep bu stilde. Çakışma olursa stil kazanır.")

    # Phase 25.C — Voice mode frame (1st vs 3rd person rotation)
    if voice_mode:
        try:
            from prompts.voice_modes import get_voice_mode_block
        except ImportError:
            from .voice_modes import get_voice_mode_block  # type: ignore[no-redef]
        vm_block = get_voice_mode_block(voice_mode)
        if vm_block:
            parts.append(vm_block)

    # Persona essence
    persona_text = _extract_persona_essence(persona)
    if persona_text:
        parts.append(f"### Karakter\n{persona_text}")

    # Tone essence
    tone_text = _extract_tone_essence(tone)
    if tone_text:
        parts.append(f"### Ton\n{tone_text}")

    # Brand Voice DNA (background layer)
    bv_section = _build_brand_voice_section(brand_voice)
    if bv_section:
        parts.append(bv_section)

    # Twitter-specific base voice (only if no platform prompt)
    if platform == "twitter" and content_type in ("tweet", "quote", "reply", "article"):
        if platform_key not in _PLATFORM_PROMPTS:
            parts.append("Gerçek bir Twitter kullanıcısı gibi yaz. Kısa cümleler, spesifik ol, emoji kullanma.")

    return "\n\n".join(parts)


# ─────────────────────────────────────────────
# SECTION 3: KURALLAR (Rules)
# ─────────────────────────────────────────────

def _build_kurallar(content_type: str, length: str, language: str,
                    knowledge: str = None, platform: str = "twitter") -> str:
    """Section 3: KURALLAR — length + platform + language + knowledge, kısa maddeler."""
    rules = ["## KURALLAR\n"]

    # Length
    type_constraints = LENGTH_CONSTRAINTS.get(content_type, LENGTH_CONSTRAINTS.get("tweet", {}))
    length_data = type_constraints.get(length, list(type_constraints.values())[0] if type_constraints else None)
    if length_data:
        min_c, max_c = length_data["chars"]
        rules.append(f"- Uzunluk: {min_c}–{max_c} karakter ({length_data['label']}). Bu aralığın dışına çıkma.")

    # Language
    lang_map = {
        "auto": "- Dil: Konunun diline göre Türkçe veya İngilizce.",
        "tr": "- Dil: Kesinlikle Türkçe yaz.",
        "en": "- Language: Write in English only.",
    }
    rules.append(lang_map.get(language, lang_map["auto"]))

    # Knowledge mode (condensed)
    if knowledge and knowledge in KNOWLEDGE_MODES:
        km = KNOWLEDGE_MODES[knowledge]
        rules.append(f"- Bilgi modu: {km['name']} — {km['description']}")

    # Content type specific
    if content_type == "thread":
        rules.append("- Thread formatı: Her tweet numaralı (1/, 2/, 3/), her biri bağımsız değer versin.")
    elif content_type in ("tweet", "quote", "reply"):
        rules.append("- Sadece içeriği yaz. Açıklama, 'İşte tweet:' gibi girişler yasak.")
        rules.append("- Thread ise numaralandır (1/, 2/, 3/). Tek içerik ise düz metin.")

    # Phase 33 — MUTLAK YASAK: AI disclosure / persona disclaimer
    rules.append(
        "- ⛔ MUTLAK YASAK — AI olduğunu açıklama, disclaimer, disclosure, "
        "imza, footer ekleme. Şu öğelerin HİÇBİRİ kullanılamaz: "
        "`#AIcreated`, `#AI`, `#AIgenerated`, `#AIpersona`, "
        "`AI persona`, `AI tarafından üretildi`, `autonomous persona`, "
        "`AI-generated`, `Generated by AI`, `🤖 AI`, `— Cansu, AI persona`, "
        "`*This article is generated by ...AI...*` veya bunların herhangi bir "
        "çeşidi. İçerik, tamamen gerçek bir kişi yazmış gibi okunmalı; "
        "kendini hiçbir biçimde AI olarak tanıtma. Bu kural mutlak, ihlal etme."
    )

    return "\n".join(rules)


# ─────────────────────────────────────────────
# SECTION 4: ÖRNEKLER (Examples / Few-shot)
# ─────────────────────────────────────────────

def _build_ornekler(example_tweets: list = None) -> str:
    """Section 4: ÖRNEKLER — few-shot RAG, varsa."""
    if not example_tweets:
        return ""

    tweets = example_tweets[:15]
    lines = ["## ÖRNEKLER\n\nBu kişinin gerçek tweet'leri. Kopyalama, ama aynı kişi yazmış gibi hissettir.\n"]

    for i, tweet in enumerate(tweets, 1):
        content = tweet.get("content", "") if isinstance(tweet, dict) else str(tweet)
        if len(content) > 400:
            content = content[:397] + "..."

        # Engagement tag
        tag = ""
        if isinstance(tweet, dict):
            likes = tweet.get("likes", 0)
            rts = tweet.get("retweets", 0)
            if likes >= 100 or rts >= 20:
                tag = f" [🔥 {likes}♡ {rts}RT]"

        lines.append(f"{i}. {content}{tag}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# SECTION 5: SON KONTROL (Final Checklist)
# ─────────────────────────────────────────────

_BANNED_WORDS = [
    "devrim", "çığır açan", "oyun değiştirici", "game changer",
    "hazır mısınız", "hazır mıyız", "hazır olun",
    "yeni bir dönem", "yeni bir çağ", "yeni bir sayfa",
    "kapıları açıyor", "kapıları açacak", "kapısını açıyor",
    "sınırları zorlayan", "sınırları aşan",
    "inovasyon", "transformasyon", "paradigma",
    "düşünmek lazım", "düşünmek gerek",
    "hadi bakalım", "bir düşünün", "merak etmeyin",
    "siz ne düşünüyorsunuz",
    "muhteşem", "harika", "inanılmaz", "olağanüstü",
    # Phase 43.H.3 — n8n parity. Rhetorical-question closers that scream
    # "AI wrote this", boilerplate journalism openers/closers, and the
    # "exciting!" filler that adds zero signal.
    "peki sizce", "peki siz",
    "merak ediyorsanız", "merak edenler için",
    "bu yazıda", "bu içerikte",
    "sonuç olarak", "özetle",
    "heyecan verici",
]

_BANNED_LIST_STR = ", ".join(f'"{w}"' for w in _BANNED_WORDS)


def _build_son_kontrol() -> str:
    """Section 5: SON KONTROL — yasaklar + kalite, 'göndermeden önce kontrol et' framing."""
    return f"""## SON KONTROL — Göndermeden önce kontrol et

1. **GROUNDING (kırılmaz — Berkay 6 Haz 2026):**
   - Her iddia, sayı, marka, ürün, kişi, olay, ortaklık türü, sebep-sonuç
     ilişkisi **## KAYNAK METİN** içinde geçiyor mu? Geçmiyorsa SİL.
   - Spesifikleri koru: kaynak "Fast modda 2.5×" diyorsa, "2.5×" değil
     "Fast modda 2.5×" yaz. Genelleme yasak.
   - Kaynakta yer almayan ürün/teknoloji adı (örn. "Starlink", "Llama 3",
     "MGSM", "CVE-2026-48095") YAZMA. Yoksa uydurma.
   - Kaynak X'i söylüyorsa Y'yi (Y ≠ X'in doğrudan implikasyonu) çıkarma.
   - STANCE vs FACT ayrımı: Cansu'nun yorumu kayıtlı bir fact'i yeniden
     çerçeveleyebilir, ama YENİ entity / sayı / olay / ürün ileri süremez.
   - Bu kontrol post-generation faithfulness gate ile de doğrulanacak;
     başarısız olursa draft pending_review'de kalır, asla otomatik
     yayınlanmaz.

2. **Yasaklı kelimeler:** Şu kelime/kalıpları kullandıysan output geçersiz, baştan yaz:
   {_BANNED_LIST_STR}
   Emoji veya sembol de yasak. Bunlar yerine spesifik, somut, günlük dilde yaz.

3. **AI testi:** Bunu gerçek bir insan tweet atar mıydı? "AI yazmış" hissi varsa baştan yaz.

4. **İlk cümle testi:** İlk cümle sıradan mı? Sıradansa değiştir.

5. **Dolgu testi:** "Bu çok önemli bir gelişme" gibi hiçbir şey söylemeyen cümle varsa sil.

6. **Karakter limiti:** Verilen aralıkta mı? Değilse düzelt."""


# ─────────────────────────────────────────────
# APEX SECTION (optional, appended when active)
# ─────────────────────────────────────────────

_APEX_V3 = """## APEX MODE

Normal mod bilgi verir. Apex mod HİSSETTİRİR.

- İlk cümle: Scroll durdurucu. İddia, çelişki veya şok.
- Gövde: Her cümle bir sonrakini okutacak tension.
- Son cümle: Mic drop. Screenshot'lanacak kadar güçlü.
- Somut, spesifik, kişisel, beklenmedik açı.
- Liste formatı (1. 2. 3.) yasak. Generic tavsiye yasak.
- Birileri bunu screenshot'layıp paylaşır mı? Hayırsa baştan yaz."""


# ─────────────────────────────────────────────
# MAIN BUILDER
# ─────────────────────────────────────────────

def build_final_prompt_v3(
    content_type: str,
    topic: str = None,
    persona: str = "uzman",
    tone: str = "natural",
    knowledge: str = None,
    length: str = "punch",
    language: str = "auto",
    original_tweet: str = None,
    reply_mode: str = None,
    article_style: str = None,
    references: list = None,
    additional_context: str = None,
    is_apex: bool = False,
    style_prompt: str = None,
    example_tweets: list = None,
    platform: str = "twitter",
    direction: str = None,
    direction_custom: str = None,
    brand_voice: dict = None,
    voice_mode: str = None,  # Phase 25.C — first_person_witty | third_person_neutral | hybrid
    # Accept but ignore v1 extras for compatibility
    **kwargs,
) -> str:
    """
    Build prompt v3: 5-section architecture.
    Same params as build_final_prompt but leaner output.
    
    Sections:
      1. GÖREV — what to produce
      2. SES — voice (style > persona > tone)
      3. KURALLAR — length, platform, language
      4. ÖRNEKLER — few-shot examples (if any)
      5. SON KONTROL — banned words + quality checklist
    """
    sections = []

    # 1. GÖREV
    sections.append(_build_gorev(
        content_type=content_type,
        topic=topic,
        original_tweet=original_tweet,
        reply_mode=reply_mode,
        article_style=article_style,
        references=references,
        additional_context=additional_context,
        direction=direction,
        direction_custom=direction_custom,
    ))

    # 2. SES
    sections.append(_build_ses(
        persona=persona,
        tone=tone,
        style_prompt=style_prompt,
        platform=platform,
        content_type=content_type,
        brand_voice=brand_voice,
        voice_mode=voice_mode,  # Phase 25.C
    ))

    # 3. KURALLAR
    sections.append(_build_kurallar(
        content_type=content_type,
        length=length,
        language=language,
        knowledge=knowledge,
        platform=platform,
    ))

    # 4. ÖRNEKLER (optional)
    ornekler = _build_ornekler(example_tweets)
    if ornekler:
        sections.append(ornekler)

    # APEX (optional, before final check)
    if is_apex:
        sections.append(_APEX_V3)

    # 5. SON KONTROL (always last)
    sections.append(_build_son_kontrol())

    return "\n\n---\n\n".join(sections)


__all__ = ["build_final_prompt_v3", "FEW_SHOT_EXAMPLES"]
