"""TrendScout agent output schema."""
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional


def _clamp(value, lo, hi):
    """Phase 28.C — Gemini occasionally emits out-of-bounds breakdown ints
    (e.g. rekabet=2 when max is 1). Strict validation kills the run; clamping
    keeps the pipeline alive and just signals the upper-bound limit was hit."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, v))


ContentType = Literal[
    "model_launch", "product_launch", "feature_major", "feature_minor",
    "api_update", "pricing", "access_expansion", "research", "security",
    "partnership", "blog_post", "other",
]


class TrendScoutBreakdown(BaseModel):
    """Phase 25.A — 12-point scoring rubric ported from n8n Content Factory.

    Sub-scores let us debug why a trend was rejected and A/B test the rubric
    over time. Sum of breakdown = final_score_12.
    """
    duyuru_tipi: int = Field(..., ge=0, le=5, description=
        "0=update yok, 1=teknik update, 2=minor feature, 3=major feature, "
        "4=yeni ürün/app, 5=yeni nesil model (GPT-5 vb.)")
    erisim: int = Field(..., ge=0, le=2, description=
        "0=erişim yok, 1=sınırlı (waitlist/Pro), 2=herkese açık")
    kullanilabilirlik: int = Field(..., ge=0, le=2, description=
        "0=belirsiz tarih, 1=yakında (bu hafta/ay), 2=bugün aktif")
    kaynak: int = Field(..., ge=0, le=1, description=
        "0=3. parti/leak, 1=resmi şirket blogu/duyurusu")
    rekabet: int = Field(..., ge=0, le=1, description=
        "0=rakipler zaten sunuyor, 1=sektörde ilk/fark yaratıyor")
    fiyat: int = Field(..., ge=0, le=1, description=
        "0=fiyat aynı/arttı/ilgisiz, 1=ücretsiz/fiyat düştü/free tier eklendi")

    # Phase 28.C — clamp LLM out-of-range outputs instead of crashing the run.
    @field_validator("duyuru_tipi", mode="before")
    @classmethod
    def _clamp_duyuru_tipi(cls, v): return _clamp(v, 0, 5)
    @field_validator("erisim", mode="before")
    @classmethod
    def _clamp_erisim(cls, v): return _clamp(v, 0, 2)
    @field_validator("kullanilabilirlik", mode="before")
    @classmethod
    def _clamp_kullanilabilirlik(cls, v): return _clamp(v, 0, 2)
    @field_validator("kaynak", mode="before")
    @classmethod
    def _clamp_kaynak(cls, v): return _clamp(v, 0, 1)
    @field_validator("rekabet", mode="before")
    @classmethod
    def _clamp_rekabet(cls, v): return _clamp(v, 0, 1)
    @field_validator("fiyat", mode="before")
    @classmethod
    def _clamp_fiyat(cls, v): return _clamp(v, 0, 1)


class TrendScoutOutput(BaseModel):
    """TrendScout'un seçtiği (veya pas geçtiği) trend.

    `passed=False` ise pipeline burada durur (Planner çağırılmaz).
    """

    trend_id: str = Field(..., description="Supabase trends.id")
    topic: str = Field(..., description="Trend konusu, kısa")
    score: int = Field(..., ge=0, le=100, description=
        "Backwards-compat skor 0-100. Hesaplama: final_score_12 * 8.33 (yaklaşık)")
    is_vip: bool = Field(False, description="VIP kaynaktan mı (Tier 1 hesaplar)")
    category: str = Field(..., description="ai/tech/business/crypto/gündem/spor/diğer")
    semantic_triggers: list[str] = Field(
        default_factory=list,
        description="launch/scandal/milestone/breaking/release/etc",
    )
    urgency_hours: int = Field(
        ..., ge=1, le=168, description="Kaç saat içinde stale olur (1-168)"
    )
    angle_hint: str = Field(
        default="",
        description="İçerik açısı önerisi (Planner'a brief input). Gemini occasionally emits null when trend is skipped — coerced to empty string.",
    )
    reasoning: str = Field(..., description="Neden bu trend seçildi / pas geçildi")

    # Phase 25.A — n8n Content Factory rubric (sub-score breakdown + content_type)
    breakdown: Optional[TrendScoutBreakdown] = Field(
        default=None, description=
        "6-sub-score breakdown (sum=final_score_12). Optional for backwards "
        "compat with old runs that only had `score`."
    )
    final_score_12: Optional[int] = Field(
        default=None, ge=0, le=12, description=
        "Toplam 12-puan rubric skoru (n8n stili). Eşik: >=8 → passed=True."
    )
    content_type: Optional[ContentType] = Field(
        default=None, description=
        "İçerik kategorisi (n8n taxonomy). Planner ve Visual Director "
        "voice_mode + visual_mode kararları için kullanır."
    )

    # Filter result — eğer False ise sonraki ajanlar çalışmaz
    passed: bool = Field(True, description="Trend pipeline'a giriyor mu")
    skip_reason: Optional[str] = Field(None, description="passed=False ise nedeni")

    # Phase 35.3 — separate video gate (Berkay 30 May 2026: text+image her
    # haber için OK ama video sadece "çok yüksek" haberler için). Score'dan
    # bağımsız ayrı semantic karar.
    video_worthy: bool = Field(
        False,
        description=(
            "Bu trend video üretimine değer mi? Sadece şu durumlarda True:\n"
            "1) Major launch (yeni model/ürün, GPT-6 / Claude 5 gibi)\n"
            "2) Breaking news (industry-shaking, anlık tepki gerektiren)\n"
            "3) Sektör değiştiren milestone (ilk, tarihsel, rekor)\n"
            "4) M&A / büyük ortaklık (Anthropic + Apple gibi)\n"
            "Sıradan duyuru, feature update, blog post, region expansion "
            "→ False. Default False, conservative."
        ),
    )
    video_reason: Optional[str] = Field(
        None,
        description="video_worthy=True ise kısa gerekçe (1 cümle)",
    )
