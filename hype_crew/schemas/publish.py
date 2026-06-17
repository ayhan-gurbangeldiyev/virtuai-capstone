"""Publisher output + Flow state schemas."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal

from .trend import TrendScoutOutput
from .plan import PlannerOutput
from .draft import WriterOutput, ComplianceOutput


class PublisherOutput(BaseModel):
    """Postiz schedule sonucu (veya dry-run log)."""

    postiz_post_id: str = Field(
        ..., description="Postiz post ID; dry_run=true ise 'DRY_RUN_<uuid>'"
    )
    integration_id: str = Field(..., description="Postiz integration_id (X account)")
    scheduled_at: datetime = Field(..., description="Yayınlanacağı zaman")
    platform: str = Field("twitter", description="twitter/x default")
    dry_run: bool = Field(..., description="Gerçek Postiz call atıldı mı")


class FlowState(BaseModel):
    """CrewAI Flow state. Persist edilir (@persist), crash recovery için."""

    account_id: str = Field(..., description="connected_accounts.id")
    run_id: Optional[str] = Field(None, description="hype_runs.id (Flow runtime'da set edilir)")

    # Pipeline stage outputs (her aşama doldurulur)
    trend: Optional[TrendScoutOutput] = None
    plan: Optional[PlannerOutput] = None
    draft: Optional[WriterOutput] = None
    compliance: Optional[ComplianceOutput] = None
    publish: Optional[PublisherOutput] = None

    # User interaction (frontend approval sonrası set edilir)
    user_action: Optional[
        Literal["approved", "rejected", "edited", "pending", "expired"]
    ] = None
    user_feedback: Optional[str] = None
    user_edited_content: Optional[str] = None
