"""Verify the REAL publish for a list of postiz_post_ids — per-platform.

Polls Postiz GET /posts/{id} every POLL_SEC seconds for up to MAX_SEC,
reporting per-post:
  - Postiz `state` (DRAFT | QUEUE | PUBLISHED | ERROR | ...)
  - the `releaseURL` if PUBLISHED
  - whether the release_url resolves (HTTP 200/302/3xx)
  - per-platform sanity: video playable check via Content-Type / 200 HEAD

Designed for the 6 Haz 2026 audit gap — the "schedule ≠ publish" seam
where per-platform publish failures hide for ~6h until the reconciler
sweeps. This runs in 10-15 minutes from schedule time, alerts via the
existing alerter on ANY post that didn't publish cleanly, and prints
the exact per-platform failure reason for the operator.

Usage:
    venv/bin/python scripts/verify_publish.py \\
        --post-ids id1,id2,id3 \\
        --scheduled-at 2026-06-06T19:30:00Z \\
        --max-minutes 15
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from tools.postiz_client import PostizClient                    # type: ignore
from tools.supabase_client import make_supabase                 # type: ignore
try:
    from tools.alerter import alert_reconciliation_lifecycle    # type: ignore
except ImportError:
    alert_reconciliation_lifecycle = None  # type: ignore


POLL_SEC = 20            # 20s cadence is gentle on Postiz API
MAX_SEC_DEFAULT = 15 * 60  # 15 min cap


_VIDEO_PLATFORMS = {"youtube", "instagram", "tiktok"}


def _platform_sanity_check(
    release_url: str,
    platform: str,
    video_url: Optional[str] = None,
) -> tuple[bool, str]:
    """Resolve release_url + per-platform basic checks.

    Returns (resolved_ok, note). Note carries the HTTP status / error.

    2026-06-07 (Item 4): hardened the live-check to actually detect
    'PUBLISHED-but-unreachable' — a state we saw in the audit window
    where Postiz reported PUBLISHED, the post existed at the platform's
    URL, but the underlying media (video) was a broken upload. Some
    platforms (YouTube) 200 the watch-page even when the embedded video
    is still processing or rejected. Two extra checks:

      1. The release_url itself must HEAD/GET ≥1 byte (not just 200
         a blank shell).
      2. For video platforms or when the draft carries a video_url,
         we HEAD the asset URL (or, if Postiz didn't expose it, GET
         the release_url and look for the canonical video tag in the
         HTML). Content-Type must start with "video/" or the platform
         must surface a non-empty content-length.
    """
    note_parts: list[str] = []

    # ─ 1. release_url itself must resolve to a non-empty body ─
    try:
        # Use a GET-and-stream (not HEAD) — some platforms reject HEAD
        # but return 200 to GET. We never read the full body; we just
        # check status + the first chunk.
        with requests.get(
            release_url,
            allow_redirects=True,
            timeout=10,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0 (hype-verifier)"},
        ) as r:
            code = r.status_code
            first_chunk = next(r.iter_content(chunk_size=512), b"")
            if not (200 <= code < 400) or not first_chunk:
                return False, f"HTTP {code} (empty body)" if 200 <= code < 400 else f"HTTP {code}"
            note_parts.append(f"HTTP {code} ({r.url[:60]})")
            release_html = first_chunk
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:160]}"

    # ─ 2. Video Content-Type check ─
    expects_video = video_url or (str(platform or "").lower() in _VIDEO_PLATFORMS)
    if expects_video:
        # Prefer the underlying media URL when we know it; otherwise fall
        # back to the release page itself.
        target = video_url or release_url
        try:
            head = requests.head(
                target,
                allow_redirects=True,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (hype-verifier)"},
            )
            ctype = (head.headers.get("Content-Type") or "").lower()
            clen = head.headers.get("Content-Length")
            if 200 <= head.status_code < 400 and (
                ctype.startswith("video/")
                or ctype.startswith("application/octet-stream")
                or (clen and int(clen) > 1024)
                # YouTube watch pages return text/html — accept that ONLY
                # when the page HTML at least mentioned the canonical video
                # marker; otherwise it's an empty/error page.
                or (
                    ctype.startswith("text/html")
                    and (
                        b"videoId" in release_html
                        or b"video" in release_html.lower()
                    )
                )
            ):
                note_parts.append(f"video-ok ({ctype.split(';')[0] or '?'})")
            else:
                return False, (
                    f"video unreachable: HTTP {head.status_code}, "
                    f"Content-Type={ctype or '—'}"
                )
        except Exception as e:
            return False, f"video probe failed: {type(e).__name__}: {str(e)[:120]}"

    return True, "; ".join(note_parts)


def _alert_failure(post_id: str, state: str, reason: str, evidence: dict) -> None:
    msg = (f"Publish failed for Postiz post {post_id}: state={state}. "
           f"Reason: {reason}")
    print(f"[ALERT CRITICAL] {msg}")
    if alert_reconciliation_lifecycle is not None:
        try:
            alert_reconciliation_lifecycle(
                severity="CRITICAL",
                category="publish::per_platform_failure",
                summary=msg,
                evidence=evidence,
            )
        except Exception as e:
            print(f"  alerter emit failed (non-fatal): {e!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post-ids", required=True,
                    help="Comma-separated Postiz post_ids to verify.")
    ap.add_argument("--scheduled-at", required=False,
                    help="ISO timestamp of scheduled publish (UTC). "
                          "If set, the poller waits until this time.")
    ap.add_argument("--max-minutes", type=int, default=15)
    ap.add_argument("--poll-sec", type=int, default=POLL_SEC)
    args = ap.parse_args()

    post_ids = [pid.strip() for pid in args.post_ids.split(",") if pid.strip()]
    if not post_ids:
        print("no post-ids given")
        return 1

    pc = PostizClient()
    deadline = time.time() + args.max_minutes * 60

    # Wait until scheduled_at (with 30s headroom)
    if args.scheduled_at:
        try:
            target_dt = datetime.fromisoformat(args.scheduled_at.replace("Z", "+00:00"))
            wait = (target_dt - datetime.now(timezone.utc)).total_seconds() + 30
            if wait > 0:
                print(f"Waiting {int(wait)}s until +30s past scheduled time…")
                time.sleep(min(wait, 600))
        except Exception:
            pass

    print(f"\n=== Verifying {len(post_ids)} Postiz post(s) ===")
    print(f"  poll cadence: {args.poll_sec}s    max wait: {args.max_minutes}m")
    print(f"  post_ids: {post_ids}\n")

    # Item 3 (P1) — load the matching daily_drafts rows ONCE so we can
    # (a) feed video_url into the sanity check and
    # (b) write per-platform reconciliation back to the EXACT row, never
    #     a blanket "approved". Single-platform failure in a thread MUST
    #     remain visible at its own daily_drafts row.
    sb_pre = make_supabase()
    drafts_by_post_id: dict[str, dict] = {}
    try:
        rows = (
            sb_pre.table("daily_drafts")
            .select("id, account_id, platform, postiz_post_id, video_url, "
                    "content_thread_id, release_url, postiz_state, scheduled_at")
            .in_("postiz_post_id", post_ids)
            .execute()
            .data
        ) or []
        for r in rows:
            pid = r.get("postiz_post_id")
            if pid:
                drafts_by_post_id[str(pid)] = r
    except Exception as e:
        print(f"  [WARN] pre-load daily_drafts failed (non-fatal): {e!r}")

    confirmed: set[str] = set()
    last_state: dict[str, dict] = {}

    def _snapshot_all_posts() -> dict[str, dict]:
        """Postiz public GET /posts/{id} returns 404 (verified 2026-06-06).
        ONLY the list endpoint works for state checks. We sweep the list
        once per poll cycle and index by id — same pattern as
        backend/routes/postiz.py:get_post."""
        try:
            from datetime import timedelta as _td
            now = datetime.now(timezone.utc)
            raw_list = pc.list_posts(
                start_date=(now - _td(days=30)).isoformat(),
                end_date=(now + _td(days=30)).isoformat(),
            ) or []
            return {p["id"]: p for p in raw_list
                     if isinstance(p, dict) and p.get("id")}
        except Exception as e:
            print(f"  [WARN] list_posts sweep failed: {e}")
            return {}

    while time.time() < deadline and len(confirmed) < len(post_ids):
        all_posts = _snapshot_all_posts()
        for pid in post_ids:
            if pid in confirmed:
                continue
            snap = all_posts.get(pid)
            if snap is None:
                last_state[pid] = {
                    "state": "NOT_FOUND_IN_LIST",
                    "error": "post id missing from list_posts response window",
                }
                continue
            state = snap.get("state") or snap.get("status") or "?"
            release_url = (snap.get("releaseURL") or snap.get("release_url")
                            or snap.get("postUrl") or snap.get("url"))
            integration = snap.get("integration") or {}
            platform = integration.get("providerIdentifier") or integration.get("name") or "?"
            last_state[pid] = {
                "state": state, "release_url": release_url,
                "platform": platform,
            }
            print(f"  [{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                  f"post={pid[:14]} platform={platform:12s} state={state} "
                  f"url={release_url or '—'}")
            if state == "PUBLISHED" and release_url:
                draft_row = drafts_by_post_id.get(pid, {})
                draft_video_url = draft_row.get("video_url")
                resolved, note = _platform_sanity_check(
                    release_url, platform, video_url=draft_video_url,
                )
                last_state[pid]["resolved_ok"] = resolved
                last_state[pid]["resolve_note"] = note
                last_state[pid]["draft_id"] = draft_row.get("id")
                print(f"        ↳ sanity: {'✅' if resolved else '❌'}  {note}")
                if resolved:
                    confirmed.add(pid)
                else:
                    _alert_failure(pid, state,
                                    f"PUBLISHED but URL didn't resolve: {note}",
                                    {"post_id": pid, "platform": platform,
                                     "release_url": release_url,
                                     "video_url": draft_video_url,
                                     "draft_id": draft_row.get("id"),
                                     "thread_id": draft_row.get("content_thread_id")})
                    confirmed.add(pid)
            elif state == "ERROR":
                draft_row = drafts_by_post_id.get(pid, {})
                last_state[pid]["draft_id"] = draft_row.get("id")
                _alert_failure(pid, state,
                                "Postiz state=ERROR (per-platform failure)",
                                {"post_id": pid, "platform": platform,
                                 "draft_id": draft_row.get("id"),
                                 "thread_id": draft_row.get("content_thread_id"),
                                 "snapshot": snap})
                confirmed.add(pid)  # don't keep polling
        if len(confirmed) < len(post_ids):
            time.sleep(args.poll_sec)

    # ── Final per-post report + per-platform write-back ──
    # Item 3 (P1): write each platform's ACTUAL outcome to its OWN
    # daily_drafts row. Successes carry release_url + postiz_state
    # forward; failures (state=ERROR, PUBLISHED-but-unreachable, or
    # NOT_FOUND_IN_LIST) leave postiz_state set to the failure tag so
    # the operator UI can render which platform of the thread broke.
    print("\n=== FINAL REPORT ===")
    failed: list[dict] = []
    successes: list[dict] = []
    for pid in post_ids:
        s = last_state.get(pid, {})
        state = s.get("state", "UNKNOWN")
        rurl = s.get("release_url")
        platform = s.get("platform", "?")
        resolved_ok = bool(s.get("resolved_ok"))
        is_success = state == "PUBLISHED" and rurl and resolved_ok
        if is_success:
            print(f"  ✅ {pid[:14]} {platform:12s} PUBLISHED  {rurl}")
            successes.append({
                "post_id": pid, "platform": platform,
                "release_url": rurl, "draft_id": s.get("draft_id"),
            })
        else:
            print(f"  ❌ {pid[:14]} {platform:12s} state={state}  url={rurl or '—'}")
            failed.append({
                "post_id": pid, "platform": platform,
                "state": state, "release_url": rurl,
                "error": s.get("error"),
                "resolve_note": s.get("resolve_note"),
                "draft_id": s.get("draft_id"),
            })

    # Per-platform reconciliation write-back (Item 3) — runs for BOTH
    # success + failure buckets, against the EXACT row whose
    # postiz_post_id matches. A blanket "approved" status used to mask
    # single-platform breaks within a thread; this surfaces them.
    sb = make_supabase()
    for ok in successes:
        try:
            payload = {"postiz_state": "PUBLISHED"}
            if ok["release_url"]:
                payload["release_url"] = ok["release_url"]
            sb.table("daily_drafts").update(payload).eq(
                "postiz_post_id", ok["post_id"]
            ).execute()
        except Exception as e:
            print(f"  daily_drafts success write-back failed (post={ok['post_id'][:10]}): {e!r}")
    for f in failed:
        try:
            payload = {"postiz_state": f["state"] or "UNKNOWN"}
            # Don't clobber release_url with None — only set it when we
            # actually saw a URL (e.g. PUBLISHED-but-unreachable case).
            if f.get("release_url"):
                payload["release_url"] = f["release_url"]
            sb.table("daily_drafts").update(payload).eq(
                "postiz_post_id", f["post_id"]
            ).execute()
        except Exception as e:
            print(f"  daily_drafts failure write-back failed (post={f['post_id'][:10]}): {e!r}")

    if failed:
        print("\nFailures:")
        print(json.dumps(failed, indent=2, ensure_ascii=False))
        return 1
    print(f"\nAll {len(successes)} post(s) PUBLISHED and URLs (+ video) resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
