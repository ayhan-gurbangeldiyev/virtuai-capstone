"""Layer 1: CLIP face/identity consistency vs persona anchor set.

Loads open-clip ViT-L-14, computes image embedding for the generated image and for
each anchor, returns mean cosine similarity. Anchor embeddings are cached in
persona_assets.generation_metadata['clip_embedding'] once computed.

Threshold (settings.clip_similarity_threshold = 0.85):
    >= 0.85  PASS
    0.80..0.85  NEEDS_REVIEW (gray zone → LLM judge)
    < 0.80  FAIL

Run device: CPU only (no GPU on Hetzner). open-clip CPU inference is ~1-2s per image
on ViT-L-14, fast enough for our ~1-2 generations/hour flow.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import httpx
import open_clip
import torch
from loguru import logger
from PIL import Image

from config import settings
from ..supabase_client import make_supabase
from ..supabase_storage import SupabaseStorage

DEVICE = "cpu"  # Hetzner = CPU-only; open-clip is fast enough on Mac too
MODEL_NAME = "ViT-L-14"
PRETRAINED = "openai"  # OpenAI CLIP weights

_model = None
_preprocess = None


def _get_model():
    global _model, _preprocess
    if _model is None:
        logger.info(f"loading CLIP {MODEL_NAME} ({PRETRAINED}) on {DEVICE}...")
        model, _, preprocess = open_clip.create_model_and_transforms(
            MODEL_NAME, pretrained=PRETRAINED
        )
        model.to(DEVICE)
        model.eval()
        _model = model
        _preprocess = preprocess
        logger.info("CLIP loaded")
    return _model, _preprocess


def _image_to_tensor(data: bytes) -> torch.Tensor:
    _, preprocess = _get_model()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return preprocess(img).unsqueeze(0).to(DEVICE)


@torch.no_grad()
def embed_image_bytes(data: bytes) -> torch.Tensor:
    """Return a unit-normalized CLIP image embedding (shape [1, 768] for ViT-L-14)."""
    model, _ = _get_model()
    tensor = _image_to_tensor(data)
    feats = model.encode_image(tensor)
    feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu()


async def _download_storage_bytes(bucket: str, key: str) -> bytes:
    storage = SupabaseStorage()
    return await storage.download_bytes(bucket, key)


async def _download_url_bytes(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
    resp.raise_for_status()
    return resp.content


async def get_or_compute_anchor_embedding(anchor_row: dict[str, Any]) -> torch.Tensor:
    """Return cached anchor CLIP embedding from metadata, else compute + persist."""
    metadata = anchor_row.get("generation_metadata") or {}
    cached = metadata.get("clip_embedding")
    if cached:
        return torch.tensor(cached).reshape(1, -1)

    bucket = anchor_row.get("storage_bucket") or settings.supabase_reference_bucket
    key = anchor_row["storage_key"]
    data = await _download_storage_bytes(bucket, key)
    emb = embed_image_bytes(data)
    emb_list = emb.flatten().tolist()

    sb = make_supabase()
    new_meta = {**metadata, "clip_embedding": emb_list}
    sb.table("persona_assets").update({"generation_metadata": new_meta}).eq(
        "id", anchor_row["id"]
    ).execute()
    logger.info(f"cached CLIP embedding for anchor {anchor_row['id']}")
    return emb


async def load_anchor_embeddings(persona_id: str) -> list[torch.Tensor]:
    """Return list of anchor embeddings for a persona (compute + cache on first call)."""
    sb = make_supabase()
    rows = (
        sb.table("persona_assets")
        .select("id, storage_bucket, storage_key, generation_metadata")
        .eq("persona_id", persona_id)
        .eq("asset_type", "reference_anchor")
        .execute()
    )
    embs = []
    for row in rows.data or []:
        emb = await get_or_compute_anchor_embedding(row)
        embs.append(emb)
    return embs


@dataclass(frozen=True)
class ClipConsistencyResult:
    score: float            # mean cosine similarity over all anchors, 0..1
    max_score: float        # best single-anchor match
    min_score: float        # worst single-anchor match
    anchor_count: int
    verdict: str            # 'PASS' | 'NEEDS_REVIEW' | 'FAIL'
    threshold: float


async def check_consistency(
    *,
    generated_image_bytes: bytes,
    persona_id: str,
    threshold: float | None = None,
    gray_zone_floor: float | None = None,
) -> ClipConsistencyResult:
    """Compute CLIP cosine similarity of generated image vs each anchor.

    Note on thresholds: full-image CLIP cosine similarity for "same person,
    different scene" typically falls in 0.50-0.65 range — much lower than
    "same scene, small variation" cases. Defaults reflect this.
    """
    threshold = threshold if threshold is not None else settings.clip_similarity_threshold
    if gray_zone_floor is None:
        # Gray zone = 10 percentage points below PASS threshold
        gray_zone_floor = max(0.30, threshold - 0.10)
    anchor_embs = await load_anchor_embeddings(persona_id)
    if not anchor_embs:
        return ClipConsistencyResult(
            score=0.0, max_score=0.0, min_score=0.0,
            anchor_count=0, verdict="FAIL", threshold=threshold,
        )
    gen_emb = embed_image_bytes(generated_image_bytes)  # [1, 768]
    sims = []
    for a_emb in anchor_embs:
        # Both are unit-normalized; cosine sim = dot product
        sim = float((gen_emb @ a_emb.T).item())
        sims.append(sim)
    mean = sum(sims) / len(sims)
    verdict = (
        "PASS" if mean >= threshold
        else "NEEDS_REVIEW" if mean >= gray_zone_floor
        else "FAIL"
    )
    return ClipConsistencyResult(
        score=mean,
        max_score=max(sims),
        min_score=min(sims),
        anchor_count=len(sims),
        verdict=verdict,
        threshold=threshold,
    )
