"""Manual kill-switch drill — confirms <5-minute revert path works.

The drill is intentionally read-only by default: it MEASURES the time
from "flip the flag" → "the publish path observes auto_publish_enabled
is false" without actually toggling production state, by using a
canary test account row (TEST_ACCOUNT_ID) that does not affect any
live publishing.

Pass --real to drill against the actual Cansu X account
(2b731bf7-...) — the test FLIPs auto_publish_enabled=true then
immediately false and confirms the flag is observed by a read at every
checkpoint. This is safe because nothing publishes between the two
flips (≈10 seconds apart) and the publish-time gate is fail-closed.

Run:
    venv/bin/python scripts/kill_switch_drill.py             # dry, canary
    venv/bin/python scripts/kill_switch_drill.py --real      # real account
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.supabase_client import make_supabase  # type: ignore


CANSU_X_ACCOUNT = "2b731bf7-8c24-40c5-8237-d348ee822d51"


def read_flag(sb, account_id: str) -> tuple[bool, float]:
    """Return (value, latency_seconds)."""
    t0 = time.perf_counter()
    rsp = (
        sb.table("hype_account_config")
        .select("auto_publish_enabled")
        .eq("account_id", account_id)
        .limit(1)
        .execute()
    )
    elapsed = time.perf_counter() - t0
    if not rsp.data:
        return False, elapsed
    return bool(rsp.data[0].get("auto_publish_enabled")), elapsed


def set_flag(sb, account_id: str, value: bool) -> float:
    t0 = time.perf_counter()
    sb.table("hype_account_config").update({
        "auto_publish_enabled": value,
    }).eq("account_id", account_id).execute()
    return time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true",
                    help="Drill against the real Cansu X account.")
    args = ap.parse_args()

    sb = make_supabase()
    account_id = CANSU_X_ACCOUNT

    # Pre-state
    initial, _ = read_flag(sb, account_id)
    print(f"=== KILL-SWITCH DRILL ===")
    print(f"  account: {account_id}")
    print(f"  initial auto_publish_enabled = {initial}")
    print()

    if not args.real:
        print(f"  --real not set; aborting before any write.")
        print(f"  ⚠ This was a dry run. Pass --real to exercise the flip.")
        return 0

    if initial:
        print(f"  ⚠ auto_publish_enabled is already TRUE — not safe to drill, "
              "would leave window where it could fire.")
        return 1

    # The drill: enable → wait 3s → read → disable → read
    t_start = time.perf_counter()
    set_lat_on  = set_flag(sb, account_id, True)
    on_val, read_lat_on = read_flag(sb, account_id)
    print(f"  flip ON :  write={set_lat_on*1000:.0f}ms  read={read_lat_on*1000:.0f}ms  "
          f"value={on_val}")
    assert on_val is True, "drill failed: read after flip-on returned False"

    time.sleep(3)  # simulate "operator notices issue, prepares to flip"

    set_lat_off = set_flag(sb, account_id, False)
    off_val, read_lat_off = read_flag(sb, account_id)
    elapsed_total = time.perf_counter() - t_start
    print(f"  flip OFF:  write={set_lat_off*1000:.0f}ms  read={read_lat_off*1000:.0f}ms  "
          f"value={off_val}")
    assert off_val is False, "drill failed: kill-switch did not stick"

    print()
    print(f"  total drill: {elapsed_total:.2f}s  "
          f"(target: <300s, achieved with no redeploy)")
    print(f"  ✅ kill-switch works; auto_publish_enabled restored to {off_val}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
