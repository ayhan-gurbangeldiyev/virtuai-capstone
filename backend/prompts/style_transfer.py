"""
Style Transfer v3 — "Başka Biri Gibi Yaz"
Kaynak metni hedef kişinin tarzıyla yeniden yazar.
2 aşamalı: (1) saf fikir çıkar, (2) hedef tarzla yeniden inşa et.
Few-shot first, style rules second.
"""


def build_extract_idea_prompt(source_text: str) -> str:
    """Aşama 1: Kaynak metinden saf fikri çıkar."""
    return f"""Aşağıdaki sosyal medya postunu analiz et.

GÖREV:
1. Ana mesajı tek cümlede özetle
2. Somut verileri çıkar (isim, sayı, ürün, şirket)
3. Duygusal tonu belirle
4. Yapıyı belirle
5. Medya/link var mı

JSON döndür:
{{
  "core_message": "yazarın asıl söylediği şey",
  "entities": ["veri1", "veri2"],
  "emotional_tone": "heyecanlı/eleştirel/bilgilendirici/şaşkın/hayran/uyarıcı",
  "structure": "single_statement/list/comparison/story/announcement",
  "has_media": false,
  "topic_domain": "AI/tech/crypto/genel"
}}

Post:
\"\"\"{source_text}\"\"\""""


def _build_natural_style_summary(fp: dict) -> str:
    """Fingerprint'ten doğal dilde stil özeti oluştur."""
    name = fp.get("twitter_display_name", "Bu kişi")
    lines = [f"## {name}'IN YAZIM TARZI (Doğal dilde özet)"]

    # Uzunluk
    avg_len = fp.get("avg_length", 120)
    if avg_len < 80:
        lines.append(f"- Kısa yazar, ortalama {avg_len} karakter. Gereksiz kelime kullanmaz.")
    elif avg_len < 150:
        lines.append(f"- Orta uzunlukta yazar, ortalama {avg_len} karakter.")
    else:
        lines.append(f"- Uzun yazar, ortalama {avg_len} karakter. Detaylı açıklamalar yapar.")

    # Dil
    lang = fp.get("language_mix", {})
    en_pct = lang.get("english_word_pct", 0)
    tr_pct = lang.get("turkish_word_pct", 0)
    if en_pct > 60:
        lines.append("- Ağırlıklı İngilizce yazar.")
    elif en_pct > 35:
        lines.append(f"- Türkçe ve İngilizce karışık yazar (%{int(tr_pct)} Türkçe, %{int(en_pct)} İngilizce). Teknik terimleri İngilizce bırakır.")
    else:
        lines.append("- Ağırlıklı Türkçe yazar.")

    # Açılış
    opening = fp.get("opening_psychology", {})
    dominant = opening.get("dominant_opening", "")
    dist = opening.get("distribution", {})
    if dominant == "bold_claim":
        pct = dist.get("bold_claim", 0)
        lines.append(f"- Tweetlerin %{int(pct)}'ında cesur bir iddiayla açar. Doğrudan söyler, etrafında dolanmaz.")
    elif dominant == "provocation":
        pct = dist.get("provocation", 0)
        lines.append(f"- Tweetlerin %{int(pct)}'ında provokatif bir açılış yapar. Dikkat çekici, bazen şok edici.")
    elif dominant == "question":
        lines.append("- Genellikle soru ile açar.")

    # Soru kullanımı
    q_per = fp.get("punctuation_dna", {}).get("question_per_tweet", 0)
    if q_per < 0.15:
        lines.append(f"- Soru işareti NADİR kullanır (tweet başına {q_per:.2f}). Genellikle ilan eder, sormaz.")
    elif q_per > 0.5:
        lines.append("- Sık soru sorar.")

    # Ünlem
    exc_per = fp.get("punctuation_dna", {}).get("exclamation_per_tweet", 0)
    if exc_per < 0.1:
        lines.append("- Ünlem işareti neredeyse hiç kullanmaz. Sakin, kontrollü bir ton.")
    elif exc_per > 0.3:
        lines.append("- Ünlem işareti sık kullanır. Heyecanlı, enerjik bir ton.")

    # Satır yapısı
    ls = fp.get("line_structure", {})
    ml_pct = ls.get("multiline_pct", 0)
    avg_lines = ls.get("avg_lines_per_tweet", 1)
    if ml_pct > 30:
        lines.append(f"- Tweetlerin %{int(ml_pct)}'si çok satırlı. Ortalama {avg_lines:.1f} satır. Satır kırarak düşüncelerini ayırır.")
    else:
        lines.append("- Genellikle tek satırda yazar.")

    # Düşünce yapısı
    ts = fp.get("thought_structure", {})
    dom_struct = ts.get("dominant_structure", "")
    if dom_struct == "single_thought":
        lines.append("- Tek bir düşünce, tek bir mesaj. Karmaşık yapmaz.")
    elif dom_struct == "conclusion_first":
        lines.append("- Sonucu önce söyler, sonra açıklar. Piramit yapısı.")
    elif dom_struct == "list_format":
        lines.append("- Liste formatını sever. Madde madde yazar.")

    # Emoji
    emoji_usage = fp.get("emoji_usage", 0)
    if emoji_usage < 0.1:
        lines.append("- Emoji neredeyse hiç kullanmaz.")
    elif emoji_usage < 0.3:
        lines.append(f"- Emoji az kullanır ({emoji_usage:.2f}/tweet). Sadece gerçekten uygun yerlerde.")
    elif emoji_usage > 0.5:
        lines.append(f"- Emoji sık kullanır ({emoji_usage:.2f}/tweet).")

    # Kapanış
    closing = fp.get("closing_strategy", {})
    dom_close = closing.get("dominant_closing", "")
    if dom_close == "no_close":
        lines.append("- Tweetlerinin çoğu kapanış cümlesi olmadan biter. Söyleyeceğini söyler, noktalar.")
    elif dom_close == "call_to_action":
        lines.append("- Genellikle bir CTA (call to action) ile bitirir.")
    elif dom_close == "question_cta":
        lines.append("- Soru sorarak bitirir.")

    # Noktalama
    no_punct = fp.get("punctuation_dna", {}).get("tweets_ending_no_punct", 0)
    if no_punct > 25:
        lines.append(f"- Tweetlerin %{int(no_punct)}'ı noktalama işareti olmadan biter.")

    # Typing habits
    th = fp.get("typing_habits", {})
    style = th.get("typing_style", "")
    if style == "chaotic":
        lines.append("- Yazım tarzı kaotik/doğal. Her zaman mükemmel dilbilgisi kullanmaz.")
    no_comma = th.get("no_comma_tweet_pct", 0)
    if no_comma > 60:
        lines.append(f"- Tweetlerin %{int(no_comma)}'ında virgül YOK. Kısa, kesik cümleler tercih eder.")

    # Cümle mimarisi
    sa = fp.get("sentence_architecture", {})
    avg_words = sa.get("avg_words_per_sentence", 0)
    short_pct = sa.get("short_sentence_pct", 0)
    if short_pct > 40:
        lines.append(f"- Cümleler kısa, ortalama {avg_words:.1f} kelime. %{int(short_pct)} kısa cümle.")

    # Duygusal yoğunluk
    ei = fp.get("emotional_intensity", {})
    dom_emotion = ei.get("dominant_emotion", "")
    level = ei.get("level", "")
    if dom_emotion:
        lines.append(f"- Dominant duygu: {dom_emotion}. Genel ton: {level}.")

    return "\n".join(lines)


def _extract_voice_patterns(tweets: list, fp: dict) -> str:
    """Few-shot tweetlerden ses kalıplarını çıkar."""
    if not tweets:
        return ""

    name = fp.get("twitter_display_name", "Bu kişi")
    patterns = [f"## {name}'IN SES KALIPLARI"]
    patterns.append("Bu kişinin tweetlerinde tekrar eden kalıplar:\n")

    # Tweetlerden açılış kalıplarını çıkar
    openers = []
    informal_words = set()
    for t in tweets[:8]:
        content = t.get('content', '') if isinstance(t, dict) else str(t)
        # İlk kelimeler
        first_words = content.split()[:3]
        first_word = first_words[0] if first_words else ""

        # "Adam" pattern
        if content.lower().startswith("adam"):
            openers.append('"Adam..." ile başlayan gözlem kalıbı')
        elif content.lower().startswith("bakın"):
            openers.append('"Bakın..." ile dikkat çekme')
        elif first_word and first_word[0].isupper() and not content.startswith("http"):
            # Product/company name opener
            if any(c in first_word for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ") and len(first_word) > 2:
                pass  # Normal sentence

        # Informal kelimeler
        for word in ["çılgın", "şahane", "bambaşka", "müthiş", "inanılmaz", "delirdi", "bi", "acayip", "bayağı"]:
            if word in content.lower():
                informal_words.add(word)

    if openers:
        unique_openers = list(set(openers))
        for o in unique_openers[:3]:
            patterns.append(f"- {o}")

    if informal_words:
        patterns.append(f"- İnformal Türkçe kelimeler kullanır: {', '.join(sorted(informal_words))}")

    # Dil karışımı pattern
    lang = fp.get("language_mix", {})
    en_pct = lang.get("english_word_pct", 0)
    if en_pct > 30:
        top_en = lang.get("top_english_words", [])
        if top_en:
            patterns.append(f"- Teknik terimleri İngilizce bırakır: {', '.join(top_en[:7])}")

    # Cümle stili
    sa = fp.get("sentence_architecture", {})
    inverted_pct = sa.get("inverted_sentence_pct", 0)
    if inverted_pct > 30:
        patterns.append(f"- Cümlelerin %{int(inverted_pct)}'inde ters sıra (nesne/yüklem öne gelir)")

    # Reader relationship
    rr = fp.get("reader_relationship", {})
    if isinstance(rr, dict):
        style = rr.get("style", "")
        if style:
            patterns.append(f"- Okuyucu ilişkisi: {style}")

    patterns.append("")
    patterns.append("ÖNEMLİ: Bu kalıpları birebir kopyalama ama aynı ENERJİ ve TARZ ile yaz.")

    return "\n".join(patterns)


def build_style_transfer_prompt(
    core_idea: dict,
    style_fingerprint: dict,
    few_shot_tweets: list,
    variant_count: int = 3,
    source_text: str = "",
    example_tweets: list = None,
) -> str:
    """Aşama 2: Saf fikri hedef tarzla yeniden yaz."""

    sections = []
    fp = style_fingerprint
    display_name = fp.get("twitter_display_name", "Hedef Kisi")
    username = fp.get("twitter_username", "")

    # 1. Görev
    sections.append(f"""## GÖREV
{display_name} (@{username}) olarak yaz. Bu kişinin Twitter hesabını yönetiyorsun.
Sana verilen fikri, bu kişinin ağzından, onun tarzında yaz.

KURALLAR:
- Orijinal metni KOPYALAMA. Fikri al, SIFIRDAN yeniden yaz.
- {display_name} bu fikri paylaşsaydı nasıl yazardı? ONU yaz.
- Aşağıdaki referans tweetleri dikkatlice oku ve TAKLİT ET.""")

    # 2. FEW-SHOT ÖRNEKLER (EN KRİTİK, en başta)
    if few_shot_tweets:
        lines = [f"\n## REFERANS: {display_name}'IN GERÇEK TWEETLERİ"]
        lines.append(f"Aşağıdaki tweetleri {display_name} yazdı.")
        lines.append(f"SENİN GÖREVİN: Bu tweetlerdeki SESİ, RİTMİ ve KELİME SEÇİMİNİ taklit etmek.")
        lines.append(f"Her tweette dikkat et: Nasıl açıyor? Hangi kelimeleri seçiyor? Cümle uzunluğu ne? Türkçe/İngilizce nasıl karıştırıyor? Noktalama nasıl?\n")
        for i, tweet in enumerate(few_shot_tweets[:8], 1):
            content = tweet.get('content', '') if isinstance(tweet, dict) else str(tweet)
            if len(content) > 400:
                content = content[:397] + "..."
            lines.append(f">>> {content}")
            lines.append("")
        sections.append('\n'.join(lines))

    # 2b. PROFILE'IN EN İYİ TWEETLERİ (stil referansı)
    if example_tweets:
        ex_lines = [f"\n## {display_name}'IN EN KARAKTERİSTİK TWEETLERİ"]
        ex_lines.append("Bu tweetler bu kişinin en tipik örnekleri. TARZINI bunlardan öğren.\n")
        for i, tweet in enumerate(example_tweets[:7], 1):
            content = tweet.get('content', '') if isinstance(tweet, dict) else str(tweet)
            if len(content) > 300:
                content = content[:297] + "..."
            if len(content) > 30:  # skip very short / link-only
                ex_lines.append(f">>> {content}")
                ex_lines.append("")
        sections.append('\n'.join(ex_lines))

    # 2c. SES KALIPLARI (few-shot'tan çıkarılmış voice patterns)
    all_tweets_for_patterns = (example_tweets or []) + (few_shot_tweets or [])
    voice_section = _extract_voice_patterns(all_tweets_for_patterns, fp)
    if voice_section:
        sections.append(voice_section)

    # 3. Stil özeti (doğal dilde, fingerprint'ten)
    sections.append(_build_natural_style_summary(fp))

    # 4. Aktarılacak fikir
    core_msg = core_idea.get("core_message", core_idea.get("core_idea", ""))
    entities = core_idea.get("entities", core_idea.get("key_data", []))
    tone = core_idea.get("emotional_tone", "")

    idea = f"""## AKTARILACAK FİKİR
{core_msg}"""
    if entities:
        idea += "\nVeri: " + ", ".join(str(e) for e in entities)

    sections.append(idea)

    # 5. Orijinal metin
    if source_text:
        sections.append(f"""## ORİJİNAL (referans, kopyalama)
\"\"\"{source_text[:500]}\"\"\"""")

    # 6. YAPMAMASI GEREKENLER (negatif kurallar)
    dont_rules = [f"- {display_name}'ın hiç kullanmadığı kalıpları KULLANMA"]

    q_per = fp.get("punctuation_dna", {}).get("question_per_tweet", 0)
    if q_per < 0.15:
        dont_rules.append("- Soru işareti ile bitirme. Bu kişi nadiren soru sorar.")

    exc_per = fp.get("punctuation_dna", {}).get("exclamation_per_tweet", 0)
    if exc_per < 0.1:
        dont_rules.append("- Ünlem işareti kullanma. Bu kişi neredeyse hiç ünlem kullanmaz.")

    emoji_use = fp.get("emoji_usage", 0)
    if emoji_use < 0.15:
        dont_rules.append("- Emoji kullanma (veya çok çok az). Bu kişi emoji sevmez.")
    elif emoji_use > 0.5:
        dont_rules.append("- Emoji'siz bırakma. Bu kişi emoji sever.")

    hashtag_use = fp.get("hashtag_usage", 0)
    if hashtag_use < 0.05:
        dont_rules.append("- Hashtag kullanma. Bu kişi hashtag kullanmaz.")

    dont_rules.append("- Yapay, robot gibi yazma")
    dont_rules.append("- Orijinal tweetin kelimelerini/cümlelerini kullanma")

    sections.append("## YAPMA\n" + "\n".join(dont_rules))

    # 7. Output
    avg_len = fp.get("avg_length", 120)
    sections.append(f"""## OUTPUT
{variant_count} varyant yaz. Her biri farklı açı veya format.
Uzunluk: ~{avg_len} karakter civarı (konuya göre kısa veya uzun olabilir, ama bu kişinin doğal uzunluğu bu).
Satır kırılması gerekiyorsa \\n kullan.

JSON:
{{
  "variants": [
    {{"content": "tweet metni", "approach": "kısa not"}}
  ]
}}""")

    return "\n\n".join(s for s in sections if s)
