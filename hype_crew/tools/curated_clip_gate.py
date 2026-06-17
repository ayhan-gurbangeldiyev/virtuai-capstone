"""Phase 42.C — CLIP similarity gate for HeyGen curated photo sync.

Critic's quantitative protection against Cansu identity drift when
Berkay generates non-selfie photos via HeyGen "Design with AI":

  HeyGen Avatar V claims identity consistency for video FROM A SINGLE
  CLIP. The "Design with AI" still-photo workflow generates each photo
  in a separate session and produces noticeable variance (different
  makeup, slightly different jaw width, different hair shine) across
  ~20-30% of cross-session photos. Manual review in isolation misses
  this — the drift is only visible side-by-side against the existing
  74 photos.

The gate runs ONCE per new photo, before the `persona_assets` INSERT:

  1. Compute mean CLIP embedding of the existing publish_ready
     `curated_photo` rows (cached in-process — only re-computed when the
     baseline grows).
  2. Embed the new photo's bytes.
  3. Cosine similarity → verdict:
       >= 0.78  PASS         (auto-approve, sync row as publish_ready)
       0.65–0.78 NEEDS_REVIEW (sync row as 'needs_review' status; the
                              curated photo selector ignores rows that
                              aren't publish_ready, so it's invisible
                              to the production picker until Berkay
                              flips the status manually)
       < 0.65   REJECT       (skip insert entirely, log ERROR)

The gate is FAIL-SAFE: if CLIP embedding fails (model not installed,
download error), the gate logs a warning and PASSES the photo through
unblocked. This keeps the sync flow working in dev environments without
the heavy ML deps installed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from .supabase_client import make_supabase


# In-process cache. Reset on process start. Holds (baseline_mean_tensor,
# baseline_size) keyed by persona_id.
_BASELINE_CACHE: dict[str, tuple[Any, int]] = {}


@dataclass(frozen=True)
class CuratedGateResult:
    verdict: str        # 'PASS' | 'NEEDS_REVIEW' | 'REJECT' | 'SKIPPED'
    score: Optional[float]    # mean cosine similarity vs baseline (None if SKIPPED)
    baseline_size: int        # number of existing photos in the baseline
    threshold_pass: float
    threshold_review: float
    reason: str               # human-readable explanation


def _load_baseline(persona_id: str) -> tuple[Any, int]:
    """Return (mean_embedding_tensor, baseline_size) for the persona's
    existing publish_ready curated photos. Cached per process."""
    if persona_id in _BASELINE_CACHE:
        return _BASELINE_CACHE[persona_id]

    # Heavy ML import deferred — keeps light-weight callers fast.
    from .compliance.clip_consistency import embed_image_bytes
    import httpx
    import torch

    sb = make_supabase()
    rows = (
        sb.table("persona_assets")
        .select("id, public_url, generation_metadata")
        .eq("persona_id", persona_id)
        .eq("asset_type", "curated_photo")
        .eq("status", "publish_ready")
        .execute()
    )
    photos = rows.data or []
    if not photos:
        _BASELINE_CACHE[persona_id] = (None, 0)
        return None, 0

    embs = []
    skipped = 0
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for r in photos:
            url = r.get("public_url")
            if not url:
                skipped += 1
                continue
            try:
                data = client.get(url).content
                emb = embed_image_bytes(data)  # already L2-normalized, [1, 768]
                embs.append(emb)
            except Exception as e:
                skipped += 1
                logger.warning(f"[curated_clip_gate] baseline embed failed for {r['id'][:8]}: {e}")

    if not embs:
        _BASELINE_CACHE[persona_id] = (None, 0)
        return None, 0

    # Mean of L2-normalized embeddings, then re-normalize. This gives a
    # centroid in the same unit sphere so cosine similarity comparisons
    # against new photos are well-defined.
    stacked = torch.cat(embs, dim=0)            # [N, 768]
    mean = stacked.mean(dim=0, keepdim=True)     # [1, 768]
    mean = mean / mean.norm(dim=-1, keepdim=True)
    logger.info(
        f"[curated_clip_gate] baseline computed: persona={persona_id[:8]} "
        f"size={len(embs)} (skipped {skipped})"
    )
    _BASELINE_CACHE[persona_id] = (mean, len(embs))
    return mean, len(embs)


def reset_baseline_cache(persona_id: Optional[str] = None) -> None:
    """Clear the in-process baseline cache. Call after manual SQL edits
    or test resets."""
    if persona_id is None:
        _BASELINE_CACHE.clear()
    else:
        _BASELINE_CACHE.pop(persona_id, None)


def check_curated_photo(
    *,
    persona_id: str,
    new_image_bytes: bytes,
    threshold_pass: float = 0.78,
    threshold_review: float = 0.65,
    min_baseline_size: int = 5,
) -> CuratedGateResult:
    """Run the CLIP similarity gate for ONE new curated photo.

    Args:
        persona_id: target persona.
        new_image_bytes: raw image bytes of the newly fetched HeyGen photo.
        threshold_pass: cosine similarity >= this → PASS.
        threshold_review: cosine in [threshold_review, threshold_pass)
            → NEEDS_REVIEW (sync as 'needs_review' status, invisible to
            the picker until Berkay flips it).
        min_baseline_size: if the baseline has fewer than this many
            photos, the gate SKIPS (always PASSES) — there isn't enough
            signal to fairly judge drift. Default 5 matches the Critic's
            "library has 5+ photos before this is meaningful" condition.

    Returns:
        CuratedGateResult. On any failure (model not installed, download
        error, baseline computation crash) the verdict is 'SKIPPED' and
        the caller MUST proceed with the sync (fail-safe).
    """
    try:
        baseline_mean, baseline_size = _load_baseline(persona_id)
    except Exception as e:
        logger.warning(
            f"[curated_clip_gate] baseline load failed ({type(e).__name__}: {e}); "
            f"SKIPPING gate (fail-safe → photo will be synced as-is)"
        )
        return CuratedGateResult(
            verdict="SKIPPED",
            score=None,
            baseline_size=0,
            threshold_pass=threshold_pass,
            threshold_review=threshold_review,
            reason=f"baseline_load_failed: {type(e).__name__}",
        )

    if baseline_mean is None or baseline_size < min_baseline_size:
        return CuratedGateResult(
            verdict="SKIPPED",
            score=None,
            baseline_size=baseline_size,
            threshold_pass=threshold_pass,
            threshold_review=threshold_review,
            reason=f"baseline_too_small: {baseline_size} < {min_baseline_size}",
        )

    try:
        from .compliance.clip_consistency import embed_image_bytes
        emb = embed_image_bytes(new_image_bytes)
        sim = float((emb @ baseline_mean.T).item())
    except Exception as e:
        logger.warning(
            f"[curated_clip_gate] new-photo embed failed ({type(e).__name__}: {e}); "
            f"SKIPPING gate"
        )
        return CuratedGateResult(
            verdict="SKIPPED",
            score=None,
            baseline_size=baseline_size,
            threshold_pass=threshold_pass,
            threshold_review=threshold_review,
            reason=f"embed_failed: {type(e).__name__}",
        )

    if sim >= threshold_pass:
        verdict = "PASS"
        reason = f"sim={sim:.3f} >= {threshold_pass:.2f} (PASS threshold)"
    elif sim >= threshold_review:
        verdict = "NEEDS_REVIEW"
        reason = f"sim={sim:.3f} in gray zone [{threshold_review:.2f}, {threshold_pass:.2f}) — manual review"
    else:
        verdict = "REJECT"
        reason = f"sim={sim:.3f} < {threshold_review:.2f} (REJECT threshold) — identity drift detected"

    logger.info(
        f"[curated_clip_gate] persona={persona_id[:8]} verdict={verdict} "
        f"score={sim:.3f} baseline_size={baseline_size}"
    )
    return CuratedGateResult(
        verdict=verdict,
        score=sim,
        baseline_size=baseline_size,
        threshold_pass=threshold_pass,
        threshold_review=threshold_review,
        reason=reason,
    )
