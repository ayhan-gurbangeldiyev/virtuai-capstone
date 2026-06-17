"""
Style Lab v3 - Ghost Writer Prompt Builder
Stil profili aktif olduğunda kullanılır.
build_final_prompt()'a DOKUNULMAZ, sadece build_style_enhanced_prompt() değişir.
"""


def build_style_enhanced_prompt(
    content_type: str,  # tweet, quote, reply
    topic: str,
    style_fingerprint: dict,
    viral_patterns: dict,
    constraints,  # StyleConstraints instance
    reference_tweets: list,  # RAG'den gelen tweet'ler
    persona: str = "uzman",  # 2026-06-08: was "otorite" (deleted from PERSONAS)
    tone: str = "natural",
    knowledge: str = None,
    length: str = "punch",
    language: str = "auto",
    original_tweet: str = None,
    reply_mode: str = None,
    additional_context: str = None,
    is_apex: bool = False,
    image_context: str = None,
    voice_mode: str = None,  # Phase 34 — voice_mode-aware DNA injection
) -> str:
    """
    Style Lab v3 Ghost Writer prompt builder.
    Mevcut builder.py fonksiyonlarını re-use eder + v3 Ghost Writer katmanı ekler.

    Phase 34: voice_mode='third_person_neutral' iken Cansu Approved DNA
    (kontrast opener, yorum-veri-yorum) inject edilmez — Tonal Çerçeve
    gazeteci kuralları kazanır. Witty/hybrid modlarında DNA aktif kalır.
    """
    # Lazy imports (circular import önleme)
    from .builder import (
        TASK_DEFINITIONS,
        build_persona_section,
        build_tone_section,
        build_knowledge_section,
        build_length_section,
        build_reply_mode_section,
    )

    sections = []

    # ─── 1. GHOST WRITER IDENTITY (en başta, voice_mode-aware) ───
    sections.append(_build_ghost_writer_identity(voice_mode=voice_mode))

    # ─── 1.5. STRATEJİ ZORUNLULUKLARI (Phase 30) ───
    # Strategist Brief'inin YASAKLAR/ZORUNLULAR bölümü Style DNA'sından
    # önceliklidir. Aksi takdirde Writer Style DNA closing pattern'ını
    # (örn. Semih'te soru kapanışı %35) Brief yasağının üstünde uygular.
    if additional_context:
        sections.append(
            "## 🚨 STRATEJİ ZORUNLULUKLARI (Style DNA'dan ÖNCELİKLİ)\n\n"
            "Aşağıdaki kurallar Strategist'ten geldi. **TÜM stil DNA'sından,\n"
            "kapanış pattern'ından, açılış pattern'ından ve örnek tweet'lerden\n"
            "öncelikli** uygulanır. Style DNA bir kuralla çelişirse Strategist\n"
            "kuralı kazanır. İhlal etme.\n\n"
            f"{additional_context}"
        )

    # ─── 2. RAG ÖRNEKLER (öne taşındı, sadeleştirildi) ───
    sections.append(_build_rag_examples_section(reference_tweets))

    # ─── 3. STİL DNA (fingerprint'ten) ───
    sections.append(_build_style_dna_section(style_fingerprint))

    # ─── 4. MİKRO KURALLAR ───
    sections.append(_build_micro_rules_section(style_fingerprint))

    # ─── 5. TYPING HABITS RULES ───
    sections.append(_build_typing_habits_section(style_fingerprint))

    # ─── 6. HARD BLOCK (sadece en kritikler) ───
    sections.append(_build_hard_block(style_fingerprint))

    # ─── 7. TASK DEFINITION ───
    task = TASK_DEFINITIONS.get(content_type, TASK_DEFINITIONS["tweet"])
    if original_tweet and "{original_tweet}" in task:
        task = task.format(original_tweet=original_tweet)
    sections.append(task)

    # ─── 8. PERSONA + TONE (sadeleştirilmiş) ───
    sections.append(build_persona_section(persona))
    sections.append(build_tone_section(tone))

    # ─── 9. TOPIC ───
    if topic:
        sections.append(f"## KONU\n\n{topic}")

    # ─── 10. OUTPUT INSTRUCTIONS (kısa) ───
    sections.append("""## ÇIKTI

Sadece içeriği yaz. Açıklama, meta bilgi, "İşte tweet:" gibi girişler yasak.
Her varyant gerçekten FARKLI olsun: farklı hook, farklı açı, farklı yapı.
Karakter sayısını verilen aralıkta tut.""")

    # ─── EK: CONSTRAINT'LER ───
    if constraints:
        sections.append(constraints.to_prompt())

    # ─── EK: KNOWLEDGE MODE ───
    if knowledge:
        sections.append(build_knowledge_section(knowledge))

    # ─── EK: LENGTH ───
    sections.append(build_length_section(content_type, length))

    # ─── EK: REPLY MODE ───
    if content_type == "reply" and reply_mode:
        sections.append(build_reply_mode_section(reply_mode))

    # ─── EK: APEX MODE ───
    if is_apex:
        from .quality import APEX_MODE
        sections.append(APEX_MODE)

    # ─── EK: LANGUAGE ───
    lang_map = {
        "auto": "Konunun diline göre otomatik olarak Türkçe veya İngilizce yaz.",
        "tr": "Kesinlikle TÜRKÇE yaz.",
        "en": "Write in ENGLISH only."
    }
    sections.append(f"## DİL\n\n{lang_map.get(language, lang_map['auto'])}")

    # ─── EK: GÖRSEL BAĞLAM ───
    # Phase 30: additional_context (Strategist Brief) artık yukarıda
    # STRATEJİ ZORUNLULUKLARI bloğuna taşındı. Burada sadece görsel
    # bilgisi kalır.
    if image_context:
        sections.append(f"## EK BAĞLAM (görsel)\n\n{image_context}")

    # ─── EK: QUALITY (3 satır) ───
    sections.append("""## KALİTE
- Klişe ve jenerik ifadelerden kaçın, spesifik ol.
- Okuyucunun ilk 3 saniyede ilgisini çek.
- Doğal ve insan gibi yaz, yapay hissettirme.""")

    return "\n\n---\n\n".join(s for s in sections if s)


# ═══════════════════════════════════════════
# V3 GHOST WRITER SECTION BUILDERS
# ═══════════════════════════════════════════

def _build_ghost_writer_identity(voice_mode: str | None = None) -> str:
    """Ghost Writer kimlik tanımı.

    Phase 34: Cansu Approved DNA voice_mode-aware render edilir.
    - third_person_neutral → DNA YOK (Tonal Çerçeve gazeteci kuralları kazanır)
    - first_person_witty / hybrid / None → DNA RENDER OLUR (Cansu yazım stili)

    Cansu DNA'sı "tek somut beat / kaynakta-gerçek kontrast / maxim-yok /
    spekülasyon-yok" — ölçülü 1. şahıs ses için tasarlandı. 3. şahıs gazeteci
    modunda haber özetiyle başlamak ZORUNLU (THIRD_PERSON_NEUTRAL_BLOCK), DNA
    bununla çelişir.
    """
    base = """## GHOST WRITER

Sen bu kişisin. Aşağıdaki tweet'leri SEN yazdın.
Yeni tweet yazarken birebir aynı tarzda yaz.
Aynı kelime tercihleri, aynı cümle yapısı, aynı noktalama, aynı büyük/küçük harf kullanımı, aynı enerji.
YAZIM ALIŞKANLIKLARI bölümündeki kurallar MUTLAK: ihlal edersen BAŞARISIZ olursun."""

    # 3. şahıs gazeteci modunda DNA inject etme — Tonal Çerçeve kazanır.
    if voice_mode == "third_person_neutral":
        return base

    # 1. şahıs witty / hybrid / None → Cansu DNA aktif
    dna = """

## CANSU APPROVED DNA (1. şahıs witty + hybrid modları için)

Cansu ÖLÇÜLÜ yazar — görüş bütçesi DÜŞÜK. Manşet atan değil, gerçek bir şeyi
fark edip sakin gösteren biri. Tonal Çerçeve (voice_mode) ÜZERİNDE çalışır:

**1. Tek somut "beat" (zorunlu)**
Haberin TEK gerçek beat'ini göster: somut bir gözlem, mekanizma ya da sonuç.
Duyurma, GÖSTER. Haberde gerçekten olan şeye yaslan — abartma, büyütme.
Haber özetiyle düz başlama ("Şirket X duyurdu") YASAK; ama yapay "herkes
X sanıyor" kurgusu da YASAK.

**2. Kontrast ANCAK kaynakta gerçekse**
Zıtlık/çelişki cümlesi sadece KAYNAKTA gerçek bir karşıtlık varsa kurulur.
Etki için kontrast UYDURMA. Yoksa düz, somut beat yeterli.

**3. Maxim/genel-hüküm closing YOK**
"Genel amaçlı asistanlar bitti." gibi kesin büyük-iddia kapanışı YASAK.
Bir haberden tüm-sektör hükmü çıkarma. Kapanış = ölçülü, somut bir nokta.
Cümleler kısa ve net; virgül zincirli uzun cümle YASAK.

**SPEKÜLASYON YASAK**
Kaynakta OLMAYAN politik/jeopolitik/pazar tahmini YASAK
("X kazanır", "Y'ye gün doğdu", "fişi Z'de"). Kaynakta olmayan nedensellik/
çerçeve iddiası YASAK. Sadece haberde yazanı yorumla.

**YASAK KALIPLAR (rejected draft'lardan)**
- "peki ne dersiniz?" / "siz ne düşünüyorsunuz?" soruyla bitirme
- "gibi görünüyor" / "olabilir" hedging (yorum güveni kaybeder)
- Aşırı jargon ("multimodal inference katmanı")"""

    return base + dna


def _build_hard_block(fp: dict = None) -> str:
    """Sadece en kritik yasaklar"""
    base = """## YASAKLAR

Aşağıdaki kalıpları ASLA kullanma:
- "devrim", "çığır açan", "game changer", "oyun değiştirici"
- "hazır mısınız", "hazır olun", "yeni bir dönem/çağ"
- "inovasyon", "transformasyon", "paradigma"
- "muhteşem", "harika", "inanılmaz", "olağanüstü"
- "siz ne düşünüyorsunuz", "hadi bakalım", "düşünmek lazım"

Bunun yerine spesifik, somut, günlük dilde yaz.

## ⛔ MUTLAK YASAK — AI DISCLOSURE / PERSONA DISCLAIMER

İçeriğin başında, ortasında, sonunda veya hashtag bloğunda ASLA AI olduğunu
belirten herhangi bir imza, footer, disclaimer veya hashtag ekleme. Şu öğelerin
**HİÇBİRİ** kullanılamaz (örneklerle, çeşitleri dahil):

- `#AIcreated`, `#AIgenerated`, `#AIpersona`, `#AI`, `#yapayzeka`
  imza/kapanış olarak
- `— Cansu, AI persona ✨`, `— Cansu, AI persona`, `Cansu AI`,
  `(AI persona)` benzeri imzalar
- `AI tarafından üretildi`, `AI-generated`, `Generated by AI`,
  `Üretildi: AI`
- `autonomous persona`, `otonom persona`, `bot yazdı`, `AI yazdı`
- `🤖`, `⚙️ AI`, `✨ AI persona` gibi robot/yapay-zekâ emoji'leriyle
  imza bırakma
- `*This article is generated by ...AI...*` veya İngilizce/Türkçe
  benzer footer'lar

İçerik, **gerçek bir insanın elinden çıkmış gibi** okunmalı. Kendini hiçbir
biçimde AI/bot/persona olarak tanıtma. Bu kural mutlak; Style DNA,
örnekler veya başka bir kuralla çelişirse bu yasak kazanır."""

    # Dinamik yasak: küçük harf profili ise büyük harf yasak
    if fp:
        habits = fp.get('typing_habits', {})
        if habits.get('all_lowercase_pct', 0) > 50:
            base += "\n\n⚠️ BÜYÜK HARF YASAĞI: Bu kişi küçük harfle yazıyor. Cümle başında bile büyük harf KULLANMA. Özel isimler dahil her şey küçük."
    
    return base


def _build_style_dna_section(fp: dict) -> str:
    """Fingerprint'ten stil DNA'sı çıkar"""
    if not fp:
        return ""

    lines = ["## STİL DNA'SI (ZORUNLU — Bu kişinin yazım kimliği)"]
    lines.append("")
    lines.append("Bu kişi gibi yaz. Aşağıdaki her madde KURAL niteliğinde, öneri değil:")
    lines.append("")

    # Ortalama uzunluk
    avg_len = fp.get('avg_length', 0)
    if avg_len:
        lines.append(f"- Ortalama tweet uzunluğu: ~{int(avg_len)} karakter")

    # Cümle yapısı
    sent = fp.get('sentence_architecture', {})
    if sent:
        avg_w = sent.get('avg_words_per_sentence', 0)
        spt = sent.get('sentences_per_tweet', 0)
        if spt:
            lines.append(f"- Cümle/tweet: ~{round(spt, 1)}")
        if avg_w:
            desc = 'kısa ve keskin' if avg_w < 8 else 'orta' if avg_w < 15 else 'uzun ve detaylı'
            lines.append(f"- Kelime/cümle: ~{round(avg_w, 1)} ({desc})")

    # Açılış stili
    opening = fp.get('opening_psychology', {})
    if opening:
        dom = opening.get('dominant_opening', '')
        pattern_names = {
            'question': 'Soru ile açar',
            'story': 'Hikaye/anekdot ile açar',
            'data': 'Veri/rakam ile açar',
            'direct_address': 'Okuyucuya direkt seslenarak açar',
            'contrast': 'Zıtlık/kontrast ile açar',
            'bold_claim': 'Cesur bir iddia ile açar',
            'provocation': 'Provokatif giriş yapar',
            'mystery': 'Merak uyandırarak başlar',
        }
        if dom in pattern_names:
            lines.append(f"- Açılış stili: {pattern_names[dom]}")

    # Kapanış stili
    closing = fp.get('closing_strategy', {})
    if closing:
        dom_close = closing.get('dominant_closing', '')
        close_names = {
            'question_cta': 'Soru sorarak bitirir',
            'statement': 'Net ifadeyle bitirir',
            'incomplete': 'Yarım bırakır (...)',
            'emoji_close': 'Emoji ile bitirir',
            'no_close': 'Doğal bırakır',
            'call_to_action': 'Aksiyon çağrısı ile bitirir',
        }
        if dom_close in close_names:
            lines.append(f"- Kapanış stili: {close_names[dom_close]}")

    # Dil karışımı
    lang = fp.get('language_mix', {})
    if lang:
        style = lang.get('language_style', '')
        en_pct = lang.get('english_word_pct', 0)
        style_names = {
            'pure_turkish': 'Saf Türkçe',
            'mostly_turkish': f'Türkçe ağırlıklı, %{int(en_pct)} İngilizce',
            'mixed': f'Türkçe/İngilizce karışık (%{int(en_pct)} EN)',
            'mostly_english': 'Ağırlıklı İngilizce',
        }
        if style in style_names:
            lines.append(f"- Dil: {style_names[style]}")

    # Emoji stratejisi
    emoji = fp.get('emoji_strategy', {})
    if emoji:
        e_style = emoji.get('style', '')
        if e_style == 'no_emoji':
            lines.append("- Emoji: KULLANMAZ")
        elif e_style == 'light':
            top = emoji.get('top_emojis', [])[:3]
            lines.append(f"- Emoji: Nadiren{' (' + ' '.join(top) + ')' if top else ''}")
        elif e_style in ('moderate', 'heavy'):
            top = emoji.get('top_emojis', [])[:5]
            lines.append(f"- Emoji: Sık{' (' + ' '.join(top) + ')' if top else ''}")

    # Noktalama DNA'sı
    punct = fp.get('punctuation_dna', {})
    if punct:
        traits = []
        if punct.get('comma_per_tweet', 0) > 2:
            traits.append("virgül sever")
        if punct.get('ellipsis_per_tweet', 0) > 0.3:
            traits.append("üç nokta kullanır")
        if punct.get('exclamation_per_tweet', 0) < 0.1:
            traits.append("ünlem kullanmaz")
        elif punct.get('exclamation_per_tweet', 0) > 1:
            traits.append("ünlem sever")
        no_punct = punct.get('tweets_ending_no_punct', 0)
        if no_punct > 50:
            traits.append("noktalama olmadan bitirir")
        if traits:
            lines.append(f"- Noktalama: {', '.join(traits)}")

    # Büyük/küçük harf
    cap = fp.get('capitalization', {})
    if cap:
        if cap.get('starts_lowercase_pct', 0) > 70:
            lines.append("- Büyük harf: Küçük harfle başlar")
        if cap.get('uses_all_caps_emphasis_pct', 0) > 15:
            lines.append("- Vurgulama: BÜYÜK HARF ile vurgular")

    # Satır yapısı
    line_struct = fp.get('line_structure', {})
    if line_struct:
        ml_pct = line_struct.get('multiline_pct', 0)
        if ml_pct > 50:
            avg_lines = line_struct.get('avg_lines_per_tweet', 3)
            lines.append(f"- Format: Çok satırlı (~{round(avg_lines)} satır)")
        elif ml_pct < 15:
            lines.append("- Format: Tek blok, satır kırmaz")

    # Typing habits entegrasyonu
    habits = fp.get('typing_habits', {})
    if habits:
        ts = habits.get('typing_style', '')
        if ts:
            style_desc = {
                'formal': 'Formal, düzgün yazım',
                'casual': 'Rahat, günlük yazım',
                'lazy': 'Lazy typing, kuralları umursamaz',
                'chaotic': 'Kaotik, tutarsız yazım',
            }
            lines.append(f"- Yazım tarzı: {style_desc.get(ts, ts)}")

    return '\n'.join(lines) if len(lines) > 3 else ""


def _build_micro_rules_section(fp: dict) -> str:
    """Somut, aksiyonel mikro kurallar"""
    if not fp:
        return ""

    rules = []

    # Kelime başına aksiyon
    sent = fp.get('sentence_architecture', {})
    avg_words = sent.get('avg_words_per_sentence', 0)
    if avg_words:
        if avg_words < 8:
            rules.append(f"⚠️ ZORUNLU: Kısa cümleler kur. Ortalama {round(avg_words, 1)} kelime/cümle. 8 kelimeyi GEÇME.")
        elif avg_words < 12:
            rules.append(f"⚠️ ZORUNLU: Orta uzunlukta cümleler kur. Ortalama {round(avg_words, 1)} kelime/cümle hedefle.")
        else:
            rules.append(f"⚠️ ZORUNLU: Detaylı, uzun cümleler kur. Ortalama {round(avg_words, 1)} kelime/cümle. Kısa kesme.")

    # Hashtag
    ht = fp.get('hashtag_usage', 0)
    if ht < 0.05:
        rules.append("⚠️ ZORUNLU: Hashtag KULLANMA. Bu kişi hashtag kullanmıyor.")
    elif ht > 0.3:
        rules.append("⚠️ ZORUNLU: Hashtag kullan (1-2 tane). Bu kişi hashtag kullanıyor.")

    # Soru kullanımı
    q_ratio = fp.get('question_ratio', 0)
    if q_ratio > 0.3:
        rules.append("⚠️ ZORUNLU: Soru sor. Bu kişi tweet'lerinin %{:.0f}'inde soru soruyor. Soru sormadan bitirme.".format(q_ratio * 100))
    elif q_ratio < 0.1:
        rules.append("⚠️ ZORUNLU: Soru SORMA. Bu kişi neredeyse hiç soru sormuyor (%{:.0f}). Direkt statement yaz.".format(q_ratio * 100))

    # Emoji
    emoji = fp.get('emoji_strategy', {})
    if emoji:
        e_style = emoji.get('style', '')
        if e_style == 'no_emoji':
            rules.append("⚠️ ZORUNLU: Emoji KULLANMA. Bu kişi hiç emoji kullanmıyor.")
        elif e_style == 'heavy':
            top = emoji.get('top_emojis', [])[:5]
            rules.append(f"⚠️ ZORUNLU: Emoji kullan. Favori emojileri: {' '.join(top)}")

    if not rules:
        return ""

    header = "## MİKRO KURALLAR\n"
    return header + '\n'.join(f"- {r}" for r in rules)


def _build_typing_habits_section(fp: dict) -> str:
    """typing_habits + capitalization dict'lerinden somut yazım kuralları üret.

    style_fingerprint may have capitalization stats either under
    `typing_habits` (legacy) or at the root level under `capitalization`
    (current Style Lab v2). We merge both so the rule engine sees a unified
    view of how the creator uses case.
    """
    habits = dict(fp.get('typing_habits') or {})
    cap = fp.get('capitalization') or {}
    # Lift capitalization stats into habits so the rules below pick them up.
    for key in ('starts_uppercase_pct', 'starts_lowercase_pct',
                'uses_all_caps_emphasis_pct', 'all_lowercase_pct',
                'lowercase_after_period_pct'):
        if key not in habits and cap.get(key) is not None:
            habits[key] = cap[key]

    if not habits:
        return ""

    rules = []

    # all_lowercase > 50% → küçük harf kuralı
    if habits.get('all_lowercase_pct', 0) > 50:
        pct = habits['all_lowercase_pct']
        rules.append(f"⚠️ KRİTİK: Bu kişi tweet'lerinin %{int(pct)}'ını TAMAMEN küçük harfle yazıyor. HİÇBİR harfi büyük yazma. Cümle başı, özel isimler, kısaltmalar dahil HER ŞEY küçük harf. Tek bir büyük harf bile yazarsan BAŞARISIZ olursun.")
    # OPPOSITE: high uppercase-start bias → enforce sentence case explicitly.
    # Without this, LLM defaults to lowercase casual Turkish even though the
    # creator writes in normal capitalization.
    elif habits.get('starts_uppercase_pct', 0) > 60:
        pct = int(habits['starts_uppercase_pct'])
        rules.append(f"⚠️ KRİTİK: Bu kişi normal Türkçe yazım kurallarına uyuyor — cümleleri BÜYÜK HARFLE başlatıyor (%{pct} oranında). Cümle başı büyük, özel isimler büyük, kısaltmalar büyük. HEPSİNİ KÜÇÜK HARFLE YAZMA — bu kişinin sesi değil. Sentence case zorunlu.")

    # lowercase_after_period > 30% → nokta sonrası küçük harf
    if habits.get('lowercase_after_period_pct', 0) > 30:
        pct = habits['lowercase_after_period_pct']
        rules.append(f"⚠️ KRİTİK: Nokta sonrası büyük harfe geçme (%{int(pct)} oranında küçük harfle devam ediyor). nokta koysan bile sonraki kelime küçük harfle başlar.")

    # number_suffix > 10% → sayı+ek bitişik
    if habits.get('number_suffix_pct', 0) > 10:
        rules.append("⚠️ ZORUNLU: Sayıları ekle bitişik yaz, ayırma. Örnek: 4üncü, 2nci, 3te, 10bin. Boşluk veya kesme işareti koyma.")

    # no_comma > 70% → virgül kullanma
    if habits.get('no_comma_tweet_pct', 0) > 70:
        pct = habits['no_comma_tweet_pct']
        rules.append(f"⚠️ ZORUNLU: Virgül KULLANMA. Tweet'lerinin %{int(pct)}'ında virgül yok. Virgül yerine boşluk veya satır sonu kullan.")
    elif habits.get('no_comma_tweet_pct', 0) < 30:
        rules.append("⚠️ ZORUNLU: Virgül kullan. Bu kişi virgülü aktif olarak kullanıyor.")

    # informal_contractions varsa → kısaltma kullan
    contractions = habits.get('informal_contractions', {})
    if contractions:
        words = list(contractions.keys())[:7]
        examples = ', '.join(words)
        rules.append(f"⚠️ ZORUNLU: Günlük kısaltmaları kullan. Bu kişinin kullandığı kısaltmalar: {examples}. Düzgün/formal yazma, bu kısaltmaları aktif kullan.")

    # missing_apostrophe > 30% → kesme işareti kullanma
    if habits.get('missing_apostrophe_pct', 0) > 30:
        pct = habits['missing_apostrophe_pct']
        rules.append(f"⚠️ ZORUNLU: Kesme işareti (') KULLANMA. Bu kişi %{int(pct)} oranında kesme işareti koymadan yazıyor. Türkiyenin, Istanbulda, Elonın gibi yaz.")
    elif habits.get('missing_apostrophe_pct', 0) < 10:
        rules.append("⚠️ ZORUNLU: Kesme işaretini doğru kullan. Bu kişi kesme işaretine dikkat ediyor.")

    # no_punctuation_end > 50% → noktalama olmadan bitir
    if habits.get('no_punctuation_end_pct', 0) > 50:
        pct = habits['no_punctuation_end_pct']
        rules.append(f"⚠️ ZORUNLU: Tweet'i noktalama işareti KOYMADAN bitir. %{int(pct)} oranında noktalama olmadan bitiriyor. Sonuna nokta, ünlem, soru işareti koyma.")
    elif habits.get('no_punctuation_end_pct', 0) < 20:
        rules.append("⚠️ ZORUNLU: Tweet'i noktalama işaretiyle bitir. Bu kişi genelde noktalama ile bitirir.")

    if not rules:
        return ""

    header = "## YAZIM ALIŞKANLIKLARI (ZORUNLU — İhlal etme)\n\n"
    return header + '\n'.join(f"- {r}" for r in rules)


def _build_rag_examples_section(tweets: list) -> str:
    """RAG'den gelen referans tweet'ler: sadeleştirilmiş, engagement metadata YOK"""
    if not tweets:
        return ""

    lines = ["## SENİN TWEET'LERİN (Bu tweet'leri sen yazdın: aynı tarzda devam et)"]
    lines.append("")

    for i, tweet in enumerate(tweets[:15], 1):
        content = tweet.get('content', '') if isinstance(tweet, dict) else str(tweet)
        if len(content) > 400:
            content = content[:397] + "..."
        lines.append(f"{i}. {content}")

    return '\n'.join(lines)
