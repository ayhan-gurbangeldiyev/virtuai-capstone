"""L4-AMBIGUOUS recall rescue via sentence-transformer cosine similarity.

The persona gate's L4 branch is the "no AI keyword found anywhere" reject
path. Most L4 rows are correct rejects (sports/gadget noise) but a real
fraction are AI-adjacent stories where the headline never contains a
literal AI keyword. Example: "Internet trafiğinde botlar insanları geçti"
— this IS an AI story (bot traffic surpassing humans) but the keyword
list won't match "bot" alone.

Approach: embed (topic + raw_content[:500]) and take max-cosine vs a
small set of AI-CONCEPT exemplars. If the max is above threshold, rescue
the row and tag it `persona_gate=semantic_rescue` so the audit trail
can distinguish a rescue from a normal positive_match.

Design rules — same shape as faithfulness_gate._get_gliner:
  - Lazy-load singleton; first call eats the ~118 MB model + a few
    seconds, subsequent calls are zero-overhead.
  - Fail-safe = REJECT (never accidentally pass when model unavailable).
  - Never override L1 (blocked) / L3b (conditional brand-no-AI-signal).
  - Anchor exemplars cover the AI domain only (capabilities, agents,
    automation, research, safety, hardware, funding). NO phone /
    car / gadget / sport / entertainment anchors — that would
    rescue exactly the noise the gate is designed to keep out.

Calibration: threshold starts at 0.55 (tuned against the historical
persona_gate_log ambiguous rows on 2026-06-07). Operator can override
by env var SEMANTIC_RESCUE_THRESHOLD.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# Pinned, CPU-friendly, TR+EN-capable multilingual model.
# ~118 MB; runs at <100 ms/call on a single core after the first load.
SEMANTIC_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Anchor exemplars — AI-CONCEPT only. Each sentence is intentionally a
# short, declarative AI-relevant statement so the cosine landscape pulls
# AI-adjacent inputs in. Mix Turkish + English so the multilingual model
# can match either-language inputs naturally.
ANCHORS = (
    # capabilities
    "Yeni bir büyük dil modeli yayınlandı ve test sonuçları açıklandı.",
    "A new large language model launched today with benchmark results.",
    "Model yetenekleri ve sınırları üzerine bir araştırma paylaşıldı.",
    "Researchers published a paper on model capabilities and limits.",
    # agents / automation
    "Yapay zeka ajanları artık kullanıcı yerine görevleri otonom yürütüyor.",
    "AI agents can now autonomously complete multi-step tasks for users.",
    "Bot trafiği insan trafiğini geçti, otomatik sistemler yayıldı.",
    "Bot traffic on the internet has overtaken human traffic.",
    # research / interpretability / safety
    "Model güvenliği ve hizalama üzerine yeni bir teknik makale yayınlandı.",
    "A new alignment and safety paper from a frontier lab was published.",
    "Modelin iç katmanlarındaki nöron devreleri incelendi.",
    "Researchers traced internal neural circuits inside a transformer.",
    # tool use / coding agent / dev experience
    "Geliştiriciler için yeni bir kod yazma ajanı yayınlandı.",
    "A coding agent that can branch, write code and open a PR.",
    "Yeni bir API geliştiricilere açıldı ve fiyatlandırma duyuruldu.",
    "A new developer API was announced with new pricing tiers.",
    # hardware / inference
    "Yeni nesil bir çıkarım hızlandırıcı çip duyuruldu.",
    "A new inference accelerator chip for serving LLMs was announced.",
    # business / funding / acquisitions
    "Bir AI şirketi büyük bir yatırım turu kapattı ve değeri açıklandı.",
    "An AI company closed a major funding round at a new valuation.",
    "Bir AI girişimi büyük bir teknoloji şirketi tarafından satın alındı.",
    "An AI startup was acquired by a major technology company.",
    # ecosystem / regulation
    "Bir AI hizmeti veya entegrasyonu için resmi soruşturma açıldı.",
    "A regulator opened an investigation into an AI service.",
    "Yapay zeka standardı veya açık spec için işbirliği duyuruldu.",
    "A standards body announced an open spec for AI agent interop.",
)


def _threshold_default() -> float:
    raw = (os.environ.get("SEMANTIC_RESCUE_THRESHOLD") or "").strip()
    try:
        return float(raw) if raw else 0.55
    except ValueError:
        return 0.55


_THRESHOLD = _threshold_default()


_MODEL_INSTANCE = None
_ANCHOR_EMBEDDINGS = None
_LOAD_LOCK_TRIED = False


@dataclass(frozen=True)
class SemanticRescueResult:
    rescued: bool                            # True → pass to TrendScout
    score: float                             # max cosine over anchors
    threshold: float
    matched_anchor: Optional[str] = None     # closest anchor (for audit)
    reason: str = ""                         # human-readable, for logs


def _get_model():
    """Lazy-load sentence-transformers + cache anchor embeddings."""
    global _MODEL_INSTANCE, _ANCHOR_EMBEDDINGS, _LOAD_LOCK_TRIED
    if _MODEL_INSTANCE is not None:
        return _MODEL_INSTANCE
    if _LOAD_LOCK_TRIED:
        return None

    _LOAD_LOCK_TRIED = True
    required = (os.environ.get("SEMANTIC_RESCUE_REQUIRED") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    try:
        # Heavy imports happen here, not at module top, so anyone who
        # imports persona_gate (and pulls this in via semantic_rescue)
        # doesn't pay the cost unless the rescue actually fires.
        from sentence_transformers import SentenceTransformer  # type: ignore
        logger.info(f"[semantic_rescue] loading {SEMANTIC_MODEL_ID} (first-call)…")
        _MODEL_INSTANCE = SentenceTransformer(SEMANTIC_MODEL_ID)
        _ANCHOR_EMBEDDINGS = _MODEL_INSTANCE.encode(
            list(ANCHORS),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        logger.info(
            f"[semantic_rescue] model + {len(ANCHORS)} anchors loaded "
            f"(threshold={_THRESHOLD})"
        )
        return _MODEL_INSTANCE
    except Exception as e:
        msg = (
            f"[semantic_rescue] load failed; L4-rescue DISABLED. "
            f"Operating in fail-safe REJECT mode. Underlying: "
            f"{type(e).__name__}: {e}"
        )
        if required:
            logger.error(msg)
            raise RuntimeError(
                "SEMANTIC_RESCUE_REQUIRED=true but sentence-transformers "
                "could not load. Install from hype_crew/requirements.txt."
            ) from e
        logger.warning(msg)
        return None


def evaluate_semantic_rescue(
    topic: str,
    raw_content: str = "",
    threshold: Optional[float] = None,
) -> SemanticRescueResult:
    """Score (topic + raw_content[:500]) against anchor exemplars.

    Returns SemanticRescueResult. On model-load failure or empty input,
    returns rescued=False (fail-safe). Never raises in normal use.
    """
    thr = float(threshold) if threshold is not None else _THRESHOLD
    text = (topic or "").strip() + " " + (raw_content or "")[:500].strip()
    text = text.strip()
    if not text:
        return SemanticRescueResult(False, 0.0, thr, None, "empty input")

    model = _get_model()
    if model is None or _ANCHOR_EMBEDDINGS is None:
        return SemanticRescueResult(False, 0.0, thr, None, "model unavailable")

    try:
        # Encode in single-sentence mode + normalize so cosine = dot.
        emb = model.encode(
            [text], convert_to_numpy=True, normalize_embeddings=True,
            show_progress_bar=False,
        )
        # max cosine over anchor set
        scores = (_ANCHOR_EMBEDDINGS @ emb.T).flatten()
        best_idx = int(scores.argmax())
        best_score = float(scores[best_idx])
        rescued = best_score >= thr
        return SemanticRescueResult(
            rescued=rescued,
            score=best_score,
            threshold=thr,
            matched_anchor=ANCHORS[best_idx],
            reason=(
                f"max_cosine={best_score:.3f} threshold={thr:.2f} "
                f"({'RESCUE' if rescued else 'keep-reject'})"
            ),
        )
    except Exception as e:
        logger.warning(
            f"[semantic_rescue] inference failed (fail-safe reject): "
            f"{type(e).__name__}: {e}"
        )
        return SemanticRescueResult(False, 0.0, thr, None,
                                    f"inference error: {type(e).__name__}")
