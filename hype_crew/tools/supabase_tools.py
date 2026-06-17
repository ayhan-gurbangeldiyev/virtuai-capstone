"""CrewAI tool wrappers for Supabase queries.

Tools agents can call to fetch trends, load account config, mark trend as processed.
Service-role bypass — RLS not enforced (we're backend worker).
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from loguru import logger
try:
    from crewai.tools import tool
except ImportError:
    def tool(*args, **kwargs):  # noqa: ARG001
        def _decorate(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return _decorate

from .supabase_client import make_supabase


# Phase 1 (within-beat comparison) — process-local stash for the most recent
# candidate pool returned by query_trends per account. Runner.py spawns a
# fresh process per cron firing, so there is no cross-firing contention.
# Read by flow.py after crew.kickoff() to persist candidates_considered.
_LAST_POOL_BY_ACCOUNT: dict[str, list[dict[str, Any]]] = {}

# Crew Akışı şeffaflığı — aday-eleme dökümü (kaç trend incelendi, kaçı dedup/
# AI-dışı/geçti). flow.py finalize'de hype_runs.flow_state'e yazılır → "Aday yok ·
# 8 trend: 5 dedup, 3 AI-dışı" gibi insan-okur açıklama.
_LAST_GATE_BREAKDOWN: dict[str, dict[str, Any]] = {}


def consume_last_pool(account_id: str) -> list[dict[str, Any]]:
    """Pop and return the most recent candidate pool for this account, or []."""
    return _LAST_POOL_BY_ACCOUNT.pop(account_id, [])


def consume_gate_breakdown(account_id: str) -> dict[str, Any]:
    """Pop the most recent persona-gate/dedup breakdown for this account, or {}."""
    return _LAST_GATE_BREAKDOWN.pop(account_id, {})


def _breakdown_reason(examined: int, dedup: int, ai_reject: int, passed: int) -> str:
    """İnsan-okur skip açıklaması (Crew Akışı boş-run satırı için)."""
    if passed > 0:
        return f"{passed} aday geçti ({examined} incelendi)"
    if examined == 0 and dedup == 0:
        return "taze AI haberi bulunamadı"
    bits = []
    if dedup:
        bits.append(f"{dedup} daha önce işlendi")
    if ai_reject:
        bits.append(f"{ai_reject} AI-dışı")
    tail = (" · " + ", ".join(bits)) if bits else ""
    return f"aday yok · {examined} incelendi{tail}"


@tool("query_trends")
def query_trends(
    account_id: str,
    min_score: int = 75,
    vip_only: bool = False,
    hours_back: int = 48,
    exclude_categories: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Fetch high-quality trends from Supabase for the account's niche.

    Returns up to 10 most recent trends matching criteria.

    Phase 37 (Berkay 31 May 2026) — eşik 90→75 düşürüldü ve News kategorisi
    exclude listesinden çıkarıldı. Önceki konfigürasyon saatlik 6 run'ın
    5'ini "no qualifying trends" ile boş bıraktı (hit rate %15-20).
    TrendScout reasoning + rubric ZATEN ikinci filter, false-positives az.

    Args:
        account_id: connected_accounts.id (for filtering processed trends per-account)
        min_score: minimum score threshold (default 75 = Phase 37; was 90)
        vip_only: if True, only is_vip=true trends. Use False unless the
                 creator's niche is exclusively Tier-1 brand drops. Most
                 pools have is_vip=false on every row, so True returns [].
        hours_back: lookback window in hours (DEFAULT 48). If the query
                   returns [], retry with 72 or 96 — the dedup filter is
                   already 24h, so older trends that haven't been written
                   about in the last 24h are still fresh content.
        exclude_categories: list of trend.category values to skip.
                           Default ['Politics','Entertainment'] — News dahil
                           (Phase 37); TrendScout LLM zaten political/celeb
                           içeriği rubric ile reddediyor.
    """
    sb = make_supabase()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    # Phase 37 default: only Politics+Entertainment hard-block. News dahil.
    excluded = exclude_categories if exclude_categories is not None else ["Politics", "Entertainment"]

    q = (
        sb.table("trends")
        # 2026-06-07 Stage 2 Step 3 — raw_content added to SELECT so the
        # persona-gate's L2/L3 layers can match AI vocabulary in the
        # source body, not just the headline. Was: gate only saw the
        # topic title → AI-adjacent stories without a literal AI keyword
        # in the title got L4-rejected.
        .select("id,topic,category,score,is_vip,semantic_triggers,sample_sources,suggested_hooks,published_at,created_at,vip_reason,source_name,raw_content")
        .gte("score", min_score)
        # 2026-06-07 Part A fix — freshness gate uses DISCOVERY time
        # (created_at, set by trend_engine when the row is inserted), not
        # the article/tweet's published_at (which Twitter signals stamp
        # from tweetCreatedAt). Without this, AI accounts (@AnthropicAI,
        # @OpenAI, @claudeai) whose underlying tweet is 2-3 days old but
        # was JUST discovered today get filtered out as "stale", and
        # hype-crew early-exits on a freshly-aggregated trend pool. The
        # 24h dedup downstream still protects against re-posting.
        .gte("created_at", since)
        .eq("is_visible", True)
        .eq("is_archived", False)
        .order("score", desc=True)
        .order("published_at", desc=True)
        .limit(10)
    )

    if vip_only:
        q = q.eq("is_vip", True)
    if excluded:
        q = q.not_.in_("category", excluded)

    # Capstone (3 Haz 2026) — Persona Gate config lookup.
    # Replaces previous forbidden_topic_keywords-only post-filter with
    # full 5-layer Persona Gate (blocked / positive AI / Tier 1 /
    # conditional brand / ambiguous). See `tools.persona_gate`.
    persona_gate_config: dict[str, Any] = {}
    try:
        cfg_row = (
            sb.table("hype_account_config")
            .select("persona_gate_config, forbidden_topic_keywords")
            .eq("account_id", account_id)
            .limit(1)
            .execute()
            .data
        )
        if isinstance(cfg_row, list) and cfg_row:
            head = cfg_row[0]
            if isinstance(head, dict):
                pg = head.get("persona_gate_config")
                if isinstance(pg, dict):
                    persona_gate_config = pg
                # Backward-compat: if persona_gate_config empty but legacy
                # forbidden_topic_keywords populated, lift them into
                # blocked_keywords so behavior never regresses.
                if not persona_gate_config.get("blocked_keywords"):
                    legacy_kw = head.get("forbidden_topic_keywords") or []
                    if isinstance(legacy_kw, list) and legacy_kw:
                        persona_gate_config = {
                            **persona_gate_config,
                            "blocked_keywords": [str(k) for k in legacy_kw if k],
                        }
    except Exception as e:
        logger.warning(f"persona_gate_config lookup failed: {e}")
        persona_gate_config = {}

    # Exclude trends recently processed by Hype Crew for this account.
    # Karar defteri penceresi — tarihçe: 6h çok kısaydı (2026-05-18 SpaceX
    # tekrarı), 24h'e çıktı; 2026-06-10 (B yaması, n8n parite) 7 GÜNE çıktı.
    # İlke: bir trend hakkında BİR kez karar verilir (seçildi ya da rubrik
    # reddetti — _finalize her iki durumda da hype_runs.trend_id damgalar);
    # o trend defter penceresi içinde TrendScout'a bir daha hiç gitmez.
    # Trendler tazelik cezasıyla ~72h'te zaten ölür → 7 gün fiilen "kalıcı"
    # demek, ama sorgu süresiz şişmeden. Story-merge (A yaması) sayesinde
    # aynı hikâyenin yeni tweet'leri de aynı trend_id'ye aktığı için bu
    # defter hikâye seviyesinde re-post'u tek başına keser.
    #
    # Phase 43.G (Berkay 2 Haz 2026): scope the dedup to ALL accounts owned
    # by the same user, not just this one account_id. Berkay had 2 connected
    # accounts under the same Cansu persona; each ran independently and both
    # picked the same NVIDIA trend, generating duplicate drafts + paying the
    # LLM bill twice. Expanding scope to user-level dedup catches this.
    dedup_since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    user_account_ids = _sibling_account_ids(sb, account_id)

    already_processed = (
        sb.table("hype_runs")
        .select("trend_id")
        .in_("account_id", user_account_ids)
        .not_.is_("trend_id", "null")
        .gte("started_at", dedup_since)
        # 2026-06-10 — failed/çökmüş run bir KARAR değildir: stuck-reaped
        # run'lar (C yaması yetimlerini de temizliyor) trendin tek karar
        # hakkını yakmasın. Yalnız gerçek kararlar (completed/skipped/
        # dry_run vb.) deftere sayılır.
        .neq("status", "failed")
        .execute()
    )
    processed_rows = already_processed.data if isinstance(already_processed.data, list) else []
    processed_ids = [r["trend_id"] for r in processed_rows if isinstance(r, dict) and r.get("trend_id")]

    # Lever 2 — Persist dedup events for AI-relevant trends that were
    # pre-filtered out by the 24h dedup window. Without this, the day-level
    # honest pair on Home has nothing to use as the "skipped" side on days
    # when repeats were silently filtered before the agent saw them.
    #
    # Only logs ONE row per trend_id per call (deduped at insert time via
    # idempotent existence check below). matched_reason carries the recorded
    # 7d match_count so home-summary can render the operator-facing N.
    if processed_ids and persona_gate_config:
        try:
            from .persona_gate import evaluate_persona_gate as _eval_gate

            # Fetch metadata for excluded trends still in the time window.
            excluded_rows = (
                sb.table("trends")
                .select("id, topic, category, source_name, url, published_at, created_at")
                .in_("id", processed_ids)
                # Same fix as the main freshness gate — use discovery time.
                .gte("created_at", since)
                .eq("is_visible", True)
                .eq("is_archived", False)
                .limit(50)
                .execute()
                .data
            ) or []

            # Per-trend 7d run count (the "N matches in last 7d" the operator sees).
            cutoff_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            counts_by_id: dict[str, int] = {}
            if excluded_rows:
                exc_ids = [r["id"] for r in excluded_rows if r.get("id")]
                hr_7d = (
                    sb.table("hype_runs")
                    .select("trend_id")
                    .in_("trend_id", exc_ids)
                    .in_("account_id", user_account_ids)
                    .gte("started_at", cutoff_7d)
                    .execute()
                    .data
                ) or []
                for h in hr_7d:
                    tid = h.get("trend_id") if isinstance(h, dict) else None
                    if tid:
                        counts_by_id[tid] = counts_by_id.get(tid, 0) + 1

            # Idempotency: skip trend_ids that already have a recently_covered
            # log row written in the last 24h.
            existing_dedup_rows = (
                sb.table("persona_gate_log")
                .select("trend_id")
                .eq("account_id", account_id)
                .eq("decision", "recently_covered")
                .gte("created_at", dedup_since)
                .execute()
                .data
            ) or []
            already_logged = {
                r["trend_id"] for r in existing_dedup_rows
                if isinstance(r, dict) and r.get("trend_id")
            }

            dedup_log_rows: list[dict[str, Any]] = []
            for trend in excluded_rows:
                tid = trend.get("id")
                if not tid or tid in already_logged:
                    continue
                topic = str(trend.get("topic", "") or "")
                category = str(trend.get("category", "") or "")
                decision = _eval_gate(
                    topic=topic,
                    raw_content="",
                    category=category,
                    config=persona_gate_config,
                )
                if not decision.passed:
                    continue  # not AI-relevant; not a useful skip to record
                match_count = counts_by_id.get(tid, 0)
                dedup_log_rows.append({
                    "account_id": account_id,
                    "trend_id": tid,
                    "decision": "recently_covered",
                    "persona_gate": "pre_filter_dedup",
                    "matched_keyword": decision.matched_keyword,
                    "matched_reason": (
                        f"recently_covered ({match_count} match(es) in last 7d, scope=user)"
                    ),
                    "final_trendscout_score": None,
                    "topic_snapshot": topic[:300],
                    "category_snapshot": category[:80],
                    "source_snapshot": str(trend.get("source_name", "") or "")[:120],
                })

            if dedup_log_rows:
                try:
                    sb.table("persona_gate_log").insert(dedup_log_rows).execute()
                    logger.info(
                        f"persona_gate_log: recorded {len(dedup_log_rows)} "
                        f"recently_covered dedup events (account={account_id[:8]})"
                    )
                except Exception as e:
                    logger.warning(f"persona_gate_log dedup insert failed: {e}")
        except Exception as e:
            logger.warning(f"Lever 2 dedup logging skipped: {e}")

    if processed_ids:
        q = q.not_.in_("id", processed_ids)

    result = q.execute()
    rows = result.data if isinstance(result.data, list) else []
    rows = [r for r in rows if isinstance(r, dict)]

    # Capstone (3 Haz 2026) — Persona Gate: deterministic 5-layer relevance
    # filter BEFORE TrendScout LLM. Hard-blocked trends never reach Gemini.
    if not persona_gate_config or not rows:
        # Şeffaflık: persona-gate yok ya da taze aday yok → breakdown yine yazılır.
        _LAST_GATE_BREAKDOWN[account_id] = {
            "examined": len(rows), "dedup": len(processed_ids), "ai_reject": 0,
            "passed": len(rows), "by_gate": {},
            "reason": _breakdown_reason(len(rows), len(processed_ids), 0, len(rows)),
        }
        return rows

    from .persona_gate import evaluate_persona_gate

    # Fetch raw_content for each row in a single query (gate uses it for L2/L3).
    # `rows` only contains the columns we SELECT'd earlier; raw_content + category
    # is included in our SELECT, so we already have it.

    passed: list[dict[str, Any]] = []
    counters: dict[str, int] = {}
    log_rows: list[dict[str, Any]] = []
    for r in rows:
        topic = str(r.get("topic", "") or "")
        category = str(r.get("category", "") or "")
        # 2026-06-07 Stage 2 Step 3 — pass the actual raw_content. The
        # title alone misses AI vocabulary in the body (e.g. an Apple
        # iOS update where the body discusses Apple Intelligence /
        # on-device LLM but the title is just "iOS 27 update").
        raw = str(r.get("raw_content", "") or "")
        decision = evaluate_persona_gate(
            topic=topic,
            raw_content=raw,
            category=category,
            config=persona_gate_config,
        )
        counters[decision.persona_gate] = counters.get(decision.persona_gate, 0) + 1

        # Build human-readable matched_reason for audit log analysis.
        # final_trendscout_score is left NULL here — backfilled by flow.py after
        # TrendScout produces final_score_12 (enables gate vs rubric correlation).
        gate = decision.persona_gate
        mk = decision.matched_keyword or ""
        if gate == "blocked":
            reason = f"L1 blocked_keyword='{mk}' matched in topic/category"
        elif gate == "positive_match":
            reason = f"L2 positive_ai_signal='{mk}' matched"
        elif gate == "tier_1_brand_match":
            reason = f"L3 tier_1_brand='{mk}' matched (TrendScout still scores rubric)"
        elif gate == "conditional_brand_match":
            reason = f"L3b conditional_brand={mk} (brand co-occurred with required AI keyword)"
        elif gate == "conditional_brand_no_ai_signal":
            reason = f"L3b REJECT conditional_brand='{mk}' present but NO required AI keyword co-occurrence"
        elif gate == "semantic_rescue":
            # 2026-06-07 A2 — surfaced separately from positive_match so
            # operator can audit recall-only rescues (and tune the
            # threshold) without losing the keyword-match track.
            reason = f"L4 RESCUE semantic_rescue {mk} matched AI-concept anchor"
        else:
            reason = "L4 ambiguous — no AI relevance signal detected"

        log_rows.append({
            "account_id": account_id,
            "trend_id": r.get("id"),
            "decision": decision.decision,
            "persona_gate": decision.persona_gate,
            "matched_keyword": decision.matched_keyword,
            "matched_reason": reason,
            "final_trendscout_score": None,
            "topic_snapshot": topic[:300],
            "category_snapshot": category[:80],
            "source_snapshot": str(r.get("source_name", "") or "")[:120],
        })

        if decision.passed:
            r["_persona_gate_tag"] = decision.persona_gate
            r["_persona_gate_matched"] = decision.matched_keyword
            passed.append(r)
        else:
            logger.info(
                f"persona_gate: REJECT '{topic[:55]}' "
                f"({decision.persona_gate}: {decision.matched_keyword})"
            )

    # Async-fire audit log insert; failure is non-fatal (audit only).
    if log_rows:
        try:
            sb.table("persona_gate_log").insert(log_rows).execute()
        except Exception as e:
            logger.warning(f"persona_gate_log insert failed: {e}")

    if len(passed) < len(rows):
        logger.info(
            f"persona_gate: {len(passed)}/{len(rows)} passed "
            f"(account={account_id[:8]}, breakdown={counters})"
        )

    # Phase 1 — Stash the pool the agent sees so flow.py can read it after
    # crew.kickoff() and persist within-firing candidates_considered. Last
    # call wins per account; runner.py is single-account-per-process.
    _LAST_POOL_BY_ACCOUNT[account_id] = [
        {
            "id": r.get("id"),
            "topic": r.get("topic"),
            "category": r.get("category"),
            "score": r.get("score"),
            "is_vip": r.get("is_vip"),
            "semantic_triggers": r.get("semantic_triggers") or [],
            "source_name": r.get("source_name"),
            "published_at": r.get("published_at"),
            "_persona_gate_tag": r.get("_persona_gate_tag"),
        }
        for r in passed
    ]

    _ai_reject = len(rows) - len(passed)
    _LAST_GATE_BREAKDOWN[account_id] = {
        "examined": len(rows), "dedup": len(processed_ids), "ai_reject": _ai_reject,
        "passed": len(passed), "by_gate": counters,
        "reason": _breakdown_reason(len(rows), len(processed_ids), _ai_reject, len(passed)),
    }

    return passed


def _sibling_account_ids(sb, account_id: str) -> list[str]:
    """Return all connected_accounts.id owned by the same user as account_id.

    Falls back to [account_id] on lookup failure. Shared helper for the
    user-scoped dedup queries (trend-id + URL).
    """
    try:
        owner_rows = (
            sb.table("connected_accounts")
            .select("user_id")
            .eq("id", account_id)
            .limit(1)
            .execute()
            .data
        )
        owner_user_id: str | None = None
        if isinstance(owner_rows, list) and owner_rows:
            first = owner_rows[0]
            if isinstance(first, dict):
                uid = first.get("user_id")
                if isinstance(uid, str):
                    owner_user_id = uid
        if owner_user_id:
            sibling_rows = (
                sb.table("connected_accounts")
                .select("id")
                .eq("user_id", owner_user_id)
                .execute()
                .data
            )
            collected: list[str] = []
            if isinstance(sibling_rows, list):
                for r in sibling_rows:
                    if isinstance(r, dict):
                        rid = r.get("id")
                        if isinstance(rid, str):
                            collected.append(rid)
            if collected:
                return collected
    except Exception:
        pass
    return [account_id]


def url_dedup_check_impl(account_id: str, source_url: str, days: int = 7) -> dict[str, Any]:
    """Phase 43.H.1 — URL-level pre-LLM dedup.

    Plain function (not a CrewAI @tool) so flow.py can call it cheaply
    from the @start initialize step BEFORE any agent kickoff.

    Returns:
        {
            "found": bool,
            "existing_draft_id": str | None,
            "existing_thread_id": str | None,
            "match_count": int,
            "match_scope": "user" | "account" | "none",
            "url_checked": str,
        }
    """
    sb = make_supabase()
    if not source_url:
        return {
            "found": False,
            "existing_draft_id": None,
            "existing_thread_id": None,
            "match_count": 0,
            "match_scope": "none",
            "url_checked": source_url,
        }

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    user_account_ids = _sibling_account_ids(sb, account_id)

    matches = (
        sb.table("daily_drafts")
        .select("id, content_thread_id, account_id, created_at")
        .in_("account_id", user_account_ids)
        .eq("source_url", source_url)
        # 2026-06-10 — soft-delete edilen draftlar (reaper yetimleri,
        # atomic-rollback artıkları) coverage SAYILMAZ: silinen içerik
        # yayınlanmadı, kaynağın yeniden işlenmesini bloklamamalı
        # (Fable-5 'performansı' vakası: silinmiş yetim draft URL
        # pre-gate'i tetikleyip mega-haberi skip ettirdi).
        .is_("deleted_at", "null")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
    )

    if not isinstance(matches, list) or not matches:
        return {
            "found": False,
            "existing_draft_id": None,
            "existing_thread_id": None,
            "match_count": 0,
            "match_scope": "none",
            "url_checked": source_url,
        }

    first = matches[0] if isinstance(matches[0], dict) else {}
    return {
        "found": True,
        "existing_draft_id": str(first.get("id") or ""),
        "existing_thread_id": str(first.get("content_thread_id") or "") or None,
        "match_count": len(matches),
        "match_scope": "user" if len(user_account_ids) > 1 else "account",
        "url_checked": source_url,
    }


@tool("url_dedup_check")
def url_dedup_check(account_id: str, source_url: str, days: int = 7) -> dict[str, Any]:
    """CrewAI-tool wrapper around url_dedup_check_impl.

    Use this when agents need the check; flow.py calls the _impl helper
    directly to skip CrewAI tool overhead during the @start step.
    """
    return url_dedup_check_impl(account_id, source_url, days)


@tool("load_account_config")
def load_account_config(account_id: str) -> dict[str, Any]:
    """Load Hype Crew settings for an account.

    Returns the hype_account_config row as dict, or sane defaults if missing.
    """
    sb = make_supabase()
    result = (
        sb.table("hype_account_config")
        .select("*")
        .eq("account_id", account_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]

    # Defaults if no config yet — safe values.
    # NOTE: `dry_run_mode` intentionally OMITTED from defaults so callers can
    # distinguish "no DB row" (→ fall back to env HYPE_DRY_RUN) from
    # "DB row exists with dry_run_mode=false" (→ live). flow.py:initialize
    # uses None-aware precedence; presence of key here would force-shadow env.
    # Same logic for `daily_cost_cap_usd` (added 2026-05-18, Gap #5).
    return {
        "account_id": account_id,
        "identity_card": "",
        "voice_description": "direct, conversational, no corporate jargon",
        "topics_focus": [],
        "forbidden_topics": ["politics", "religion", "medical_advice", "financial_advice"],
        "watch_accounts": [],
        "reactive_enabled": True,
        "reactive_triggers": ["launch", "breaking", "milestone"],
        "follower_goal": None,
        "posting_cadence": "daily",
        "daily_post_quota": 2,
        "auto_publish_enabled": False,
    }


@tool("mark_trend_processed")
def mark_trend_processed(trend_id: str, run_id: str, account_id: str) -> bool:
    """Record that a trend was processed by a Hype Crew run.

    Idempotent — if hype_runs row already has trend_id, no-op.
    Safety: only updates if run_id belongs to account_id (no cross-account writes).
    """
    sb = make_supabase()
    # 2026-06-10 — TrendScout LLM'i bazen uydurma run_id/account_id geçiyor
    # ("ef6cdb3b..._1739818800" vakası: uuid+epoch birleşimi → 22P02 ve tool
    # hatası). Geçersiz UUID'de sessiz no-op: defteri _finalize zaten
    # deterministik damgalıyor, tool kaydı best-effort.
    import uuid as _uuid
    for _val, _name in ((trend_id, "trend_id"), (run_id, "run_id"), (account_id, "account_id")):
        try:
            _uuid.UUID(str(_val))
        except (ValueError, AttributeError, TypeError):
            logger.warning(f"mark_trend_processed: geçersiz {_name}={str(_val)[:50]!r} — no-op")
            return False
    sb.table("hype_runs").update({"trend_id": trend_id}).eq("id", run_id).eq("account_id", account_id).execute()
    return True
