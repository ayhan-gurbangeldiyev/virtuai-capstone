"""Deploy drift check — fires CRITICAL alert when prod runs stale code.

PART 2.2 of the deploy-discipline stage. Catches both gaps that caused
today's ghost-red class:

  (a) commit-vs-deploy gap — git HEAD is ahead of prod's running md5
      for any critical file. FIX-1 sat in git for 3.5h before it was
      synced to /opt/hype-crew/flow.py; 4 cron crashes happened in
      that window.

  (b) install-vs-restart gap — a critical file changed on disk AFTER
      the service started. The yesterday-NER-install / today-stale-
      process pattern that produced 2 gate ERRORs.

Wired as a systemd timer (5 min) so a fresh drift surfaces quickly.

The check runs from the cron host (Hetzner) where it can see both
filesystems (/opt/contentfactory + /opt/hype-crew) AND the
hype-crew.service / contentfactory.service mtimes via systemctl.

Modes:
  --once             evaluate + fire alert if drift (default)
  --print-only       evaluate + print, no alert push (CI-safe / test mode)
  --synthetic        inject a synthetic drift, fire alert, exit
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

REPO_ROOT = "/opt/contentfactory"   # backend tree is HERE
HYPE_ROOT = "/opt/hype-crew"        # hype-crew tree mirror
MANIFEST_PATH = "/opt/contentfactory/.deployed_manifest.json"

# PART B (2026-06-07) — Drift baseline.
# Prod git tree is divergent from origin (its remote isn't reachable
# from the host). Comparing prod disk md5 vs prod git HEAD ALWAYS
# shows drift because git-tree-on-prod is stale. The right baseline
# is a deployed-manifest: at deploy time, we record the intended commit
# + per-file md5s. The drift check compares against THAT.
#
# If the manifest is missing, we fall back to the legacy
# prod-git-HEAD comparison so the check still surfaces obvious drift
# in fresh installs before the first deploy_manifest write.
SERVICES = {
    # service_name : (root, files belonging to it)
    "contentfactory": (REPO_ROOT, [
        "backend/routes/hype.py",
        "backend/server.py",
    ]),
    "hype-crew": (HYPE_ROOT, [
        "flow.py",
        "tools/alerter.py",
        "tools/video_pipeline.py",
        "tools/faithfulness_gate.py",
        "tools/persona_gate.py",
        "tools/pre_spend_guard.py",
    ]),
}


def _md5(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return None


def _git_head_md5(rel: str, *, cwd: str = REPO_ROOT) -> str | None:
    try:
        b = subprocess.check_output(
            ["git", "-C", cwd, "show", f"HEAD:{rel}"],
            stderr=subprocess.DEVNULL, timeout=3,
        )
        return hashlib.md5(b).hexdigest()
    except Exception:
        return None


def _service_start_epoch(svc: str) -> float | None:
    try:
        out = subprocess.check_output(
            ["systemctl", "show", svc, "--property=ActiveEnterTimestamp",
             "--value"], stderr=subprocess.DEVNULL, timeout=3,
        ).decode().strip()
        if not out or out == "0" or out == "n/a":
            return None
        # E.g. "Sun 2026-06-07 14:50:27 UTC"
        # systemd's --value output drops the day-of-week if not requested,
        # but historically includes it; parse robustly.
        for fmt in ("%a %Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S %Z",
                    "%Y-%m-%d %H:%M:%S UTC"):
            try:
                return datetime.strptime(out, fmt).timestamp()
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _load_manifest() -> dict | None:
    """Read the deployed-manifest baseline. Returns None if not present."""
    import json
    try:
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _rel_to_disk(rel: str) -> str:
    """Map a manifest-relative path to its on-disk location.

    backend/* under /opt/contentfactory.
    hype_crew/* under /opt/hype-crew (strip the leading prefix).
    """
    if rel.startswith("backend/"):
        return os.path.join(REPO_ROOT, rel)
    if rel.startswith("hype_crew/"):
        return os.path.join(HYPE_ROOT, rel[len("hype_crew/"):])
    return os.path.join(REPO_ROOT, rel)


def evaluate() -> dict:
    findings = {"services": {}, "drift_files": [], "stale_files": [],
                "errors": [], "baseline": "none"}

    # ── New baseline: deployed manifest ──
    manifest = _load_manifest()
    if manifest:
        findings["baseline"] = "deployed_manifest"
        findings["manifest_commit"] = manifest.get("commit")
        findings["manifest_deployed_at"] = manifest.get("deployed_at")
        for rel, expected_md5 in (manifest.get("critical_md5s") or {}).items():
            disk = _md5(_rel_to_disk(rel))
            if disk is None:
                findings["errors"].append(f"{rel} missing on disk (but in manifest)")
                continue
            if expected_md5 == "MISSING":
                # Manifest deployer also missed it — treat as warning, not drift.
                continue
            if disk != expected_md5:
                # Determine which service this file belongs to.
                svc = "hype-crew" if rel.startswith("hype_crew/") else "contentfactory"
                findings["drift_files"].append({
                    "service": svc, "file": rel,
                    "disk_md5": disk, "manifest_md5": expected_md5,
                    "baseline": "deployed_manifest",
                })
        # Capture service start times the same way as legacy
        for svc, (root, files) in SERVICES.items():
            svc_start = _service_start_epoch(svc)
            findings["services"][svc] = {
                "active_enter": (
                    datetime.fromtimestamp(svc_start, tz=timezone.utc).isoformat()
                    if svc_start else None
                ),
            }
            for rel in files:
                full = os.path.join(root, rel)
                if not os.path.exists(full):
                    continue
                if svc_start is not None:
                    try:
                        mtime = os.path.getmtime(full)
                        if mtime > svc_start:
                            findings["stale_files"].append({
                                "service": svc, "file": rel,
                                "file_mtime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                                "service_started_at": datetime.fromtimestamp(svc_start, tz=timezone.utc).isoformat(),
                            })
                    except Exception:
                        pass
        findings["clean"] = (
            not findings["drift_files"] and not findings["stale_files"]
            and not findings["errors"]
        )
        return findings

    # ── Legacy fallback: prod git HEAD comparison ──
    findings["baseline"] = "prod_git_head"
    for svc, (root, files) in SERVICES.items():
        svc_start = _service_start_epoch(svc)
        findings["services"][svc] = {
            "active_enter": (
                datetime.fromtimestamp(svc_start, tz=timezone.utc).isoformat()
                if svc_start else None
            ),
        }
        for rel in files:
            full = os.path.join(root, rel)
            md5_disk = _md5(full)
            if md5_disk is None:
                findings["errors"].append(f"{svc}:{rel} missing on disk")
                continue
            # git HEAD md5 — use the appropriate repo
            git_root = REPO_ROOT  # both backend + hype_crew live in same repo
            git_rel = rel if rel.startswith("backend/") else (
                f"hype_crew/{rel}" if not rel.startswith("hype_crew/") else rel
            )
            md5_head = _git_head_md5(git_rel, cwd=git_root)
            if md5_head and md5_disk != md5_head:
                findings["drift_files"].append({
                    "service": svc, "file": rel,
                    "disk_md5": md5_disk, "head_md5": md5_head,
                })
            # mtime newer than service start → install without restart
            if svc_start is not None:
                try:
                    mtime = os.path.getmtime(full)
                    if mtime > svc_start:
                        findings["stale_files"].append({
                            "service": svc, "file": rel,
                            "file_mtime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                            "service_started_at": datetime.fromtimestamp(svc_start, tz=timezone.utc).isoformat(),
                        })
                except Exception:
                    pass
    findings["clean"] = (
        not findings["drift_files"] and not findings["stale_files"]
        and not findings["errors"]
    )
    return findings


def fire_alert_if_dirty(findings: dict, *, dry: bool):
    if findings["clean"]:
        print("[deploy-drift] OK — prod == git HEAD, all services restarted "
              "after their file changes")
        return
    drift_n = len(findings["drift_files"])
    stale_n = len(findings["stale_files"])
    summary = []
    for f in findings["drift_files"]:
        summary.append(f"DRIFT {f['service']}:{f['file']} "
                       f"(disk={f['disk_md5'][:8]} head={f['head_md5'][:8]})")
    for f in findings["stale_files"]:
        summary.append(f"STALE {f['service']}:{f['file']} "
                       f"changed AFTER service start")
    print(f"[deploy-drift] {drift_n} drift + {stale_n} stale + "
          f"{len(findings['errors'])} errors")
    for s in summary:
        print(f"  {s}")
    if dry:
        print("[DRY] would fire CRITICAL alert")
        return
    sys.path.insert(0, "/opt/hype-crew")
    try:
        from tools.alerter import send_alert
        send_alert(
            title="Deploy drift detected",
            severity="CRITICAL",
            reason=(f"{drift_n} files drift from git HEAD; "
                    f"{stale_n} files newer than service start. "
                    f"Top: {summary[0] if summary else 'unknown'}"),
            action="Sync prod (git pull / scp) and restart the affected "
                   "service. Check /api/health and /api/version for the "
                   "running stamp.",
            extra={"drift_n": drift_n, "stale_n": stale_n,
                   "summary": summary[:5]},
        )
    except Exception as e:
        print(f"[deploy-drift] alerter import failed: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--print-only", action="store_true")
    ap.add_argument("--synthetic", action="store_true",
                    help="Inject a synthetic drift finding, fire alert")
    args = ap.parse_args()
    if args.synthetic:
        synth = {
            "clean": False,
            "services": {"hype-crew": {"active_enter": "(synthetic)"}},
            "drift_files": [{
                "service": "hype-crew", "file": "flow.py",
                "disk_md5": "00000000aaaaaaaa", "head_md5": "ffffffffbbbbbbbb",
            }],
            "stale_files": [{
                "service": "contentfactory",
                "file": "backend/routes/hype.py",
                "file_mtime": "2099-01-01T00:00:00+00:00",
                "service_started_at": "2026-06-07T14:50:27+00:00",
            }],
            "errors": [],
        }
        fire_alert_if_dirty(synth, dry=args.print_only)
        print(json.dumps(synth, indent=2))
        return 0

    findings = evaluate()
    fire_alert_if_dirty(findings, dry=args.print_only)
    if args.print_only:
        print(json.dumps(findings, indent=2))
    return 0 if findings["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
