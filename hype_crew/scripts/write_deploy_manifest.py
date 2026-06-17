"""Write a deployed-manifest file recording what code is INTENDED to run
on prod right now.

Solves PART B: prod git tree is divergent from origin (its remote isn't
reachable), so comparing prod disk md5 vs prod git HEAD always shows
drift. The right baseline is: "at deploy time, the deployer recorded
the exact commit + per-file md5 they meant to deploy". Drift = current
prod disk != that recorded baseline.

Run this as the LAST step of a deploy:
  1. scp / git pull / whatever brings the files to prod
  2. python3 -m scripts.write_deploy_manifest    ← records what's deployed
  3. systemctl restart contentfactory hype-crew  ← picks up the manifest

The manifest at /opt/contentfactory/.deployed_manifest.json:
  {
    "commit":            "<sha>",
    "branch":            "main",
    "deployed_at":       "<ISO>",
    "deployer":          "<source>",
    "critical_md5s":     {<rel>: <md5>},
    "all_files_in_repo": <count, for sanity>
  }

The drift check (deploy_drift_check.py) reads this manifest. If a file
on disk doesn't match its manifest md5 → drift. If the manifest itself
is older than 7 days, that's a SOFT WARN ("deploy is stale").
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone

# Critical files we'll track in the manifest — same set as the drift
# check's targets. Keep both lists in sync.
CRITICAL = [
    "backend/routes/hype.py",
    "backend/server.py",
    "hype_crew/flow.py",
    "hype_crew/runner.py",
    "hype_crew/tools/alerter.py",
    "hype_crew/tools/video_pipeline.py",
    "hype_crew/tools/faithfulness_gate.py",
    "hype_crew/tools/persona_gate.py",
    "hype_crew/tools/pre_spend_guard.py",
    "hype_crew/scripts/smoke_test_flow.py",
    "hype_crew/scripts/deploy_drift_check.py",
    "hype_crew/scripts/check_quality_thresholds.py",
]

REPO_ROOT_DEFAULT = "/opt/contentfactory"
HYPE_ROOT_DEFAULT = "/opt/hype-crew"
MANIFEST_PATH = "/opt/contentfactory/.deployed_manifest.json"


def md5_file(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except FileNotFoundError:
        return None


def file_path_for(rel: str, repo_root: str, hype_root: str) -> str:
    """Map relative path to its actual prod location.

    backend/* lives under /opt/contentfactory.
    hype_crew/* lives under /opt/hype-crew (without the leading
    hype_crew/ prefix on prod).
    """
    if rel.startswith("backend/"):
        return os.path.join(repo_root, rel)
    if rel.startswith("hype_crew/"):
        # Strip the leading hype_crew/ because /opt/hype-crew IS that root
        return os.path.join(hype_root, rel[len("hype_crew/"):])
    return os.path.join(repo_root, rel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", default=None,
                    help="Explicit commit sha to record. If omitted, "
                         "uses the commit the LOCAL git tree at "
                         "--repo-root currently has checked out.")
    ap.add_argument("--repo-root", default=REPO_ROOT_DEFAULT)
    ap.add_argument("--hype-root", default=HYPE_ROOT_DEFAULT)
    ap.add_argument("--out", default=MANIFEST_PATH)
    ap.add_argument("--deployer", default=f"{os.environ.get('USER', 'unknown')}@{socket.gethostname()}")
    args = ap.parse_args()

    commit = args.commit
    if not commit:
        try:
            commit = subprocess.check_output(
                ["git", "-C", args.repo_root, "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL, timeout=3,
            ).decode().strip()
        except Exception:
            commit = "unknown"

    try:
        branch = subprocess.check_output(
            ["git", "-C", args.repo_root, "branch", "--show-current"],
            stderr=subprocess.DEVNULL, timeout=3,
        ).decode().strip()
    except Exception:
        branch = "unknown"

    md5s: dict[str, str] = {}
    missing: list[str] = []
    for rel in CRITICAL:
        path = file_path_for(rel, args.repo_root, args.hype_root)
        m = md5_file(path)
        if m is None:
            missing.append(rel)
            md5s[rel] = "MISSING"
        else:
            md5s[rel] = m

    manifest = {
        "schema_version": 1,
        "commit": commit,
        "branch": branch,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "deployer": args.deployer,
        "critical_md5s": md5s,
        "tracked_count": len(CRITICAL),
        "missing_count": len(missing),
    }
    with open(args.out, "w") as f:
        json.dump(manifest, f, indent=2)
    os.chmod(args.out, 0o644)

    print(f"[deploy-manifest] wrote {args.out}")
    print(f"  commit       = {commit}")
    print(f"  branch       = {branch}")
    print(f"  tracked      = {len(CRITICAL)} files")
    print(f"  missing      = {len(missing)}")
    if missing:
        for r in missing:
            print(f"    - {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
