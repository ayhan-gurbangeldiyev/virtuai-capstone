"""G4 — advisory lock under REAL concurrency.

Two concurrent run_or_resume-style attempts on the SAME thread_id. Exactly one
must acquire pg_try_advisory_lock and proceed; the other must observe BUSY and
return WITHOUT invoking the graph.

We exercise the REAL _advisory_lock context manager from lg/graph.py (no copy)
against the REAL session pooler (port 5432). To make the race deterministic and
to PROVE the loser does not invoke, we use a barrier: thread A acquires the lock
and HOLDS it inside the critical section (sleep) while thread B attempts the same
lock. B must get acquired=False.

We also assert exactly-one-invoke semantics by mirroring run_or_resume's guard:
each worker only "invokes" (increments a shared counter) when acquired=True.

Port check: confirms checkpoint URL is on 5432 (SESSION pooler) — advisory locks
are unreliable on the 6543 transaction pooler.

NO graph invoke, NO posting, NO DB writes (advisory locks are session-scoped and
auto-released on disconnect; nothing to clean up). Uses a unique synthetic
thread_id so it never collides with a real run.

Run:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_gate_g4_advlock
"""
from __future__ import annotations

import os
import threading
import time
import uuid


def main() -> int:
    from lg.graph import _advisory_lock

    failures: list[str] = []

    # ── Port check — must be 5432 (session pooler) ──
    url = os.environ.get("HYPE_CHECKPOINT_DB_URL", "")
    port = None
    try:
        port = url.split("@", 1)[1].split("/", 1)[0].rsplit(":", 1)[1]
    except Exception:
        pass
    print(f"[G4] checkpoint pooler port observed: {port}")
    if port != "5432":
        failures.append(
            f"checkpoint URL port={port} — advisory locks need SESSION pooler "
            f"5432 (6543 transaction pooler is unreliable for session locks)"
        )

    thread_id = f"g4-advlock-{uuid.uuid4().hex}"

    results: dict[str, dict] = {}
    invoke_counter = {"n": 0}
    counter_lock = threading.Lock()
    a_acquired_evt = threading.Event()

    def _worker(name: str, hold: bool):
        with _advisory_lock(thread_id) as acquired:
            results[name] = {"acquired": bool(acquired)}
            if acquired:
                # mirror run_or_resume: only the holder "invokes"
                with counter_lock:
                    invoke_counter["n"] += 1
                if hold:
                    # signal that A is inside the critical section, then HOLD
                    a_acquired_evt.set()
                    time.sleep(2.0)  # keep lock so B's attempt overlaps
            else:
                # BUSY path — must NOT invoke (counter untouched)
                pass

    # Thread A acquires + holds; thread B starts only after A is confirmed inside.
    ta = threading.Thread(target=_worker, args=("A", True), daemon=True)
    ta.start()
    got = a_acquired_evt.wait(timeout=10)
    if not got:
        failures.append("worker A never entered critical section (lock acquire failed?)")

    tb = threading.Thread(target=_worker, args=("B", False), daemon=True)
    tb.start()
    tb.join(timeout=10)
    ta.join(timeout=10)

    a = results.get("A", {})
    b = results.get("B", {})
    print(f"[G4] A acquired={a.get('acquired')}  B acquired={b.get('acquired')}")
    print(f"[G4] invoke_counter (only holder may invoke) = {invoke_counter['n']}")

    # Exactly one acquired
    n_acquired = sum(1 for r in (a, b) if r.get("acquired"))
    if n_acquired != 1:
        failures.append(
            f"expected exactly 1 lock holder, got {n_acquired} "
            f"(A={a.get('acquired')}, B={b.get('acquired')})"
        )
    if not a.get("acquired"):
        failures.append("A (the holder) did not acquire the lock")
    if b.get("acquired"):
        failures.append("B acquired the lock while A held it — advisory lock NOT serializing")
    if invoke_counter["n"] != 1:
        failures.append(
            f"invoke_counter={invoke_counter['n']} — exactly-one-invoke violated "
            f"(BUSY loser must NOT invoke)"
        )

    # ── Confirm lock is session-scoped (separate conn) — after both released,
    # a 3rd attempt should re-acquire cleanly (proves unlock on disconnect). ──
    with _advisory_lock(thread_id) as third:
        re_acq = bool(third)
    print(f"[G4] post-release re-acquire (session-scoped unlock works): {re_acq}")
    if not re_acq:
        failures.append("could not re-acquire after release — lock not properly freed")

    ok = not failures
    print("\n" + "=" * 64)
    if ok:
        print("✅ G4 PASS — exactly one concurrent attempt acquired the advisory "
              "lock + invoked; the other observed BUSY and did NOT invoke. "
              "Lock on SESSION pooler 5432, session-scoped, freed on release.")
    else:
        print("❌ G4 FAIL:")
        for f in failures:
            print("   -", f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
