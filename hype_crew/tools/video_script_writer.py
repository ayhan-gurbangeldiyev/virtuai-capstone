"""Three-act video script writer for Cansu's videos.

Locked spec (Berkay 5 Haz 2026):

  GİRİŞ (intro) — 1 sentence, news-specific hook. BANNED:
    "Bence asıl olay şu", "Asıl olay şu", "Şöyle ki", or any fixed
    catchphrase. The hook must drop straight into the story and vary
    by news type (punchy news statement / stakes line / contrast /
    surprising angle).

  GELİŞME (development) — 2-4 sentences. The substance: what it is,
    what changes operationally, why it matters. Cansu's "amelelik /
    iş akışı / süreç" operational frame.

  SONUÇ (conclusion) — 1-2 sentences that ZOOM OUT from the specific
    news to its broader meaning, THEN end on a SHORT 3-6 word
    decisive declarative final line (the gavel). No CTA, no
    self-reference, no hype.

Generation pattern:
  1. Sonnet 4.6 produces 3 GİRİŞ candidates (varied hooks) and
     3 SONUÇ candidates (different zoom-out angles), plus one GELİŞME.
  2. Caller picks the strongest of each (defaults to candidate[0],
     which the model is instructed to rank as the strongest).
  3. Final script = giris + " " + gelisme + " " + sonuc.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

from loguru import logger


MODEL = "anthropic/claude-sonnet-4.6"
TEMPERATURE = 0.5
MAX_TOKENS = 2000


SYSTEM_PROMPT = """Sen Cansu Dut'sun — AI haberlerini operasyonel zihinle yorumlayan, samimi konuşan Türk içerik üreticisi.

Bir VIDEO narration için ÜÇ AŞAMALI bir senaryo yazıyorsun. Toplam uzunluk ~25-40 saniye, ~550-800 karakter. YouTube Shorts / Reels — dikey, hızlı tempolu.

YAPI — ÜÇ AŞAMA, HEPSİ ZORUNLU:

═══ 1. GİRİŞ (1 cümle — HOOK, varied) ═══
- Habere özgü, dikkat çekici giriş cümlesi.
- KESİNLİKLE YASAK ifadeler:
  * "Bence asıl olay şu", "Asıl olay şu", "Şöyle ki", "Şunu söyleyeyim"
  * herhangi bir sabit catchphrase / formül başlangıç.

- BRAND/MODEL/AI TERİM İLE BAŞLAMA YASAK (Berkay 6 Haz 2026):
  * İlk 2-4 kelime MUTLAKA bir çerçeveleme ifadesi olmalı.
  * Brand / model / AI terim (OpenAI, Anthropic, Google, NVIDIA, Microsoft,
    ChatGPT, Claude, Gemini, GPT, AI, vb.) İLK KELİME OLAMAZ.
  * Pattern: [çerçeveleme] + [brand] + [eylem]
  * YANLIŞ: "OpenAI duyurdu..."
  * DOĞRU:  "Bu hafta gözler OpenAI'da; yeni modelini duyurdu."

- Doğru giriş tipleri (her aday için FARKLI tip seç):
  a) Punchy news statement (çerçeveleme ile): "Bu hafta dikkat çeken hamle OpenAI'dan geldi..."
  b) Stakes line: "Yapay zeka yarışında asıl soru artık model değil, para."
  c) Contrast: "Yıllardır ChatGPT sektörü modele uyduruyordu, bu sefer tam tersi oldu."
  d) Surprising angle: "Yapay zekânın araştırmada bir tavanı vardı: her şeyi bilen ama hiçbir şeyi derinlemesine bilmeyen modeller."

═══ 2. GELİŞME (2-4 cümle — substance) ═══
- Haberin gerçek substansı: ne olduğu, operasyonel olarak ne değiştiği.
- Cansu'nun "amelelik / iş akışı / süreç" diliyle somut anlatım.
- Gelmesi gereken bilgi: izleyici videoyu açtığında neyi öğrenecek?

═══ 3. SONUÇ — STRUCTURAL MIRRORING (KRİTİK) ═══

Daha önceki sonuçlar başarısız oldu çünkü hikayeyi BIRAKIP soyut bir
makro-trend ilan ediyorlardı ("Dikey model dönemi açıldı"). Giriş'in
açtığı thread havada kaldı → izleyici tamamlanmış hissetmedi.

DOĞRU YAPI (3 kural birlikte):

(a) STRUCTURAL MIRRORING (callback): SONUÇ, GİRİŞ'in açtığı SOMUT
    soruyu/gerilimi çözer. Yeni bir soyut trend tanıtmaz. GİRİŞ ve
    SONUÇ birlikte yazılır — eşleştirilmiş çift olarak.

    Örnek 1 — mirroring çifti:
      GİRİŞ:  "Yapay zekânın araştırmada bir tavanı vardı: her şeyi
               bilen ama hiçbir şeyi derinlemesine bilmeyen modeller."
      SONUÇ:  "Bugün o tavan deldi: artık araştırmacı modele uymuyor,
               model sektöre uyuyor. İlaç keşfinde mesai yeniden başladı."
      ↑ "tavan" referansı GİRİŞ'ten gelir, SONUÇ "tavan deldi" ile yanıtlar.

    Örnek 2 — mirroring çifti:
      GİRİŞ:  "Yapay zekâ yarışında asıl soru artık model değil, para."
      SONUÇ:  "65 milyar dolar tek şeyi kanıtlıyor: bu yarışı en akıllı
               değil, en uzun dayanan kazanacak. Ve saat işliyor."
      ↑ "para" sorusu açık, "65 milyar dolar" + "en uzun dayanan" cevaplar.

(b) SOMUT SONUÇ (abstract NO): Belirli, kontrol edilebilir bir
    SONUCU belirt — "şimdi spesifik olarak şu değişiyor". Soyut çağ
    açıklaması/era-pronouncement YASAK.

    YASAK: "X dönemi açıldı/kapanıyor", "yeni standart bu",
           "alan bilgisi yeni parametre" gibi era-claims.
    GEREKLI: "İlaç keşfinde mesai yeniden başladı." gibi spesifik
             operasyonel sonuç.

(c) SHORT FINAL BEAT (the landing): Son cümle KISA olmalı — 3-6
    kelime, declarative, decisive. <#0.5#> sessizliğin landingi.
    NO question. NO exclamation.

KESİNLİKLE YASAK (the gavel için):
  * CTA: takipteyim, takip et, abone ol, beğenmeyi unutmayın
  * Self-referans: "bunu işlemeye devam", "burada", "kanalda"
  * Hype: müthiş, devrim, game-changer, çağ açan
  * Soyut era-claim: "X dönemi açıldı/kapanıyor", "yeni standart bu"
  * Trailing long analytical sentence — gavel KISA olmalı
  * Ünlem işareti, soru işareti

GENEL YAZIM YASAKLARI (TTS filler tetikleyicisi):
- "ee", "ııı", "şey", "yani şey" sesleri YOK
- Em-dash (—) YOK; yerine virgül veya nokta
- "..." (ellipsis) YOK
- "!" (ünlem) YOK

ÇIKTI FORMATI — kesinlikle parse edilebilir JSON, başka metin yok, kod bloğu yok:

{
  "matched_pairs": [
    {
      "giris": "EN GÜÇLÜ giriş (çerçeveleme + brand) — direkt habere atlar",
      "sonuc": "Bu giriş'in açtığı sorunun SOMUT cevabı. Kısa son cümle."
    },
    {
      "giris": "İKİNCİ giriş — FARKLI bir hook tipi",
      "sonuc": "Bu ikinci giriş'in soruyla mirroring eden somut cevap. Kısa son."
    },
    {
      "giris": "ÜÇÜNCÜ giriş — yine FARKLI bir hook tipi",
      "sonuc": "Üçüncü giriş'e karşılık gelen mirroring sonuç. Kısa son."
    }
  ],
  "gelisme": "..."
}

KRİTİK: matched_pairs MUTLAKA eşleştirilmiş çiftler olmalı — her sonuç
SADECE kendi giriş'ine cevap vermeli. Üç çift birbirinden farklı
açıdan haberi ele almalı (her bir farklı hook tipi)."""


@dataclass(frozen=True)
class MatchedPair:
    giris: str
    sonuc: str


@dataclass(frozen=True)
class VideoScriptCandidates:
    matched_pairs: list[MatchedPair]   # 3 GİRİŞ ↔ SONUÇ mirror pairs
    gelisme: str

    # Convenience accessors so legacy callers (and the report) can still
    # talk about "giris_candidates" / "sonuc_candidates" lists.
    @property
    def giris_candidates(self) -> list[str]:
        return [p.giris for p in self.matched_pairs]

    @property
    def sonuc_candidates(self) -> list[str]:
        return [p.sonuc for p in self.matched_pairs]


# Brand / model / AI terms that may NEVER be the first token of the
# narration (intro brand-first ban). Lowercase for case-insensitive match.
INTRO_BANNED_FIRST_TOKENS: set[str] = {
    "openai", "anthropic", "google", "deepmind", "microsoft", "apple",
    "nvidia", "meta", "amazon", "aws", "azure",
    "chatgpt", "claude", "gemini", "copilot", "codex", "scout",
    "gpt", "ai", "llm", "api",
}


def lint_intro_brand_first(narration: str) -> Optional[str]:
    """Return a violation message if the first content word is a banned
    brand/AI token; None if the intro is clean."""
    if not narration:
        return "empty narration"
    import re as _re_lint
    tokens = _re_lint.findall(r"\b[\wÇĞİÖŞÜçğıöşü']+", narration.strip())
    if not tokens:
        return "no tokens"
    first = tokens[0].lower().rstrip("'")
    if first in INTRO_BANNED_FIRST_TOKENS:
        return f"first token '{tokens[0]}' is a banned brand/AI term (must be a framing phrase first)"
    return None


def _sanitize(text: str) -> str:
    """Strip TTS filler triggers that MiniMax interprets as hesitation."""
    out = (text or "").strip()
    out = out.replace("—", ",").replace("…", ".").replace("!", ".")
    while "..." in out:
        out = out.replace("...", ".")
    return out


async def build_video_script_candidates(
    *,
    topic: str,
    raw_content: str,
    additional_context: Optional[str] = None,
) -> Optional[VideoScriptCandidates]:
    """Run ONE LLM pass to produce 3 GİRİŞ + 1 GELİŞME + 3 SONUÇ candidates.

    Returns None on LLM unavailable / parse failure. Caller picks
    candidate[0] from each list for the strongest combo.
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("video_script_writer: openai not installed")
        return None
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        logger.warning("video_script_writer: no OPENROUTER_API_KEY; skipping")
        return None

    client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
    user_lines = [f"Haber başlığı: {topic}", "", f"Haber içeriği: {raw_content}"]
    if additional_context:
        user_lines += ["", f"Ek bağlam: {additional_context}"]
    user_msg = "\n".join(user_lines)

    # LiteLLM Router (flag-gated, fail-open). Async writer call → router_chat_messages
    # with model_name="writer" (claude-sonnet). On any router error we fall through
    # to the existing OpenAI sync path below (no behavior change when flag OFF).
    from .llm_router import router_enabled, router_chat_messages
    if router_enabled():
        try:
            text, _meta = await router_chat_messages(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                model_name="writer", temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
            )
            text = (text or "").strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                if text.endswith("```"):
                    text = "\n".join(text.split("\n")[:-1])
                text = text.strip()
            parsed = json.loads(text)
            raw_pairs = parsed.get("matched_pairs") or []
            pairs: list[MatchedPair] = []
            for p in raw_pairs:
                if not isinstance(p, dict):
                    continue
                g = _sanitize(p.get("giris") or "")
                s = _sanitize(p.get("sonuc") or "")
                if g and s:
                    pairs.append(MatchedPair(giris=g, sonuc=s))
            gelisme = _sanitize(parsed.get("gelisme") or "")
            if not (pairs and gelisme):
                logger.warning("video_script_writer: incomplete candidates from router")
                return None
            for i, p in enumerate(pairs):
                violation = lint_intro_brand_first(p.giris)
                if violation:
                    logger.warning(
                        f"video_script_writer: matched_pair[{i}] intro lint: {violation}"
                    )
            return VideoScriptCandidates(matched_pairs=pairs, gelisme=gelisme)
        except Exception:
            logger.warning("video_script_writer: router atlandı (fail-open)")

    try:
        resp = client.chat.completions.create(
            model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])
            text = text.strip()
        parsed = json.loads(text)
    except Exception:
        logger.exception("video_script_writer: LLM call or parse failed")
        return None

    raw_pairs = parsed.get("matched_pairs") or []
    pairs: list[MatchedPair] = []
    for p in raw_pairs:
        if not isinstance(p, dict):
            continue
        g = _sanitize(p.get("giris") or "")
        s = _sanitize(p.get("sonuc") or "")
        if g and s:
            pairs.append(MatchedPair(giris=g, sonuc=s))
    gelisme = _sanitize(parsed.get("gelisme") or "")

    if not (pairs and gelisme):
        logger.warning("video_script_writer: incomplete candidates from LLM")
        return None

    # Lint: flag any matched_pair whose intro opens with a banned brand
    # token. We don't drop them — caller can choose to skip — but logging
    # surfaces drift so the prompt can be tightened.
    for i, p in enumerate(pairs):
        violation = lint_intro_brand_first(p.giris)
        if violation:
            logger.warning(
                f"video_script_writer: matched_pair[{i}] intro lint: {violation}"
            )

    return VideoScriptCandidates(matched_pairs=pairs, gelisme=gelisme)


def assemble_script(c: VideoScriptCandidates, *, pair_idx: int = 0) -> str:
    """Assemble final narration from a selected matched pair.

    `pair_idx` picks one matched (GİRİŞ, SONUÇ) pair so the conclusion
    mirrors the same intro that opens the piece — the structural
    mirroring is what makes the close feel earned.
    """
    p = c.matched_pairs[pair_idx]
    return _sanitize(f"{p.giris} {c.gelisme} {p.sonuc}")


# ───────────────────────── complete-news writer (v2) ─────────────────────────
# Berkay 10 Haz 2026 — product principle: the Reel viewer must LEARN the WHOLE
# news from the video alone (not a teaser / single-beat). This replaces the
# 3-act tek-beat structure for the cansu_video_v2 path. Length: target ~30s,
# flexes to ~40s for dense news (665-char ceiling ≈ 40s at the locked
# 1.1-speed + light-pause prosody — measured 669c → 39.0s). A deterministic
# rotating outro is appended in code (never the LLM) so the body stays CTA-free
# and the autonomous gate can flag any in-body CTA.

# 2026-06-10 — prompt ASCII Türkçe yazılmıştı ("gunluk", "icin", "DEGIL");
# model promptun imlasını aynalayıp gövdeyi diakritiksiz üretiyordu → TTS
# "ş"yi "s", "ç"yi "c" okuyordu (Fable 5 videosu vakası). Prompt doğru
# Türkçe imla ile yeniden yazıldı + açık diakritik zorunluluğu eklendi.
# Deterministik emniyet: video_script_lint.asciified_turkish dedektörü.
COMPLETE_NEWS_SYSTEM_PROMPT = """Sen Cansu'sun — AI haberlerini arkadaşına çaktırır gibi anlatan; kuru, casual, hafif alaycı biri. Dikey kısa video (Reels) için TTS ile okunacak KONUŞMA dili narration yaz. Haber spikeri DEĞİLsin, kurumsal/gergin DEĞİLsin — olayı çözmüş, sana iki çift laf eden biri gibisin.

SES (KESİN):
- İKİNCİ TEKİL ŞAHIS, "sen" formu: "kullanabiliyorsun, takıldığında, senin için". Resmi "siz" formu ("kullanabilirsiniz, sizin, yapıyordunuz") KESİNLİKLE YASAK.
- Kuru, doğal, hype'sız. Yer yer hafif keskin/alaycı olabilir ama abartma. "Harika haber, müthiş, devrim" gibi coşku/reklam dili YOK.
- HOOK ile başla: ilk cümle olayı düz ama çarpıcı versin. Merak teaser'ı yapma (ne olduğunu söyle) ama sıkıcı spiker gibi de açma.

OLGU (ÇOK KATI): SADECE kaynakta olanı anlat. Kaynakta olmayan isim, sayı, oran, tarih, iddia UYDURMA, abartma. Yorum/bakış açısı (ne işe yarar, ne değişir) senin olabilir ama OLGU gibi sunma; "işin pratiği şu" gibi ayır.

İÇERİK (liste DEĞİL, anlat): İzleyen başka yere bakmadan olayı kapsın — ama HER detayı dökme. EN ÖNEMLİ tek resmi ver: ne oldu + neden önemli + varsa TEK kritik detay. Ürün-paketi sayma (Go, Plus, Pro... gibi listeyi KISA geç ya da AT), yan platform/ikincil sayıları at. Akıcı anlat, madde sıralar gibi okuma.

ANLAŞILIRLIK (KESİN): İngilizce teknik terimi (rate limit, reset, prompt, token, agent, frontier model...) OLDUĞU GİBİ KULLANMA — TTS yanlış seslendirir, izleyici takılır. Düz Türkçe karşılığını kullan: rate limit → kullanım sınırı/kotası, reset → sıfırlama ya da yenileme hakkı, prompt → komut, token → kullanım kredisi. Akış içinde doğal söyle; "X yani Y" diye cümleyi durdurup ders verme. Şüphedeysen terimi hiç kullanma, olayı düz Türkçe anlat.

UZUNLUK: ~25-35 saniye. Gövde 420-560 karakter. Sığmıyorsa ikincil şeyi at, olayı kesme. Boş laf/tekrarla uzatma.

DİL/BİÇİM:
- Akıcı, nefes alan kısa cümleler. Konuşma dili.
- TÜRKÇE İMLA ZORUNLU: ş, ç, ğ, ü, ö, ı, İ her kelimede doğru. ASCII'leşmiş Türkçe ("icin", "calisiyor") KESİNLİKLE YASAK (TTS yanlış okur).
- Sayıları YAZIYLA yaz (yüzde seksen yedi gibi).
- Kendi adını, "Cansu" kelimesini, "ben/biz/kanal/abone" gibi self-referans KULLANMA.
- Kanal/marka adı UYDURMA.
- Em-dash, kısa çizgi, üç nokta, ünlem, soru işareti YOK. Sadece nokta ve virgül.
- CTA/outro EKLEME (sistem ekleyecek).

Çıktı: SADECE narration metni, tek paragraf."""


# Rotating follow-CTA outros (Berkay 10 Haz 2026). Appended deterministically by
# topic hash so the close is always clean + budget-stable but not monotone.
VIDEO_OUTROS = [
    "En güncel yapay zeka haberleri için takipte kalın.",
    "Yapay zeka gündemini kaçırmamak için takipte kal.",
    "Daha fazlası için takipte kal.",
]


def pick_outro(topic: str) -> str:
    """Deterministic outro by topic hash (same topic → same outro)."""
    import hashlib

    h = int(hashlib.md5((topic or "").encode("utf-8")).hexdigest(), 16)
    return VIDEO_OUTROS[h % len(VIDEO_OUTROS)]


def _strip_code_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = "\n".join(t.split("\n")[1:])
        if t.endswith("```"):
            t = "\n".join(t.split("\n")[:-1])
    return t.strip()


async def build_complete_news_script(
    *, topic: str, source: str, avoid_feedback: Optional[str] = None
) -> Optional[str]:
    """Complete-news narration body (NO outro). Returns None on failure.

    Single Sonnet 4.6 pass. The caller appends the outro via append_outro()
    and runs the result through script_lint before spending on a render.
    Returns the RAW model body (only code-fence/whitespace stripped) so the
    autonomous gate sees any artifacts the prompt failed to prevent.
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("complete_news_writer: openai not installed")
        return None
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        logger.warning("complete_news_writer: no OPENROUTER_API_KEY; skipping")
        return None

    client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
    # 2026-06-11 (Berkay): kaynak eskiden [:1500] sessizce kesiliyordu — kirli
    # çok-tweet blob'da bu, video'nun HANGİ tweet'i göreceğini rastgele
    # belirleyip caption'dan farklı (yanlış) habere atlamasına yol açtı. Kaynak
    # artık trend_engine'de tek hikâyeye temizlendiği için tam veriyoruz; yine de
    # token güvenliği için makul üst sınır (tek hikâye nadiren bunu aşar).
    _fb = (
        f"\n\nÖNEMLİ — önceki TTS denemesi şu kelime/ifadeleri KÖTÜ seslendirdi: "
        f"{avoid_feedback}. Bunları düz Türkçe karşılığıyla DEĞİŞTİR ya da hiç kullanma; "
        f"İngilizce teknik terimi ham bırakma."
        if avoid_feedback else ""
    )
    user_msg = f"Haber: {topic}\nKaynak: {(source or '')[:4000]}{_fb}\n\nNarration:"

    # LiteLLM Router (flag-gated, fail-open). Async writer call → router_chat_messages
    # with model_name="writer". Returns RAW body (only code-fence stripped), same as
    # the existing path. On any router error fall through to the OpenAI sync path.
    from .llm_router import router_enabled, router_chat_messages
    if router_enabled():
        try:
            text, _meta = await router_chat_messages(
                [
                    {"role": "system", "content": COMPLETE_NEWS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                model_name="writer", temperature=TEMPERATURE, max_tokens=700,
            )
            body = _strip_code_fence(text or "")
            if not body:
                logger.warning("complete_news_writer: empty body (router)")
                return None
            return body
        except Exception:
            logger.warning("complete_news_writer: router atlandı (fail-open)")

    try:
        resp = client.chat.completions.create(
            model=MODEL, temperature=TEMPERATURE, max_tokens=700,
            messages=[
                {"role": "system", "content": COMPLETE_NEWS_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        body = _strip_code_fence(resp.choices[0].message.content or "")
    except Exception:
        logger.exception("complete_news_writer: LLM call failed")
        return None

    if not body:
        logger.warning("complete_news_writer: empty body")
        return None
    return body


def append_outro(body: str, topic: str) -> str:
    """Append the deterministic rotating outro to a clean body."""
    body = (body or "").strip()
    if body and body[-1] not in ".!?":
        body += "."
    return f"{body} {pick_outro(topic)}".strip()


# ≤40s ceiling in chars at the locked prosody (669c → 39.0s render → ~17.1
# chars/s). 660 ≈ 38.5s leaves a small margin under the 40s hard line so the
# normalized script reliably clears pre_spend_guard + the script_lint gate.
COMPLETE_NEWS_MAX_CHARS = 660


def assemble_complete_news(
    body: str, topic: str, *, max_chars: int = COMPLETE_NEWS_MAX_CHARS
) -> str:
    """Body + deterministic outro, trimmed to the ≤40s budget.

    The writer is told to order sentences by importance (most critical first),
    so when a dense body would overflow we drop trailing (least-critical) body
    sentences — keeping the news complete on its essentials and the outro
    intact — instead of burning a retry or falling back to image-only.
    """
    import re

    body = (body or "").strip()
    outro = pick_outro(topic)
    budget = max_chars - len(outro) - 1  # space before outro

    if len(body) > budget:
        sents = re.split(r"(?<=[.!?])\s+", body)
        kept: list[str] = []
        for s in sents:
            candidate = (" ".join(kept + [s])).strip()
            if kept and len(candidate) > budget:
                break
            kept.append(s)
        body = " ".join(kept).strip()

    if body and body[-1] not in ".!?":
        body += "."
    return f"{body} {outro}".strip()
