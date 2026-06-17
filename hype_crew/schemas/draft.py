"""Writer and Compliance agent output schemas."""
from pydantic import BaseModel, Field
from typing import Optional


class WriterOutput(BaseModel):
    """Writer'ın ürettiği son draft.

    Note: 280-char limit is enforced by Compliance.hard_rules_check, not schema —
    TypeHype V3 may produce longer drafts for 'storm' (thread-like) uzunluk. Schema
    accepts up to 4000 to avoid validation errors; Compliance rejects if > 280.
    """

    content: str = Field(
        ..., min_length=1, max_length=4000,
        description="Tweet metni, formatlanmış (line breaks dahil)"
    )
    character_count: int = Field(..., ge=1, le=4000)
    hook_type: str = Field(..., description="Kullanılan hook stili")
    line_count: int = Field(..., ge=1, description="Satır sayısı")

    # Self-assessment (Writer kendi çıktısını değerlendirir)
    has_em_dash: bool = Field(
        False, description="Em-dash içeriyor mu (hard rule violation)"
    )
    has_corporate_words: list[str] = Field(
        default_factory=list,
        description="Tespit edilen kurumsal kelimeler (boş olmalı)"
    )
    voice_alignment_score: int = Field(
        ..., ge=0, le=100,
        description="Writer'ın self-assessment: brand voice ile uyum %"
    )


class ComplianceOutput(BaseModel):
    """Compliance agent kararı."""

    approved: bool = Field(..., description="Pipeline devam etsin mi (Publisher'a gider)")

    # Detailed checks
    dedup_passed: bool = Field(..., description="Son 7 günde benzer post yok mu")
    similarity_to_recent: float = Field(
        ..., ge=0.0, le=1.0,
        description="En benzer son posta Jaccard veya cosine benzerlik"
    )
    forbidden_topics_detected: list[str] = Field(
        default_factory=list,
        description="Yasaklı topic'lerle eşleşme (boş olmalı)"
    )
    hard_rules_violated: list[str] = Field(
        default_factory=list,
        description="İhlal edilen hard rule'lar"
    )
    brand_voice_score: int = Field(
        ..., ge=0, le=100,
        description="LLM critic ile brand voice alignment skoru"
    )

    rejection_reason: Optional[str] = Field(
        None, description="approved=False ise neden"
    )
    confidence: int = Field(
        ..., ge=0, le=100,
        description="Compliance kararının güveni (0-100)"
    )
