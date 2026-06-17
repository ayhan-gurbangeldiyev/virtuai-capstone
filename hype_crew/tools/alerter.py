"""Phase E3 — minimum reliable alerting layer.

Channel ladder (first non-empty wins, with journald always also receiving):
  1. HYPE_ALERT_SLACK_WEBHOOK_URL   — Slack incoming webhook
  2. HYPE_ALERT_EMAIL_TO + HYPE_ALERT_SMTP_URL — basic SMTP fallback
  3. journald via loguru.logger.critical — always logs, machine-greppable
     with the literal prefix '[ALERT]'.

Used by:
  - runner.py failure-streak alarm (existing path, was log-only before E3)
  - reconcile_postiz_state observe-mode script when verdict != live
  - any future caller via `send_alert(...)`

Design notes:
  - No new dependencies. Uses httpx (already in venv) + stdlib smtplib.
  - Never raises. A failed alert must not crash the caller.
  - Output is structured (severity + platform + ids + reason + action)
    so a future Slack-app bridge can re-parse it.
"""
from __future__ import annotations

import json
import os
import smtplib
import socket
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional

from loguru import logger

try:
    import httpx  # already in venv
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


SEVERITY_LEVELS = ("INFO", "WARN", "CRITICAL")
DEFAULT_SEVERITY = "WARN"


@dataclass(frozen=True)
class Alert:
    """Structured alert payload. All fields optional except title."""

    title: str
    severity: str = DEFAULT_SEVERITY
    platform: Optional[str] = None
    draft_id: Optional[str] = None
    postiz_post_id: Optional[str] = None
    reason: Optional[str] = None
    action: Optional[str] = None  # recommended operator action
    extra: dict = field(default_factory=dict)
    source: str = "hype_crew"
    host: str = field(default_factory=socket.gethostname)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_text(self) -> str:
        """Single-line text form for journald + email subject."""
        bits = [f"[ALERT][{self.severity}]", self.title]
        if self.platform:
            bits.append(f"platform={self.platform}")
        if self.draft_id:
            bits.append(f"draft_id={self.draft_id[:36]}")
        if self.postiz_post_id:
            bits.append(f"postiz_post_id={self.postiz_post_id[:36]}")
        if self.reason:
            bits.append(f"reason='{(self.reason or '')[:120]}'")
        if self.action:
            bits.append(f"action='{(self.action or '')[:160]}'")
        return " | ".join(bits)

    def to_slack_blocks(self) -> dict:
        """Slack Block Kit payload — OPERATÖR DİLİNDE (2026-06-10, Berkay:
        "bildirimler anlaşılır olmalı"). Ham hata dökümü ana mesajda değil
        küçük teknik dipnotta; ana gövde: ne oldu / ne yapmalı."""
        emoji = {"CRITICAL": ":rotating_light:",
                 "WARN": ":warning:",
                 "INFO": ":information_source:"}.get(self.severity, ":bell:")
        sev_tr = {"CRITICAL": "KRİTİK", "WARN": "UYARI",
                  "INFO": "BİLGİ"}.get(self.severity, self.severity)
        header = f"{emoji} *{sev_tr}* — {self.title}"

        body_lines = []
        if self.action:
            body_lines.append(f"*Ne yapmalı:* {self.action}")
        ctx = []
        if self.platform:
            ctx.append(f"platform: {self.platform}")
        if self.draft_id:
            ctx.append(f"draft: `{str(self.draft_id)[:8]}`")
        if self.postiz_post_id:
            ctx.append(f"post: `{str(self.postiz_post_id)[:12]}`")
        if ctx:
            body_lines.append("*Bağlam:* " + " · ".join(ctx))

        blocks = [
            {"type": "section",
             "text": {"type": "mrkdwn", "text": header}},
        ]
        if body_lines:
            blocks.append({"type": "section",
                           "text": {"type": "mrkdwn", "text": "\n".join(body_lines)}})
        # Teknik detay — küçük, gri, katlanır algı: context bloğu
        tech_bits = []
        if self.reason:
            tech_bits.append(str(self.reason)[:280])
        try:
            ts_short = str(self.timestamp)[11:16] + " UTC"
        except Exception:
            ts_short = str(self.timestamp)
        tech_bits.append(f"{self.host} · {ts_short}")
        blocks.append({"type": "context",
                       "elements": [{"type": "mrkdwn",
                                     "text": " | ".join(tech_bits)[:600]}]})
        return {
            "text": f"{sev_tr}: {self.title}",  # bildirim önizlemesi
            "blocks": blocks,
        }


def _journald_emit(alert: Alert) -> None:
    """Always-on emission. Even when Slack/email succeed, we log so the
    operator can `journalctl | grep '\\[ALERT\\]'` for full history."""
    if alert.severity == "CRITICAL":
        logger.critical(alert.to_text())
    elif alert.severity == "WARN":
        logger.warning(alert.to_text())
    else:
        logger.info(alert.to_text())


def _slack_emit(alert: Alert, webhook_url: str) -> bool:
    if httpx is None:
        return False
    try:
        r = httpx.post(webhook_url, json=alert.to_slack_blocks(), timeout=10.0)
        ok = (200 <= r.status_code < 300)
        if not ok:
            logger.warning(f"[alerter] slack webhook returned {r.status_code}: {r.text[:160]}")
        return ok
    except Exception as e:
        logger.warning(f"[alerter] slack post failed: {type(e).__name__}: {str(e)[:160]}")
        return False


def _slack_dm_emit(alert: Alert, bot_token: str, user_id: str) -> bool:
    """DM a Slack user via chat.postMessage (bot token) — kanala değil
    doğrudan kişiye. Berkay (12 Haz 2026): bildirimler DM'e gelsin.
    Başarısızsa False (çağıran webhook'a düşer)."""
    if httpx is None:
        return False
    try:
        payload = dict(alert.to_slack_blocks())
        payload["channel"] = user_id  # user-id → IM (DM) olarak açılır
        payload.setdefault("text", alert.to_text()[:200])
        r = httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {bot_token}",
                     "Content-Type": "application/json; charset=utf-8"},
            json=payload, timeout=10.0,
        )
        data = r.json() if (200 <= r.status_code < 300) else {}
        ok = bool(data.get("ok"))
        if not ok:
            logger.warning(
                f"[alerter] slack DM failed: {r.status_code} "
                f"{str(data.get('error') or r.text[:160])}"
            )
        return ok
    except Exception as e:
        logger.warning(f"[alerter] slack DM post failed: {type(e).__name__}: {str(e)[:160]}")
        return False


def _email_emit(alert: Alert, to_addr: str, smtp_url: str) -> bool:
    """smtp_url shape: smtp://USER:PASS@HOST:PORT (or smtps:// for TLS).
    Kept deliberately minimal; production deployments can configure
    a transactional provider via this URL."""
    try:
        from urllib.parse import urlparse
        p = urlparse(smtp_url)
        msg = EmailMessage()
        msg["Subject"] = alert.to_text()[:240]
        msg["From"] = p.username or "hype-crew@localhost"
        msg["To"] = to_addr
        msg.set_content(json.dumps(alert.to_dict(), indent=2, default=str))
        klass = smtplib.SMTP_SSL if p.scheme == "smtps" else smtplib.SMTP
        with klass(p.hostname or "localhost", p.port or 587, timeout=15) as s:
            if p.scheme == "smtp":
                try:
                    s.starttls()
                except Exception:
                    pass
            if p.username:
                s.login(p.username, p.password or "")
            s.send_message(msg)
        return True
    except Exception as e:
        logger.warning(f"[alerter] email send failed: {type(e).__name__}: {str(e)[:160]}")
        return False


# ──────────────────────────────────────────────────────────────────────
# 2026-06-10 (Berkay: "bildirim yağmuru, sistem çöktü sanıyorum") —
# TEKRAR BASTIRMA. Aynı alarm (severity+başlık parmak izi) soğuma süresi
# içinde Slack/e-postaya İKİNCİ kez gitmez; journald'a her zaman yazılır
# (kayıt kaybolmaz). Saatlik timer'ların aynı durumu her saat yeniden
# bağırması (örn. "22 cron failed" × her saat) bu yüzden kesilir.
# INFO bastırılmaz: yayın bildirimleri her seferinde düşmeli.
_DEDUP_FILE = "/var/tmp/hype_alert_dedup.json"
_DEDUP_COOLDOWN_S = {"CRITICAL": 4 * 3600, "WARN": 12 * 3600}


def _dedup_should_send(severity: str, title: str) -> bool:
    if severity not in _DEDUP_COOLDOWN_S:
        return True
    import hashlib as _hl
    import time as _t
    fp = _hl.md5(f"{severity}|{title[:120]}".encode()).hexdigest()[:16]
    now = _t.time()
    state: dict = {}
    try:
        with open(_DEDUP_FILE) as f:
            state = json.load(f) or {}
    except Exception:
        state = {}
    last = float(state.get(fp) or 0)
    if now - last < _DEDUP_COOLDOWN_S[severity]:
        return False
    # kaydet + 7 günden eski girdileri buda
    state = {k: v for k, v in state.items() if now - float(v) < 7 * 86400}
    state[fp] = now
    try:
        with open(_DEDUP_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass
    return True


def send_alert(
    title: str,
    *,
    severity: str = DEFAULT_SEVERITY,
    platform: Optional[str] = None,
    draft_id: Optional[str] = None,
    postiz_post_id: Optional[str] = None,
    reason: Optional[str] = None,
    action: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Send an alert through the configured channels. Always logs to
    journald regardless of other channel success.

    Returns a dict describing which channels actually delivered, for
    audit/debug purposes. Never raises.
    """
    sev = severity if severity in SEVERITY_LEVELS else DEFAULT_SEVERITY
    alert = Alert(
        title=title[:240],
        severity=sev,
        platform=platform,
        draft_id=draft_id,
        postiz_post_id=postiz_post_id,
        reason=reason,
        action=action,
        extra=extra or {},
    )

    delivery = {"journald": False, "slack": False, "email": False}

    # Channel 3 (always-on) — journald
    try:
        _journald_emit(alert)
        delivery["journald"] = True
    except Exception as e:
        logger.warning(f"[alerter] journald emit failed: {e}")

    # Tekrar bastırma — journald'a HER ZAMAN yazıldı; Slack/e-posta yalnız
    # soğuma penceresi dışındaysa.
    if not _dedup_should_send(sev, title):
        logger.info(f"[alerter] tekrar bastırıldı (soğuma): {title[:80]}")
        return {"alert": alert.to_dict(),
                "delivery": {**delivery, "slack": "deduped", "email": "deduped"}}

    # Channel 1 — Slack. DM (bot token) TERCİH edilir; yoksa webhook (kanal).
    # Berkay (12 Haz 2026): "bana DM'den yazsın, kanala bağlanmak zorunda değil."
    bot_token = os.environ.get("HYPE_ALERT_SLACK_BOT_TOKEN")
    dm_user = os.environ.get("HYPE_ALERT_SLACK_DM_USER")
    slack_url = os.environ.get("HYPE_ALERT_SLACK_WEBHOOK_URL") or \
                os.environ.get("HYPE_QUALITY_AUDIT_SLACK_WEBHOOK_URL")
    if bot_token and dm_user:
        delivery["slack"] = _slack_dm_emit(alert, bot_token, dm_user)
        # DM başarısızsa webhook'a düş (varsa) — sessiz kalma
        if not delivery["slack"] and slack_url:
            delivery["slack"] = _slack_emit(alert, slack_url)
    elif slack_url:
        delivery["slack"] = _slack_emit(alert, slack_url)

    # Channel 2 — email fallback
    to_addr = os.environ.get("HYPE_ALERT_EMAIL_TO")
    smtp_url = os.environ.get("HYPE_ALERT_SMTP_URL")
    if to_addr and smtp_url:
        delivery["email"] = _email_emit(alert, to_addr, smtp_url)

    return {"alert": alert.to_dict(), "delivery": delivery}


# ─── Pre-built helpers for the canonical alert types ───────────────────


def alert_runner_failure_streak(account_id: str, streak: int) -> dict:
    return send_alert(
        title="Üst üste başarısız üretim turları",
        severity="CRITICAL",
        platform=None,
        reason=f"Son {streak} içerik turu peş peşe başarısız oldu — üretim hattı tıkanmış olabilir.",
        action="Sunucuda son 1 saatin hatasına bak: journalctl -u hype-crew --since '1 hour ago'. "
               "Wiro/yapay zeka servisi geçici çökmüşse beklenir, kendiliğinden düzelir; "
               "değilse son başarısız turu incele.",
        extra={"account_id": account_id, "streak": streak},
    )


def alert_reconciliation_anomaly(
    draft_id: str, postiz_post_id: str, platform: str, verdict: str,
    state: str, evidence: str | None = None,
) -> dict:
    severity = "CRITICAL" if verdict == "failed_silently" else "WARN"
    _verdict_tr = {
        "failed_silently": "yayınlandı sanıldı ama gerçekte gitmedi",
        "published_no_url": "yayınlandı ama linki gelmedi",
    }.get(verdict, verdict)
    return send_alert(
        title=f"Postiz yayın uyumsuzluğu — {_verdict_tr}",
        severity=severity,
        platform=platform,
        draft_id=draft_id,
        postiz_post_id=postiz_post_id,
        reason=(f"Bu gönderi {platform} için '{_verdict_tr}'. Postiz durumu: {state}."
                + (f" Kanıt: {evidence}" if evidence else "")),
        action=(f"Postiz panelinde bu gönderiyi aç. Gönderi orada hiç yoksa: ya bu "
                f"taslağı panelden sil ya da yayını yeniden tetikle. Instagram ise: "
                f"instagram entegrasyonunun sağlıklı olduğunu kontrol et."),
    )


def alert_reconciliation_lifecycle(
    *,
    severity: str,
    category: str,
    # Reconciler call shape — used by poll_engagement.py.
    draft_id: str | None = None,
    postiz_post_id: str | None = None,
    platform: str | None = None,
    state: str | None = None,
    late_hours: float | None = None,
    # Circuit-breaker / generic call shape — used by
    # shadow_circuit_breaker.py and any caller that doesn't have a single
    # draft_id but does have a one-line operator summary.
    # 2026-06-07 (FIX-4): added so the breaker stops silently TypeError'ing
    # every fire (the trip itself flipped the flag, but the alert never
    # reached Slack/journald with [ALERT] tag).
    summary: str | None = None,
    # `evidence` is shared by both call shapes — accept either a string
    # blurb (reconciler) or a structured dict (breaker).
    evidence: object | None = None,
) -> dict:
    """Lifecycle-aware reconciliation alert.

    Two call shapes:

      Reconciler (per-draft, Phase E1.1):
        alert_reconciliation_lifecycle(
            severity='WARN', category='queue_late_long',
            draft_id=..., postiz_post_id=..., platform=...,
            state='QUEUE', late_hours=3.4, evidence='…',
        )

      Circuit-breaker / generic (no single draft):
        alert_reconciliation_lifecycle(
            severity='CRITICAL',
            category='faithfulness::circuit_breaker::gate_errored',
            summary='Circuit breaker tripped … N accounts flipped.',
            evidence={errors_24h: 1, budget: 0},
        )

    `category` is one of:
      queue_late_short, queue_late_long, queue_stuck,
      error_terminal, published_no_url,
      faithfulness::circuit_breaker::<reason>,
      or any other dotted-namespace string.
    """
    action_by_category = {
        "queue_late_short": "Postiz'in ±2 saatlik kendi kendine düzeltme penceresinde. "
                            "Bir şey yapma; sistem kendi toplamalı.",
        "queue_late_long":  "Postiz'in kendi düzeltme aralığını aştı. Postiz panelini "
                            "kontrol et; hâlâ kuyruktaysa elle yeniden sıraya al.",
        "queue_stuck":      "Postiz kendi düzeltmesini geçti (>4 saat gecikme). Postiz "
                            "panelinden elle yeniden sıraya al ya da taslağı kapat.",
        "error_terminal":   "Postiz durumu HATA — artık tekrar denemez. Gönderiyi Postiz "
                            "panelinde incele; yeniden sıraya al ya da kapat.",
        "published_no_url": "Gönderi yayınlandı ama linki hâlâ boş. Muhtemelen Postiz "
                            "tarafında küçük bir aksaklık; panelden doğrula.",
    }
    _cat_tr = {
        "queue_late_short": "yayın biraz gecikti", "queue_late_long": "yayın çok gecikti",
        "queue_stuck": "yayın takıldı", "error_terminal": "yayın hata verdi",
        "published_no_url": "yayınlandı ama link yok",
    }.get(category, category)
    bits = []
    if state is not None:
        bits.append(f"Postiz durumu: {state}")
    if late_hours is not None:
        bits.append(f"gecikme: {late_hours:.1f} saat")
    if summary:
        bits.append(summary)
    if evidence:
        bits.append(f"kanıt: {evidence}")
    return send_alert(
        title=f"Postiz yayın sorunu — {_cat_tr}",
        severity=severity,
        platform=platform,
        draft_id=draft_id,
        postiz_post_id=postiz_post_id,
        reason=(". ".join(str(b) for b in bits) if bits else _cat_tr),
        action=action_by_category.get(category, "Postiz panelinden elle incele."),
        extra={"category": category, "late_hours": late_hours},
    )


def alert_quality_health_breach(
    *,
    severity: str,
    breach_key: str,
    summary: str,
    metric: str,
    value,
    threshold,
    extra: Optional[dict] = None,
) -> dict:
    """Push for a /quality-health threshold breach (PART 3).

    Fired by scripts/check_quality_thresholds.py on schedule. Title +
    reason line are operator-language; the metric path lets the
    operator jump straight to the right card on /control/health.
    """
    return send_alert(
        title=f"Kalite eşiği aşıldı — {breach_key}",
        severity=severity,
        reason=f"{summary} (ölçülen: {value}, eşik: {threshold})",
        action=(
            "/control/health sayfasını aç ve ilgili kartı genişlet, sorunlu "
            "satırları gör. Video bütünlüğü sorunuysa /regen-video tek taslağı "
            "düzeltir; cron hatasıysa sunucuda 'journalctl -u hype-crew' "
            "hatanın detayını gösterir."
        ),
        extra={"breach_key": breach_key, "metric": metric, **(extra or {})},
    )


def alert_quality_health_digest(*, summary: str, breach_count: int, top: list[dict]) -> dict:
    """Daily one-line digest. Always fires (severity INFO) so Berkay sees
    the system is alive even when nothing is broken."""
    bullets = "; ".join(
        f"{b.get('breach_key','?')}: {b.get('summary','?')[:80]}"
        for b in (top or [])[:3]
    ) or "no breaches"
    return send_alert(
        title="Günlük kalite özeti",
        severity="INFO" if breach_count == 0 else "WARN",
        reason=f"{summary} | başlıca: {bullets}",
        action="Tüm tabloyu /control/health sayfasında gör.",
        extra={"digest": True, "breach_count": breach_count},
    )


def alert_zero_publishes_in_window(window_hours: int, expected_min: int) -> dict:
    return send_alert(
        title="Pencerede hiç yayın çıkmadı",
        severity="CRITICAL",
        reason=f"Son {window_hours} saatte hiçbir gönderi yayınlanamadı "
               f"(en az {expected_min} beklenirdi). Üretim hattı durmuş olabilir.",
        action="Cron çalışıyor mu bak (systemctl status hype-crew.timer); son "
               "turlarda hata var mı diye hype_runs'a bak; Postiz bağlantısının "
               "sağlıklı olduğunu kontrol et.",
        extra={"window_hours": window_hours, "expected_min": expected_min},
    )


def alert_synthetic_test() -> dict:
    return send_alert(
        title="Alarm sistemi testi",
        severity="INFO",
        reason="Bu bir kendi kendine test — alarm kanalının çalıştığını gösterir.",
        action="Bir şey yapmana gerek yok. Bu mesajı görüyorsan alarmlar düzgün kurulu demektir.",
    )
