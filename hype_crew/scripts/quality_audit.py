"""Phase 43.D — Monthly Slack quality audit.

Runs on the 1st of each month at 09:00 UTC via systemd timer. For each
persona that has `auto_publish_enabled=true` on its primary
hype_account_config, this script:

  1. Picks 10 random auto_published posts from the past 30 days.
  2. Inserts a `pending_audits` row for each (rating='pending').
  3. Posts a single Slack message to the persona's
     `quality_audit_slack_webhook_url` (falls back to env
     HYPE_QUALITY_AUDIT_SLACK_WEBHOOK_URL) listing the picks with
     pass/fail action links pointing at the backend audit endpoint.

  The Slack message records its `ts` on the first pending_audits row so
  later rating callbacks can update the same thread.

The Critic-mandated freeze gate runs in a SEPARATE pass (handled by the
backend endpoint that records ratings — see Phase 43.D backend). Once
≥3 of the 10 audits come back 'fail', the endpoint flips
hype_account_config.auto_publish_enabled=false and notes the cause.

CLI:
    python -m scripts.quality_audit                        # run for all
    python -m scripts.quality_audit --dry-run              # log only
    python -m scripts.quality_audit --persona <id>         # single
    python -m scripts.quality_audit --force                # ignore last_quality_audit_at dedupe
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx

try:
    from tools.supabase_client import make_supabase
except Exception:  # pragma: no cover — package fallback
    from hype_crew.tools.supabase_client import make_supabase  # type: ignore

logger = logging.getLogger("quality-audit")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)


SAMPLE_SIZE = 10               # Berkay's chosen audit batch size
LOOKBACK_DAYS = 30
DEDUPE_DAYS = 25               # don't re-run if last audit was less than 25 days ago
PUBLIC_BASE_URL = os.environ.get(
    "HYPE_PUBLIC_BASE_URL", "https://api.typehype.io"
)


def _month_key(dt: Optional[datetime] = None) -> date:
    """Return the audit month key — first day of the calendar month."""
    dt = dt or datetime.now(timezone.utc)
    return date(dt.year, dt.month, 1)


def _build_slack_blocks(persona_slug: str, audit_month: date, picks: list[dict]) -> dict:
    """Compose the Slack message body. Single message per audit cycle."""
    header = f"🧪 *Aylık kalite denetimi* — {persona_slug} ({audit_month.isoformat()})"
    intro = (
        f"Geçen 30 günde otomatik yayınlanmış {len(picks)} post seçildi. "
        "Her birine *Pass* veya *Fail* ver. 3+ Fail gelirse "
        "`auto_publish_enabled=false` otomatik kapatılır."
    )
    block_list: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": intro}},
    ]
    for i, pick in enumerate(picks, start=1):
        draft_id = pick["draft_id"]
        audit_id = pick["audit_id"]
        topic = (pick.get("trend_topic") or "—")[:80]
        content_preview = (pick.get("content") or "")[:140]
        platform = pick.get("platform") or "?"
        line = (
            f"*#{i}* [{platform}] _{topic}_\n"
            f"> {content_preview}…\n"
            f"<{PUBLIC_BASE_URL}/api/hype/audits/{audit_id}/pass|✅ Pass> · "
            f"<{PUBLIC_BASE_URL}/api/hype/audits/{audit_id}/fail|❌ Fail> · "
            f"<{PUBLIC_BASE_URL}/api/hype/drafts/{draft_id}|🔗 draft>"
        )
        block_list.append({"type": "section", "text": {"type": "mrkdwn", "text": line}})
    return {"text": header, "blocks": block_list}


def _post_to_slack(webhook_url: str, payload: dict) -> Optional[str]:
    """POST to Slack webhook. Returns message ts on success, None otherwise."""
    try:
        r = httpx.post(webhook_url, json=payload, timeout=15.0)
        r.raise_for_status()
        # Webhook returns 'ok' as plain text; ts isn't exposed via webhook
        # responses (only via chat.postMessage). Caller may pass None.
        logger.info(f"[quality-audit] Slack post OK ({r.status_code})")
        return None
    except Exception as e:
        logger.exception(f"[quality-audit] Slack post failed: {e}")
        return None


def _audit_persona(
    sb,
    persona: dict,
    *,
    dry_run: bool,
    force: bool,
) -> dict:
    persona_id = persona["id"]
    slug = persona.get("slug") or persona_id
    audit_month = _month_key()

    # Dedupe: skip if we audited this persona <DEDUPE_DAYS ago.
    if not force and persona.get("last_quality_audit_at"):
        try:
            last_iso = persona["last_quality_audit_at"]
            last_dt = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - last_dt < timedelta(days=DEDUPE_DAYS):
                logger.info(
                    f"[{slug}] skip — last audit {last_iso} (<{DEDUPE_DAYS}d ago); "
                    "use --force to override"
                )
                return {"persona_id": persona_id, "skipped": "recent_audit"}
        except Exception:
            pass

    # Pre-condition: persona's primary account must have auto_publish_enabled.
    # Without that, there are no auto_published rows to audit.
    primary_account_id = persona.get("primary_account_id")
    if not primary_account_id:
        logger.info(f"[{slug}] skip — no primary_account_id")
        return {"persona_id": persona_id, "skipped": "no_primary_account"}

    cfg = (
        sb.table("hype_account_config")
        .select("auto_publish_enabled")
        .eq("account_id", primary_account_id)
        .limit(1)
        .execute()
    )
    if not cfg.data or not cfg.data[0].get("auto_publish_enabled"):
        logger.info(f"[{slug}] skip — auto_publish_enabled=false")
        return {"persona_id": persona_id, "skipped": "auto_publish_off"}

    # Pick auto_published candidates. Exclude rows already picked for
    # THIS audit_month (idempotency on retries).
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    candidates_q = (
        sb.table("daily_drafts")
        .select(
            "id, content, trend_topic, platform, postiz_post_id, "
            "scheduled_at, audit_picked_for_month"
        )
        .eq("persona_id", persona_id)
        .eq("auto_published", True)
        .gte("created_at", cutoff)
        .execute()
    )
    pool = [
        r for r in (candidates_q.data or [])
        if r.get("audit_picked_for_month") != audit_month.isoformat()
    ]
    if not pool:
        logger.warning(f"[{slug}] no auto_published drafts in {LOOKBACK_DAYS}d window")
        return {"persona_id": persona_id, "skipped": "empty_pool"}

    random.shuffle(pool)
    picks = pool[:SAMPLE_SIZE]

    # Insert pending_audits rows + mark drafts as picked.
    audit_ids: list[str] = []
    enriched: list[dict] = []
    if dry_run:
        for p in picks:
            audit_ids.append("dry_run")
            enriched.append({"draft_id": p["id"], "audit_id": "dry_run", **p})
    else:
        for p in picks:
            row = {
                "persona_id": persona_id,
                "draft_id": p["id"],
                "audit_month": audit_month.isoformat(),
                "rating": "pending",
            }
            try:
                ins = sb.table("pending_audits").insert(row).execute()
                if ins.data:
                    aid = ins.data[0]["id"]
                    audit_ids.append(aid)
                    enriched.append({"draft_id": p["id"], "audit_id": aid, **p})
            except Exception as e:
                logger.warning(f"[{slug}] pending_audits insert failed for {p['id']}: {e}")
            try:
                sb.table("daily_drafts").update({
                    "audit_picked_for_month": audit_month.isoformat(),
                    "quality_audit_pending": True,
                }).eq("id", p["id"]).execute()
            except Exception as e:
                logger.warning(f"[{slug}] draft pick-mark failed for {p['id']}: {e}")

    # Slack notify. Phase 43.E — when no webhook is set the audit is
    # consumed entirely through the dashboard at /dashboard/quality-audit,
    # so this is the EXPECTED no-op path, not a misconfiguration.
    webhook = (
        persona.get("quality_audit_slack_webhook_url")
        or os.environ.get("HYPE_QUALITY_AUDIT_SLACK_WEBHOOK_URL")
    )
    if not webhook:
        logger.info(
            f"[{slug}] slack disabled — dashboard-only mode "
            f"({len(audit_ids)} audits queued for /dashboard/quality-audit)"
        )
    elif dry_run:
        payload = _build_slack_blocks(slug, audit_month, enriched)
        logger.info(
            f"[{slug}] DRY RUN Slack payload:\n{json.dumps(payload, ensure_ascii=False, indent=2)[:1500]}"
        )
    else:
        payload = _build_slack_blocks(slug, audit_month, enriched)
        _post_to_slack(webhook, payload)

    # Bookmark the run on the persona so the dedupe guard triggers next month.
    if not dry_run:
        try:
            sb.table("personas").update({
                "last_quality_audit_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", persona_id).execute()
        except Exception as e:
            logger.warning(f"[{slug}] last_quality_audit_at update failed: {e}")

    return {
        "persona_id": persona_id,
        "slug": slug,
        "audit_month": audit_month.isoformat(),
        "picked": len(picks),
        "audit_ids": audit_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--persona", help="single persona id")
    parser.add_argument("--force", action="store_true",
                        help="bypass DEDUPE_DAYS guard")
    args = parser.parse_args()

    sb = make_supabase()
    q = (
        sb.table("personas")
        .select(
            "id, slug, primary_account_id, "
            "quality_audit_slack_webhook_url, last_quality_audit_at, is_active"
        )
        .eq("is_active", True)
    )
    if args.persona:
        q = q.eq("id", args.persona)
    personas = q.execute().data or []

    if not personas:
        logger.info("no active personas to audit")
        return 0

    for p in personas:
        try:
            _audit_persona(sb, p, dry_run=args.dry_run, force=args.force)
        except Exception as e:
            logger.exception(f"persona {p.get('slug')} audit failed: {e}")
    logger.info(
        f"quality audit pass complete: personas={len(personas)} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
