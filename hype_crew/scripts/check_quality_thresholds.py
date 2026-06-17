"""Hourly threshold check + daily digest for /quality-health.

Computes the same payload the backend's GET /api/hype/quality-health
endpoint returns (locally — no HTTP), evaluates the threshold list,
and fires alerts through the existing alerter (Slack + journald).

Modes:
  --once          Hourly threshold check. Fires CRITICAL/WARN per breach.
                  Skips alerts when ALERT_DRY_RUN=true (used by tests).
  --digest        Daily summary push. Fires a single INFO/WARN line.
  --synthetic-breach KEY  Inject a fake breach (for the SEV-1-style proof
                          run; key must match a known breach key like
                          `any_failed_cron`). Cleans nothing — the script
                          just fires the alert and exits.

Env:
  ALERT_DRY_RUN=true   — eval thresholds + print payload, no alert push.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, "/opt/hype-crew")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Backend route — we import the helper functions, not run the FastAPI app.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend"))


def _build_payload() -> dict:
    """Re-implement the aggregation that GET /quality-health does, calling
    Supabase directly (so this can run from the cron without HTTP)."""
    import re
    from datetime import datetime, timezone, timedelta
    from supabase import create_client

    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY"),
    )

    HEYGEN_USD_PER_SEC = 0.10
    FORMULA_PATTERNS = [
        r"bence\s+as[ıi]l\s+olay",
        r"herkes\s+(?:bunu\s+)?(?:\S+\s+){0,8}?san[ıi]yor",
        r"ço[ğg]u\s+ki[şs]i\s+(?:bunu\s+)?(?:\S+\s+){0,8}?san[ıi]yor",
        r"as[ıi]l\s+olay\s+(?:bu|şu)",
        r"kimse\s+bunu\s+konu[şs]m[ıi]yor",
        r"as[ıi]l\s+mesele",
        r"ama\s+bence\s+as[ıi]l",
        r"ço[ğg]u\s+(?:insan|ki[şs]i)\s+(?:bunu\s+)?(?:\S+\s+){0,6}?(?:san[ıi]yor|d[üu][şs][üu]n[üu]yor)",
    ]

    def is_formulaic(c):
        if not c:
            return False
        head = c.strip().lower()[:300]
        return any(re.search(p, head) for p in FORMULA_PATTERNS)

    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)
    cutoff_3d = now - timedelta(days=3)

    accs = sb.table("connected_accounts").select("id").execute().data or []
    account_ids = [a["id"] for a in accs if a.get("id")]
    if not account_ids:
        account_ids = ["00000000-0000-0000-0000-000000000000"]

    drafts_24h = (
        sb.table("daily_drafts")
        .select(
            "id, status, platform, content, video_url, video_duration_s, "
            "video_integrity_ok, video_integrity_reason, account_id, created_at"
        )
        .in_("account_id", account_ids)
        .gte("created_at", cutoff_24h.isoformat())
        .execute()
    ).data or []
    drafts_active = (
        sb.table("daily_drafts")
        .select("id, status, account_id, created_at")
        .in_("account_id", account_ids)
        .in_("status", ["pending", "pending_review"])
        .execute()
    ).data or []
    drafts_archived = (
        sb.table("daily_drafts")
        .select("id, deleted_reason, deleted_at, account_id")
        .in_("account_id", account_ids)
        .eq("status", "archived_quality_sweep")
        .gte("deleted_at", cutoff_7d.isoformat())
        .execute()
    ).data or []

    produced_24h = len(drafts_24h)
    published_24h = sum(1 for d in drafts_24h if d.get("status") == "published")
    stuck_pending = sum(
        1 for d in drafts_24h if d.get("status") in ("pending", "pending_review")
    )

    video_drafts = [
        d for d in drafts_24h
        if d.get("video_url") and d.get("video_integrity_ok") is not None
    ]
    video_total = len(video_drafts)
    video_pass = sum(1 for d in video_drafts if d.get("video_integrity_ok") is True)
    video_fail_list = [
        {
            "draft_id": d["id"],
            "platform": d.get("platform"),
            "actual_s": float(d.get("video_duration_s") or 0),
            "reason": d.get("video_integrity_reason"),
        }
        for d in video_drafts if d.get("video_integrity_ok") is False
    ]
    video_pass_pct = (video_pass / video_total * 100.0) if video_total else 100.0

    formulaic_list = [
        {"draft_id": d["id"], "platform": d.get("platform"),
         "opener": (d.get("content") or "")[:120]}
        for d in drafts_24h if is_formulaic(d.get("content"))
    ]
    formulaic_pct = (len(formulaic_list) / produced_24h * 100.0) if produced_24h else 0.0

    gate_pass = gate_block = gate_error = 0
    try:
        verdicts = (
            sb.table("faithfulness_verdicts")
            .select("verdict, final_action, created_at")
            .gte("created_at", cutoff_24h.isoformat())
            .execute()
        ).data or []
        for v in verdicts:
            fa = (v.get("final_action") or "").lower()
            ver = (v.get("verdict") or "").lower()
            if fa == "error" or ver == "error":
                gate_error += 1
            elif fa == "block" or ver == "fail":
                gate_block += 1
            elif fa in ("pass", "publish") or ver == "pass":
                gate_pass += 1
    except Exception:
        pass

    heygen_today = sum(
        float(d.get("video_duration_s") or 0) * HEYGEN_USD_PER_SEC for d in video_drafts
    )
    heygen_waste = sum(
        float(d.get("video_duration_s") or 0) * HEYGEN_USD_PER_SEC
        for d in video_drafts if d.get("video_integrity_ok") is False
    )

    runs_24h = (
        sb.table("hype_runs")
        .select("id, status, total_cost_usd, started_at, error, account_id")
        .in_("account_id", account_ids)
        .gte("started_at", cutoff_24h.isoformat())
        .execute()
    ).data or []
    # 2026-06-12 (Berkay): executive_freeze / cost_cap satırlarının status'u
    # "failed" DEĞİL ama error alanı dolu ("frozen by executive board" /
    # "daily_cost_cap_exceeded") — eski "or r.get('error')" bunları failure
    # sayıp her saat YANLIŞ "48 cron failed" CRITICAL spam'i üretiyordu.
    # Kasıtlı-skip statüleri failure değildir; hariç tut.
    _BENIGN_RUN_STATUSES = {"executive_freeze", "cost_cap_exceeded"}
    failed_runs = [
        {"run_id": r["id"], "error": (r.get("error") or "")[:240],
         "started_at": r.get("started_at"), "account_id": r.get("account_id")}
        for r in runs_24h
        if r.get("status") not in _BENIGN_RUN_STATUSES
        and ((r.get("status") in ("failed", "error")) or r.get("error"))
    ]

    supply = {"ai_core": 0, "ai_news_tr": 0}
    try:
        feed = (
            sb.table("tweet_feed")
            .select("batch_type, tweet_created_at")
            .gte("tweet_created_at", cutoff_24h.isoformat())
            .in_("batch_type", list(supply.keys()))
            .execute()
        ).data or []
        for r in feed:
            b = r.get("batch_type")
            if b in supply:
                supply[b] += 1
    except Exception:
        pass

    stale_active = 0
    for d in drafts_active:
        c_at = d.get("created_at") or ""
        if not c_at:
            continue
        try:
            dt = datetime.fromisoformat(c_at.replace("Z", "+00:00"))
            if dt < cutoff_3d:
                stale_active += 1
        except Exception:
            pass

    return {
        "generated_at": now.isoformat(),
        "produced": {"produced_24h": produced_24h, "published_24h": published_24h,
                     "stuck_pending": stuck_pending},
        "video": {
            "total": video_total, "pass_count": video_pass,
            "fail_count": len(video_fail_list),
            "pass_pct": round(video_pass_pct, 1),
            "fail_list": video_fail_list[:20],
        },
        "text": {
            "produced_24h": produced_24h,
            "formulaic_count": len(formulaic_list),
            "formulaic_pct": round(formulaic_pct, 1),
            "flagged_list": formulaic_list[:20],
        },
        "gate": {"pass": gate_pass, "block": gate_block, "error": gate_error},
        "money": {
            "heygen_today_usd": round(heygen_today, 4),
            "heygen_wasted_usd": round(heygen_waste, 4),
        },
        "supply": {
            "batches_24h": supply,
            "supply_gap": [b for b, n in supply.items() if n == 0],
        },
        "cron": {
            "runs_24h": len(runs_24h),
            "failed_count": len(failed_runs),
            "failed_list": failed_runs[:10],
        },
        "queue": {
            "active_publishable": len(drafts_active),
            "archived_7d": len(drafts_archived),
            "stale_buildup": stale_active,
        },
    }


def _eval_breaches(payload):
    """Inlined copy of backend's evaluate_quality_thresholds(). Kept in sync
    by hand — both helpers operate on the same payload shape."""
    breaches = []
    v = payload.get("video", {})
    if v.get("total", 0) > 0 and (v.get("pass_pct") or 0) < 90:
        breaches.append({
            "key": "video_pass_pct_below_90", "severity": "WARN",
            "summary": f"Video integrity {v['pass_pct']}% < 90% — "
                       f"{v['fail_count']}/{v['total']} kesik",
            "metric": "video.pass_pct", "value": v.get("pass_pct"),
            "threshold": 90,
        })
    t = payload.get("text", {})
    if t.get("produced_24h", 0) > 0 and (t.get("formulaic_pct") or 0) > 10:
        breaches.append({
            "key": "formulaic_rate_above_10", "severity": "WARN",
            "summary": f"Formülaik açılış oranı %{t['formulaic_pct']} > %10 — "
                       f"{t['formulaic_count']}/{t['produced_24h']} metin",
            "metric": "text.formulaic_pct", "value": t.get("formulaic_pct"),
            "threshold": 10,
        })
    g = payload.get("gate", {})
    if (g.get("error") or 0) > 0:
        breaches.append({
            "key": "gate_error_above_0", "severity": "CRITICAL",
            "summary": f"Gate ERROR x{g['error']} — faithfulness pipeline patladı",
            "metric": "gate.error", "value": g.get("error"), "threshold": 0,
        })
    c = payload.get("cron", {})
    if (c.get("failed_count") or 0) > 0:
        first = (c.get("failed_list") or [{}])[0].get("error", "")[:120]
        breaches.append({
            "key": "any_failed_cron", "severity": "CRITICAL",
            "summary": f"{c['failed_count']} cron run failed — \"{first}\"",
            "metric": "cron.failed_count", "value": c.get("failed_count"),
            "threshold": 0,
        })
    m = payload.get("money", {})
    if (m.get("heygen_wasted_usd") or 0) > 5:
        breaches.append({
            "key": "heygen_waste_above_5usd", "severity": "WARN",
            "summary": f"HeyGen israfı ${m['heygen_wasted_usd']:.2f} > $5 — "
                       "kesik videolara harcanan para",
            "metric": "money.heygen_wasted_usd", "value": m.get("heygen_wasted_usd"),
            "threshold": 5,
        })
    p = payload.get("produced", {})
    if (p.get("produced_24h") or 0) == 0:
        breaches.append({
            "key": "zero_drafts_24h", "severity": "CRITICAL",
            "summary": "Son 24 saatte hiç taslak üretilmedi — pipeline durmuş olabilir",
            "metric": "produced.produced_24h", "value": 0, "threshold": 1,
        })
    s = payload.get("supply", {})
    for batch in s.get("supply_gap") or []:
        breaches.append({
            "key": f"supply_batch_zero_{batch}", "severity": "CRITICAL",
            "summary": f"Tedarik batch '{batch}' son 24 saatte 0 — "
                       "sebep boş kuyruk olabilir",
            "metric": f"supply.batches_24h.{batch}",
            "value": 0, "threshold": 1,
        })
    return breaches


def _fire_breach(b: dict, *, dry: bool):
    if dry:
        print(f"[DRY] would fire {b['severity']} {b['key']}: {b['summary']}")
        return
    from tools.alerter import alert_quality_health_breach
    alert_quality_health_breach(
        severity=b["severity"],
        breach_key=b["key"],
        summary=b["summary"],
        metric=b["metric"],
        value=b["value"],
        threshold=b["threshold"],
    )


def cmd_once(args):
    payload = _build_payload()
    breaches = _eval_breaches(payload)
    dry = os.environ.get("ALERT_DRY_RUN", "false").lower() == "true"
    print(json.dumps({"breach_count": len(breaches),
                      "breaches": breaches,
                      "alert_dry_run": dry}, indent=2, ensure_ascii=False))
    for b in breaches:
        _fire_breach(b, dry=dry)


def cmd_digest(args):
    payload = _build_payload()
    breaches = _eval_breaches(payload)
    produced = payload["produced"]["produced_24h"]
    video = payload["video"]
    money = payload["money"]
    summary = (
        f"24h: {produced} taslak, video {video['pass_count']}/{video['total']} tam, "
        f"HeyGen ${money['heygen_today_usd']:.2f} (${money['heygen_wasted_usd']:.2f} israf)"
    )
    print(json.dumps({"summary": summary, "breaches": breaches},
                     indent=2, ensure_ascii=False))
    dry = os.environ.get("ALERT_DRY_RUN", "false").lower() == "true"
    if dry:
        print("[DRY] would push digest")
        return
    from tools.alerter import alert_quality_health_digest
    alert_quality_health_digest(
        summary=summary,
        breach_count=len(breaches),
        top=breaches[:3],
    )


def cmd_synthetic_breach(args):
    """Fire one synthetic breach by key so we can confirm the alerter is
    actually pushing (used by PART 4 proof, then cleaned by hand)."""
    canned = {
        "any_failed_cron": {
            "key": "any_failed_cron", "severity": "CRITICAL",
            "summary": "1 cron run failed — \"SYNTHETIC: NameError: account_id not defined\"",
            "metric": "cron.failed_count", "value": 1, "threshold": 0,
        },
        "gate_error_above_0": {
            "key": "gate_error_above_0", "severity": "CRITICAL",
            "summary": "Gate ERROR x1 — SYNTHETIC test breach (faithfulness fake)",
            "metric": "gate.error", "value": 1, "threshold": 0,
        },
        "heygen_waste_above_5usd": {
            "key": "heygen_waste_above_5usd", "severity": "WARN",
            "summary": "HeyGen israfı $7.50 > $5 — SYNTHETIC test breach",
            "metric": "money.heygen_wasted_usd", "value": 7.5, "threshold": 5,
        },
    }
    b = canned.get(args.synthetic_breach)
    if not b:
        print(f"unknown synthetic breach key: {args.synthetic_breach}")
        sys.exit(2)
    print(f"firing SYNTHETIC breach: {b['key']} (severity={b['severity']})")
    dry = os.environ.get("ALERT_DRY_RUN", "false").lower() == "true"
    _fire_breach(b, dry=dry)
    print("DONE — operator should see one alert with [SYNTHETIC] in the summary")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true",
                   help="Hourly threshold check (default).")
    p.add_argument("--digest", action="store_true",
                   help="Daily digest push.")
    p.add_argument("--synthetic-breach", default=None,
                   help="Fire one synthetic breach by key.")
    args = p.parse_args()
    if args.synthetic_breach:
        cmd_synthetic_breach(args)
    elif args.digest:
        cmd_digest(args)
    else:
        cmd_once(args)


if __name__ == "__main__":
    main()
