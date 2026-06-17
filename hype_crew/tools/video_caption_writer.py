# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""Multi-platform video caption writer for Cansu's videos.

Generates LinkedIn / YouTube Shorts / Instagram Reels copy for a Cansu
video, grounded in the source raw_content (no overclaiming) and with
per-platform conventions baked in.

Replaces the inline Sonnet call previously used in /tmp/create_meta_drafts.py.
Used by both manual draft routing and (future) the auto-routing path
inside hype_crew/flow.py video_branch.

Locked spec (Berkay 6 Haz 2026):

  (a) Grounding — every factual claim must be supported by source
      raw_content. No "all of X moved to Y" when source says "X is
      now also available in Y". No naming specific products (Creator
      Studio, etc.) unless the source names them. No expertise-is-
      obsolete reframings when source just says easier-to-use.
      Per-claim self-check enforced in the prompt + reported in the
      output JSON so the operator can audit.

  (b) Hashtags — Instagram gets 5–8 topical hashtags. YouTube Shorts
      ALWAYS gets #Shorts + 3–5 topical hashtags. LinkedIn gets none
      (no native hashtag convention on LI).

  (c) Voice — Cansu's distinctive editorial edge per-platform:
      LinkedIn analytical (operational frame, 1 sharp question close),
      Instagram punchy (concrete + zero-fluff hook),
      YouTube explainer (hook title + plain "ne değişti" frame).
      Banlist: "müthiş / devrim / game-changer / heyecan verici /
      olağanüstü", em-dash, ellipsis, exclamation.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

from loguru import logger

MODEL = "anthropic/claude-sonnet-4.6"
TEMPERATURE = 0.35
MAX_TOKENS = 2000


SYSTEM_PROMPT = """Sen Cansu Dut'sun. Bir Cansu video'sunun ALT METİNLERİNİ üreteceksin: LinkedIn post + YouTube Shorts title/description + Instagram Reels caption.

KIRILMAZ KURALLAR:

(A) GROUNDING — KAYNAK NE DİYORSA ONU SÖYLE:

Sana kaynak haberin raw_content'i veriliyor. HER iddianın kaynakta açıkça desteklenmesi gerekir. Kaynak modest (mütevazı) bir hamle diyorsa, sen abartmayacaksın.

KESİN YASAK aşırılıklar:
- Kaynak "X'i Y'ye TAŞIYOR" diyorsa, sen "X tarihe karıştı" / "X dönemi kapandı" / "Sekme açmak yok" YAZAMAZSIN. Move ≠ replace.
- Kaynak "şu beceri kolaylaşıyor" diyorsa, sen "beceri artık gereksiz / uzmanlık bitti" YAZAMAZSIN.
- Kaynakta GEÇMEYEN bir ürün/marka/özellik adı (örn. "Creator Studio") kullanamazsın. Sadece raw_content'te varsa kullan.
- Kaynak "bir özellik" diyorsa "tüm X" YAPMA. "Yeni asistan analizleri sohbete taşıyor" → "tüm analitik sohbete taşındı" YAZAMAZSIN.
- Spekülatif uzantı yasak: kaynak söylemiyorsa, "bu, X sektörünü değiştirecek" tarzı tahminler ekleme.

(B) HASHTAG KURALLARI:
- INSTAGRAM: 5-8 alakalı hashtag (konuya/markaya/sektöre dair).
- YOUTUBE SHORTS: HER ZAMAN #Shorts dahil + 3-5 konuya özel hashtag.
- LINKEDIN: Hashtag YOK (LinkedIn'in native hashtag kültürü zayıf).

(C) PER-PLATFORM VOICE (Cansu'nun belirgin editör tonu):

1. LINKEDIN (400-700 karakter):
   - Analitik, operasyonel zihinden konuşan ton.
   - "Şu ana kadar / yeni yapı / operasyonel çıkarım" tarzı somut yapı.
   - Influencer cheese YOK; "beğeni, abone, takip" YOK.
   - Sonu: kısa, dürüst bir soru veya gözlem. CTA yok.
   - Cansu'nun edge'i: yüzeysel yorumu reddet, somut iş akışı çıkarımı ver.

2. INSTAGRAM REELS CAPTION (100-200 karakter):
   - Punchy. Konkret. Sıfır floş.
   - 1-2 cümlede "ne değişti, ne işe yarar" diyen sert hook.
   - Hashtags ayrı satırda, captiondan sonra.

3. YOUTUBE SHORTS:
   - title (50-70 char): Hook'lu, brand-first değil. Soru tipi veya stakes tipi.
   - description (100-200 char): "ne değişti, neden önemli" — basit explainer.
   - Description sonu (yeni satırda): hashtagler.

(D) GENEL YAZIM YASAKLARI:
- "müthiş", "devrim", "game-changer", "heyecan verici", "olağanüstü", "çağ açan"
- Em-dash (—) yerine virgül veya nokta
- "..." yerine nokta
- Ünlem işareti (!)
- "Bizler", "ekibimiz" (3. şahıs gazetecide YASAK)

(E) ÖZ-DENETİM (zorunlu):
Çıktında her platform için bir `grounding_check` array'i ver. Her iddia için kaynaktaki kanıtı alıntıla. Kaynakta dayanak bulamadığın iddiayı DÜŞÜR ve `dropped_claims` listesine ekle.

ÇIKTI FORMAT — sadece JSON, başka metin yok, kod bloğu yok:

{
  "linkedin": {
    "body": "...",
    "grounding_check": [
      {"claim": "kısa iddia parçası", "source_evidence": "raw_content'ten alıntı"}
    ]
  },
  "youtube_shorts": {
    "title": "...",
    "description": "...",
    "hashtags": ["#Shorts", "#yapayzeka", "..."],
    "grounding_check": [...]
  },
  "instagram_reels": {
    "caption": "...",
    "hashtags": ["#yapayzeka", "#metaai", "..."],
    "grounding_check": [...]
  },
  "dropped_claims": [
    "Kaynakta dayanağı olmayan iddialar (varsa)"
  ]
}"""


@dataclass(frozen=True)
class PlatformCopy:
    linkedin_body: str
    youtube_title: str
    youtube_description: str
    youtube_hashtags: list[str]
    instagram_caption: str
    instagram_hashtags: list[str]
    grounding_checks: dict[str, list[dict]]
    dropped_claims: list[str]

    @property
    def youtube_full_content(self) -> str:
        hashtag_line = " ".join(self.youtube_hashtags) if self.youtube_hashtags else ""
        return f"{self.youtube_title}\n\n{self.youtube_description}\n\n{hashtag_line}".strip()

    @property
    def instagram_full_content(self) -> str:
        hashtag_line = " ".join(self.instagram_hashtags) if self.instagram_hashtags else ""
        return f"{self.instagram_caption}\n\n{hashtag_line}".strip()


def _sanitize(text: str) -> str:
    out = (text or "").strip()
    out = out.replace("—", ",").replace("…", ".").replace("!", ".")
    while "..." in out:
        out = out.replace("...", ".")
    return out


async def build_video_captions(
    *,
    narration_text: str,
    source_raw_content: str,
    topic: str,
    source_name: Optional[str] = None,
) -> Optional[PlatformCopy]:
    """Build grounded, voice-tuned multi-platform copy for a Cansu video.

    The narration is provided for tone/topic context, but factual claims
    must trace to `source_raw_content` per the grounding rule. Returns
    None on LLM unavailable / parse failure.
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("video_caption_writer: openai not installed")
        return None
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        logger.warning("video_caption_writer: no OPENROUTER_API_KEY")
        return None

    client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
    user_msg = (
        f"Konu: {topic}\n\n"
        f"Kaynak ({source_name or 'kaynak'}) raw_content:\n{source_raw_content}\n\n"
        f"Cansu'nun video narration'ı (ton referansı, faktör değil):\n{narration_text}"
    )

    # LiteLLM Router (flag-gated, fail-open). Async writer call → router_chat_messages
    # with model_name="writer" (claude-sonnet). On any router error we fall through to
    # the existing OpenAI sync path below (no behavior change when flag OFF).
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
            li = parsed.get("linkedin") or {}
            yt = parsed.get("youtube_shorts") or {}
            ig = parsed.get("instagram_reels") or {}
            yt_hashtags = list(yt.get("hashtags") or [])
            if not any(h.lstrip("#").lower() == "shorts" for h in yt_hashtags):
                yt_hashtags = ["#Shorts"] + yt_hashtags
            yt_hashtags = [h if h.startswith("#") else f"#{h}" for h in yt_hashtags if h]
            ig_hashtags = [h if h.startswith("#") else f"#{h}" for h in (ig.get("hashtags") or []) if h]
            return PlatformCopy(
                linkedin_body=_sanitize(li.get("body") or ""),
                youtube_title=_sanitize(yt.get("title") or ""),
                youtube_description=_sanitize(yt.get("description") or ""),
                youtube_hashtags=yt_hashtags,
                instagram_caption=_sanitize(ig.get("caption") or ""),
                instagram_hashtags=ig_hashtags,
                grounding_checks={
                    "linkedin": li.get("grounding_check") or [],
                    "youtube_shorts": yt.get("grounding_check") or [],
                    "instagram_reels": ig.get("grounding_check") or [],
                },
                dropped_claims=list(parsed.get("dropped_claims") or []),
            )
        except Exception:
            logger.warning("video_caption_writer: router atlandı (fail-open)")

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
        logger.exception("video_caption_writer: LLM call or parse failed")
        return None

    li = parsed.get("linkedin") or {}
    yt = parsed.get("youtube_shorts") or {}
    ig = parsed.get("instagram_reels") or {}

    # Hashtag-rule enforcement: YouTube Shorts ALWAYS includes #Shorts.
    yt_hashtags = list(yt.get("hashtags") or [])
    if not any(h.lstrip("#").lower() == "shorts" for h in yt_hashtags):
        yt_hashtags = ["#Shorts"] + yt_hashtags
    # Normalize: ensure leading '#' on every hashtag entry.
    yt_hashtags = [h if h.startswith("#") else f"#{h}" for h in yt_hashtags if h]
    ig_hashtags = [h if h.startswith("#") else f"#{h}" for h in (ig.get("hashtags") or []) if h]

    return PlatformCopy(
        linkedin_body=_sanitize(li.get("body") or ""),
        youtube_title=_sanitize(yt.get("title") or ""),
        youtube_description=_sanitize(yt.get("description") or ""),
        youtube_hashtags=yt_hashtags,
        instagram_caption=_sanitize(ig.get("caption") or ""),
        instagram_hashtags=ig_hashtags,
        grounding_checks={
            "linkedin": li.get("grounding_check") or [],
            "youtube_shorts": yt.get("grounding_check") or [],
            "instagram_reels": ig.get("grounding_check") or [],
        },
        dropped_claims=list(parsed.get("dropped_claims") or []),
    )
