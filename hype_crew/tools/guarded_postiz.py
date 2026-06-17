"""Single choke-point for ALL Postiz publish operations.

Every publish path — manual approve, cron auto-publish, video distribution,
direct postiz API — physically routes through `GuardedPostizClient`. The
gate (`assert_publishable`) runs `run_faithfulness_gate` and returns a
signed `GateOutcome`. `GuardedPostizClient.schedule_posts` *refuses to
publish without a matching token*, so "gated draft A but published B" is
impossible.

Architecture (Berkay 6 Haz 2026 fabrication audit — Phase 1):

  caller        → assert_publishable(text, source, *, path, draft_id)
                  • runs run_faithfulness_gate
                  • PASS → signs (draft_id, sha256(content)) with the
                    process-local FAITHFULNESS_GATE_SECRET → token
                  • HARD_BLOCK → no token, GateOutcome.is_block=True
                  • ERROR → no token, fail_closed=True (NOT a silent pass)

  caller        → GuardedPostizClient.schedule_posts(
                      posts=[PlatformPost, ...],
                      scheduled_at=...,
                      gate_outcomes=[GateOutcome, ...],  # one per post
                  )
                  • for each (post, outcome):
                      verify outcome.verdict == "PASS"
                      verify HMAC(secret, draft_id|sha256(post.content))
                              == outcome.token
                  • any mismatch → raises GuardedPublishRefused
                  • only on success → delegates to PostizClient.schedule_posts

The CI invariant (`tests/test_postiz_choke_point.py`) greps the codebase
for any direct `PostizClient(` or `.schedule_posts(` outside this module
and the wrapper itself, and fails the build if any are found.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from .postiz_client import PostizClient, PlatformPost
from .faithfulness_gate import FaithfulnessVerdict, run_faithfulness_gate


# ──────────────────────────────────────────────────────────────────────
# Verdict signing — prevents "gated A but published B" + caller-forged tokens
# ──────────────────────────────────────────────────────────────────────

GATE_VERSION = "v2-2026-06-06-self-heal"

# SEV-1 guard (2026-06-07) — module-level operator-UI marker. Incremented
# by `operator_publish_context()` and decremented on exit. Only set by
# the FastAPI approve handlers; tests / scripts / cron paths leave it at
# 0 and the real-publish call is refused.
_OPERATOR_PUBLISH_CTX = 0


class _OperatorPublishContext:
    """Context manager that marks the current logical scope as an
    operator-driven publish call. ONLY the approve_draft / approve_thread
    handlers should enter this. Tests + scripts MUST NOT use it; if they
    need to exercise the publish path, they should mock or sandbox.
    """

    def __enter__(self):
        global _OPERATOR_PUBLISH_CTX
        _OPERATOR_PUBLISH_CTX += 1
        return self

    def __exit__(self, *exc):
        global _OPERATOR_PUBLISH_CTX
        _OPERATOR_PUBLISH_CTX = max(0, _OPERATOR_PUBLISH_CTX - 1)
        return False  # never swallow


def operator_publish_context() -> _OperatorPublishContext:
    """Mark the current scope as an operator-UI publish. The real-publish
    guard in GuardedPostizClient.schedule_posts checks this marker.

    Usage (in routes/hype.py only):
        from hype_crew.tools.guarded_postiz import operator_publish_context
        with operator_publish_context():
            pc.schedule_posts(...)
    """
    return _OperatorPublishContext()

# Process-local HMAC key. Defaults to a static fallback so the gate
# survives a missing env var, but production should set
# `FAITHFULNESS_GATE_SECRET` in /opt/hype-crew/.env so callers in other
# processes can't replay tokens. The token still works as a same-process
# anti-mismatch guard either way.
_GATE_SECRET = os.environ.get(
    "FAITHFULNESS_GATE_SECRET",
    "default-rotate-in-prod-set-FAITHFULNESS_GATE_SECRET",
).encode("utf-8")


def _content_hash(content: str) -> str:
    """SHA-256 of the exact bytes that will hit Postiz. Whitespace-sensitive
    so a post-gate edit invalidates the token."""
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def _sign_token(draft_id: str, content: str) -> str:
    """HMAC token that binds (draft_id, content) to a PASS verdict."""
    msg = f"{GATE_VERSION}|{draft_id}|{_content_hash(content)}".encode("utf-8")
    return hmac.new(_GATE_SECRET, msg, hashlib.sha256).hexdigest()


def _verify_token(token: str, draft_id: str, content: str) -> bool:
    if not token:
        return False
    expected = _sign_token(draft_id, content)
    return hmac.compare_digest(token, expected)


# ──────────────────────────────────────────────────────────────────────
# GateOutcome — the only thing GuardedPostizClient will accept
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GateOutcome:
    """The single record threaded from caller → GuardedPostizClient."""

    draft_id: str
    path: str                       # "manual_approve" | "cron_auto" | "video" | "direct_api"
    verdict: str                    # "PASS" | "HARD_BLOCK" | "ERROR"
    token: Optional[str] = None     # only set on PASS; verified at publish time
    content_hash: Optional[str] = None
    reasoning: str = ""
    fail_closed: bool = False       # True on HARD_BLOCK or ERROR
    gate_version: str = GATE_VERSION
    raw_verdict: Optional[FaithfulnessVerdict] = None
    elapsed_ms: int = 0

    @property
    def is_block(self) -> bool:
        return self.verdict != "PASS"


class GuardedPublishRefused(Exception):
    """Raised when GuardedPostizClient is asked to publish without a valid
    PASS verdict token. Callers MUST handle this — never swallow + retry."""


# ──────────────────────────────────────────────────────────────────────
# assert_publishable — the choke-point caller-facing API
# ──────────────────────────────────────────────────────────────────────


async def assert_publishable(
    draft_text: str,
    source_raw_content: str,
    *,
    path: str,
    draft_id: str,
    claim_grounding_floor: float = 0.9,
) -> GateOutcome:
    """Run the faithfulness gate against (draft_text, source_raw_content).

    Returns a `GateOutcome` whose `verdict` is one of:
      - "PASS"        → token populated; safe to pass to GuardedPostizClient
      - "HARD_BLOCK"  → faithfulness gate rejected the draft
      - "ERROR"       → gate could not run (LLM down, no source, etc.)

    Both HARD_BLOCK and ERROR set `fail_closed=True`. Callers MUST hold the
    draft as pending_review on either — never publish on ERROR (the
    previous fail-OPEN bug at backend/routes/hype.py:752 was exactly this
    mistake).

    The verdict is logged so monitoring (Phase 6) can σ-band alert on
    block-rate spikes/collapses.
    """
    t0 = time.perf_counter()
    if not source_raw_content:
        elapsed = int((time.perf_counter() - t0) * 1000)
        logger.warning(
            f"[gate] path={path} draft={draft_id[:8]} verdict=ERROR "
            f"reason=no_source_raw_content elapsed_ms={elapsed}"
        )
        outcome = GateOutcome(
            draft_id=draft_id,
            path=path,
            verdict="ERROR",
            fail_closed=True,
            reasoning="no_source_raw_content — refuse to publish unverified draft",
            elapsed_ms=elapsed,
        )
        _persist_verdict(outcome)
        return outcome

    try:
        v: FaithfulnessVerdict = await run_faithfulness_gate(
            draft_text=draft_text,
            source_raw_content=source_raw_content,
            claim_grounding_floor=claim_grounding_floor,
        )
    except Exception as e:
        elapsed = int((time.perf_counter() - t0) * 1000)
        logger.exception(
            f"[gate] path={path} draft={draft_id[:8]} verdict=ERROR "
            f"reason=gate_exception elapsed_ms={elapsed} err={e!r}"
        )
        outcome = GateOutcome(
            draft_id=draft_id,
            path=path,
            verdict="ERROR",
            fail_closed=True,
            reasoning=f"gate_exception: {type(e).__name__}: {e}",
            elapsed_ms=elapsed,
        )
        _persist_verdict(outcome)
        return outcome

    elapsed = int((time.perf_counter() - t0) * 1000)
    if v.is_block:
        logger.warning(
            f"[gate] path={path} draft={draft_id[:8]} verdict=HARD_BLOCK "
            f"reasoning={v.reasoning!r} elapsed_ms={elapsed}"
        )
        outcome = GateOutcome(
            draft_id=draft_id,
            path=path,
            verdict="HARD_BLOCK",
            fail_closed=True,
            reasoning=v.reasoning,
            content_hash=_content_hash(draft_text),
            raw_verdict=v,
            elapsed_ms=elapsed,
        )
        _persist_verdict(outcome)
        return outcome

    # PASS — sign and return
    token = _sign_token(draft_id, draft_text)
    logger.info(
        f"[gate] path={path} draft={draft_id[:8]} verdict=PASS "
        f"elapsed_ms={elapsed}"
    )
    outcome = GateOutcome(
        draft_id=draft_id,
        path=path,
        verdict="PASS",
        token=token,
        content_hash=_content_hash(draft_text),
        reasoning=v.reasoning,
        raw_verdict=v,
        elapsed_ms=elapsed,
    )
    _persist_verdict(outcome)
    return outcome


# ──────────────────────────────────────────────────────────────────────
# Phase 6 — verdict persistence (drives σ-band block-rate alerts)
# ──────────────────────────────────────────────────────────────────────


def _persist_verdict(outcome: "GateOutcome", *, retry_count: int = 0,
                     healed: bool = False, final_action: Optional[str] = None,
                     account_id: Optional[str] = None,
                     trend_id: Optional[str] = None,
                     source_url: Optional[str] = None,
                     draft_text: Optional[str] = None) -> None:
    """Insert one row into public.faithfulness_verdicts. Best-effort:
    a logging failure must NEVER block the publish path or raise."""
    try:
        from .supabase_client import make_supabase  # type: ignore
        supabase = make_supabase()
        v = outcome.raw_verdict
        row = {
            "draft_id": outcome.draft_id,
            "account_id": account_id,
            "trend_id": trend_id,
            "source_url": source_url,
            "draft_text_hash": (_content_hash(draft_text) if draft_text else
                                 outcome.content_hash),
            "path": outcome.path,
            "gate_version": outcome.gate_version,
            "model_versions": {
                "tier1": "google/gemini-3-flash-preview",
                "tier2": "google/gemini-3-flash-preview",
            },
            "verdict": outcome.verdict,
            "tier0_blocked": bool(v.tier0_blocked) if v else False,
            "tier1_blocked": bool(v.tier1_blocked) if v else False,
            "tier2_blocked": bool(v.tier2_blocked) if v else False,
            "tier1_pass_ratio": (float(v.tier1_claim_pass_ratio)
                                 if v and v.tier1_claim_pass_ratio is not None else None),
            "ungrounded_entities": (v.tier0_entities_missing if v else []) or [],
            "ungrounded_claims":   (v.tier1_ungrounded_claims if v else []) or [],
            "ungrounded_angles":   (v.tier2_ungrounded_angles if v else []) or [],
            "contradiction_hit": bool(v and v.tier1_blocked
                                      and (v.tier1_claim_pass_ratio or 1.0) <= 0.34),
            "retry_count": retry_count,
            "healed": healed,
            "final_action": final_action,
            "reasoning": (outcome.reasoning or "")[:2000],
            "cost_usd": float(v.cost_usd) if v else 0.0,
            "latency_ms": int(outcome.elapsed_ms),
        }
        supabase.table("faithfulness_verdicts").insert(row).execute()
    except Exception as e:
        logger.warning(f"[gate] verdict-persist failed (non-fatal): {e!r}")


# ──────────────────────────────────────────────────────────────────────
# Shadow-mode advisory gate — runs at draft-generation time
# ──────────────────────────────────────────────────────────────────────


async def shadow_gate(
    draft_text: str,
    source_raw_content: str,
    *,
    draft_id: str,
    account_id: Optional[str] = None,
    trend_id: Optional[str] = None,
    source_url: Optional[str] = None,
    path_tag: str = "shadow",
    claim_grounding_floor: float = 0.9,
) -> GateOutcome:
    """Advisory-mode gate. Runs the full faithfulness check, logs the
    verdict with path='shadow' (or 'shadow_backfill'), and returns the
    outcome — but **never raises and never holds publication**. The
    publish-time gate (assert_publishable) remains the fail-closed
    barrier; this helper is purely observational for the operator UI
    and for the graduation-readiness math.

    Use at draft generation time:

        outcome = await shadow_gate(
            draft_text=draft.content,
            source_raw_content=trend.raw_content,
            draft_id=draft.id,
            account_id=account.id,
            trend_id=trend.id,
            source_url=trend.url,
        )
        # show outcome.is_block (advisory) in the UI; never gate on it
    """
    t0 = time.perf_counter()

    # Special-case: no source ⇒ ERROR (advisory; doesn't block anything)
    if not source_raw_content:
        elapsed = int((time.perf_counter() - t0) * 1000)
        outcome = GateOutcome(
            draft_id=draft_id,
            path=path_tag,
            verdict="ERROR",
            fail_closed=False,        # advisory; never fail-closes
            reasoning="no_source_raw_content (advisory)",
            elapsed_ms=elapsed,
        )
        _persist_verdict(outcome, account_id=account_id, trend_id=trend_id,
                         source_url=source_url, draft_text=draft_text)
        return outcome

    try:
        v: FaithfulnessVerdict = await run_faithfulness_gate(
            draft_text=draft_text,
            source_raw_content=source_raw_content,
            source_url=source_url,
            claim_grounding_floor=claim_grounding_floor,
        )
    except Exception as e:
        elapsed = int((time.perf_counter() - t0) * 1000)
        logger.warning(f"[shadow] gate exception (advisory, ignored): {e!r}")
        outcome = GateOutcome(
            draft_id=draft_id,
            path=path_tag,
            verdict="ERROR",
            fail_closed=False,
            reasoning=f"gate_exception: {type(e).__name__}: {e}",
            elapsed_ms=elapsed,
        )
        _persist_verdict(outcome, account_id=account_id, trend_id=trend_id,
                         source_url=source_url, draft_text=draft_text)
        return outcome

    elapsed = int((time.perf_counter() - t0) * 1000)
    verdict_str = "HARD_BLOCK" if v.is_block else "PASS"
    outcome = GateOutcome(
        draft_id=draft_id,
        path=path_tag,
        verdict=verdict_str,
        # NOTE: no token even on PASS — shadow outcomes never publish
        token=None,
        content_hash=_content_hash(draft_text),
        reasoning=v.reasoning,
        raw_verdict=v,
        fail_closed=False,
        elapsed_ms=elapsed,
    )
    _persist_verdict(outcome, account_id=account_id, trend_id=trend_id,
                     source_url=source_url, draft_text=draft_text)
    logger.info(
        f"[shadow] draft={draft_id[:8]} would={verdict_str} "
        f"path={path_tag} elapsed_ms={elapsed}"
    )
    return outcome


def classify_reject_reason(category: Optional[str], free_text: Optional[str] = None) -> str:
    """Map the RejectRequest.category from backend/routes/hype.py into the
    faithfulness/quality/fit/other taxonomy used by graduation-readiness.

    The UI's category set is descriptive (too_long, sounds_like_ai,
    inaccurate, etc.). Only 'inaccurate' / 'misread_trend' carry a
    faithfulness signal; the rest are quality/style.
    """
    if not category:
        return "other"
    c = category.lower().strip()
    if c in {"inaccurate", "misread_trend", "fabrication", "ungrounded",
             "wrong_facts", "wrong_attribution"}:
        return "faithfulness"
    if c in {"too_long", "too_short", "tone_too_harsh", "tone_too_soft",
             "tone_too_corporate", "sounds_like_ai", "shallow_insight",
             "weak_hook"}:
        return "quality"
    if c in {"off_brand", "wrong_persona", "wrong_audience"}:
        return "fit"
    # Free-text mentions of fabrication keywords → flag as faithfulness
    if free_text and any(k in free_text.lower()
                          for k in ("fabricat", "uydur", "ungrounded",
                                    "kaynakta yok", "yanlış bilgi")):
        return "faithfulness"
    return "other"


def record_human_decision(
    draft_id: str,
    decision: str,                    # 'approve' | 'reject'
    *,
    reason: Optional[str] = None,
    decided_by: Optional[str] = None,
    draft_text_hash: Optional[str] = None,
    reject_reason_class: Optional[str] = None,
) -> bool:
    """Stamp the human approve/reject decision on the most-recent shadow
    verdict row for this draft_id. Returns True if a row was updated.

    Best-effort: a failure here does not break the UI's approve/reject
    flow. If no matching shadow row exists (the draft predates shadow
    mode), inserts a stand-alone 'human_only' row so the human signal
    is still captured for the graduation-readiness math.
    """
    if decision not in ("approve", "reject"):
        logger.warning(f"[shadow] record_human_decision: bad decision {decision!r}")
        return False

    try:
        from .supabase_client import make_supabase  # type: ignore
        supabase = make_supabase()
        now_iso = datetime.utcnow().isoformat() + "Z"

        # Find the most-recent shadow row for this draft (no human_decision yet)
        existing = (
            supabase.table("faithfulness_verdicts")
            .select("id")
            .eq("draft_id", draft_id)
            .in_("path", ["shadow", "shadow_backfill"])
            .is_("human_decision", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ).data or []

        if existing:
            row_id = existing[0]["id"]
            update_payload = {
                "human_decision":   decision,
                "human_reason":     (reason or "")[:1000],
                "human_decided_at": now_iso,
                "human_decided_by": (decided_by or "operator")[:120],
            }
            if reject_reason_class:
                update_payload["reject_reason_class"] = reject_reason_class
            supabase.table("faithfulness_verdicts").update(
                update_payload
            ).eq("id", row_id).execute()
            logger.info(
                f"[shadow] stamped human_decision={decision} on shadow row "
                f"{row_id[:8]} draft={draft_id[:8]}"
            )
            return True

        # No shadow row — insert a human-only row so the signal is captured
        supabase.table("faithfulness_verdicts").insert({
            "draft_id": draft_id,
            "draft_text_hash": draft_text_hash,
            "path": "human_only",
            "gate_version": GATE_VERSION,
            "verdict": "PASS",          # placeholder; no gate verdict
            "human_decision": decision,
            "human_reason": (reason or "")[:1000],
            "human_decided_at": now_iso,
            "human_decided_by": (decided_by or "operator")[:120],
            "model_versions": {},
        }).execute()
        logger.info(
            f"[shadow] inserted human_only row for draft={draft_id[:8]} "
            f"decision={decision}"
        )
        return True

    except Exception as e:
        logger.warning(f"[shadow] record_human_decision failed (non-fatal): {e!r}")
        return False


# ──────────────────────────────────────────────────────────────────────
# GuardedPostizClient — replaces every PostizClient() construction at
# publish call sites. Read-only methods inherit unchanged.
# ──────────────────────────────────────────────────────────────────────


class GuardedPostizClient(PostizClient):
    """PostizClient subclass that refuses to schedule without verified
    PASS tokens for every post. Construction-compatible with PostizClient
    so existing call sites drop in as `pc = GuardedPostizClient()`."""

    # ── SEV-1 guard (2026-06-07) ────────────────────────────────────
    # The fastapi handler stack carries no implicit signal that says
    # "this call originated from a real operator UI session". A test
    # harness can construct a FakeUser and call approve_thread(...)
    # in-process; the call reaches schedule_posts with valid tokens
    # because it ran the real gate. The 10:49 incident exposed this.
    #
    # The rule we enforce here: real platform publish only when the
    # backend route handler explicitly stamps an operator-UI marker.
    # The marker is a thread-local context flag set by the FastAPI
    # dependency that mints the user; any other code path (scripts,
    # background workers, pytest, ad-hoc Python REPL) falls through
    # to a refusal that names the missing marker.
    #
    # The marker is intentionally NOT pulled from an env var (which
    # any process could set). It must be applied by the request
    # handler via the `operator_publish_context()` context manager.

    @classmethod
    def _operator_publish_context_active(cls) -> bool:
        # Lazy import — keep this module free of FastAPI imports so it
        # stays usable from the hype-crew side too.
        from . import guarded_postiz as _self
        return getattr(_self, "_OPERATOR_PUBLISH_CTX", 0) > 0

    # Overridden to require gate_outcomes
    def schedule_posts(  # type: ignore[override]
        self,
        posts: list[PlatformPost],
        scheduled_at: datetime,
        *,
        gate_outcomes: Optional[list[GateOutcome]] = None,
    ) -> dict[str, Any]:
        # ── SEV-1 guard: only operator UI sessions reach real Postiz ──
        if not self._operator_publish_context_active():
            # Allow when the operator explicitly opts in via env var for
            # legitimate non-UI publishers (cron auto-publish, etc.).
            # That env var is set ONLY on the Hetzner host and only on
            # production-publishing services. Any developer machine,
            # pytest run, or ad-hoc script does not have it.
            allowed = (os.environ.get("POSTIZ_PUBLISH_ALLOW_NON_UI") or "").strip().lower() in {
                "1", "true", "yes", "on",
            }
            if not allowed:
                raise GuardedPublishRefused(
                    "GuardedPostizClient.schedule_posts called WITHOUT an "
                    "operator UI session context AND without POSTIZ_PUBLISH_ALLOW_NON_UI=true. "
                    "Real-platform publish is refused. "
                    "If this is a test/proof, use --dry-run or a sandbox account. "
                    "If this is the cron auto-publisher, set the env var on the "
                    "deploy unit only — never on developer machines."
                )
        if not gate_outcomes or len(gate_outcomes) != len(posts):
            raise GuardedPublishRefused(
                "GuardedPostizClient.schedule_posts requires one GateOutcome "
                f"per post (got posts={len(posts)} outcomes="
                f"{len(gate_outcomes) if gate_outcomes else 0}). "
                "All callers must obtain outcomes via assert_publishable()."
            )
        for i, (post, outcome) in enumerate(zip(posts, gate_outcomes)):
            if outcome.verdict != "PASS":
                raise GuardedPublishRefused(
                    f"post[{i}] outcome.verdict={outcome.verdict!r} "
                    f"(must be PASS). reasoning={outcome.reasoning!r}"
                )
            if not outcome.token:
                raise GuardedPublishRefused(
                    f"post[{i}] outcome.verdict=PASS but no token; "
                    "token forging attempted"
                )
            if not _verify_token(outcome.token, outcome.draft_id, post.content):
                raise GuardedPublishRefused(
                    f"post[{i}] token does not match (draft_id={outcome.draft_id[:8]}, "
                    f"content_hash={_content_hash(post.content)[:12]}). "
                    "Gated draft A but trying to publish draft B."
                )
        logger.info(
            f"[guarded_postiz] schedule_posts releasing {len(posts)} post(s) "
            f"(all PASS, tokens verified) at {scheduled_at.isoformat()}"
        )
        _result = super().schedule_posts(posts, scheduled_at)
        # 2026-06-10 (Berkay) — yayın planlandı bildirimi. Choke point
        # olduğu için OTONOM ve MANUEL tüm yayınlar buradan geçer; bildirim
        # yayın BAŞARISINDAN sonra ve tamamen izole: alerter ne yaparsa
        # yapsın (timeout, webhook hatası...) yayın sonucu etkilenmez.
        try:
            from .alerter import send_alert
            from datetime import timedelta as _td
            _plats = ", ".join(p_.provider for p_ in posts)
            _tr_time = (scheduled_at + _td(hours=3)).strftime("%H:%M")
            # newline'ları temizle + etiketle → operatör ham metin yerine
            # "ne yayınlanıyor"u anlaşılır görsün (içerik sızıntısı/jargon değil).
            _preview = " ".join((posts[0].content or "").split())[:90] if posts else ""
            send_alert(
                f"Yayın planlandı — {len(posts)} platform ({_plats}), TR saat {_tr_time}",
                severity="INFO",
                reason=(f"İçerik: «{_preview}…»" if _preview else None),
                action="Bir şey yapmana gerek yok. İstersen yayın saatinden önce panelden iptal edebilirsin.",
            )
        except Exception as _ne:
            logger.warning(f"[guarded_postiz] yayın bildirimi gönderilemedi (yayın ETKİLENMEDİ): {_ne}")
        return _result

    @classmethod
    def from_unguarded(cls, _pc: PostizClient) -> "GuardedPostizClient":
        """Migration helper for callers transitioning from PostizClient."""
        return cls()


# ──────────────────────────────────────────────────────────────────────
# Phase 5 — Self-heal: regenerate-on-block + re-gate
# ──────────────────────────────────────────────────────────────────────

_HEAL_INSTRUCTION_HEADER = """Önceki taslağın FAITHFULNESS GATE'i geçemedi.

KURAL: Yalnızca KAYNAK METİN'de geçen entity / sayı / olay'ı kullan.
Görüş (opinion) yazabilirsin; uydurma fakt yazamazsın.

KAYNAKTA YOK OLAN VE TASLAĞA EKLENMİŞ:
{ungrounded_summary}

DÜZELTME:
- Yukarıdaki kaynakta-olmayan iddiaları taslaktan çıkar.
- Aynı haberi, kaynaktaki entity ve sayılarla yeniden yaz.
- Aynı persona stili (Cansu Dut'un sesi), aynı uzunluk hedefi.
- Yeni entity veya sayı UYDURMA; emin değilsen bahsetme.

ORİJİNAL KAYNAK:
{source}

DÜZELTİLECEK ÖNCEKİ TASLAK:
{prev_draft}

Sadece düzeltilmiş taslak metnini ver. Açıklama, JSON, başlık yok."""


def build_correction_instruction(prev_draft: str, source: str, outcome: GateOutcome) -> str:
    """Build the writer-facing correction prompt from a HARD_BLOCK verdict.

    Lists the specific ungrounded entities / claims / angles the writer
    must remove. The writer then regenerates from scratch with this
    constraint, and the new draft is RE-GATED — never trusted unchecked.
    """
    v = outcome.raw_verdict
    parts: list[str] = []
    if v:
        if v.tier0_entities_missing:
            parts.append(
                "  - Kaynakta olmayan entity / sayı: "
                + ", ".join(repr(e) for e in v.tier0_entities_missing[:8])
            )
        if v.tier1_ungrounded_claims:
            parts.append(
                "  - Kanıtlanmayan iddialar: "
                + " ; ".join(c[:140] for c in v.tier1_ungrounded_claims[:5])
            )
        if v.tier2_ungrounded_angles:
            parts.append(
                "  - Kaynak desteklemeyen çerçeveleme: "
                + " ; ".join(a[:140] for a in v.tier2_ungrounded_angles[:5])
            )
    if not parts:
        parts.append(f"  - {outcome.reasoning[:240]}")
    summary = "\n".join(parts)
    return _HEAL_INSTRUCTION_HEADER.format(
        ungrounded_summary=summary,
        source=source[:1800],
        prev_draft=prev_draft[:1200],
    )


@dataclass
class HealAttempt:
    """One regen+re-gate cycle."""
    iteration: int                # 0 = initial gate; 1, 2 = regen attempts
    draft_text: str
    outcome: GateOutcome
    correction_instruction: Optional[str] = None
    regen_cost_usd: float = 0.0
    gate_cost_usd: float = 0.0
    elapsed_ms: int = 0
    halt_reason: Optional[str] = None  # "loop_guard" | "cost_cap" | "passed" | "exhausted"


@dataclass
class HealResult:
    final_outcome: GateOutcome
    final_draft: str
    healed: bool                       # True only if final outcome.verdict == "PASS"
    attempts: list[HealAttempt] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_elapsed_ms: int = 0
    halt_reason: str = "passed"        # "passed" | "exhausted" | "loop_guard" | "cost_cap"

    @property
    def is_block(self) -> bool:
        return self.final_outcome.is_block


async def assert_publishable_with_healing(
    draft_text: str,
    source_raw_content: str,
    *,
    path: str,
    draft_id: str,
    regenerate_callback,    # async (correction_instruction: str, attempt: int) -> (new_draft: str, regen_cost_usd: float)
    max_retries: int = 2,
    cost_cap_usd: float = 0.05,
    claim_grounding_floor: float = 0.9,
) -> HealResult:
    """Run the gate; on BLOCK, ask the writer to regenerate with a
    correction instruction; re-gate the new draft. Stop on PASS,
    `max_retries` reached, same-ungrounded-set loop, or cost cap.

    The healing is fully INSIDE the choke point — every regenerated
    draft is re-verified before any publish-side code sees it. There
    is no path from "writer regenerated" to "publish" without a fresh
    PASS verdict and a fresh HMAC token bound to the new content.

    Args:
        regenerate_callback: async fn called as
            new_draft, regen_cost_usd = await regenerate_callback(
                correction_instruction, attempt_idx
            )
            Caller wires this to the writer (gemini-3-flash, the same
            writer that produced the original draft).
        max_retries: number of REGEN attempts (so total gates = max_retries+1).
        cost_cap_usd: hard ceiling across gate + regen calls; abort to
            needs_human past this.
    """
    t_start = time.perf_counter()
    attempts: list[HealAttempt] = []

    # ── Attempt 0 — initial gate ──────────────────────────────────────
    initial_outcome = await assert_publishable(
        draft_text,
        source_raw_content,
        path=path,
        draft_id=draft_id,
        claim_grounding_floor=claim_grounding_floor,
    )
    initial_gate_cost = (initial_outcome.raw_verdict.cost_usd
                        if initial_outcome.raw_verdict else 0.0)
    attempts.append(HealAttempt(
        iteration=0,
        draft_text=draft_text,
        outcome=initial_outcome,
        gate_cost_usd=initial_gate_cost,
        elapsed_ms=initial_outcome.elapsed_ms,
        halt_reason="passed" if initial_outcome.verdict == "PASS" else None,
    ))
    total_cost = initial_gate_cost

    if initial_outcome.verdict == "PASS":
        return HealResult(
            final_outcome=initial_outcome,
            final_draft=draft_text,
            healed=False,
            attempts=attempts,
            total_cost_usd=total_cost,
            total_elapsed_ms=initial_outcome.elapsed_ms,
            halt_reason="passed",
        )
    if initial_outcome.verdict == "ERROR":
        # Don't try to heal an ERROR (no useful verdict for correction).
        return HealResult(
            final_outcome=initial_outcome,
            final_draft=draft_text,
            healed=False,
            attempts=attempts,
            total_cost_usd=total_cost,
            total_elapsed_ms=initial_outcome.elapsed_ms,
            halt_reason="error_no_heal",
        )

    # ── Retry loop ────────────────────────────────────────────────────
    current_draft = draft_text
    current_outcome = initial_outcome
    last_ungrounded_set: Optional[tuple[str, ...]] = None

    if current_outcome.raw_verdict:
        last_ungrounded_set = tuple(sorted(current_outcome.raw_verdict.tier0_entities_missing))

    halt_reason = "exhausted"

    for retry in range(1, max_retries + 1):
        # Cost cap check
        if total_cost >= cost_cap_usd:
            logger.warning(
                f"[heal] path={path} draft={draft_id[:8]} "
                f"abort=cost_cap total_cost=${total_cost:.4f} cap=${cost_cap_usd}"
            )
            halt_reason = "cost_cap"
            break

        correction = build_correction_instruction(current_draft, source_raw_content, current_outcome)

        # Writer call
        try:
            new_draft, regen_cost = await regenerate_callback(correction, retry)
        except Exception as e:
            logger.exception(
                f"[heal] path={path} draft={draft_id[:8]} attempt={retry} "
                f"regenerate_callback failed: {e!r}"
            )
            halt_reason = "regen_error"
            attempts.append(HealAttempt(
                iteration=retry,
                draft_text="",
                outcome=current_outcome,
                correction_instruction=correction,
                halt_reason="regen_error",
            ))
            break

        total_cost += regen_cost or 0.0

        # Re-gate the new draft
        new_outcome = await assert_publishable(
            new_draft,
            source_raw_content,
            path=path,
            draft_id=draft_id,
            claim_grounding_floor=claim_grounding_floor,
        )
        new_gate_cost = (new_outcome.raw_verdict.cost_usd
                         if new_outcome.raw_verdict else 0.0)
        total_cost += new_gate_cost

        attempt_log = HealAttempt(
            iteration=retry,
            draft_text=new_draft,
            outcome=new_outcome,
            correction_instruction=correction,
            regen_cost_usd=regen_cost or 0.0,
            gate_cost_usd=new_gate_cost,
            elapsed_ms=new_outcome.elapsed_ms,
        )

        if new_outcome.verdict == "PASS":
            attempt_log.halt_reason = "passed"
            attempts.append(attempt_log)
            halt_reason = "passed"
            current_outcome = new_outcome
            current_draft = new_draft
            break

        # Loop-guard: same ungrounded entity set ⇒ writer is stuck
        new_unset: tuple[str, ...] = ()
        if new_outcome.raw_verdict:
            new_unset = tuple(sorted(new_outcome.raw_verdict.tier0_entities_missing))
        if last_ungrounded_set is not None and new_unset == last_ungrounded_set and new_unset:
            logger.warning(
                f"[heal] path={path} draft={draft_id[:8]} "
                f"abort=loop_guard same_ungrounded_set={list(new_unset)[:5]}"
            )
            attempt_log.halt_reason = "loop_guard"
            attempts.append(attempt_log)
            halt_reason = "loop_guard"
            current_outcome = new_outcome
            current_draft = new_draft
            break

        attempts.append(attempt_log)
        current_outcome = new_outcome
        current_draft = new_draft
        last_ungrounded_set = new_unset
        # else: keep looping

    total_elapsed_ms = int((time.perf_counter() - t_start) * 1000)
    healed = (current_outcome.verdict == "PASS" and len(attempts) > 1)

    logger.info(
        f"[heal] path={path} draft={draft_id[:8]} done halt={halt_reason} "
        f"healed={healed} attempts={len(attempts)} "
        f"final_verdict={current_outcome.verdict} cost=${total_cost:.4f}"
    )

    return HealResult(
        final_outcome=current_outcome,
        final_draft=current_draft,
        healed=healed,
        attempts=attempts,
        total_cost_usd=total_cost,
        total_elapsed_ms=total_elapsed_ms,
        halt_reason=halt_reason,
    )
