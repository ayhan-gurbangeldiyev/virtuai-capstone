"""Memory tools — transparent SQL + pgvector semantic recall.

We use:
- Simple SELECT for recency-based loading (cheap, transparent — SELECT to inspect).
- pgvector + cosine for semantic recall when relevance matters (dedup, voice match).

Each agent receives a formatted markdown string in its backstory
({memory_context} placeholder) plus on-demand semantic search tools.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

try:
    from crewai.tools import tool
except ImportError:
    def tool(*args, **kwargs):  # noqa: ARG001
        def _decorate(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return _decorate

from config import settings
from .supabase_client import make_supabase


# ─── Embedding helper ──────────────────────────────────────────────────────


_EMBED_MODEL = "openai/text-embedding-3-small"  # 1536 dim, $0.02/1M tokens


def embed_text(text: str) -> Optional[list[float]]:
    """Embed text via OpenRouter (passes through to OpenAI embeddings).

    Returns None on failure (caller falls back to non-semantic path).
    """
    if not text or not text.strip():
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        resp = client.embeddings.create(
            model=_EMBED_MODEL,
            input=text[:8000],  # cap input size for safety
        )
        return resp.data[0].embedding
    except Exception:
        return None


MemoryType = Literal[
    "voice_examples", "approved_drafts", "rejected_drafts",
    "performance_log", "trend_log", "editor_diffs",
    "refinement_pattern",  # Phase 28.P — rejection→acceptance refinement chains
]


# ─────────────────────────────────────────────────────────────────────
# Phase 43.B.3 — scope-tagged memory (Critic's overfitting fix)
# ─────────────────────────────────────────────────────────────────────
# Edit signals and visual rejections can over-fit if every one-off user
# tweak becomes a global rule (the "kahvehane sahnesi" problem). New
# writes carry metadata.scope_tag with one of:
#   - "draft_only"  → consumed only by the originating draft's own
#                     refinement loop; HIDDEN from Strategist/Writer/
#                     Visual Director context. Default for editor_diffs.
#   - "trend_type"  → applies across the same content_type/trend cluster
#                     but not globally. Visible.
#   - "global"      → persona-wide rule. Visible. Default for legacy
#                     rows that have no scope_tag (preserves existing
#                     behavior on rollout).
#
# Promotion from draft_only → trend_type/global happens via the Edit
# Elevation batch analyzer (Phase 43.D) — never auto-promote on a single
# edit.

SCOPE_TAG_DRAFT_ONLY = "draft_only"
SCOPE_TAG_TREND_TYPE = "trend_type"
SCOPE_TAG_GLOBAL = "global"
_VISIBLE_SCOPE_TAGS = {SCOPE_TAG_TREND_TYPE, SCOPE_TAG_GLOBAL}


def _is_scope_visible(row: dict) -> bool:
    """Phase 43.B.3 — return True if this memory row should leak into
    Strategist / Writer / Visual Director context.

    Backward-compat: rows written before scope_tag existed have no tag,
    so we treat 'missing' as 'global' (their previous effective scope).
    Only rows explicitly tagged 'draft_only' are filtered out.
    """
    md = row.get("metadata") or {}
    tag = (md.get("scope_tag") or "").strip().lower()
    if not tag:
        return True  # legacy rows — preserve old behavior
    return tag in _VISIBLE_SCOPE_TAGS


def load_memory_dict(account_id: str, limits: Optional[dict[str, int]] = None) -> dict[str, list[dict]]:
    """Load memory entries grouped by type. Plain helper (not a CrewAI tool).

    Returns dict[memory_type, list_of_rows_newest_first].
    """
    sb = make_supabase()
    default_limits = {
        "voice_examples": 20,
        "approved_drafts": 10,
        "rejected_drafts": 10,
        "performance_log": 5,
        "trend_log": 30,
        "editor_diffs": 10,
        "refinement_pattern": 8,  # Phase 28.P — last 8 refinement chains
    }
    limits = {**default_limits, **(limits or {})}

    out: dict[str, list[dict]] = {}
    for mtype, lim in limits.items():
        # Phase 43.B.3 — over-fetch so we can drop draft_only rows in-Python
        # and still satisfy the requested limit. 3× headroom is enough for
        # typical draft_only ratios (<30% per Critic estimate).
        result = (
            sb.table("hype_memory")
            .select("content, metadata, importance_score, created_at")
            .eq("account_id", account_id)
            .eq("memory_type", mtype)
            .order("created_at", desc=True)
            .limit(max(lim * 3, lim + 5))
            .execute()
        )
        rows = result.data or []
        visible: list[dict] = [r for r in rows if isinstance(r, dict) and _is_scope_visible(r)]
        out[mtype] = visible[:lim]
    return out


def format_memory_context(account_id: str) -> str:
    """Format all memory as markdown for prompt injection (TEXT subsystem).

    Used at crew kickoff to populate agent backstory {memory_context}
    placeholders. Phase 28: skips rejected_drafts entries whose
    `metadata.rejection_target == 'image'` — those rejections mean the text
    was fine and only the visual was bad, so they don't belong in the
    Strategist/Writer learning loop.
    """
    mem = load_memory_dict(account_id)

    def section(title: str, items: list[dict], formatter) -> str:
        if not items:
            return f"## {title}\n(no entries yet — first runs, fall back to voice_description)\n"
        body = "\n\n".join(formatter(r) for r in items)
        return f"## {title}\n{body}\n"

    # Phase 28 — filter rejected_drafts: skip image-only rejections.
    # Phase 28.R-Lite-V2 Sprint 3 — also skip target='both' when only
    # image was the actual complaint (image_rejection_reason set + no
    # text_rejection_reason and feedback is purely visual). Prevents
    # text-side learning pollution from "image was bad too" signals.
    def _is_text_polluted(r: dict) -> bool:
        md = r.get("metadata") or {}
        target = md.get("rejection_target")
        if target == "image":
            return True
        if target == "both":
            image_reason = md.get("image_rejection_reason")
            text_reason = md.get("reason") or ""
            # If user only flagged image reason and feedback text is short
            # generic ("ai gibi", "kötü") — treat as image-driven both.
            generic_short = (
                len(text_reason.strip()) < 12
                or text_reason.strip().lower() in {"ai gibi", "kötü", "kotu", "ai", "n/a"}
            )
            return bool(image_reason) and generic_short
        return False

    text_rejections = [
        r for r in (mem.get("rejected_drafts") or [])
        if not _is_text_polluted(r)
    ]

    # Phase 28.R-Lite-V2 Sprint 4 — number rejected entries so Strategist
    # can cite specific evidence ("memory: rejected #3") instead of
    # generalizing/hallucinating rules.
    def _numbered_reject(idx: int, r: dict) -> str:
        md = r.get("metadata") or {}
        return (
            f"[{idx + 1}] ❌ {r['content']}\n"
            f"    reason: {md.get('reason') or 'n/a'}\n"
            f"    category: {md.get('category') or 'n/a'}"
        )

    return "\n".join([
        section(
            "VOICE EXAMPLES (creator's authentic past tweets — match this tone)",
            mem.get("voice_examples", []),
            lambda r: r["content"],
        ),
        section(
            "APPROVED DRAFTS (recent wins — do more of this)",
            mem.get("approved_drafts", []),
            lambda r: r["content"],
        ),
        # Sprint 4 — use numbered renderer so Strategist can reference
        # specific entries in its reasoning (grounding discipline).
        (
            "## REJECTED DRAFTS (avoid these — NEVER repeat angle)\n"
            + (
                "\n\n".join(_numbered_reject(i, r) for i, r in enumerate(text_rejections))
                if text_rejections
                else "(no text rejections yet)"
            )
            + "\n"
        ),
        section(
            "RECENT PERFORMANCE (engagement signals)",
            mem.get("performance_log", []),
            lambda r: r["content"],
        ),
        # Phase 28.P — refinement chains. Strategist learns:
        # "trend X needed 4 iterations of softening tone before user approved".
        # When planning the NEXT trend, biases toward angles that historically
        # required FEW iterations (less user friction).
        section(
            "REFINEMENT PATTERNS (rejection→approval chains — bias toward angles that needed fewer iterations)",
            mem.get("refinement_pattern", []),
            lambda r: (
                f"{r['content']}\n"
                f"  iterations: {(r.get('metadata') or {}).get('iteration_count', '?')} | "
                f"platform: {(r.get('metadata') or {}).get('platform', '?')} | "
                f"trend: {(r.get('metadata') or {}).get('trend_topic', '?')[:60]}"
            ),
        ),
    ])


# ─── Visual learning loop (Phase 28) ────────────────────────────────────────


_IMAGE_REASON_TR = {
    "deformed_hand": "Bozuk eller / parmaklar (extra fingers, melted webbing, anatomik hata)",
    "fake_logo": "Sahte / bozuk marka logosu (laptop kapağı, telefon arkası)",
    "off_brand": "Marka kimliğine uymuyor (yanlış renk paleti, yanlış stil)",
    "identity_drift": "Persona'ya benzemiyor (face mismatch)",
    "ai_obvious": "Çok yapay görünüm (porselen cilt, plastik doku, beauty filter)",
    "aesthetic_poor": "Kompozisyon / ışık / renk dengesi zayıf",
    "wrong_scene": "Sahne yanlış (prompt'taki ortamla eşleşmiyor)",
    "other": "Diğer",
}


def format_visual_rejection_memory(account_id: str, *, limit: int = 8) -> str:
    """Format recent visual-only / image-targeted rejections for Visual Director prompt.

    Returns a markdown block listing recent image rejections grouped by reason
    so the image generator can avoid repeating the same mistakes. Returns
    empty string if no relevant signals.
    """
    sb = make_supabase()
    rows = (
        sb.table("hype_memory")
        .select("content, metadata, created_at")
        .eq("account_id", account_id)
        .eq("memory_type", "rejected_drafts")
        .order("created_at", desc=True)
        .limit(40)
        .execute()
    )
    def _md(row: dict) -> dict:
        md = row.get("metadata")
        return md if isinstance(md, dict) else {}

    # Phase 43.B.3 — scope-tag filter prevents one-off "kahvehane sahnesi"
    # complaints from becoming global Visual Director rules. Legacy rows
    # (no scope_tag) stay visible for back-compat.
    image_rows: list[dict] = [
        r for r in (rows.data or [])
        if isinstance(r, dict)
        and _md(r).get("rejection_target") in ("image", "both")
        and _is_scope_visible(r)
    ]
    if not image_rows:
        return ""

    # Group by reason
    by_reason: dict[str, list[dict]] = {}
    for r in image_rows[:limit]:
        reason = _md(r).get("image_rejection_reason") or "other"
        by_reason.setdefault(str(reason), []).append(r)

    lines: list[str] = ["## SON GÖRSEL HATALARI (BU KALIPLARDAN KAÇIN)"]
    for reason, items in by_reason.items():
        label = _IMAGE_REASON_TR.get(reason, reason)
        lines.append(f"\n### ❌ {label}  ({len(items)} kez reddedildi)")
        for r in items[:3]:  # max 3 examples per reason
            md = r.get("metadata") or {}
            url = md.get("image_url")
            topic = md.get("trend_topic") or "—"
            extra = ""
            if url:
                extra = f"  · referans: {url}"
            lines.append(f"- konu: {topic}{extra}")

    lines.append("\nBu hataları tekrarlama. Görseli üretirken bu kalıplarda gözlemlenen sorunları aktif olarak ÖNLEYECEK detaylar ekle.")
    return "\n".join(lines)


# ─── Recently-processed trends (to avoid duplicate processing) ──────────────


@tool("recent_trend_topics")
def recent_trend_topics(account_id: str, days: int = 7) -> list[str]:
    """List topics already covered by Hype Crew runs for this account.

    Used by Compliance for dedup signal (in addition to content similarity).
    """
    sb = make_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        sb.table("hype_memory")
        .select("content, metadata")
        .eq("account_id", account_id)
        .eq("memory_type", "trend_log")
        .gte("created_at", since)
        .execute()
    )
    return [(r.get("metadata") or {}).get("topic") for r in (result.data or []) if (r.get("metadata") or {}).get("topic")]


# ─── Save (called from backend API endpoints after user action) ─────────────


def save_memory_entry(
    account_id: str,
    memory_type: MemoryType,
    content: str,
    metadata: Optional[dict] = None,
    importance: float = 0.5,
    scope: Optional[str] = None,
    skip_embedding: bool = False,
    scope_tag: Optional[str] = None,
) -> str:
    """Insert a memory entry with embedding for semantic recall.

    Embedding is computed via text-embedding-3-small (1536 dim). On failure,
    falls back to inserting without embedding (will still work for recency-based
    recall but not semantic search).

    Phase 43.B.3 — `scope_tag` controls visibility in agent context. One of
    'draft_only' (default for editor_diffs — per-draft only, hidden from
    crew), 'trend_type' (applies per content_type cluster), 'global'
    (persona-wide). Callers can override; if unset, editor_diffs default to
    'draft_only' and everything else defaults to 'global' (the legacy
    behavior). The tag lives in metadata.scope_tag so it adds no new column
    and the filter reads it without schema changes.

    Returns the inserted row's id.
    """
    # Phase 43.B.3 — pick default scope_tag based on memory_type
    effective_scope_tag = scope_tag
    if effective_scope_tag is None:
        effective_scope_tag = (
            SCOPE_TAG_DRAFT_ONLY if memory_type == "editor_diffs" else SCOPE_TAG_GLOBAL
        )

    metadata_with_scope = {**(metadata or {}), "scope_tag": effective_scope_tag}

    sb = make_supabase()
    row: dict = {
        "account_id": account_id,
        "memory_type": memory_type,
        "scope": scope or f"/account/{account_id}/{memory_type.replace('_', '-')}",
        "content": content,
        "metadata": metadata_with_scope,
        "importance_score": importance,
    }
    if not skip_embedding:
        emb = embed_text(content)
        if emb is not None:
            row["embedding"] = emb
    result = sb.table("hype_memory").insert(row).execute()
    return result.data[0]["id"] if result.data else ""


# ─── Semantic recall (pgvector) ────────────────────────────────────────────


@tool("semantic_recall")
def semantic_recall(
    query: str,
    account_id: str,
    memory_types: Optional[list[str]] = None,
    limit: int = 5,
    min_similarity: float = 0.5,
) -> list[dict]:
    """Find memory entries semantically similar to `query` via pgvector cosine.

    Use cases:
    - "Find voice examples matching this trend topic" → Writer
    - "Has this angle been rejected before?" → Compliance / Planner
    - "Find similar past wins for this hook style" → Planner

    Returns list of {id, content, memory_type, similarity, metadata} sorted by similarity.
    Empty list if embedding fails or no matches above threshold.
    """
    emb = embed_text(query)
    if emb is None:
        return []

    sb = make_supabase()
    try:
        result = sb.rpc("match_hype_memory", {
            "query_embedding": emb,
            "match_account_id": account_id,
            "match_types": memory_types,
            "match_count": limit,
            "min_similarity": min_similarity,
        }).execute()
        return result.data or []
    except Exception:
        return []


def cosine_dedup_check(
    content: str,
    account_id: str,
    threshold: float = 0.85,
    types: Optional[list[str]] = None,
) -> dict:
    """Cosine-similarity dedup against approved/voice memory.

    Returns {passed, max_similarity, similar_id, similar_content}.
    Used by Compliance agent's dedup_check (replaces Jaccard for better quality).
    """
    matches = semantic_recall.func(  # bypass CrewAI tool wrapper (raw call)
        query=content,
        account_id=account_id,
        memory_types=types or ["approved_drafts", "voice_examples"],
        limit=1,
        min_similarity=0.0,
    ) if hasattr(semantic_recall, "func") else []

    if not matches:
        return {"passed": True, "max_similarity": 0.0, "similar_id": None, "similar_content": None}

    top = matches[0]
    sim = float(top.get("similarity", 0.0))
    return {
        "passed": sim < threshold,
        "max_similarity": round(sim, 3),
        "similar_id": top["id"] if sim >= threshold else None,
        "similar_content": top["content"] if sim >= threshold else None,
    }
