"""fal.ai Wizper client — fast Turkish ASR with real time-aligned segments.

Uses `fal-ai/wizper` (Whisper large-v3, fal's optimized fast variant).
Per fal.ai pricing: $0.50 / 1000 audio-minutes → ~$0.0001 per 14s narration.

Returns a `TranscriptionResult` with the same shape the Wiro client used
(`.srt` field) so the call-site is drop-in compatible — but timestamps
are real ASR-aligned, not character-proportional.

Authentication: reads `FAL_KEY` from the environment. The fal-client
Python library picks it up automatically.

Drop-in replacement for wiro_whisper_client.WiroWhisperClient when Wiro
returns 0 segments on short Turkish clips (consistent failure mode
observed on our 14s narration).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger


@dataclass(frozen=True)
class TranscriptionResult:
    plain_text: str
    srt: str
    segment_count: int
    cost_usd: float
    latency_ms: int


def _format_srt_timestamp(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec) % 60
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _chunks_to_srt(chunks: list[dict[str, Any]]) -> str:
    """Build an SRT block from wizper's `chunks` array.

    Each chunk is `{"timestamp": [start_s, end_s], "text": "..."}`.
    Wizper occasionally returns a `[start, None]` timestamp on the last
    chunk; pad to start+2s in that case so the segment still renders.
    """
    lines: list[str] = []
    n = 0
    for c in chunks:
        ts = c.get("timestamp") or []
        text = (c.get("text") or "").strip()
        if not text:
            continue
        start = float(ts[0]) if len(ts) >= 1 and ts[0] is not None else 0.0
        end = float(ts[1]) if len(ts) >= 2 and ts[1] is not None else start + 2.0
        if end <= start:
            end = start + 1.5
        n += 1
        lines.append(str(n))
        lines.append(f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


class FalWizperClient:
    """Thin async wrapper around `fal-ai/wizper`.

    Usage:
        async with FalWizperClient() as w:
            r = await w.transcribe(audio_url, language="tr")
        write(r.srt)
    """

    # Default to fal-ai/whisper (supports chunk_level="word") rather than
    # fal-ai/wizper (segment-only, returns a single chunk for short clips).
    # Wizper is faster but useless for subtitle alignment.
    MODEL_SLUG = "fal-ai/whisper"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("FAL_KEY")
        if not self.api_key:
            raise RuntimeError("FAL_KEY not set in env; cannot call fal.ai/wizper")
        # fal-client reads FAL_KEY from env automatically; we just ensure
        # it is set on this process before any submit call.
        os.environ["FAL_KEY"] = self.api_key

    async def __aenter__(self) -> "FalWizperClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None

    async def transcribe(
        self,
        audio_url: str,
        *,
        language: str = "tr",
        chunk_level: str = "word",
    ) -> TranscriptionResult:
        """Submit a public audio URL → real time-aligned SRT.

        Args:
            audio_url: Publicly accessible audio (mp3/wav/m4a).
            language: ISO code. "tr" for Turkish — strongly preferred
                over "auto" on short clips (auto often returns 0 chunks
                on <15s Turkish audio, matching the Wiro failure mode).
            chunk_level: "segment" (sentence-ish) or "word" (per-word
                timestamps when supported).

        Returns:
            TranscriptionResult with `.srt` ready to burn-in.
        """
        if not audio_url:
            raise ValueError("audio_url is required")
        try:
            import fal_client
        except ImportError as e:
            raise RuntimeError(
                "fal-client not installed; pip install fal-client"
            ) from e

        # Use `subscribe_async` so we get the final result without
        # spinning a manual poll loop. The library handles queue + poll.
        payload = {
            "audio_url": audio_url,
            "task": "transcribe",
            "language": language,
            "chunk_level": chunk_level,
        }
        t0 = time.perf_counter()
        result = await fal_client.subscribe_async(
            self.MODEL_SLUG,
            arguments=payload,
            with_logs=False,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        chunks = (result or {}).get("chunks") or []
        plain_text = ((result or {}).get("text") or "").strip()
        if not plain_text:
            plain_text = " ".join(
                (c.get("text") or "").strip() for c in chunks
            ).strip()
        srt = _chunks_to_srt(chunks)

        # Wizper bills per inference-second; for a 14s clip the real cost
        # is well under a cent. We don't get a billing field back, so we
        # estimate from inference latency at the documented $0.50/1k-min
        # → $0.0083/min → $0.000139/sec rate. This is logging-only.
        cost_estimate = (latency_ms / 1000.0) * (0.50 / 60.0 / 1000.0)

        logger.info(
            f"fal_whisper.complete chunks={len(chunks)} plain_chars={len(plain_text)} "
            f"latency_ms={latency_ms} est_cost=${cost_estimate:.5f}"
        )
        return TranscriptionResult(
            plain_text=plain_text,
            srt=srt,
            segment_count=len(chunks),
            cost_usd=cost_estimate,
            latency_ms=latency_ms,
        )


# ---------------------------------------------------------------
# High-level helpers used by video_pipeline.heygen_avatar_v
# ---------------------------------------------------------------

import re as _re_subs


def _format_srt_ts(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec) % 60
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _collapse_subwords(chunks: list[dict[str, Any]]) -> list[tuple]:
    """Merge Whisper sub-word tokens (e.g. "-5", ".5") into spoken-word
    boundaries. A continuation chunk has no leading whitespace in its text.
    Returns list of (start_sec, end_sec, text)."""
    spoken: list[tuple] = []
    for ch in chunks:
        t = ch.get("text") or ""
        ts = ch.get("timestamp") or [None, None]
        if t and not t.startswith(" ") and spoken:
            ls, le, lt = spoken[-1]
            spoken[-1] = (ls, ts[1] or le, lt + t)
            continue
        spoken.append((ts[0], ts[1], t.strip()))
    return [(s, e, txt) for s, e, txt in spoken if txt]


def _group_words_to_segments(
    aligned: list[dict[str, Any]], *, target_chars: int = 48,
) -> list[dict[str, Any]]:
    """Group word-level entries into ~target_chars caption segments.
    Cuts at sentence punctuation or when buf reaches target_chars."""
    segs: list[dict[str, Any]] = []
    buf: list[dict[str, Any]] = []
    buf_chars = 0
    for w in aligned:
        buf.append(w)
        buf_chars += len(w["text"]) + 1
        ends_sent = w["text"].rstrip()[-1:] in ".!?:"
        if ends_sent or buf_chars >= target_chars:
            text_joined = " ".join(x["text"] for x in buf)
            segs.append({
                "start": buf[0]["start"],
                "end": buf[-1]["end"],
                "text": text_joined,
            })
            buf = []
            buf_chars = 0
    if buf:
        text_joined = " ".join(x["text"] for x in buf)
        segs.append({
            "start": buf[0]["start"],
            "end": buf[-1]["end"],
            "text": text_joined,
        })
    return segs


def _script_proportional_srt(script_text: str, duration_sec: float) -> str:
    """Last-resort fallback when Whisper returns no usable chunks.
    Distributes script text proportionally across the audio duration.
    Caller should log that this fallback fired."""
    parts = [p.strip() for p in _re_subs.split(r"(?<=[.!?…])\s+", script_text.strip()) if p.strip()]
    if not parts:
        parts = [script_text.strip()]
    refined: list[str] = []
    for p in parts:
        if len(p) <= 80:
            refined.append(p); continue
        chunks: list[str] = []
        cur = ""
        for piece in (s.strip() for s in p.split(",") if s.strip()):
            if len(cur) + len(piece) + 2 <= 80:
                cur = (cur + ", " + piece) if cur else piece
            else:
                if cur: chunks.append(cur)
                cur = piece
        if cur: chunks.append(cur)
        refined.extend(chunks)
    total = sum(len(p) for p in refined) or 1
    lines: list[str] = []
    cursor = 0.0
    for i, p in enumerate(refined, 1):
        share = len(p) / total
        end = min(duration_sec, cursor + min(duration_sec * share, 4.5))
        if i == len(refined):
            end = duration_sec
        lines.append(str(i))
        lines.append(f"{_format_srt_ts(cursor)} --> {_format_srt_ts(end)}")
        lines.append(p)
        lines.append("")
        cursor = end
    return "\n".join(lines)


async def build_subtitle_srt(
    *,
    narration_url: str,
    script_text: str,
    audio_duration_sec: float,
    language: str = "tr",
    target_segment_chars: int = 48,
) -> tuple[str, str]:
    """Produce a burn-ready SRT for the narration.

    Strategy:
      1. fal-ai/whisper word-level transcription on the public narration URL.
      2. Collapse Whisper sub-word tokens into spoken-word boundaries.
      3. Index-align script words ↔ whisper-spoken-word boundaries (so
         displayed text is from the SCRIPT, immune to Whisper Turkish
         mistranscriptions like "ameleliği" → "ameliyatı").
      4. Group into ~48-char readable segments, cutting at sentence
         punctuation. Caps each segment to 2 wrapped lines at FontSize=54.

    Returns: (srt_text, source) where source is "whisper" on success or
    "script_proportional_fallback" when Whisper returns no usable chunks.
    """
    src = "whisper"
    # Direct fal call so we get the raw word chunks (TranscriptionResult
    # only exposes the segment-glued SRT; we need per-word timestamps).
    if not os.environ.get("FAL_KEY"):
        logger.warning("build_subtitle_srt: FAL_KEY missing; falling back")
        return _script_proportional_srt(script_text, audio_duration_sec), "script_proportional_fallback"
    try:
        import fal_client
        res = await fal_client.subscribe_async(
            FalWizperClient.MODEL_SLUG,
            arguments={
                "audio_url": narration_url, "task": "transcribe",
                "language": language, "chunk_level": "word",
            },
            with_logs=False,
        )
        word_chunks = res.get("chunks") or []
    except Exception as e:
        logger.warning(f"build_subtitle_srt: fal call raised: {e!r}")
        return _script_proportional_srt(script_text, audio_duration_sec), "script_proportional_fallback"

    spoken = _collapse_subwords(word_chunks)
    if not spoken:
        logger.warning("build_subtitle_srt: whisper returned 0 spoken-word boundaries")
        return _script_proportional_srt(script_text, audio_duration_sec), "script_proportional_fallback"

    script_words = _re_subs.findall(r"\S+", script_text)
    n = min(len(script_words), len(spoken))
    aligned: list[dict[str, Any]] = []
    for i in range(n):
        st, en, _ = spoken[i]
        start = float(st) if st is not None else 0.0
        end = float(en) if en is not None else start + 0.3
        aligned.append({"start": start, "end": end, "text": script_words[i]})
    if len(script_words) > n:
        tail_start = aligned[-1]["end"] if aligned else 0.0
        per = max(0.25, (audio_duration_sec - tail_start) / max(1, len(script_words) - n))
        for j, w in enumerate(script_words[n:], 1):
            aligned.append({
                "start": tail_start + (j - 1) * per,
                "end": tail_start + j * per,
                "text": w,
            })

    segs = _group_words_to_segments(aligned, target_chars=target_segment_chars)
    if not segs:
        return _script_proportional_srt(script_text, audio_duration_sec), "script_proportional_fallback"

    lines: list[str] = []
    for i, s in enumerate(segs, 1):
        lines.append(str(i))
        lines.append(f"{_format_srt_ts(s['start'])} --> {_format_srt_ts(s['end'])}")
        lines.append(s["text"])
        lines.append("")
    logger.info(
        f"build_subtitle_srt: {len(segs)} segments from "
        f"{len(spoken)} whisper boundaries / {len(script_words)} script words"
    )
    return "\n".join(lines), src
