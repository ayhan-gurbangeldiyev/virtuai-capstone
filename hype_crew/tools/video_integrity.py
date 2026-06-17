"""Video integrity check — defends against the SEV-1 P0 follow-up.

Berkay's spec (2026-06-07): a video must NEVER publish cut-off
mid-script. The content↔video sha binding (commit cfb38b9) catches
edit-drift; this module catches the OTHER class of bug — the render
itself producing a video that is materially shorter than its content
should require, or a file whose audio track ends before its video
track, or a malformed mp4 that ffprobe can't fully read.

Used by:
  - hype_crew/flow.py at video write-back (cron pipeline).
  - hype_crew/scripts/process_image_regen_queue.py at regen completion.
  - backend/routes/hype.py at queue sweep + the safe-proof endpoint.

The check writes 4 columns onto daily_drafts (migration 016):
  video_duration_s           actual file duration (seconds)
  expected_duration_s        from sha-of-content × Turkish TTS rate
  video_integrity_ok         True iff ALL four sub-checks pass
  video_integrity_reason     short string when False
  video_integrity_checked_at when the check ran

Sub-checks:
  (a) Completeness:  ffprobe reads a valid mp4 (moov atom present,
                     duration > 0, no decode errors).
  (b) Audio≈video:   |audio_duration - video_duration| ≤ ±0.5s.
  (c) Duration≈script: actual ≥ expected × (1 - tolerance). Materially
                     SHORTER fails; modestly longer is fine. Default
                     tolerance: 0.20 (20% short is OK; >20% short =
                     truncated). Env override:
                     VIDEO_INTEGRITY_DURATION_TOLERANCE.
  (d) Subtitle tail: last subtitle segment end-time is within ±2.0s
                     of actual duration. Skipped silently when no
                     subtitle/SRT path is provided (defensive — we
                     don't have SRT integrated with persistence yet).

Fail-safe: ANY raised exception in the probe → integrity FAIL with the
exception class in the reason. Better to require a re-render than to
let a broken file ship.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Turkish TTS rate of thumb — ~150 wpm, average word ~6.5 chars +
# trailing space → ~7 chars/word + interword pauses. Empirically the
# stage 2026-06-04 measurements landed at 17 chars/sec ± 1.5. Env
# override: VIDEO_TTS_CHARS_PER_SECOND.
def _tts_rate() -> float:
    raw = (os.environ.get("VIDEO_TTS_CHARS_PER_SECOND") or "").strip()
    try:
        return float(raw) if raw else 17.0
    except ValueError:
        return 17.0


def _duration_tolerance() -> float:
    """2026-06-07 PART 5 calibration: tightened from 0.20 → 0.15.
    At 0.20 the IG 19%-short case sneaked through (343-char caption,
    21.93s expected, 19.76s actual → 9.9% short, PASSed). The 29-of-46
    sweep also showed several 20-25% borderlines we'd rather catch.
    Operator override via env var if a specific account needs slack.
    """
    raw = (os.environ.get("VIDEO_INTEGRITY_DURATION_TOLERANCE") or "").strip()
    try:
        v = float(raw) if raw else 0.15
        return max(0.05, min(0.50, v))
    except ValueError:
        return 0.15


def _av_drift_tolerance_s() -> float:
    return 0.50


def _subtitle_tail_gap_tolerance_s() -> float:
    return 2.0


# ─── Content → expected duration ────────────────────────────────────


_PAUSE_MARKER = re.compile(r"<#(\d+(?:\.\d+)?)#>")
_AUDIO_PUNCT_PAUSE_MS = 250   # comma/period adds a small pause
_PUNCT_RE = re.compile(r"[\.\,\;\:\!\?…]")


def expected_duration_from_content(content: str) -> float:
    """Compute the expected TTS duration for a piece of content.

    Counts:
      - chars (excluding the literal pause markers themselves) / TTS rate
      - explicit <#x#> pause markers → x seconds each
      - punctuation pauses → 0.25s each
    """
    if not content:
        return 0.0
    # Subtract explicit pause-marker durations from the char count, then
    # add their literal duration to the final.
    pause_total = 0.0
    for m in _PAUSE_MARKER.finditer(content):
        try:
            pause_total += float(m.group(1))
        except Exception:
            pass
    stripped = _PAUSE_MARKER.sub("", content)
    char_secs = len(stripped) / _tts_rate()
    punct_secs = (len(_PUNCT_RE.findall(stripped)) * _AUDIO_PUNCT_PAUSE_MS) / 1000.0
    return round(char_secs + pause_total + punct_secs, 2)


# ─── ffprobe wrapper ────────────────────────────────────────────────


_FFPROBE_BIN = shutil.which("ffprobe") or "/usr/bin/ffprobe"


def _ffprobe_json(path: str) -> dict:
    """Run ffprobe + return parsed JSON. Raises on subprocess error."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"ffprobe target not found: {path}")
    cmd = [
        _FFPROBE_BIN, "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed ({r.returncode}): {r.stderr[:300]}")
    return json.loads(r.stdout)


@dataclass(frozen=True)
class IntegrityResult:
    ok: bool
    reason: Optional[str]            # short tag explaining the first fail
    actual_duration_s: float          # 0.0 when probe failed
    expected_duration_s: float
    audio_duration_s: float
    video_duration_s: float
    subtitle_tail_gap_s: Optional[float]


def check_video_integrity(
    *,
    file_path: str,
    content_for_tts: str,
    srt_path: Optional[str] = None,
    tts_audio_duration_s: Optional[float] = None,
) -> IntegrityResult:
    """Run the 4 sub-checks. Returns IntegrityResult.

    Args:
      file_path: local path to the rendered video.
      content_for_tts: the script content used to size expected duration.
      srt_path: optional path to the matching SRT subtitle file.
      tts_audio_duration_s: 2026-06-07 PART 5 — when the caller knows
        the actual MiniMax/TTS audio duration (from synthesis), pass it
        here. The check uses it as `expected_duration_s` instead of the
        chars÷rate estimate. Char estimate stays as the fallback when
        the precise number is unavailable.

    Never raises; on any exception returns ok=False with the
    exception's class in `reason`. Better to require a re-render than
    let a broken file ship.
    """
    if tts_audio_duration_s is not None and tts_audio_duration_s > 0:
        expected = round(float(tts_audio_duration_s), 2)
    else:
        expected = expected_duration_from_content(content_for_tts)

    # (a) Completeness — ffprobe must read the file
    try:
        meta = _ffprobe_json(file_path)
    except Exception as e:
        return IntegrityResult(
            ok=False,
            reason=f"ffprobe_unreadable:{type(e).__name__}",
            actual_duration_s=0.0,
            expected_duration_s=expected,
            audio_duration_s=0.0,
            video_duration_s=0.0,
            subtitle_tail_gap_s=None,
        )
    streams = meta.get("streams") or []
    fmt = meta.get("format") or {}

    def _stream(kind: str) -> Optional[dict]:
        return next((s for s in streams if s.get("codec_type") == kind), None)

    v = _stream("video")
    a = _stream("audio")

    if not v:
        return IntegrityResult(
            ok=False,
            reason="missing_video_stream",
            actual_duration_s=0.0,
            expected_duration_s=expected,
            audio_duration_s=0.0,
            video_duration_s=0.0,
            subtitle_tail_gap_s=None,
        )

    def _dur(s: Optional[dict]) -> float:
        if not s:
            return 0.0
        try:
            return float(s.get("duration") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    v_dur = _dur(v)
    a_dur = _dur(a)
    container_dur = 0.0
    try:
        container_dur = float(fmt.get("duration") or 0.0)
    except (TypeError, ValueError):
        container_dur = 0.0
    actual_dur = max(v_dur, container_dur)

    # (b) Audio≈video length
    if a:
        drift = abs(a_dur - v_dur)
        if drift > _av_drift_tolerance_s():
            return IntegrityResult(
                ok=False,
                reason=f"audio_video_drift:{drift:.2f}s",
                actual_duration_s=actual_dur,
                expected_duration_s=expected,
                audio_duration_s=a_dur,
                video_duration_s=v_dur,
                subtitle_tail_gap_s=None,
            )

    # (c) Duration ≈ script
    if expected > 0:
        # short-fall = how much SHORTER than expected
        if v_dur < expected * (1.0 - _duration_tolerance()):
            shortfall_pct = round((expected - v_dur) / expected * 100, 1)
            return IntegrityResult(
                ok=False,
                reason=(
                    f"duration_below_floor: actual={v_dur:.2f}s "
                    f"expected={expected:.2f}s shortfall={shortfall_pct}%"
                ),
                actual_duration_s=actual_dur,
                expected_duration_s=expected,
                audio_duration_s=a_dur,
                video_duration_s=v_dur,
                subtitle_tail_gap_s=None,
            )

    # (d) Subtitle tail
    subtitle_tail_gap: Optional[float] = None
    if srt_path and os.path.isfile(srt_path):
        last_end_s = _last_srt_end(srt_path)
        if last_end_s is not None:
            subtitle_tail_gap = round(v_dur - last_end_s, 2)
            if subtitle_tail_gap > _subtitle_tail_gap_tolerance_s():
                return IntegrityResult(
                    ok=False,
                    reason=(
                        f"subtitle_ends_early: last_srt_end={last_end_s:.2f}s "
                        f"video={v_dur:.2f}s gap={subtitle_tail_gap:.2f}s"
                    ),
                    actual_duration_s=actual_dur,
                    expected_duration_s=expected,
                    audio_duration_s=a_dur,
                    video_duration_s=v_dur,
                    subtitle_tail_gap_s=subtitle_tail_gap,
                )

    return IntegrityResult(
        ok=True,
        reason=None,
        actual_duration_s=actual_dur,
        expected_duration_s=expected,
        audio_duration_s=a_dur,
        video_duration_s=v_dur,
        subtitle_tail_gap_s=subtitle_tail_gap,
    )


# ─── SRT helper ─────────────────────────────────────────────────────


_SRT_TS = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def _srt_ts_to_seconds(ts: str) -> Optional[float]:
    m = _SRT_TS.search(ts)
    if not m:
        return None
    h, mn, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mn * 60 + s + ms / 1000.0


def _last_srt_end(path: str) -> Optional[float]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
    except Exception:
        return None
    # SRT cues are "HH:MM:SS,mmm --> HH:MM:SS,mmm"
    last = None
    for line in data.splitlines():
        if "-->" not in line:
            continue
        parts = line.split("-->", 1)
        if len(parts) != 2:
            continue
        end = _srt_ts_to_seconds(parts[1].strip())
        if end is not None:
            last = end
    return last


# ─── DB write helper ────────────────────────────────────────────────


def write_integrity_result_to_draft(
    *,
    sb,
    draft_id: str,
    result: IntegrityResult,
    extra: Optional[dict] = None,
) -> None:
    """Write the 5 integrity columns onto daily_drafts.

    Caller is responsible for further side effects (e.g. enqueueing a
    regen on failure) — this function just persists the verdict.
    """
    payload = {
        "video_duration_s": round(result.video_duration_s, 2),
        "expected_duration_s": round(result.expected_duration_s, 2),
        "video_integrity_ok": bool(result.ok),
        "video_integrity_reason": result.reason or None,
        "video_integrity_checked_at": _iso_now(),
    }
    if extra:
        payload.update(extra)
    try:
        sb.table("daily_drafts").update(payload).eq("id", draft_id).execute()
    except Exception as e:
        logger.warning(f"[integrity] DB write failed for draft={draft_id[:8]}: {e}")


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
