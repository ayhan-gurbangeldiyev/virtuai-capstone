"""
Twitter Trend Fetcher v3 — XQuik-powered multi-signal pipeline.

3 batch + Radar + Monitor + Feed sistemi.
Eski tier/keyword sistemi kaldırıldı (v2).

Batch'ler:
    AI/Tech (10 hesap): OpenAI, AnthropicAI, ClaudeAI, ChatGPTapp, GoogleDeepMind,
                        GoogleAI, cursor_ai, webtekno, technopatnet, shiftdeletenet
    TR Haber (7 hesap): gusholderhaber, onedio, bpthaber, ozetgechaber,
                        bosunatiklama, haber, conflicttr
    Spor (4 hesap):     deportesreports, demarkesports, bbosports, ntvspor

Radar (ücretsiz): google_trends, hacker_news, reddit, github, polymarket, trustmrr, wikipedia
"""
import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from services.xquik_client import xquik
from services.quota_manager import get_quota_status

logger = logging.getLogger(__name__)

# Supabase client
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# ================================================================
# BATCH CONFIG
# ================================================================
# Hardcoded BATCHES is the FALLBACK if trend_x_sources table is empty/unreachable.
# The active source list is normally loaded from DB via get_active_batches().
# UI (Trends page → gear icon) manages the DB rows.
# 2026-06-07 A1 — the legacy hardcoded BATCHES was the source the
# audit found upstream n8n still consulting; rows for tr_haber/spor
# kept arriving in tweet_feed long after trend_x_sources.is_active
# was flipped to false. Emptying the lists here removes the noise
# accounts from the only place callers could read them at face value.
# DB-side migration 013_tweet_feed_reject_inactive_batch is the
# authoritative defense; this constant is now strictly documentation.
BATCHES = {
    "ai_core":    {"accounts": [], "limit": 50, "category": "ai_tech"},
    "ai_news_en": {"accounts": [], "limit": 30, "category": "ai_tech"},
    "ai_news_tr": {"accounts": [], "limit": 30, "category": "ai_tech"},
    # The following batches are documented as RETIRED. Their accounts
    # used to be hardcoded here; that list is removed so a stale caller
    # can't resurrect them. Even if a rogue caller writes to tweet_feed
    # with these batch_types, the DB trigger trg_tweet_feed_reject_inactive_batch
    # rejects the insert because trend_x_sources has no active rows
    # for them.
    "ai_tech":  {"accounts": [], "limit": 50, "category": "ai_tech"},
    "tr_haber": {"accounts": [], "limit": 40, "category": "tr_haber"},
    "spor":     {"accounts": [], "limit": 30, "category": "spor"},
}


# Defaults used when no DB row specifies a custom fetch_limit per account.
# 6 Haz 2026 — the ai_tech batch crowd-out incident split the AI accounts
# into ai_core (their OWN batch) and ai_news_tr (TR-language AI
# commentators). The legacy ai_tech batch is now deactivated. The
# noise-batches (spor / tr_haber) are kept here for backward-compat with
# rows still in trend_x_sources but they're set is_active=false in DB so
# they won't fetch.
_BATCH_DEFAULTS = {
    "ai_core":    {"limit": 50, "category": "ai_tech"},   # OpenAI, Anthropic, etc.
    "ai_news_tr": {"limit": 30, "category": "ai_tech"},   # @semihdev etc.
    "ai_news_en": {"limit": 30, "category": "ai_tech"},   # rowancheung, swyx, simonw, etc. (Stage 2 Step 1)
    # 11 Haz 2026 — Güvenilir-küratör kaçış yolu. @upcornco gibi güvenilir
    # editörler ayrı batch'te; her tweet'i tek tek news-filter'dan geçip
    # (curator_filter.classify_curator_news) force-seed edilebilir.
    # _BATCH_DEFAULTS'a EKLENMESİ ZORUNLU — yoksa get_active_batches satırı
    # "unknown batch_type" diye sessizce atar (R1).
    "ai_curator": {"limit": 20, "category": "ai_tech"},   # @upcornco (trusted editor)
    "ai_tech":    {"limit": 50, "category": "ai_tech"},   # legacy (DB rows now inactive)
    "tr_haber":   {"limit": 40, "category": "tr_haber"},  # legacy / inactive
    "spor":       {"limit": 30, "category": "spor"},      # legacy / inactive
}

# AI accounts get a HARD lookback window instead of the dynamic
# _get_last_fetch_date — that function returns the most-recent tweet
# date for the WHOLE batch, which means one high-volume account snaps
# the sinceDate to today and crowds out everyone tweeting yesterday.
# A hard 72h window for ai_core ensures every AI account's recent
# tweets land regardless of when peers tweeted. (6 Haz 2026 audit
# confirmed: OpenAI's last tweet was Jun 4 20:19; the dynamic
# sinceDate had snapped to Jun 6 → OpenAI never re-entered the pool.)
_HARD_LOOKBACK_HOURS = {
    "ai_core": 72,
    "ai_news_tr": 48,
    "ai_news_en": 48,
    "ai_curator": 48,
    "ai_tech": 72,
}


def _alert_supply_misconfig(reason: str, evidence: dict) -> None:
    """Loud alert when the source-list config is broken. Best-effort.

    Audit 2026-06-06: the previous silent fallback to a hardcoded
    BATCHES dict (which contained noise accounts like webtekno /
    shiftdeletenet) meant a DB read failure or accidental empty-list
    silently flipped the source list back to noise. A config that
    says "AI only" must NEVER be silently replaced by "sports + gadget
    news." Now we fail loud and refuse to fetch.
    """
    try:
        from services.alerter import alert_supply
        alert_supply(
            severity="CRITICAL",
            category=f"trend_supply::config_failure::{reason}",
            summary=(f"trend_x_sources read FAILED ({reason}). "
                      "Trend fetch SKIPPED to avoid silently falling back to "
                      "stale hardcoded noise accounts. Check DB / config."),
            evidence=evidence,
        )
    except Exception as e:
        logger.warning(f"alerter unavailable: {e!r}")


def get_active_batches() -> dict:
    """Read the active X source list from `trend_x_sources` table.

    Audit 2026-06-06 (silent-fallback fix): if the DB is unreachable OR
    returns zero active rows, we now FAIL LOUD and return {} (no fetch
    will happen) — INSTEAD of silently falling back to the hardcoded
    BATCHES dict, which contained the deactivated noise accounts and
    would have brought them back from the dead. The hardcoded BATCHES
    is kept ONLY as documentation of the legacy default — never
    returned.
    """
    if not supabase:
        logger.error(
            "trend_x_sources: SUPABASE client unavailable. Returning empty "
            "batch dict — fetch will SKIP. (Never falling back to hardcoded "
            "noise accounts; that was the audit-2026-06-06 silent-failure path.)"
        )
        _alert_supply_misconfig("no_supabase_client",
                                 {"supabase_set": bool(supabase)})
        return {}
    try:
        rows = (
            supabase.table("trend_x_sources")
            .select("batch_type, username, fetch_limit")
            .eq("is_active", True)
            .execute()
        )
        data = rows.data or []
        if not data:
            logger.error(
                "trend_x_sources: zero active rows. Returning empty batch dict "
                "— fetch will SKIP. (No silent fallback to hardcoded noise.)"
            )
            _alert_supply_misconfig("zero_active_rows", {"rows_returned": 0})
            return {}
        result = {bt: {"accounts": [], "limit": d["limit"], "category": d["category"]}
                  for bt, d in _BATCH_DEFAULTS.items()}
        unknown_batches: list[str] = []
        for r in data:
            bt = r.get("batch_type")
            uname = r.get("username")
            if bt not in result and bt:
                unknown_batches.append(bt)
                continue
            if bt in result and uname:
                result[bt]["accounts"].append(uname)
                fl = r.get("fetch_limit")
                if fl and fl > result[bt]["limit"]:
                    result[bt]["limit"] = fl
        if unknown_batches:
            logger.warning(
                f"trend_x_sources: unknown batch_type(s) {sorted(set(unknown_batches))!r}; "
                f"skipped. Add them to _BATCH_DEFAULTS if intended."
            )
        # Drop empty batches so we don't waste an API call
        active = {k: v for k, v in result.items() if v["accounts"]}
        if not active:
            logger.error(
                "trend_x_sources: rows present but every batch ended empty "
                "(filtered out). Fetch will SKIP."
            )
            _alert_supply_misconfig("all_batches_empty_after_filter",
                                     {"raw_rows": len(data)})
            return {}
        # Tight loud confirmation of the source list, every call.
        summary = ", ".join(
            f"{bt}({len(b['accounts'])})" for bt, b in active.items()
        )
        logger.info(f"trend_x_sources: active source list = {summary}")
        return active
    except Exception as e:
        logger.exception(
            f"trend_x_sources read RAISED ({type(e).__name__}: {e}). Returning "
            f"empty batch dict; fetch will SKIP. NEVER silently falling back "
            f"to hardcoded noise."
        )
        _alert_supply_misconfig("db_read_exception",
                                 {"err": f"{type(e).__name__}: {str(e)[:300]}"})
        return {}


def get_curator_usernames() -> set:
    """Güvenilir-küratör whitelist'i — `trend_x_sources` batch_type='ai_curator'.

    Tüm küratör mantığının TEK kaynağı (analyze_trends 40-cap baypası +
    _seed_curator_trends bunu kullanır). Config-driven: yeni küratör = yeni
    DB satırı, sıfır kod. DB hatası → boş set (kaçış yolu sessizce kapanır;
    ana çoklu-kaynak yolu etkilenmez). Lowercased döner.
    """
    if not supabase:
        return set()
    try:
        rows = (
            supabase.table("trend_x_sources")
            .select("username")
            .eq("is_active", True)
            .eq("batch_type", "ai_curator")
            .execute()
        ).data or []
        return {(r.get("username") or "").lower() for r in rows if r.get("username")}
    except Exception as e:
        logger.warning(f"get_curator_usernames okuma hatası (boş döndü): {e!r}")
        return set()


# ================================================================
# RADAR CONFIG (tümü ücretsiz)
# ================================================================
# 2026-06-10 (Berkay) — RADAR KAPALI: "ora hiç kafa karıştırmasın".
# Sinyal kaynağı yalnız trend_x_sources'taki X hesapları (ai_core resmi
# hesaplar + ai_news_tr + ai_tech). Radar taramaları (google_trends,
# hacker_news, reddit, github, polymarket, trustmrr, wikipedia) persona
# kapsamı dışında gürültü + TR siyaset/eğlence gibi gate'in zaten
# blokladığı kategorilerde boşa quota üretiyordu. Geri açmak istersen
# eski liste git geçmişinde (commit 2429c27 öncesi).
RADAR_SCANS: list[dict] = []


# ================================================================
# X TRENDS (metered, cache'lenecek)
# ================================================================
async def fetch_x_trends() -> dict:
    """
    X trending topics — TR + Worldwide.
    Metered (~3 kredi/çağrı), agresif cache önerilir.
    """
    try:
        turkey = await xquik.get_trends(woeid=23424969, count=50)
        worldwide = await xquik.get_trends(woeid=1, count=30)
        logger.info(f"X Trends: {len(turkey)} TR, {len(worldwide)} WW")
        return {"turkey": turkey, "worldwide": worldwide}
    except Exception as e:
        logger.error(f"X Trends hatası: {e}")
        return {"turkey": [], "worldwide": []}


# ================================================================
# BATCH TWEET FETCHING
# ================================================================
def _get_last_fetch_date(batch_type: str) -> str:
    """Feed tablosundan bu batch'in en son çektiği tweet tarihini al."""
    if not supabase:
        return None
    try:
        result = (
            supabase.table("tweet_feed")
            .select("tweet_created_at")
            .eq("batch_type", batch_type)
            .order("tweet_created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            dt_str = result.data[0].get("tweet_created_at", "")
            if dt_str:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"Last fetch date sorgusu başarısız [{batch_type}]: {e}")
    return None


async def _process_raw_results(
    raw_results: List[dict],
    batch_type: str,
    usernames: List[str],
    since_date: Optional[str],
) -> List[dict]:
    """Shared post-fetch processing: filter RTs / short / link-only,
    map to canonical dict, run enrichment. Same logic the legacy
    combined-batch path had — extracted so the per-account path uses
    identical filters."""
    results: List[dict] = []
    for item in raw_results:
        text = item.get("tweetText", "")
        tweet_id = item.get("tweetId", "")
        username = item.get("xUsername", "")
        if text.startswith("RT @"):
            continue
        raw_date = item.get("tweetCreatedAt")
        tweet_dt = None
        if raw_date:
            try:
                tweet_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except Exception:
                pass
        if len(text.split()) < 4:
            continue
        if text.startswith("http") and len(text.split()) <= 2:
            continue
        results.append({
            "tweet_id": str(tweet_id),
            "username": username,
            "display_name": item.get("xDisplayName", ""),
            "avatar_url": (item.get("xProfileImageUrl") or "").replace("_normal.", "_400x400."),
            "text": text,
            "likes": item.get("likeCount", 0),
            "retweets": item.get("retweetCount", 0),
            "replies": item.get("replyCount", 0),
            "views": item.get("viewCount", 0),
            "quotes": item.get("quoteCount", 0),
            "bookmarks": item.get("bookmarkCount", 0),
            "media": [],
            "has_media": False,
            "image_url": None,
            "verified": item.get("xVerified", False),
            "followers_count": item.get("xFollowersCount", 0),
            "created_at": tweet_dt.isoformat() if tweet_dt else raw_date,
            "url": f"https://x.com/{username}/status/{tweet_id}",
        })
    logger.info(
        f"[{batch_type}] {len(results)} tweets after filtering "
        f"(since={since_date}, from {len(usernames)} accounts)"
    )
    return await enrich_tweets_with_lookup(results)


_ZERO_STREAK_THRESHOLD = 3        # consecutive fetches at 0 → alert
_ZERO_STREAK_STATE: dict[str, int] = {}


def _alert_zero_streak_per_account(batch_type: str,
                                     per_account_counts: dict[str, int]) -> None:
    """Track consecutive zero-fetch counts per AI account; alert at threshold.

    Best-effort: uses an in-memory counter (resets on process restart).
    For durable streak tracking the counts could be persisted to
    `account_fetch_streaks`, but the in-memory version still catches the
    "AI account silently stopped" case across a single process lifetime.
    """
    try:
        from services.alerter import alert_supply as _alert
    except Exception:
        _alert = None
    for handle, count in per_account_counts.items():
        key = f"{batch_type}:{handle}"
        if count == 0:
            _ZERO_STREAK_STATE[key] = _ZERO_STREAK_STATE.get(key, 0) + 1
        else:
            _ZERO_STREAK_STATE[key] = 0
        streak = _ZERO_STREAK_STATE[key]
        if streak == _ZERO_STREAK_THRESHOLD:
            msg = (
                f"AI ingestion: @{handle} ({batch_type}) returned 0 tweets "
                f"for {streak} consecutive fetches. Check the handle (renamed? "
                f"suspended?) or the lookback window."
            )
            logger.warning(f"[ai-supply-alert] {msg}")
            if _alert is not None:
                try:
                    _alert(
                        severity="WARN",
                        category=f"ai_supply::zero_streak::{handle}",
                        summary=msg,
                        evidence={"handle": handle, "batch_type": batch_type,
                                  "streak": streak},
                    )
                except Exception:
                    pass


async def _fetch_single_account(
    username: str,
    limit: int,
    since_date: Optional[str],
) -> tuple[List[dict], Optional[str]]:
    """Fetch one account in isolation. Returns (raw_results, error_or_None).

    Used by fetch_batch_tweets when AI_CORE_PER_ACCOUNT is on so a single
    bad/renamed handle (e.g. ClaudeAI rebranded) does NOT zero the rest.
    """
    body = {
        "toolType": "tweet_search_extractor",
        "searchQuery": f"from:{username}",
        "resultsLimit": limit,
        "retweets": "exclude",
    }
    if since_date:
        body["sinceDate"] = since_date
    try:
        job = await xquik._post("/extractions", body)
        ext = job.get("id")
        if not ext:
            return [], f"no_extraction_id (job={str(job)[:120]})"
        raw = await xquik.get_extraction_results(ext) or []
        return raw, None
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:160]}"


async def fetch_batch_tweets(
    usernames: List[str],
    limit: int = 50,
    batch_type: str = "",
) -> List[dict]:
    """
    Birden fazla hesabın tweetlerini tek sorguda çek.
    tweet_search_extractor: from:user1 OR from:user2 OR ...
    RT exclude, sinceDate ile sadece yenileri çek.
    Upsert ile dedup — hiçbir tweet kaçmaz.

    6 Haz 2026 — for AI batches we use per-account isolation + a hard
    lookback window instead of the dynamic batch-level sinceDate. This
    closes the "high-volume account snaps sinceDate forward → low-volume
    AI accounts get filtered out" crowding-out bug.
    """
    if not usernames:
        return []

    # ── HARD lookback for AI batches (overrides dynamic sinceDate) ─────
    hard_h = _HARD_LOOKBACK_HOURS.get(batch_type)
    if hard_h is not None:
        since_date = (datetime.now(timezone.utc)
                       - timedelta(hours=hard_h)).strftime("%Y-%m-%d")
    else:
        since_date = _get_last_fetch_date(batch_type)

    # ── Per-account isolation for AI batches (Step 3) ─────────────────
    # Each AI account in its own Xquik call → log per-account count → a
    # single 401 / rate-limit / renamed-handle does NOT zero the rest.
    # The cost is N Xquik calls per batch (N=7 for ai_core); each
    # extractor call is a few credits — well within the 335K-credit budget.
    if batch_type in {"ai_core", "ai_news_tr", "ai_news_en", "ai_tech"}:
        raw_results: List[dict] = []
        per_account_counts: dict[str, int] = {}
        per_account_errors: dict[str, str] = {}
        for handle in usernames:
            results, err = await _fetch_single_account(handle, limit, since_date)
            per_account_counts[handle] = len(results)
            if err:
                per_account_errors[handle] = err
            raw_results.extend(results)
        # Per-account log line — visible in journalctl, the missing
        # observability that let AI ingestion die silently since Jun 5.
        breakdown = ", ".join(f"@{h}={n}" for h, n in per_account_counts.items())
        logger.info(
            f"[{batch_type}] per-account fetch (since={since_date}): {breakdown}"
        )
        if per_account_errors:
            for h, err in per_account_errors.items():
                logger.warning(f"[{batch_type}] @{h} fetch error: {err}")

        # Step 5 — alert on zero-streak per AI account (best-effort)
        try:
            _alert_zero_streak_per_account(batch_type, per_account_counts)
        except Exception as _ae:
            logger.warning(f"[{batch_type}] zero-streak alert failed: {_ae!r}")

        # Re-use the existing post-fetch processing path below
        return await _process_raw_results(
            raw_results, batch_type, usernames, since_date,
        )

    # ── Legacy combined-batch path (kept for non-AI batches) ──────────
    query = " OR ".join(f"from:{u}" for u in usernames)

    try:
        body = {
            "toolType": "tweet_search_extractor",
            "searchQuery": query,
            "resultsLimit": limit,
            "retweets": "exclude",
        }
        if since_date:
            body["sinceDate"] = since_date

        job = await xquik._post("/extractions", body)
        extraction_id = job.get("id")
        if not extraction_id:
            logger.error(f"Batch fetch [{batch_type}]: no extraction ID: {job}")
            return []

        raw_results = await xquik.get_extraction_results(extraction_id)
        logger.info(f"Batch [{batch_type}]: {len(raw_results)} raw tweets from {len(usernames)} accounts")

        results = []
        for item in raw_results:
            text = item.get("tweetText", "")
            tweet_id = item.get("tweetId", "")
            username = item.get("xUsername", "")

            if text.startswith("RT @"):
                continue

            raw_date = item.get("tweetCreatedAt")
            tweet_dt = None
            if raw_date:
                try:
                    tweet_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except Exception:
                    pass

            # 4 kelimeden kısa atla
            if len(text.split()) < 4:
                continue

            # Sadece link olan atla
            if text.startswith("http") and len(text.split()) <= 2:
                continue

            results.append({
                "tweet_id": str(tweet_id),
                "username": username,
                "display_name": item.get("xDisplayName", ""),
                "avatar_url": (item.get("xProfileImageUrl") or "").replace("_normal.", "_400x400."),
                "text": text,
                "likes": item.get("likeCount", 0),
                "retweets": item.get("retweetCount", 0),
                "replies": item.get("replyCount", 0),
                "views": item.get("viewCount", 0),
                "quotes": item.get("quoteCount", 0),
                "bookmarks": item.get("bookmarkCount", 0),
                "media": [],
                "has_media": False,
                "image_url": None,
                "verified": item.get("xVerified", False),
                "followers_count": item.get("xFollowersCount", 0),
                "created_at": tweet_dt.isoformat() if tweet_dt else raw_date,
                "url": f"https://x.com/{username}/status/{tweet_id}",
            })

        logger.info(f"Batch [{batch_type}]: {len(results)} tweets after filtering (since={since_date})")

        # Enrichment: lookup ile engagement + media çek
        results = await enrich_tweets_with_lookup(results)

        return results

    except Exception as e:
        logger.error(f"Batch fetch hatası [{batch_type}]: {e}")
        return []


# ================================================================
# ENRICHMENT — lookup_tweet ile engagement + media
# ================================================================
async def enrich_tweets_with_lookup(
    tweets: List[dict],
    batch_size: int = 10,
) -> List[dict]:
    """
    Tweet listesini lookup_tweet() ile enrich et.
    Engagement metrikleri + media + verified + followers ekler.
    Quota-aware: free_only modda skip eder.
    Rate limit: batch'ler arası 1s sleep.
    """
    if not tweets:
        return tweets

    quota = await get_quota_status()
    if quota.get("mode") == "free_only":
        logger.info("Enrichment skipped: quota free_only mode")
        return tweets

    tweet_ids = [t["tweet_id"] for t in tweets if t.get("tweet_id") and not t["tweet_id"].startswith("radar_")]
    if not tweet_ids:
        return tweets

    # Faz 1 — enrichment-skip (XQuik kota tasarrufu): zaten enrich edilmiş (enriched_at
    # TTL içinde) tweet'leri TEKRAR lookup'lama. Media KORU (carry-over → upsert ezmesin).
    # Flag OFF → bu blok hiç girilmez, davranış BİREBİR eski. fail-open.
    if os.environ.get("TREND_ENRICH_SKIP_ENABLED", "false").lower() in ("1", "true", "yes", "on"):
        try:
            _ttl_h = int(os.environ.get("TREND_ENRICH_SKIP_TTL_HOURS", "48"))
            # tz-aware (session-TZ bağımsız): cutoff +00:00 taşır, stored enriched_at ile tutarlı kıyas.
            _cutoff = (datetime.now(timezone.utc) - timedelta(hours=_ttl_h)).isoformat()
            _existing = {}
            if supabase:
                _rows = (
                    supabase.table("tweet_feed")
                    .select("tweet_id, media, has_media, image_url, enriched_at")
                    .in_("tweet_id", tweet_ids)
                    .not_.is_("enriched_at", "null")
                    .gte("enriched_at", _cutoff)
                    .execute().data
                ) or []
                _existing = {r["tweet_id"]: r for r in _rows}
            if _existing:
                _skipped = 0
                for t in tweets:
                    e = _existing.get(t.get("tweet_id"))
                    if not e:
                        continue
                    # Carry-over: mevcut media/enriched_at'i taşı (upsert media'yı EZMESİN).
                    # _enriched_now SET ETME → enriched_at orijinal kalır (gerçek lookup değil).
                    t["media"] = e.get("media") or []
                    t["has_media"] = bool(e.get("has_media"))
                    t["image_url"] = e.get("image_url")
                    t["enriched_at"] = e.get("enriched_at")
                    _skipped += 1
                tweet_ids = [tid for tid in tweet_ids if tid not in _existing]
                logger.info(f"Enrichment skip: {_skipped} zaten-enriched (TTL {_ttl_h}h) → lookup'tan çıkarıldı")
        except Exception as _se:
            logger.warning(f"enrichment skip kontrolü atlandı (fail-open): {_se}")

    if not tweet_ids:
        logger.info("Enrichment: tüm tweet'ler zaten enriched (skip), lookup yapılmadı")
        return tweets

    enrichment = {}
    for i in range(0, len(tweet_ids), batch_size):
        batch = tweet_ids[i:i + batch_size]
        tasks = [xquik.lookup_tweet(tid) for tid in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for tid, result in zip(batch, results):
            if isinstance(result, Exception) or not result:
                continue

            tweet_data = result.get("tweet", {})
            author_data = result.get("author", {})

            raw_media = tweet_data.get("media") or []
            media = []
            for m in raw_media:
                media.append({
                    "type": m.get("type", "photo"),
                    "url": m.get("url", ""),
                    "preview_url": m.get("previewUrl", m.get("url", "")),
                })

            enrichment[tid] = {
                "likes": tweet_data.get("likeCount", 0),
                "retweets": tweet_data.get("retweetCount", 0),
                "replies": tweet_data.get("replyCount", 0),
                "quotes": tweet_data.get("quoteCount", 0),
                "views": tweet_data.get("viewCount", 0),
                "bookmarks": tweet_data.get("bookmarkCount", 0),
                "media": media,
                "has_media": len(media) > 0,
                "image_url": media[0]["url"] if media else None,
                "verified": author_data.get("verified", False),
                "followers_count": author_data.get("followers", 0),
            }

        if i + batch_size < len(tweet_ids):
            await asyncio.sleep(1)

    # Enrichment verilerini tweet'lere merge et
    for t in tweets:
        data = enrichment.get(t.get("tweet_id"))
        if data:
            t.update(data)
            t["_enriched_now"] = True   # Faz 0: enriched_at'i yalnız gerçek lookup'ta tazele

    logger.info(f"Enrichment: looked_up={len(enrichment)}/{len(tweet_ids)} (skip-sonrası kalan)")
    return tweets


# ================================================================
# RADAR FETCHING (tümü ücretsiz)
# ================================================================
def _radar_to_signal(item: dict, source_key: str) -> dict:
    """Radar item → raw_signals formatına normalize."""
    return {
        "source_type": "radar",
        "source_name": f"Radar:{source_key}",
        "niche": item.get("category", "tech"),
        "title": item.get("title", "")[:500],
        "url": item.get("url", "")[:2000],
        "raw_data": {
            "description": item.get("description", ""),
            "score": item.get("score", 0),
            "radar_source": item.get("source", ""),
            "metadata": item.get("metadata", {}),
            "published_at": item.get("publishedAt"),
            "image_url": item.get("imageUrl"),
        },
        "status": "pending",
    }


async def fetch_radar_signals() -> List[dict]:
    """
    XQuik Radar'dan trend sinyalleri çek — tümü ÜCRETSİZ.
    12 tarama: 7 kaynak × farklı kategoriler.
    """
    items = []
    for scan in RADAR_SCANS:
        try:
            data = await xquik.get_radar(**scan)
            source_key = f"{scan['source']}_{scan.get('region', 'global')}_{scan['category']}"
            for item in data.get("items", []):
                items.append(_radar_to_signal(item, source_key))
        except Exception as e:
            logger.warning(f"Radar {scan.get('source', '?')}/{scan.get('category', '?')}: {e}")

    logger.info(f"Radar: {len(items)} sinyal toplandı (ücretsiz)")
    return items


# ================================================================
# FEED UPSERT
# ================================================================
async def _upsert_to_feed(tweets: List[dict], batch_type: str) -> int:
    """Tweetleri tweet_feed tablosuna yaz (upsert by tweet_id)."""
    if not supabase or not tweets:
        return 0

    rows = []
    for t in tweets:
        media_val = t.get("media", [])
        rows.append({
            "tweet_id": t["tweet_id"],
            "username": t.get("username", ""),
            "display_name": t.get("display_name", ""),
            "avatar_url": t.get("avatar_url", ""),
            "content": t.get("text", ""),
            "likes": t.get("likes", 0),
            "retweets": t.get("retweets", 0),
            "replies": t.get("replies", 0),
            "views": t.get("views", 0),
            "quotes": t.get("quotes", 0),
            "bookmarks": t.get("bookmarks", 0),
            "media": media_val if media_val else [],
            "has_media": t.get("has_media", False),
            "image_url": t.get("image_url"),
            "verified": t.get("verified", False),
            "followers_count": t.get("followers_count", 0),
            "tweet_url": t.get("url", ""),
            "batch_type": batch_type,
            "source_detail": t.get("username", ""),
            "tweet_created_at": t.get("created_at"),
            # Faz 0 fix: enriched_at YALNIZ gerçek lookup yapıldıysa tazele; aksi halde
            # mevcut değeri taşı (skip carry-over) — buglu "has_media is not None" kaldırıldı.
            "enriched_at": datetime.now(timezone.utc).isoformat() if t.get("_enriched_now") else t.get("enriched_at"),
        })

    try:
        result = supabase.table("tweet_feed").upsert(
            rows, on_conflict="tweet_id"
        ).execute()
        count = len(result.data) if result.data else 0
        logger.info(f"Feed upsert [{batch_type}]: {count} tweets")
        return count
    except Exception as e:
        logger.error(f"Feed upsert hatası [{batch_type}]: {e}")
        return 0


async def _upsert_radar_to_feed(signals: List[dict], score_threshold: int = 5000) -> int:
    """Yüksek skorlu radar sinyallerini feed'e yaz."""
    if not supabase or not signals:
        return 0

    rows = []
    seen_ids = set()
    for s in signals:
        score = s.get("raw_data", {}).get("score", 0)
        if score < score_threshold:
            continue
        tid = f"radar_{hash(s['url'])}"
        if tid in seen_ids:
            continue
        seen_ids.add(tid)
        radar_image = s.get("raw_data", {}).get("image_url")
        rows.append({
            "tweet_id": tid,
            "username": s.get("source_name", "Radar"),
            "display_name": s.get("source_name", "Radar"),
            "content": f"{s.get('title', '')} — {s.get('raw_data', {}).get('description', '')}".strip()[:1000],
            "likes": score,
            "retweets": 0,
            "replies": 0,
            "views": 0,
            "quotes": 0,
            "bookmarks": 0,
            "media": [{"type": "photo", "url": radar_image, "preview_url": radar_image}] if radar_image else [],
            "has_media": bool(radar_image),
            "image_url": radar_image,
            "tweet_url": s.get("url", ""),
            "batch_type": "radar",
            "source_detail": s.get("raw_data", {}).get("radar_source", ""),
            "tweet_created_at": s.get("raw_data", {}).get("published_at"),
        })

    if not rows:
        return 0

    try:
        result = supabase.table("tweet_feed").upsert(
            rows, on_conflict="tweet_id"
        ).execute()
        count = len(result.data) if result.data else 0
        logger.info(f"Radar feed upsert: {count} items (score>{score_threshold})")
        return count
    except Exception as e:
        logger.error(f"Radar feed upsert hatası: {e}")
        return 0


# ================================================================
# MONITOR EVENTS (ücretsiz)
# ================================================================
async def fetch_monitor_events() -> List[dict]:
    """Monitor'lenen hesapların yeni tweet event'lerini çek (ücretsiz)."""
    try:
        events = await xquik.list_events(event_type="tweet.new", limit=50)
        if not events:
            return []

        results = []
        for event in events:
            data = event.get("data", {})
            author = data.get("author", {})
            tweet_id = data.get("id", "")
            text = data.get("text", "")

            if not tweet_id or not text:
                continue
            if text.startswith("RT @"):
                continue
            if len(text.split()) < 4:
                continue

            raw_media = data.get("media") or []
            media = [{"type": m.get("type", "photo"), "url": m.get("url", ""), "preview_url": m.get("previewUrl", m.get("url", ""))} for m in raw_media]

            results.append({
                "tweet_id": str(tweet_id),
                "username": author.get("userName", ""),
                "display_name": author.get("name", ""),
                "avatar_url": "",
                "text": text,
                "likes": data.get("likeCount", 0),
                "retweets": data.get("retweetCount", 0),
                "replies": data.get("replyCount", 0),
                "views": data.get("viewCount", 0),
                "quotes": data.get("quoteCount", 0),
                "bookmarks": data.get("bookmarkCount", 0),
                "media": media,
                "has_media": len(media) > 0,
                "image_url": media[0]["url"] if media else None,
                "created_at": data.get("createdAt"),
                "url": f"https://x.com/{author.get('userName', '')}/status/{tweet_id}",
            })

        logger.info(f"Monitor events: {len(results)} yeni tweet")
        return results
    except Exception as e:
        logger.error(f"Monitor events hatası: {e}")
        return []


# ---------------------------------------------------------------
# Faz 2-3 (2026-06-14) — fetch telemetri + ANINDA kuraklık alarmı.
# Per-batch sonuç trend_fetch_batch_stats'a yazılır (DB-backed, restart-safe);
# bir batch 0 dönerse O TURDA alarm (ai_core → CRITICAL). 24h beklemeden.
# In-memory _ZERO_STREAK_STATE'in restart-dayanıklı halefi.
# ---------------------------------------------------------------
_BATCH_ZERO_CRITICAL = {"ai_core"}   # 0 dönerse CRITICAL (içerik bunsuz ölüyor)


def _db_zero_streak(batch_type: str, limit: int = 6) -> int:
    """Son `limit` batch-toplam kaydında ardışık 0-streak (restart-dayanıklı)."""
    if not supabase:
        return 0
    try:
        rows = (
            supabase.table("trend_fetch_batch_stats")
            .select("tweets_fetched")
            .eq("batch_type", batch_type)
            .is_("username", "null")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        ) or []
    except Exception:
        return 0
    streak = 0
    for r in rows:
        if int(r.get("tweets_fetched") or 0) == 0:
            streak += 1
        else:
            break
    return streak


def _record_batch_telemetry(per_batch: dict) -> None:
    """Per-batch fetch sonucunu DB'ye yaz + batch-zero için ANINDA alarm."""
    import uuid
    try:
        from services.alerter import alert_supply as _alert
    except Exception:
        _alert = None
    cycle_id = str(uuid.uuid4())
    rows = [
        {
            "run_id": cycle_id,
            "batch_type": bt,
            "username": None,                       # batch-toplam satırı
            "tweets_fetched": int(info.get("fetched", 0)),
            "error": (info.get("error") or None),
        }
        for bt, info in per_batch.items()
    ]
    if supabase and rows:
        try:
            supabase.table("trend_fetch_batch_stats").insert(rows).execute()
        except Exception as e:
            logger.warning(f"trend_fetch_batch_stats insert failed: {e}")
    # ANINDA batch-zero alarmı (DB-backed streak ile)
    for bt, info in per_batch.items():
        if int(info.get("fetched", 0)) > 0:
            continue
        streak = _db_zero_streak(bt)
        sev = "CRITICAL" if bt in _BATCH_ZERO_CRITICAL else "WARN"
        err = info.get("error")
        summary = (
            f"'{bt}' batch fetch 0 tweet döndü (ardışık {streak} tur). "
            + (f"Hata: {err}" if err
               else "Hesaplar tweet atmadı ya da hepsi filtrelendi / kota.")
        )
        logger.warning(f"[ai-supply-alert] {summary}")
        if _alert:
            try:
                _alert(severity=sev,
                       category=f"trend_supply::batch_zero::{bt}",
                       summary=summary,
                       evidence={"batch_type": bt, "fetched": 0,
                                 "streak": streak, "error": err})
            except Exception:
                pass


# ================================================================
# MAIN PIPELINE — BATCH ONLY (ücretli, 2x/gün)
# ================================================================
async def fetch_batch_signals() -> List[dict]:
    """
    Sadece 3 batch çalıştırır (AI Tech, TR Haber, Spor).
    ÜCRETLİ — 2x/gün çalıştır.
    Tweetleri tweet_feed'e yazar.
    """
    all_signals = []

    active_batches = get_active_batches()
    if not active_batches:
        # get_active_batches already logged ERROR + emitted CRITICAL alert.
        # Skip cleanly; never quietly invoke a stale BATCHES list.
        logger.error(
            "fetch_batch_signals: get_active_batches returned EMPTY — "
            "trend supply is misconfigured. Skipping this fetch entirely "
            "(NOT falling back to hardcoded noise)."
        )
        return []
    batch_summary = ", ".join(
        f"{k}=[{','.join(v['accounts'])}]" for k, v in active_batches.items()
    )
    logger.info(
        f"fetch_batch_signals: using {len(active_batches)} batches → {batch_summary}"
    )

    # Faz 1 — kota SESSİZ DEĞİL: degrade varsa anında alarm. ai_core gibi ağır
    # batch'ler kota tükenince sessizce 0 dönüyordu; artık görünür.
    try:
        from services.quota_manager import get_quota_status as _gqs
        _q = await _gqs()
        _mode = (_q or {}).get("mode", "normal")
        if _mode != "normal":
            from services.alerter import alert_supply as _qalert
            _sev = "CRITICAL" if _mode in ("free_only", "minimal") else "WARN"
            _qalert(severity=_sev,
                    category=f"trend_supply::quota::{_mode}",
                    summary=f"XQuik kota '{_mode}' (kalan ~{(_q or {}).get('remaining')}). Fetch kısıtlı.",
                    evidence=_q or {})
    except Exception as _qe:
        logger.warning(f"quota probe failed: {_qe}")

    batch_tasks = {}
    for batch_name, config in active_batches.items():
        batch_tasks[batch_name] = fetch_batch_tweets(
            config["accounts"], limit=config["limit"], batch_type=batch_name
        )

    batch_results = await asyncio.gather(
        *batch_tasks.values(), return_exceptions=True
    )

    batch_count = 0
    per_batch: dict = {}
    for (batch_name, config), result in zip(active_batches.items(), batch_results):
        if isinstance(result, Exception):
            logger.error(f"Batch {batch_name} hatası: {result}")
            per_batch[batch_name] = {
                "fetched": 0,
                "error": f"{type(result).__name__}: {str(result)[:200]}",
            }
            continue

        tweets = result
        for tweet in tweets:
            tweet["tier"] = 1
            tweet["category"] = config["category"]
        all_signals.extend(tweets)
        batch_count += len(tweets)
        per_batch[batch_name] = {"fetched": len(tweets), "error": None}

        await _upsert_to_feed(tweets, batch_type=batch_name)

    # Faz 2-3 — per-batch telemetri (trend_fetch_batch_stats) + ANINDA batch-zero
    # alarmı (ai_core 0 → CRITICAL). Kuraklık 24h beklemeden görünür.
    _record_batch_telemetry(per_batch)

    logger.info(f"Batch signals: {batch_count} tweets collected")
    return all_signals


# ================================================================
# MAIN PIPELINE — RADAR + MONITOR (ücretsiz, 4x/gün)
# ================================================================
async def fetch_radar_signals_full() -> List[dict]:
    """
    Radar + Monitor Events birlikte çalıştırır.
    ÜCRETSİZ — 4x/gün çalıştır.
    Tweetleri tweet_feed'e yazar.
    """
    all_signals = []

    # --- Radar (ücretsiz) ---
    radar_signals = await fetch_radar_signals()
    all_signals.extend([{
        "tweet_id": f"radar_{hash(s['url'])}",
        "username": s.get("source_name", ""),
        "text": s.get("title", ""),
        "likes": s.get("raw_data", {}).get("score", 0),
        "retweets": 0,
        "replies": 0,
        "views": 0,
        "tier": 0,
        "category": "radar",
        "created_at": s.get("raw_data", {}).get("published_at"),
        "url": s.get("url", ""),
    } for s in radar_signals])

    # Radar feed upsert devre dışı — radar artık feed'de gösterilmiyor
    # await _upsert_radar_to_feed(radar_signals, score_threshold=5000)

    # --- Monitor Events (ücretsiz) ---
    monitor_tweets = await fetch_monitor_events()
    for tweet in monitor_tweets:
        tweet["tier"] = 1
        tweet["category"] = "monitor"
    all_signals.extend(monitor_tweets)
    await _upsert_to_feed(monitor_tweets, batch_type="monitor")

    logger.info(f"Radar+Monitor signals: radar={len(radar_signals)}, monitor={len(monitor_tweets)}")
    return all_signals


# ================================================================
# MAIN PIPELINE — HEPSİ BİRLİKTE (backward compat)
# ================================================================
async def fetch_all_twitter_signals() -> List[dict]:
    """
    Tüm Twitter + Radar sinyallerini topla.
    3 batch + radar + monitor events.
    Sonuçları hem raw_signals'a hem tweet_feed'e yaz.
    """
    all_signals = []

    # Batch'ler (ücretli)
    batch_signals = await fetch_batch_signals()
    all_signals.extend(batch_signals)

    # Radar + Monitor (ücretsiz)
    radar_signals = await fetch_radar_signals_full()
    all_signals.extend(radar_signals)

    logger.info(f"Toplam {len(all_signals)} sinyal toplandı")
    return all_signals
