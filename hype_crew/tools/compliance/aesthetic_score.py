"""Layer 3: LAION aesthetic predictor (improved v2, sac+logos+ava1 weights).

Uses CLIP ViT-L-14 image embeddings (already in memory from layer 1) + a small
MLP head to score image aesthetic quality on a 1..10 scale, normalized to 0..1.

Threshold (settings.aesthetic_threshold = 0.65):
    >= 0.65  PASS (high quality)
    0.50..0.65  NEEDS_REVIEW
    < 0.50  FAIL

Reference weights: christophschuhmann/improved-aesthetic-predictor
    sac+logos+ava1-l14-linearMSE.pth — small MLP, ~4MB

Downloaded on first use, cached in ~/.cache/hype_crew/aesthetic_predictor.pth
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import httpx
import torch
import torch.nn as nn
from loguru import logger
from PIL import Image

from config import settings
from .clip_consistency import embed_image_bytes, _get_model

# LAION improved aesthetic predictor v2 — CLIP ViT-L/14 → MLP → score 1..10
WEIGHTS_URL = (
    "https://github.com/christophschuhmann/improved-aesthetic-predictor/"
    "raw/main/sac%2Blogos%2Bava1-l14-linearMSE.pth"
)
CACHE_PATH = Path.home() / ".cache" / "hype_crew" / "aesthetic_predictor.pth"

DEVICE = "cpu"
_predictor = None


class _AestheticMLP(nn.Module):
    """Architecture matches christophschuhmann/improved-aesthetic-predictor."""

    def __init__(self, input_size: int = 768):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, 1024),
            nn.Dropout(0.2),
            nn.Linear(1024, 128),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.Dropout(0.1),
            nn.Linear(64, 16),
            nn.Linear(16, 1),
        )

    def forward(self, x):
        return self.layers(x)


def _ensure_weights() -> Path:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE_PATH.exists():
        logger.info(f"downloading aesthetic predictor weights → {CACHE_PATH}")
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            resp = client.get(WEIGHTS_URL)
        resp.raise_for_status()
        CACHE_PATH.write_bytes(resp.content)
        logger.info(f"  cached {len(resp.content) / 1024:.1f} KB")
    return CACHE_PATH


def _get_predictor() -> _AestheticMLP:
    global _predictor
    if _predictor is None:
        weights_path = _ensure_weights()
        mlp = _AestheticMLP(input_size=768)  # ViT-L/14 → 768d
        state = torch.load(weights_path, map_location=DEVICE, weights_only=True)
        mlp.load_state_dict(state)
        mlp.to(DEVICE)
        mlp.eval()
        _predictor = mlp
        logger.info("aesthetic predictor loaded")
    return _predictor


@dataclass(frozen=True)
class AestheticResult:
    raw_score: float       # 1..10 LAION scale
    normalized: float      # 0..1
    verdict: str           # 'PASS' | 'NEEDS_REVIEW' | 'FAIL'
    threshold: float


def score_aesthetic(generated_image_bytes: bytes) -> AestheticResult:
    """Return aesthetic score for the image."""
    threshold = settings.aesthetic_threshold
    embedding = embed_image_bytes(generated_image_bytes)  # [1, 768]
    predictor = _get_predictor()
    with torch.no_grad():
        raw = float(predictor(embedding).item())
    # LAION scale 1..10. Normalize to 0..1 using simple linear (clamp).
    normalized = max(0.0, min(1.0, (raw - 1.0) / 9.0))
    verdict = (
        "PASS" if normalized >= threshold
        else "NEEDS_REVIEW" if normalized >= 0.50
        else "FAIL"
    )
    return AestheticResult(
        raw_score=raw,
        normalized=normalized,
        verdict=verdict,
        threshold=threshold,
    )
