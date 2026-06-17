"""STAGE D ön-koşulları B+C+D2 — flag-on öncesi son doğrulama kapıları.

YEREL-TEST/PROD-DOĞRULAMA amaçlı. Critic güvenlik guard'ları: her testte try/finally
cleanup; poison CRITICAL sonrası dedup TEMİZLE (gerçek poison alarmı 4h penceresinde
bastırılmasın); sentetik satırlar HARD DELETE.

B  — alert_synthetic_test() → Slack (INFO; alert kanalı ucu çalışıyor mu).
C  — poison-gate: sentetik resume_attempts=MAX+1 run → get_resumable_run_id None
     (poison atlanır) + _force_fail_poison_run → status=failed + CRITICAL Slack.
D2 — SCHEDULING orphan arm: >15dk eski postiz_post_id='SCHEDULING' satırı →
     _alert_stale_scheduling_orphans >=1 + CRITICAL Slack (flag-bağımsız rollback koruması).

Çalıştır (cron'u önce DURDUR — test kesinliği):
  cd /opt/hype-crew && set -a && . ./.env && set +a && \
  HYPE_LANGGRAPH_ENABLED=true ./venv/bin/python -m scripts.lg_stageD_preconds
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

DEDUP_FILE = "/var/tmp/hype_alert_dedup.json"
CANSU = "2b731bf7-8c24-40c5-8237-d348ee822d51"


def _clear_dedup():
    try:
        os.remove(DEDUP_FILE)
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001
        print(f"   [warn] dedup temizlenemedi: {e}")


def main() -> int:
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    results = {}

    # ── B — alert_synthetic_test → Slack (INFO) ─────────────────────────
    print("\n=== B — alert_synthetic_test (Slack INFO) ===")
    _clear_dedup()
    try:
        from tools.alerter import alert_synthetic_test
        d = alert_synthetic_test()
        slack_ok = bool(d.get("delivery", {}).get("slack"))
        print(f"   delivery={d.get('delivery')}")
        results["B_alert_slack"] = slack_ok
        print(f"   {'✅' if slack_ok else '❌'} Slack ucu {'çalışıyor' if slack_ok else 'ÇALIŞMIYOR'}")
    except Exception as e:  # noqa: BLE001
        results["B_alert_slack"] = False
        print(f"   ❌ B hata: {e}")

    # ── C — poison-gate (sentetik run, try/finally HARD DELETE) ─────────
    print("\n=== C — poison-gate (resume_attempts=MAX+1) ===")
    from lg.graph import get_resumable_run_id, _force_fail_poison_run, MAX_RESUME_ATTEMPTS
    rid = str(uuid.uuid4())
    c_ok = False
    try:
        sb.table("hype_runs").insert({
            "id": rid, "account_id": CANSU, "status": "running",
            "triggered_by": "manual", "dry_run": False,
            "resume_attempts": MAX_RESUME_ATTEMPTS + 1,
            # started_at default now() → reaper cutoff (<2h) dışı; finally siler.
        }).execute()
        got = get_resumable_run_id(CANSU)
        skip_ok = got is None
        print(f"   get_resumable_run_id={got} (None bekleniyor — poison atlanır): "
              f"{'✅' if skip_ok else '❌ poison resume adayı seçildi!'}")
        _force_fail_poison_run(rid, CANSU, MAX_RESUME_ATTEMPTS + 1)
        chk = sb.table("hype_runs").select("status").eq("id", rid).execute().data
        fail_ok = bool(chk) and chk[0].get("status") == "failed"
        print(f"   force_fail sonrası status={chk[0].get('status') if chk else '?'}: "
              f"{'✅' if fail_ok else '❌'}")
        c_ok = skip_ok and fail_ok
    except Exception as e:  # noqa: BLE001
        print(f"   ❌ C hata: {e}")
    finally:
        try:
            dd = sb.table("hype_runs").delete().eq("id", rid).execute()
            print(f"   [cleanup] hype_runs_deleted={len(dd.data or [])}")
        except Exception as e:  # noqa: BLE001
            print(f"   [cleanup][warn] poison run silinemedi {rid}: {e}")
        _clear_dedup()  # poison CRITICAL dedup'ı temizle (gerçek poison bastırılmasın)
    results["C_poison_gate"] = c_ok
    print(f"   {'✅' if c_ok else '❌'} poison-gate")

    # ── D2 — SCHEDULING orphan arm (sentetik stale satır, try/finally) ──
    print("\n=== D2 — SCHEDULING orphan arm (>15dk stale) ===")
    from scripts.lg_faz2_idem_testlib import lookup_account_user_id
    from runner import _alert_stale_scheduling_orphans
    did = str(uuid.uuid4())
    d2_ok = False
    _clear_dedup()
    try:
        old = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        sb.table("daily_drafts").insert({
            "id": did, "account_id": CANSU,
            "user_id": lookup_account_user_id(CANSU),
            "content": "stage-d SCHEDULING orphan test",
            "platform": "twitter", "status": "pending",
            "source": "hype_auto", "postiz_post_id": "SCHEDULING",
            "created_at": old,  # >15dk → stale
        }).execute()
        n = _alert_stale_scheduling_orphans(sb, CANSU)
        d2_ok = n >= 1
        print(f"   stale SCHEDULING orphan sayısı={n} (>=1 bekleniyor): {'✅' if d2_ok else '❌'}")
    except Exception as e:  # noqa: BLE001
        print(f"   ❌ D2 hata: {e}")
    finally:
        try:
            dd = sb.table("daily_drafts").delete().eq("id", did).execute()
            print(f"   [cleanup] daily_drafts_deleted={len(dd.data or [])}")
        except Exception as e:  # noqa: BLE001
            print(f"   [cleanup][warn] orphan draft silinemedi {did}: {e}")
        _clear_dedup()
    results["D2_scheduling_orphan"] = d2_ok

    # ── ÖZET ──
    print("\n" + "=" * 60)
    allok = all(results.values())
    for k, v in results.items():
        print(f"   {'✅' if v else '❌'} {k}")
    print(("✅ STAGE D ÖN-KOŞULLARI PASS — flag-on alert/poison/rollback kapıları hazır."
           if allok else "❌ STAGE D ÖN-KOŞUL FAIL — yukarıdaki ❌ düzeltilmeden flag-on YOK."))
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
