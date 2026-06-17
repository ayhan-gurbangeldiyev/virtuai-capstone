"""Reference anchor readiness + selection for Wiro identity-locked image gen.

Ported from VirtuAI/providers/reference_readiness.py.
Adapted: SQLAlchemy Asset model → dict (Supabase REST rows from persona_assets table).
Adapted: storage.signed_url protocol → hype_crew.tools.supabase_storage.SupabaseStorage.

Usage:
    anchors = await load_persona_anchors(persona_id)
    inputs = await prepare_reference_prompt_inputs(
        anchors,
        scene_description="..." ,
        outfit="...",
    )
    signed_urls = inputs.signed_reference_urls  # → pass to WiroClient.input_image
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import settings
from .supabase_client import make_supabase
from .supabase_storage import SupabaseStorage

ALLOWED_REFERENCE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MIN_REFERENCE_ANCHORS = 3
MIN_REFERENCE_DIMENSION = 512
MAX_REFERENCE_PROMPT_INPUTS = 8
DEFAULT_SIGNED_URL_EXPIRES_SECONDS = 3600


@dataclass(frozen=True)
class AnchorAsset:
    """Plain dict-backed view of a persona_assets row (asset_type='reference_anchor')."""

    id: str
    storage_bucket: str
    storage_key: str
    mime_type: str
    content_hash: str
    status: str
    width: int | None
    height: int | None
    metadata: dict[str, Any]
    created_at: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> AnchorAsset:
        return cls(
            id=str(row["id"]),
            storage_bucket=row.get("storage_bucket") or settings.supabase_reference_bucket,
            storage_key=row["storage_key"],
            mime_type=row["mime_type"],
            content_hash=row.get("content_hash") or "",
            status=row.get("status") or "pending",
            width=row.get("width"),
            height=row.get("height"),
            metadata=row.get("generation_metadata") or {},
            created_at=row.get("created_at") or "",
        )


@dataclass(frozen=True)
class ReferenceAnchorSummary:
    asset_id: str
    storage_key: str
    mime_type: str
    width: int | None
    height: int | None
    content_hash: str
    status: str


@dataclass(frozen=True)
class ReferenceAnchorReadiness:
    ready: bool
    anchor_count: int
    usable_anchor_count: int
    required_anchor_count: int
    min_dimension: int
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    anchors: list[ReferenceAnchorSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "anchor_count": self.anchor_count,
            "usable_anchor_count": self.usable_anchor_count,
            "required_anchor_count": self.required_anchor_count,
            "min_dimension": self.min_dimension,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "anchors": [a.__dict__ for a in self.anchors],
        }


@dataclass(frozen=True)
class ReferencePromptInputs:
    readiness: ReferenceAnchorReadiness
    signed_reference_urls: list[str]
    selected_anchors: list[ReferenceAnchorSummary]
    expires_seconds: int


async def load_persona_anchors(persona_id: str) -> list[AnchorAsset]:
    """Fetch all reference_anchor rows for a persona from Supabase."""
    sb = make_supabase()
    rows = (
        sb.table("persona_assets")
        .select("*")
        .eq("persona_id", persona_id)
        .eq("asset_type", "reference_anchor")
        .order("created_at", desc=False)
        .execute()
    )
    return [AnchorAsset.from_row(row) for row in (rows.data or [])]


def build_reference_anchor_readiness(
    anchors: list[AnchorAsset],
    *,
    min_count: int = MIN_REFERENCE_ANCHORS,
    min_dimension: int = MIN_REFERENCE_DIMENSION,
) -> ReferenceAnchorReadiness:
    sorted_anchors = sorted(anchors, key=lambda a: a.created_at)
    blockers: list[str] = []
    warnings: list[str] = []
    summaries: list[ReferenceAnchorSummary] = []
    usable_count = 0

    if not sorted_anchors:
        blockers.append("No reference_anchor assets found for this persona")

    for asset in sorted_anchors:
        asset_blockers = _asset_blockers(asset, min_dimension=min_dimension)
        blockers.extend(asset_blockers)
        if not asset_blockers:
            usable_count += 1
        summaries.append(
            ReferenceAnchorSummary(
                asset_id=asset.id,
                storage_key=asset.storage_key,
                mime_type=asset.mime_type,
                width=asset.width,
                height=asset.height,
                content_hash=asset.content_hash,
                status=asset.status,
            )
        )

    if len(sorted_anchors) < min_count:
        blockers.append(
            f"Need at least {min_count} reference anchors, found {len(sorted_anchors)}"
        )
    if usable_count < min_count:
        blockers.append(
            f"Need at least {min_count} usable reference anchors, found {usable_count}"
        )
    if len(sorted_anchors) > MAX_REFERENCE_PROMPT_INPUTS:
        warnings.append(
            f"More than {MAX_REFERENCE_PROMPT_INPUTS} anchors found; "
            "curate a smaller set for Wiro input"
        )

    return ReferenceAnchorReadiness(
        ready=not blockers,
        anchor_count=len(sorted_anchors),
        usable_anchor_count=usable_count,
        required_anchor_count=min_count,
        min_dimension=min_dimension,
        blockers=blockers,
        warnings=warnings,
        anchors=summaries,
    )


async def prepare_reference_prompt_inputs(
    anchors: list[AnchorAsset],
    *,
    storage: SupabaseStorage | None = None,
    expires_seconds: int = DEFAULT_SIGNED_URL_EXPIRES_SECONDS,
    min_count: int = MIN_REFERENCE_ANCHORS,
    min_dimension: int = MIN_REFERENCE_DIMENSION,
    max_prompt_inputs: int = MAX_REFERENCE_PROMPT_INPUTS,
    scene_description: str | None = None,
    content_context: str | None = None,
    outfit: str | None = None,
) -> ReferencePromptInputs:
    """Return short-lived private signed URLs for Wiro prompt input."""
    if max_prompt_inputs < 1 or max_prompt_inputs > MAX_REFERENCE_PROMPT_INPUTS:
        raise ValueError(
            f"max_prompt_inputs must be 1..{MAX_REFERENCE_PROMPT_INPUTS}"
        )
    readiness = build_reference_anchor_readiness(
        anchors,
        min_count=min_count,
        min_dimension=min_dimension,
    )
    if not readiness.ready:
        raise RuntimeError("Reference anchors are not ready: " + "; ".join(readiness.blockers))

    storage_client = storage or SupabaseStorage()
    selected_anchors = _select_prompt_anchors(
        anchors,
        max_prompt_inputs=max_prompt_inputs,
        scene_description=scene_description,
        content_context=content_context,
        outfit=outfit,
    )
    urls = []
    for anchor in selected_anchors:
        signed = await storage_client.signed_url(
            anchor.storage_bucket,
            anchor.storage_key,
            expires_seconds=expires_seconds,
        )
        urls.append(signed)

    return ReferencePromptInputs(
        readiness=readiness,
        signed_reference_urls=urls,
        selected_anchors=[
            ReferenceAnchorSummary(
                asset_id=a.id,
                storage_key=a.storage_key,
                mime_type=a.mime_type,
                width=a.width,
                height=a.height,
                content_hash=a.content_hash,
                status=a.status,
            )
            for a in selected_anchors
        ],
        expires_seconds=expires_seconds,
    )


def _asset_blockers(asset: AnchorAsset, *, min_dimension: int) -> list[str]:
    blockers: list[str] = []
    label = f"asset {asset.id}"

    if asset.status not in ("generated", "compliance_passed", "publish_ready", "pending"):
        blockers.append(f"{label}: status must be valid (got {asset.status})")
    if asset.mime_type not in ALLOWED_REFERENCE_IMAGE_TYPES:
        blockers.append(f"{label}: unsupported MIME type {asset.mime_type}")
    if not asset.content_hash:
        blockers.append(f"{label}: content_hash is required")

    md = asset.metadata or {}
    if md.get("consent_confirmed") is not True:
        blockers.append(f"{label}: consent_confirmed metadata must be true")
    if md.get("real_person_reference") is not True:
        blockers.append(f"{label}: real_person_reference metadata must be true")
    if md.get("do_not_publish") is not True:
        blockers.append(f"{label}: do_not_publish metadata must be true")
    if md.get("private_reference_storage") is not True:
        blockers.append(f"{label}: private_reference_storage metadata must be true")

    width = asset.width
    height = asset.height
    if width is None or height is None:
        blockers.append(f"{label}: width/height required")
    elif width < min_dimension or height < min_dimension:
        blockers.append(
            f"{label}: image must be at least {min_dimension}px on both sides (got {width}x{height})"
        )
    return blockers


def _select_prompt_anchors(
    anchors: list[AnchorAsset],
    *,
    max_prompt_inputs: int,
    scene_description: str | None = None,
    content_context: str | None = None,
    outfit: str | None = None,
) -> list[AnchorAsset]:
    """Pick the strongest Image 1 + scene-aware support anchors."""
    if not anchors:
        return []
    identity_anchor = min(
        anchors,
        key=lambda asset: (_identity_anchor_score(asset), asset.created_at),
    )
    selected = [identity_anchor]
    if max_prompt_inputs == 1:
        return selected

    scene_context = _selection_context(
        scene_description=scene_description,
        content_context=content_context,
        outfit=outfit,
    )
    remaining = [a for a in anchors if a.id != identity_anchor.id]
    for role in _desired_scene_roles(scene_context):
        if len(selected) >= max_prompt_inputs or not remaining:
            break
        next_anchor = min(
            remaining,
            key=lambda asset: (_role_anchor_score(asset, role, scene_context), asset.created_at),
        )
        selected.append(next_anchor)
        remaining = [a for a in remaining if a.id != next_anchor.id]
    if len(selected) < max_prompt_inputs and remaining:
        sorted_remaining = sorted(
            remaining,
            key=lambda asset: (_scene_anchor_score(asset, scene_context), asset.created_at),
        )
        selected.extend(sorted_remaining[: max_prompt_inputs - len(selected)])
    return selected


def _identity_anchor_score(asset: AnchorAsset) -> int:
    text = f"{asset.storage_key} {asset.metadata}".lower()
    score = 100
    if "front" in text: score -= 35
    if "close" in text: score -= 30
    if "neutral" in text: score -= 12
    if "medium" in text: score -= 18
    if "profile" in text: score += 25
    if "_34" in text or "three_quarter" in text: score += 8
    if "workspace" in text: score += 18
    if "fullbody" in text: score += 20
    if "back" in text: score += 80
    if "smile" in text: score += 4
    if "alt" in text: score += 5
    return score


def _scene_anchor_score(asset: AnchorAsset, scene_context: str) -> int:
    text = f"{asset.storage_key} {asset.metadata}".lower()
    score = 100
    if "close" in text: score -= 20
    if "_34" in text or "three_quarter" in text: score -= 28
    if "profile" in text: score -= 12
    if "neutral" in text: score -= 8
    if "medium" in text: score -= 8
    if "smile" in text: score += 8
    if _has_any(scene_context, ("warm", "coffee", "cafe", "kitchen", "home", "casual")):
        if "smile" in text or "warm" in text: score -= 24
    if _has_any(scene_context, ("workspace", "laptop", "dashboard", "office", "product", "levent")):
        if "workspace" in text or "laptop" in text or "dashboard" in text: score -= 42
    elif "workspace" in text or "laptop" in text or "dashboard" in text: score += 25
    if _has_any(scene_context, ("full body", "fullbody", "outfit", "jeans", "walking", "standing")):
        if "fullbody" in text or "jeans" in text: score -= 45
    elif "fullbody" in text: score += 18
    if _has_any(scene_context, ("back view", "rear", "walking away")):
        if "back" in text: score -= 50
    elif "back" in text: score += 90
    if "alt" in text: score += 6
    return score


def _desired_scene_roles(scene_context: str) -> tuple[str, ...]:
    if _has_any(scene_context, ("workspace", "laptop", "dashboard", "office", "product", "levent")):
        return ("POSE", "ENVIRONMENT", "IDENTITY_SUPPORT", "OUTFIT")
    if _has_any(scene_context, ("warm", "coffee", "cafe", "kitchen", "home", "casual")):
        return ("IDENTITY_SUPPORT", "ENVIRONMENT", "POSE", "OUTFIT")
    if _has_any(scene_context, ("full body", "fullbody", "outfit", "jeans", "walking", "standing")):
        return ("OUTFIT", "POSE", "IDENTITY_SUPPORT", "ENVIRONMENT")
    return ("POSE", "IDENTITY_SUPPORT", "ENVIRONMENT", "OUTFIT")


def _role_anchor_score(asset: AnchorAsset, role: str, scene_context: str) -> int:
    text = f"{asset.storage_key} {asset.metadata}".lower()
    if role == "POSE":
        score = 100
        if "_34" in text or "three_quarter" in text: score -= 45
        if "profile" in text: score -= 20
        if "close" in text: score -= 12
        if "medium" in text: score -= 10
        if "workspace" in text or "laptop" in text or "dashboard" in text: score += 18
        if "fullbody" in text: score += 12
        if "back" in text: score += 90
        return score
    if role == "ENVIRONMENT":
        score = 120
        if _has_any(scene_context, ("workspace", "laptop", "dashboard", "office", "product")):
            if "workspace" in text or "laptop" in text or "dashboard" in text: score -= 90
        if _has_any(scene_context, ("warm", "coffee", "cafe", "kitchen", "home", "casual")):
            if "warm" in text or "kitchen" in text or "cafe" in text or "coffee" in text: score -= 80
        if "back" in text: score += 80
        if "_34" in text or "profile" in text: score += 15
        return score
    if role == "OUTFIT":
        score = 110
        if "fullbody" in text or "jeans" in text: score -= 70
        if "front" in text: score -= 10
        if "back" in text and not _has_any(scene_context, ("back view", "rear", "walking away")):
            score += 55
        return score
    return _scene_anchor_score(asset, scene_context)


def _selection_context(
    *,
    scene_description: str | None,
    content_context: str | None,
    outfit: str | None,
) -> str:
    return " ".join((scene_description or "", content_context or "", outfit or "")).lower()


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)
