"""Planner agent output schema."""
from pydantic import BaseModel, Field
from typing import Literal, Optional


# Re-export so callers can `from schemas.plan import ContentType` if needed
ContentType = Literal[
    "model_launch", "product_launch", "feature_major", "feature_minor",
    "api_update", "pricing", "access_expansion", "research", "security",
    "partnership", "blog_post", "other",
]

VoiceMode = Literal["first_person_witty", "third_person_neutral", "hybrid"]


# Phase 25.B + Capstone F5 (4 Haz 2026) — Voice rotation mapping for Cansu.
# Phase 25.B originally mapped model_launch/research/security/partnership to
# third_person_neutral (gazeteci tone). This silently stripped Cansu Approved
# DNA via style_prompt_v2:167 — producing press-release output. Capstone
# resolves the conflict with planner_prompt.py:53 ("Cansu için
# third_person_neutral KULLANILMAZ") by upgrading those 4 types to `hybrid`
# (3.şahıs fact opener + 1.şahıs insider reaction close + DNA retained).
VOICE_BY_CONTENT_TYPE: dict[str, str] = {
    "model_launch": "hybrid",       # F5: was third_person_neutral
    "research": "hybrid",           # F5: was third_person_neutral
    "security": "hybrid",           # F5: was third_person_neutral
    "partnership": "hybrid",        # F5: was third_person_neutral
    "feature_major": "hybrid",
    "feature_minor": "hybrid",
    "api_update": "hybrid",
    "pricing": "hybrid",
    "product_launch": "hybrid",
    "access_expansion": "first_person_witty",
    "blog_post": "first_person_witty",
    "other": "first_person_witty",
}


def voice_mode_for_content_type(content_type: Optional[str]) -> str:
    """Return the canonical voice_mode for a given content_type.
    Falls back to 'first_person_witty' when content_type is missing/unknown
    (preserves pre-Phase-25 Cansu behaviour)."""
    if not content_type:
        return "first_person_witty"
    return VOICE_BY_CONTENT_TYPE.get(content_type, "first_person_witty")


class PlannerOutput(BaseModel):
    """Planner'ın seçtiği angle + V3 prompt builder parametreleri.

    TypeHype'ın mevcut prompt builder v3 ile uyumlu (etki/karakter/uzunluk).

    Phase 25 additions (content_type + voice_mode): Optional for backwards
    compatibility with old hype_runs whose flow_state predates these fields.
    """

    etki: Literal[
        "patlassin", "konustursun", "ogretsin", "iz_biraksin", "shitpost"
    ] = Field(..., description="İçeriğin hedef etkisi")

    karakter: Literal[
        "uzman", "otorite", "iceriden", "mentalist", "haberci"
    ] = Field(..., description="Anlatıcı karakter")

    uzunluk: Literal["micro", "punch", "spark", "storm"] = Field(
        ..., description="micro=1-2 cümle, punch=3-4, spark=tweet thread feel, storm=thread"
    )

    brief: str = Field(
        ..., min_length=20, max_length=800,
        description="Writer'a 2-3 cümle: konu + açı + neden önemli. Stil/opener kuralı yazma — Writer'ın kendi DNA'sı var."
    )

    # Phase 34 — hook_type, angle, target_engagement, reasoning Optional.
    # TypeHype API'ye parametre olarak gitmiyorlardı zaten; legacy log için tutulur.
    hook_type: Optional[Literal[
        "curiosity", "first-person", "result", "contrast", "question", "story"
    ]] = Field(default=None, description="Hook stili (opsiyonel, Writer'a iletilmez)")

    angle: Optional[str] = Field(
        default=None, max_length=500,
        description="Creator'ın bakışı (opsiyonel, log için)"
    )

    target_engagement: Optional[Literal["replies", "bookmarks", "reposts", "mixed"]] = Field(
        default=None, description="Engagement hedefi (opsiyonel, kullanılmıyor)"
    )

    reasoning: Optional[str] = Field(
        default=None, max_length=500,
        description="Seçim gerekçesi — kısa, memory citation içermeli"
    )

    # Phase 25.B — n8n Content Factory taxonomy + voice rotation
    content_type: Optional[ContentType] = Field(
        default=None, description=
        "İçerik kategorisi (n8n taxonomy). Strategist trend.breakdown ve "
        "trend.content_type'tan inherit edebilir veya override edebilir. "
        "Visual + voice mode kararları bundan türetilir."
    )
    voice_mode: Optional[VoiceMode] = Field(
        default=None, description=
        "Cansu'nun bu draft'taki sesi. Default: content_type'tan mapping "
        "(voice_mode_for_content_type). Strategist override edebilir."
    )
