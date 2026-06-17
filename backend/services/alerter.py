"""Backend alerter — generic supply / health alerts.

twitter_trend_fetcher.py imports `from services.alerter import
alert_reconciliation_lifecycle` with a 4-positional call shape
(severity, category, summary, evidence) that does NOT match the
reconciler-specific helper in hype_crew/tools/alerter.py.

This module exposes that exact shape as `alert_supply(...)` AND a
backwards-compat `alert_reconciliation_lifecycle(...)` so the existing
import keeps working. Output:
  - journald via logging.critical (always; literal '[ALERT]' prefix
    keeps the `journalctl … grep ALERT` pattern working)
  - optional Slack incoming webhook if HYPE_ALERT_SLACK_WEBHOOK_URL set
"""
from __future__ import annotations

import json
import logging
import os
import socket
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import httpx  # already in venv
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


SEVERITY_LEVELS = {"INFO", "WARN", "CRITICAL"}


def _slack_emit(payload: dict, webhook_url: str) -> bool:
    if httpx is None:
        return False
    try:
        body = {"text": payload["title"], "blocks": [
            {"type": "section", "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{payload['severity']} — {payload['category']}*\n"
                    f"{payload['summary']}\n"
                    f"```{json.dumps(payload.get('evidence') or {}, indent=2, ensure_ascii=False)[:1500]}```"
                ),
            }},
        ]}
        with httpx.Client(timeout=8.0) as client:
            r = client.post(webhook_url, json=body)
            return 200 <= r.status_code < 300
    except Exception:
        return False


def alert_supply(
    severity: str,
    category: str,
    summary: str,
    evidence: Optional[dict] = None,
) -> dict:
    """Generic supply / health alert.

    Args:
        severity: "INFO" | "WARN" | "CRITICAL"
        category: short stable identifier (used for routing / dedup),
                  e.g. "trend_supply::config_failure::zero_active_rows"
        summary:  one-line human description
        evidence: optional dict of structured evidence

    Always emits a `[ALERT]` line to journald — the literal prefix keeps
    the existing `journalctl -u contentfactory | grep ALERT` pattern
    working. Best-effort: failure to deliver does not raise.
    """
    sev = severity if severity in SEVERITY_LEVELS else "WARN"
    payload = {
        "title": f"{sev}: {category}",
        "severity": sev,
        "category": category,
        "summary": summary,
        "evidence": evidence or {},
        "host": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log_line = (
        f"[ALERT] severity={sev} category={category} "
        f"summary={summary!r} evidence={json.dumps(payload['evidence'], ensure_ascii=False)[:600]}"
    )
    if sev == "CRITICAL":
        logger.critical(log_line)
    elif sev == "WARN":
        logger.warning(log_line)
    else:
        logger.info(log_line)

    webhook = (os.environ.get("HYPE_ALERT_SLACK_WEBHOOK_URL") or "").strip()
    delivered_slack = False
    if webhook:
        delivered_slack = _slack_emit(payload, webhook)
    return {
        "delivered_slack": delivered_slack,
        "delivered_journald": True,
        "payload": payload,
    }


# Back-compat: the old import path was
#   from services.alerter import alert_reconciliation_lifecycle
# with a 4-positional call shape. Twitter trend fetcher uses this. Map it
# to alert_supply so nothing breaks.
def alert_reconciliation_lifecycle(
    severity: str = "WARN",
    category: str = "unknown",
    summary: str = "",
    evidence: Optional[dict] = None,
    **_compat_kwargs: Any,
) -> dict:
    return alert_supply(
        severity=severity, category=category,
        summary=summary, evidence=evidence,
    )
