"""Hype Crew runner — entry point for systemd timer (or manual CLI).

Usage:
  python -m hype_crew.runner                     # process all active accounts
  python -m hype_crew.runner --account=<uuid>    # single account
  python -m hype_crew.runner --account=<uuid> --triggered-by=manual

Environment guards (set in .env):
  HYPE_DRY_RUN=true              # fallback only — DB hype_account_config.dry_run_mode wins
  HYPE_DAILY_COST_CAP_USD=2.00   # fallback only — DB daily_cost_cap_usd wins (Gap #5)
  HYPE_LOG_LEVEL=INFO

Each invocation = one fresh Python process. No global state between accounts.

Pre-flight checks (before Flow.kickoff):
  • Cost cap (Gap #5)         — if today's spend >= effective cap, skip + log cost_cap_exceeded
  • Failure-rate alarm (Gap #6) — log ERROR when last 3 runs all failed
"""
import argparse
import sys
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

# Load config first (sets env vars for CrewAI, disables telemetry, etc.)
from config import settings  # noqa: F401  (side-effects)


# Pre-flight thresholds
CAP_STATUS = "cost_cap_exceeded"
FAILURE_ALARM_THRESHOLD = 3
STUCK_RUN_THRESHOLD_HOURS = 2   # mark as failed if running > N hours (likely OOM/crash)


def _today_utc_iso() -> str:
    """UTC 00:00 boundary as ISO. Used for 'today's spend' window."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _get_effective_cap(sb, account_id: str) -> float:
    """Per-account cap > env default. NULL → env fallback. 0 → disabled."""
    try:
        row = (
            sb.table("hype_account_config")
            .select("daily_cost_cap_usd")
            .eq("account_id", account_id).limit(1).execute()
        )
        if row.data and row.data[0].get("daily_cost_cap_usd") is not None:
            return float(row.data[0]["daily_cost_cap_usd"])
    except Exception as e:
        logger.warning(f"[Runner] _get_effective_cap query failed: {e}; using env")
    return float(settings.daily_cost_cap_usd)


def _today_spend(sb, account_id: str) -> float:
    r = (
        sb.table("hype_runs").select("total_cost_usd")
        .eq("account_id", account_id)
        .gte("started_at", _today_utc_iso()).execute()
    )
    return sum(float(x.get("total_cost_usd") or 0) for x in (r.data or []))


def reap_orphan_drafts(sb, run_id: str, reason: str) -> int:
    """Soft-delete a run's not-yet-scheduled (postiz_post_id IS NULL) draft rows.

    Shared helper: used by `_reap_stuck_runs` (auto-reaped stuck runs) and by
    lg/graph.py's MED-4 max-resume gate (poison-run force-fail). Only touches
    pending/pending_review rows WITHOUT a postiz_post_id — anything already on
    the publish path (real id OR the 'SCHEDULING' write-ahead sentinel) is left
    alone so we never orphan a live/in-flight post. Returns count soft-deleted.
    """
    if not run_id:
        return 0
    try:
        orphans = (
            sb.table("daily_drafts")
            .update({
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "deleted_reason": reason,
            })
            .eq("hype_run_id", run_id)
            .in_("status", ["pending", "pending_review"])
            .is_("postiz_post_id", "null")
            .is_("deleted_at", "null")
            .execute()
        )
        n = len(orphans.data) if orphans.data else 0
        if n:
            logger.warning(
                f"[Runner] run {str(run_id)[:8]}: {n} yetim draft soft-delete "
                f"edildi (reason={reason!r})"
            )
        return n
    except Exception as _oe:
        logger.warning(f"[Runner] yetim draft temizliği başarısız ({run_id}): {_oe}")
        return 0


def _reap_stuck_runs(sb, account_id: str) -> int:
    """Auto-fail hype_runs stuck in 'running' beyond threshold (OOM/crash recovery).

    Returns count of reaped rows. Safe to call every run — idempotent.
    Without this, a single OOM event leaves rows stuck in 'running' indefinitely
    and the corresponding `daily_drafts` show as 'pending' forever from the UI.

    LangGraph Faz 2 koordinasyonu: bu reaper YALNIZ >STUCK_RUN_THRESHOLD_HOURS
    (.lt(cutoff)) satırları failed yapar. Bu yüzden <2h yaşında, canlı
    checkpoint'li ('next' dolu) bir 'running' satır ASLA reap edilmez — cutoff
    dışındadır → run_for_account onu resume eder. Tersine, >2h gerçekten takılı
    bir satır (checkpoint'i olsun ya da olmasın) failed olur; resume sonsuz
    döngüye giremez. Yani kural "checkpoint-less veya >2h reaple, <2h +
    canlı-checkpoint resume et" yaşam-süresi sınırıyla otomatik sağlanır.
    """
    from datetime import timedelta
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=STUCK_RUN_THRESHOLD_HOURS)
    ).isoformat()
    try:
        r = (
            sb.table("hype_runs")
            .update({
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": f"auto-reaped by runner: stuck >{STUCK_RUN_THRESHOLD_HOURS}h",
            })
            .eq("account_id", account_id)
            .eq("status", "running")
            .lt("started_at", cutoff)
            .execute()
        )
        reaped = r.data or []
        # 2026-06-10 (C yaması) — yetim draft temizliği: stuck run yarıda
        # kaldıysa yazabildiği KISMÎ platform seti review kuyruğunda normal
        # kart gibi duruyordu ("X-only" / "video var ama YT-IG yok" vakaları).
        # Reap edilen run'ların henüz schedule edilmemiş draftları soft-delete
        # edilir; postiz_post_id'si olanlara (zaten yayın yolunda) dokunulmaz.
        for _run in reaped:
            _rid = _run.get("id")
            if not _rid:
                continue
            reap_orphan_drafts(sb, str(_rid), "orphan of auto-reaped stuck run")
        return len(reaped)
    except Exception as e:
        logger.warning(f"[Runner] _reap_stuck_runs failed: {e}")
        return 0


SCHEDULING_ORPHAN_MAX_AGE_MIN = 15  # >bu yaştaki 'SCHEDULING' sentinel = yetim


def _alert_stale_scheduling_orphans(sb, account_id: str) -> int:
    """Flag-BAĞIMSIZ: takılı 'SCHEDULING' write-ahead sentinel'lerini alarmlat.

    Write-ahead `postiz_post_id='SCHEDULING'` yazar, sonra gerçek id'ye UPDATE eder.
    Crash schedule_posts ile writeback ARASINDA olursa sentinel kalır. flow.py'deki
    FAIL-CLOSED tespiti YALNIZ langgraph_enabled iken çalışır → flag-off rollback'te
    o satır alarmsız zombi kalır; reaper de KORUR (filtre postiz_post_id IS NULL).
    Bu kontrol flag'den bağımsız her cron'da çalışır: >N dk eski 'SCHEDULING' satırı
    → CRITICAL alarm. OTOMATİK SİLMEZ — gerçek bir Postiz post'unu yetim bırakmamak
    için operatör Postiz panelinden reconcile etmeli. Returns stale orphan sayısı.
    """
    from datetime import timedelta
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(minutes=SCHEDULING_ORPHAN_MAX_AGE_MIN)
    ).isoformat()
    try:
        r = (
            sb.table("daily_drafts")
            .select("id, platform, hype_run_id, created_at")
            .eq("account_id", account_id)
            .eq("postiz_post_id", "SCHEDULING")
            .is_("deleted_at", "null")
            .lt("created_at", cutoff)
            .execute()
        )
        rows = r.data or []
        if not rows:
            return 0
        plats = sorted({x.get("platform") for x in rows if x.get("platform")})
        ids = [x.get("id") for x in rows][:10]
        try:
            from tools.alerter import send_alert
            send_alert(
                "Postiz SCHEDULING orphan — yetim write-ahead sentinel (manuel reconcile)",
                severity="CRITICAL",
                reason=(
                    f"{len(rows)} daily_drafts satırı >{SCHEDULING_ORPHAN_MAX_AGE_MIN}dk "
                    f"'SCHEDULING' sentinel'inde takılı (platform={plats}). Write-ahead "
                    "sonrası crash → Postiz'e gerçekten post atıldı mı belirsiz."
                ),
                action=(
                    "Postiz panelini kontrol et: post VARSA daily_drafts.postiz_post_id'yi "
                    "gerçek id'ye güncelle; YOKSA SCHEDULING satırını sil. OTOMATİK "
                    "silinmedi (gerçek post'u yetim bırakmamak için)."
                ),
                extra={"account_id": account_id, "draft_ids": ids, "platforms": plats},
            )
        except Exception as _ae:
            logger.warning(f"[Runner] SCHEDULING orphan alarmı gönderilemedi: {_ae}")
        logger.error(
            f"[Runner] {len(rows)} yetim SCHEDULING orphan (account={account_id[:8]}) "
            f"— CRITICAL alarm, manuel Postiz reconcile gerek"
        )
        return len(rows)
    except Exception as e:
        logger.warning(f"[Runner] SCHEDULING orphan kontrolü başarısız ({account_id[:8]}): {e}")
        return 0


def _recent_failure_streak(sb, account_id: str, n: int = FAILURE_ALARM_THRESHOLD) -> int:
    """Return n if last n runs are all 'failed', else 0. Ignores cost_cap_exceeded
    (not a real failure) and 'running' (in-progress, doesn't count)."""
    r = (
        sb.table("hype_runs").select("status")
        .eq("account_id", account_id)
        .neq("status", CAP_STATUS)
        .neq("status", "running")
        .order("started_at", desc=True).limit(n).execute()
    )
    rows = r.data or []
    if len(rows) < n:
        return 0
    return n if all(row.get("status") == "failed" for row in rows) else 0


def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    )


def get_eligible_accounts() -> list[dict]:
    """Pull accounts that have hype_account_config set up.

    For V1 we run for all configured accounts. Later we can add filters like
    `dry_run_mode=true` or `auto_publish_enabled=true`.
    """
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    r = (
        sb.table("hype_account_config")
        .select("account_id, dry_run_mode, auto_publish_enabled, daily_post_quota")
        .execute()
    )
    return r.data or []


def run_for_account(account_id: str, triggered_by: str = "cron") -> dict:
    """Execute one Flow run for one account. Returns final state summary.

    Pre-flight checks (before Flow.kickoff):
      • Cost cap: if today's spend >= effective cap → skip + insert
        hype_runs row with status='cost_cap_exceeded'
      • Failure alarm: if last 3 (non-running, non-cap) runs all 'failed' → log ERROR
    """
    from flow import AutonomousContentFlow
    from tools.supabase_client import make_supabase

    sb = make_supabase()

    # Watchdog — reap stuck 'running' rows from prior crashes (OOM, SIGKILL).
    # Must run before failure-streak check so reaped rows count as 'failed'.
    reaped = _reap_stuck_runs(sb, account_id)
    if reaped:
        logger.warning(f"[Runner] reaped {reaped} stuck run(s) for account={account_id}")

    # Flag-BAĞIMSIZ rollback-güvenliği: takılı 'SCHEDULING' write-ahead sentinel'leri
    # (flag-off'ta fail-closed kapanır + reaper korur → alarmsız zombi olurlardı).
    _alert_stale_scheduling_orphans(sb, account_id)

    # Gap #6 — Failure-rate alarm. 2026-06-10 (otonomi D0-2a): "log only"
    # ölü koddu — alert_runner_failure_streak hiç çağrılmıyordu, ardışık
    # hatalar yalnız journald'da kalıyordu. Artık gerçek alert (Slack +
    # journald [ALERT] prefix'i).
    streak = _recent_failure_streak(sb, account_id)
    if streak:
        logger.error(
            f"[ALARM] {streak} consecutive failures for account={account_id}; "
            f"investigate before continuing autonomous publishing"
        )
        try:
            from tools.alerter import alert_runner_failure_streak
            alert_runner_failure_streak(account_id, streak)
        except Exception as _ae:
            logger.warning(f"[Runner] failure-streak alert gönderilemedi: {_ae}")

    # Phase 26.H — Executive freeze pre-flight (C-suite kill switch).
    # If the executive board (or user) has set hype_account_config.executive_freeze=true,
    # skip this run entirely without spending any LLM/Wiro budget.
    try:
        cfg_row = sb.table("hype_account_config").select("executive_freeze")\
            .eq("account_id", account_id).limit(1).execute()
        first = (cfg_row.data or [None])[0]
        frozen = bool(first.get("executive_freeze")) if isinstance(first, dict) else False
        if frozen:
            logger.warning(f"[Runner] executive_freeze active for account={account_id}; skipping run")
            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                sb.table("hype_runs").insert({
                    "account_id": account_id,
                    "status": "executive_freeze",
                    "triggered_by": triggered_by,
                    "total_cost_usd": 0,
                    "error": "frozen by executive board",
                    "started_at": now_iso,
                    "completed_at": now_iso,
                    "dry_run": False,
                }).execute()
            except Exception as e:
                logger.warning(f"[Runner] freeze-skip hype_runs insert failed: {e}")
            return {
                "account_id": account_id,
                "run_id": None,
                "final_status": "executive_freeze",
                "trend_topic": None,
                "draft_preview": None,
                "dry_run": None,
            }
    except Exception as e:
        # Never crash the runner on a config-read error; just log and proceed.
        logger.warning(f"[Runner] executive_freeze check failed (continuing): {e}")

    # Gap #5 — Daily cost cap (pre-flight, before any LLM/Wiro spend)
    cap = _get_effective_cap(sb, account_id)
    if cap > 0:
        spent = _today_spend(sb, account_id)
        if spent >= cap:
            logger.warning(
                f"[Runner] cost cap reached account={account_id} "
                f"spent=${spent:.4f} cap=${cap:.2f}; skipping run"
            )
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                sb.table("hype_runs").insert({
                    "account_id": account_id,
                    "status": CAP_STATUS,
                    "triggered_by": triggered_by,
                    "total_cost_usd": 0,
                    "error": f"daily_cost_cap_exceeded: spent={spent:.4f} cap={cap:.2f}",
                    "started_at": now_iso,
                    "completed_at": now_iso,
                    "dry_run": False,
                }).execute()
            except Exception as e:
                logger.warning(f"[Runner] cap-skip hype_runs insert failed: {e}")
            return {
                "account_id": account_id,
                "run_id": None,
                "final_status": CAP_STATUS,
                "trend_topic": None,
                "draft_preview": None,
                "dry_run": None,
            }

    # ── Faz 1: LangGraph yolu (PER-ACCOUNT flag açıkken). CrewAI yolu AŞAĞIDA
    # byte-for-byte korunur; kapalı = bu blok atlanır (anında rollback).
    # effective_langgraph_enabled: hype_account_config.langgraph_enabled (DB-wins) →
    # NULL ise env HYPE_LANGGRAPH_ENABLED. flow publish'teki _lg_resume_safety AYNI
    # değeri okur → tutarlı (resume-safety kuplajı korunur).
    # Tüm pre-flight kontroller (cost-cap, executive_freeze, reaper) YUKARIDA çalıştı.
    from config import effective_langgraph_enabled
    if effective_langgraph_enabled(account_id):
        from lg.graph import run_or_resume, get_resumable_run_id
        logger.info(f"[Runner] LangGraph yolu account={account_id} triggered_by={triggered_by} cap=${cap:.2f}")
        final = None

        # Faz 2 — RESUME-vs-FRESH. Önce bu hesap için yarım-checkpoint'li
        # ('running' + .next dolu) bir prior run var mı bak. Varsa AYNI run_id
        # ile RESUME et (stable thread_id → checkpoint kaldığı yerden devam);
        # yoksa TAZE bir run_id mint edip fresh başlat.
        #
        # Reaper koordinasyonu: _reap_stuck_runs (yukarıda çağrıldı) yalnız
        # >2h 'running' satırları failed yapar. <2h + canlı-checkpoint'li bir
        # satır reap EDİLMEZ (cutoff dışında) → bu çağrıda resume edilir.
        # Saatlik timer bu sayede resume'u doğal sürer: her firing önce devam
        # eden işi tamamlar, sonra (yoksa) yenisini açar. Bir run gerçekten
        # >2h takılırsa reaper onu 'failed' yapar; o zaman resumable_id None
        # döner ve fresh başlanır (resume sonsuz döngüye girmez).
        resume_id = None
        try:
            resume_id = get_resumable_run_id(account_id)
        except Exception as _re:
            logger.warning(f"[Runner] resumable tespiti başarısız (fresh'e düşülüyor): {_re}")

        if resume_id:
            run_id = resume_id
            logger.info(f"[Runner] LangGraph RESUME account={account_id[:8]} run={run_id}")
        else:
            import uuid as _uuid
            run_id = _uuid.uuid4().hex
            logger.info(f"[Runner] LangGraph FRESH account={account_id[:8]} run={run_id}")

        try:
            final = run_or_resume(account_id, triggered_by=triggered_by, run_id=run_id)
        except Exception as e:
            logger.exception(f"[Runner] run_or_resume exception: {e}")
            try:
                from tools.alerter import send_alert
                send_alert(
                    f"LangGraph run hatayla düştü ({account_id[:8]})",
                    severity="CRITICAL",
                    reason=f"{type(e).__name__}: {str(e)[:300]}",
                    extra={"account_id": account_id},
                )
            except Exception:
                pass
        summary = {
            "account_id": account_id,
            "run_id": getattr(final, "run_id", None) if final else None,
            "final_status": getattr(final, "final_status", "") if final else "",
            "trend_topic": (final.trend.topic if final and getattr(final, "trend", None) else None),
            "draft_preview": (final.draft.content[:80] if final and getattr(final, "draft", None) else None),
            "dry_run": getattr(final, "dry_run", None) if final else None,
        }
        logger.info(f"[Runner] LangGraph complete: {summary}")
        return summary

    flow = AutonomousContentFlow()
    flow.state.account_id = account_id
    flow.state.triggered_by = triggered_by

    logger.info(f"[Runner] starting flow account={account_id} triggered_by={triggered_by} cap=${cap:.2f}")
    try:
        flow.kickoff()
    except Exception as e:
        logger.exception(f"[Runner] flow.kickoff exception: {e}")
        # 2026-06-10 (otonomi D0-2d, chaos drill bulgusu) — bu iç catch
        # hatayı yutup boş statülü summary döndürüyordu; loop-seviyesi
        # alarm hiç tetiklenmiyordu. Alert burada da atılır.
        try:
            from tools.alerter import send_alert
            send_alert(
                f"Flow kickoff hatayla düştü ({account_id[:8]})",
                severity="CRITICAL",
                reason=f"{type(e).__name__}: {str(e)[:300]}",
                extra={"account_id": account_id,
                       "run_id": getattr(flow.state, "run_id", "") or ""},
            )
        except Exception:
            pass
        # If flow finalize never ran, mark hype_runs row failed using flow.state.run_id
        # (no ContextVar needed — run_id is in flow state since init_run)
        try:
            run_id = flow.state.run_id
            if run_id:
                from tools.supabase_client import make_supabase
                sb = make_supabase()
                sb.table("hype_runs").update({
                    "status": "failed",
                    "error": f"{type(e).__name__}: {str(e)[:500]}",
                }).eq("id", run_id).execute()
        except Exception:
            pass

    summary = {
        "account_id": account_id,
        "run_id": flow.state.run_id,
        "final_status": flow.state.final_status,
        "trend_topic": flow.state.trend.topic if flow.state.trend else None,
        "draft_preview": (flow.state.draft.content[:80] if flow.state.draft else None),
        "dry_run": flow.state.dry_run,
    }
    logger.info(f"[Runner] flow complete: {summary}")
    return summary


_HYPE_CREW_HEAVY_DEPS = [
    # (module_name, requirement_name, why)
    ("gliner",                "gliner",                "faithfulness_gate T0 NER"),
    ("rapidfuzz",             "rapidfuzz",             "faithfulness_gate fuzzy match"),
    ("sentence_transformers", "sentence-transformers", "semantic_rescue (persona_gate L4)"),
    ("torch",                 "torch",                 "transformer backbone"),
    ("transformers",          "transformers",          "model load"),
    ("crewai",                "crewai",                "Flow framework"),
]


def _check_heavy_deps_or_die() -> None:
    """Boot-time guard for the hype-crew interpreter.

    Each entry in _HYPE_CREW_HEAVY_DEPS is a hard dependency for at
    least one served path. We try to import every one BEFORE the run
    starts; if any is missing, we exit non-zero with a clear message.
    This is the durable cure for the gate-ERROR pattern that left a
    stale process serving requests after a venv package install.
    """
    import importlib
    missing: list[tuple[str, str, str, str]] = []
    for mod, pkg, why in _HYPE_CREW_HEAVY_DEPS:
        try:
            importlib.import_module(mod)
        except Exception as e:
            missing.append((mod, pkg, why, f"{type(e).__name__}: {e}"))
    if missing:
        logger.error(
            f"[boot-guard] hype-crew venv missing {len(missing)} heavy dep(s); "
            "refusing to start. The cron will SKIP this firing rather than serve "
            "broken requests."
        )
        for mod, pkg, why, err in missing:
            logger.error(
                f"[boot-guard]   - {mod} (pip: {pkg}) — needed for {why} — {err}"
            )
        logger.error(
            "[boot-guard] Cure: source /opt/hype-crew/venv/bin/activate && "
            "pip install -r requirements.txt, then systemctl restart "
            "hype-crew.timer."
        )
        sys.exit(2)
    logger.info(
        f"[boot-guard] hype-crew venv OK — {len(_HYPE_CREW_HEAVY_DEPS)} heavy dep(s) importable"
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Hype Crew runner")
    parser.add_argument("--account", help="UUID of connected_accounts row; if omitted, runs for all configured accounts")
    parser.add_argument("--triggered-by", default="cron", choices=["cron", "manual", "webhook"])
    parser.add_argument("--mode", default="news", choices=["news", "cards-dry-day"],
                        help="news=normal haber akışı; cards-dry-day=kurak gün SÖZLÜK/SENCE? kartları")
    args = parser.parse_args(argv)

    _setup_logging()

    # Katman B — Phoenix tracing (PHOENIX_TRACING_ENABLED=1 ise; default OFF = no-op).
    # LLM client'larından ÖNCE çağrılmalı (auto-instrument patch'leri için). fail-open.
    try:
        from obs import init_tracing
        init_tracing()
    except Exception:  # noqa: BLE001 — gözlemlenebilirlik pipeline'ı asla bloklamaz
        pass

    # STAGE 3 boot-guard — fail LOUD if any heavy dep this venv must
    # carry is missing. Catches the install-without-restart class
    # (yesterday's gliner gap) BEFORE we hit a request that needs it.
    _check_heavy_deps_or_die()

    logger.info(f"[Runner] HYPE_DRY_RUN={settings.dry_run} model_smart={settings.model_smart} cost_cap=${settings.daily_cost_cap_usd}")

    if args.account:
        accounts = [{"account_id": args.account}]
    else:
        # 2026-06-10 (otonomi D0-2c) — bu çağrı korumasızdı: Supabase
        # erişim hatası tüm runner'ı düşürüp saati sessizce yutuyordu.
        try:
            accounts = get_eligible_accounts()
        except Exception as _ge:
            logger.exception(f"[Runner] get_eligible_accounts FAILED: {_ge}")
            try:
                from tools.alerter import send_alert
                send_alert(
                    "Runner hesap listesini alamadı — bu saatlik döngü boş geçiyor",
                    severity="CRITICAL",
                    reason=str(_ge)[:300],
                    action="Supabase erişimini kontrol et; Restart=on-failure 30sn sonra yeniden deneyecek",
                )
            except Exception:
                pass
            return 1  # non-zero → D0-1 Restart=on-failure 30sn sonra yeniden dener
        logger.info(f"[Runner] eligible accounts: {len(accounts)}")

    if not accounts:
        logger.warning("[Runner] no eligible accounts; exiting")
        return 0

    # --- Kurak-gün kart modu (SÖZLÜK/SENCE?) — haber akışından AYRI ---
    if args.mode == "cards-dry-day":
        import asyncio
        from tools.card_scheduler import has_recent_news, schedule_drought_cards
        total = 0
        for acc in accounts:
            aid = acc["account_id"]
            try:
                if has_recent_news(aid, hours=24):
                    logger.info(f"[cards] {aid[:8]} son 24s haber var → kurak DEĞİL, atla")
                    continue
                n = asyncio.run(schedule_drought_cards(aid, count=4, status="pending_review"))
                total += n
            except Exception as e:  # noqa: BLE001
                logger.exception(f"[cards] {aid[:8]} kurak job hata: {e}")
        logger.info(f"[cards] DONE — {total} kurak kart yazıldı")
        return 0

    results = []
    for acc in accounts:
        account_id = acc["account_id"]
        try:
            res = run_for_account(account_id, triggered_by=args.triggered_by)
            results.append(res)
        except Exception as e:
            # 2026-06-10 (otonomi D0-2b) — exception yutuluyordu: hesap
            # özetten kayboluyor, alert yoktu ("2/3 hesap işlendi" yanılgısı).
            # Artık başarısız hesap da özette + Slack'te görünür.
            logger.exception(f"[Runner] unexpected error for {account_id}: {e}")
            results.append({
                "account_id": account_id,
                "run_id": None,
                "final_status": f"runner_exception:{type(e).__name__}",
                "trend_topic": None,
                "draft_preview": None,
                "dry_run": None,
            })
            try:
                from tools.alerter import send_alert
                send_alert(
                    f"Hesap run'ı beklenmedik hatayla düştü ({account_id[:8]})",
                    severity="CRITICAL",
                    reason=f"{type(e).__name__}: {str(e)[:300]}",
                    extra={"account_id": account_id},
                )
            except Exception:
                pass

    # Summary
    logger.info(f"[Runner] DONE — {len(results)} accounts processed")
    for r in results:
        logger.info(f"  • {r['account_id'][:8]}... → {r['final_status']} (run={r['run_id'][:8] if r['run_id'] else 'n/a'})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
