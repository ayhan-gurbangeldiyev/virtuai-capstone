"""
Content Evolution — Prompt builder for iterative content refinement.
"""

QUICK_TAG_PROMPTS = {
    "shorter": "Daha kısa ve öz yaz. Gereksiz kelimeleri kes, her kelime kazansın.",
    "longer": "Daha detaylı ve derinlemesine yaz. Örnekler, açıklamalar ekle.",
    "bolder": "Daha provokatif bir ton. Tartışmalı bir iddia, zorlayıcı bir soru ile aç.",
    "softer": "Daha yumuşak ve empatik. Okuyucuyu kucaklayan, anlayışlı bir ton.",
    "professional": "Daha kurumsal ve otoriter. Veri, kaynak, uzmanlık hissi ver.",
    "casual": "Daha samimi ve konuşkan. Arkadaşına anlatır gibi, doğal akış.",
    "provocative": "Sınır zorlayan, insanları düşündüren, reply çekecek bir yaklaşım.",
    "informative": "Bilgi yoğun, öğretici. Okuyucu bir şey öğrenmiş hissetsin.",
    "different_opening": "Tamamen farklı bir açılış dene. Soru, istatistik, şok edici bilgi veya alıntı ile başla.",
    "stronger_ending": "Güçlü bir kapanış yap. CTA, düşündürücü soru veya akılda kalıcı cümle ile bitir.",
    "add_hook": "İlk 2 saniyede yakalayan bir hook ekle. Scroll durduran açılış.",
    "simplify": "Sadeleştir. Karmaşık fikirleri basit, anlaşılır cümlelerle anlat.",
}


# Phase 28.P (thinker) — when user only picked a category (no free text),
# infer what they likely meant. Prevents silent feedback dead-ends.
CATEGORY_INFERENCE = {
    "too_long": "Içerik fazla uzun. Yarıya indir, her cümle zorunlu olmalı.",
    "too_short": "Içerik çok kısa. Fikri tam açmak için yer lazım, en az 2-3 cümle ekle.",
    "tone_off": "Ton uygun değil. Daha farklı bir ses dene — ya daha samimi ya daha az formal.",
    "wrong_topic": "Konu kaymış. Orijinal trend noktasına geri dön.",
    "inaccurate": "Bilgi hatalı veya iddialı. Daha temkinli, doğrulanabilir ifadeler kullan.",
    "already_posted": "Daha önce benzer paylaşıldı. Açı değiştir, farklı bir bakış aç.",
    "low_quality": "Genel olarak zayıf. Daha güçlü hook + daha keskin gözlem dene.",
    "off_brand": "Marka sesi kaymış. Stil profiline çok daha sadık kal.",
    "too_salesy": "Çok satışçı hissediyor. Push yerine value odaklı yaklaş.",
    "shallow_insight": "Yüzeysel kalmış. Spesifik bir detay, anekdot veya kontrarian açı ekle.",
    "no_hook": "İlk satır kanca yok. Soru, şok edici tespit veya istatistikle aç.",
    "ai_obvious": "AI gibi geliyor. Daha insani, samimi, kuralsız bir dil kullan.",
    "other": "Genel rahatsızlık. Tarzı, açıyı veya formatı değiştirmeyi dene.",
}


# Phase 28.P — mutually exclusive tag groups; latest tag wins
MUTUALLY_EXCLUSIVE_GROUPS = [
    {"shorter", "longer"},
    {"casual", "professional"},
    {"softer", "bolder", "provocative"},
]


def _resolve_tag_conflicts(tags: list[str]) -> list[str]:
    """Within mutually exclusive groups, keep only the latest tag.
    Tags outside any group pass through unchanged."""
    if not tags:
        return []
    seen_groups: dict[frozenset, str] = {}
    independents: list[str] = []
    for tag in tags:
        group = next((g for g in MUTUALLY_EXCLUSIVE_GROUPS if tag in g), None)
        if group is None:
            if tag not in independents:
                independents.append(tag)
        else:
            seen_groups[frozenset(group)] = tag  # last wins
    return independents + list(seen_groups.values())


def _extract_rejected_themes(iterations: list[dict]) -> list[str]:
    """Pull distinct rejection categories + key feedback nouns from older
    iterations for sliding-window summary mode (used past iter 6)."""
    themes: list[str] = []
    for r in iterations:
        cat = r.get("rejection_category")
        if cat and cat not in themes:
            themes.append(cat)
    return themes[:5]  # cap to 5 themes


def build_evolve_prompt(
    selected_variants: list[str],
    feedback: str = "",
    quick_tags: list[str] = None,
    original_topic: str = "",
    platform: str = "twitter",
    content_type: str = "tweet",
    variant_count: int = 3,
    style_prompt: str = "",
    previous_iterations: list[dict] | None = None,
    preserve_user_edits: bool = False,
    preserved_segments: list[str] | None = None,
) -> str:
    """Build the evolution prompt.

    Phase 28.P: `previous_iterations` is a list of dicts shaped:
        {"version": int, "content": str, "rejection_category": str,
         "rejection_feedback": str}
    sorted by version ascending. When present, the prompt includes the
    full rejection chain so the LLM sees what was tried + why it was
    rejected, avoiding repeating the same mistakes.
    """

    # Quick tag instructions (Phase 28.P — conflict resolution: latest wins
    # within MUTUALLY_EXCLUSIVE_GROUPS, e.g. shorter+longer → longer kept)
    tag_instructions = ""
    if quick_tags:
        resolved_tags = _resolve_tag_conflicts(list(quick_tags))
        tag_parts = [QUICK_TAG_PROMPTS[tag] for tag in resolved_tags if tag in QUICK_TAG_PROMPTS]
        if tag_parts:
            tag_instructions = "\n\nKullanıcının istediği yönlendirmeler:\n" + "\n".join(f"- {p}" for p in tag_parts)

    # User feedback — if free text empty, infer from latest rejection category
    feedback_section = ""
    if feedback and feedback.strip():
        feedback_section = f'\n\nKullanıcının detaylı yönlendirmesi:\n"{feedback.strip()}"'
    elif previous_iterations:
        # No explicit feedback — try to infer from the latest rejection category
        last_rejected = next(
            (r for r in reversed(previous_iterations) if r.get("rejection_category")),
            None,
        )
        if last_rejected:
            cat = last_rejected.get("rejection_category", "")
            inferred = CATEGORY_INFERENCE.get(cat, "")
            if inferred:
                feedback_section = f"\n\nKategori bazlı yönlendirme ({cat}):\n{inferred}"

    # Style prompt
    style_section = ""
    if style_prompt and style_prompt.strip():
        style_section = f"\n\nKullanıcının yazım stili profili (bunu koru):\n{style_prompt.strip()}"

    # Phase 28.P — iteration history (sliding window, thinker recommendation)
    # Strategy: keep last 2 iterations FULL, older ones as rejected-theme summary.
    # Avoids "lost in the middle" + cumulative token bloat past iter 7.
    iteration_history_section = ""
    if previous_iterations:
        rejected_iters = [
            r for r in previous_iterations
            if (r.get("rejection_category") or r.get("rejection_feedback"))
        ]
        if rejected_iters:
            WINDOW_FULL = 2
            recent = rejected_iters[-WINDOW_FULL:]
            older = rejected_iters[:-WINDOW_FULL] if len(rejected_iters) > WINDOW_FULL else []

            lines = ["\n\n--- ÖNCEKİ DENEMELER (kullanıcı bunların hepsini reddetti) ---"]
            lines.append(f"Toplam {len(rejected_iters)} red, hiçbiri kabul edilmedi.")

            if older:
                older_themes = _extract_rejected_themes(older)
                lines.append(f"\nÖnceki {len(older)} denemenin reddedilen kategorileri: "
                             + ", ".join(older_themes))

            lines.append("\nSon detaylı denemeler:")
            for r in recent:
                ver = r.get("version")
                cat = r.get("rejection_category") or "?"
                fb = (r.get("rejection_feedback") or "").strip()
                content = (r.get("content") or "").strip()
                lines.append(f"\n• Versiyon {ver} (red: {cat}):")
                if content:
                    lines.append(f"    içerik: {content[:250]}")
                if fb:
                    lines.append(f"    kullanıcı yorumu: \"{fb}\"")

            lines.append("\n--- ---")
            lines.append(
                "\nKULLANICI BU DENEMELERİN HİÇBİRİNİ KABUL ETMEDİ.\n"
                "Bu denemelerdeki ortak hatalardan KAÇIN. Reddedilen kategoriler ile çelişen, "
                "farklı bir yaklaşım dene. Catisan tag varsa son tag onceligini tasir."
            )
            iteration_history_section = "\n".join(lines)

    if len(selected_variants) == 1:
        # Phase 28.P (thinker): block order optimized for "lost in the middle":
        # 1. Task intro, 2. Context, 3. History, 4. Feedback, 5. Tags,
        # 6. Style (sonda — strongest attend), 7. JSON instruction (en sonda).
        intro = (
            "Kullanıcı aşağıdaki içeriği reddetti, yeni bir versiyon istiyor."
            if iteration_history_section
            else "Kullanıcı aşağıdaki içeriği beğendi ve geliştirmek istiyor."
        )

        # Adaptive style emphasis — iter count'a göre vurgu artar
        iter_count = len(previous_iterations) if previous_iterations else 0
        style_emphasis = ""
        if iter_count >= 6:
            style_emphasis = "\n[KRİTİK: STİL KİMLİK — MUTLAK KORU. İterasyon baskısı altında bile sesi DEĞİŞTİRME.]"
        elif iter_count >= 3:
            style_emphasis = "\n[ÖNEMLİ: STİL KİMLİĞİ KORU — kullanıcı yönlendirmeleri bu sesin İÇİNDE uygulanmalı.]"

        # Phase 43.B.4 — anchor-preserve regen (Midjourney V7 "Remix Mode"
        # equivalent). When `preserve_user_edits=True`, the LLM is told to
        # carry the marked segments forward UNCHANGED (byte-for-byte) and
        # only rewrite the surrounding text. XML delimiters per Critic's
        # implementation note — concrete tag names raise compliance rate
        # vs. natural-language instructions.
        preserve_section = ""
        if preserve_user_edits and preserved_segments:
            cleaned_segments = [
                s.strip() for s in preserved_segments
                if s and s.strip()
            ]
            if cleaned_segments:
                segments_md = "\n".join(
                    f"<PRESERVE_VERBATIM>{seg}</PRESERVE_VERBATIM>"
                    for seg in cleaned_segments
                )
                preserve_section = (
                    "\n\n--- KULLANICI DÜZENLEMESİ KORUMA TALİMATI ---\n"
                    "Aşağıdaki <PRESERVE_VERBATIM> bloklarındaki metni "
                    "AYNEN, harf harf, noktalama dahil koruyarak yeni "
                    "varyantlara yerleştir. Bu blokların içeriğini DEĞİŞTİRME, "
                    "yeniden ifade etme, çevirme, kısaltma. Sadece bu blokların "
                    "ÇEVRESİNDEKİ metni yeniden yazabilirsin.\n\n"
                    f"{segments_md}\n"
                    "--- ---"
                )

        prompt = f"""{intro}

Orijinal konu: {original_topic}
Platform: {platform}
İçerik türü: {content_type}

--- Mevcut İçerik ---
{selected_variants[0]}
--- ---
{iteration_history_section}{feedback_section}{tag_instructions}

Kullanıcının istediği yönde geliştirerek {variant_count} yeni varyant üret.

Kurallar:
- Her varyant farklı bir yaklaşım denesin
- Birebir kopya yapma, her biri özgün olsun
- Platform kurallarına uy ({platform})
- Kullanıcının yönlendirmelerini mutlaka uygula
- ÖNCEKİ DENEMELERdeki hataları TEKRARLAMA
{style_emphasis}
{style_section}
{preserve_section}

ÇIKTI FORMATI — BU KURALI BOZMA:
Sadece aşağıdaki JSON formatında dön. Markdown blok (```json), açıklama,
giriş cümlesi veya kapanış metni EKLEME — sistemde parse hatası yaratır.

{{"variants": [{{"content": "...", "variant_index": 0}}, ...]}}"""
    else:
        variants_text = ""
        for i, v in enumerate(selected_variants):
            variants_text += f"\n--- Beğenilen İçerik {i+1} ---\n{v}\n--- ---\n"

        prompt = f"""Kullanıcı aşağıdaki içerikleri beğendi ve bunların en iyi özelliklerini birleştirmek istiyor.

Orijinal konu: {original_topic}
Platform: {platform}
İçerik türü: {content_type}
{variants_text}
{tag_instructions}{feedback_section}{style_section}{iteration_history_section}

Her iki içeriğin güçlü yanlarını harmanlayarak {variant_count} yeni varyant üret.

Kurallar:
- Her varyant, seçilen içeriklerin en iyi özelliklerini farklı şekillerde birleştirsin
- Birebir kopya yapma, her biri özgün olsun
- Platform kurallarına uy ({platform})
- Kullanıcının yönlendirmelerini mutlaka uygula

JSON formatında dön:
{{"variants": [{{"content": "...", "variant_index": 0}}, ...]}}"""

    return prompt
