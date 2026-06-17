# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""Wiro Whisper-large-v3 Turkish transcription wrapper — Phase 35.3.2.

Used by HeyGenSplitScreenPipeline to transcribe HeyGen-generated MP4 audio
into SRT subtitles for Creatomate burn-in.

Slug: openai/whisper-large-v3 (verified via Wiro blog + WebSearch 2026-05-29)
Body:
    inputAudioUrl: public audio URL (MP4/MP3/WAV)
    language: "tr" for Turkish (or "auto")
    maxNewTokens: 256 (default ok)
    chunkLength: 30 (default ok)
    batchSize: 8 (default ok)
    numSpeakers: 1 (Cansu monologue)

Output: timestamped segments. Different possible response shapes — we try
multiple extraction paths and fall back to raw text if structure unknown.

Returns SRT-formatted string ready for Creatomate's subtitle source field.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from loguru import logger

from config import settings


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TranscriptionResult:
    srt: str                  # SRT-formatted transcript (Creatomate-ready)
    plain_text: str           # concatenated text (audit + grounding)
    segment_count: int
    language: str
    duration_sec: float
    task_uuid: str
    cost_usd: float
    latency_ms: int
    raw_response: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class WiroWhisperClient:
    """Wiro Whisper-large-v3 async wrapper. Same submit+poll pattern as WiroClient."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
        slug: str | None = None,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
        poll_max_attempts: int = 180,  # 6 minutes max — Whisper ~30sec on 20sec audio
    ):
        self.api_key = api_key or settings.wiro_api_key
        self.api_secret = api_secret if api_secret is not None else settings.wiro_api_secret
        self.base_url = _normalize_base_url(base_url or settings.wiro_base_url)
        self.slug = slug or getattr(settings, "wiro_whisper_slug", None) or "openai/whisper-large-v3"
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.poll_max_attempts = poll_max_attempts
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WiroWhisperClient":
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def transcribe(
        self,
        audio_url: str,
        *,
        language: str = "tr",
        max_new_tokens: int = 256,
        chunk_length: int = 30,
        batch_size: int = 8,
        num_speakers: int = 1,
    ) -> TranscriptionResult:
        """Transcribe a public audio URL → SRT-formatted transcript.

        Args:
            audio_url: Publicly accessible audio URL (MP3/MP4/WAV).
            language: "tr" for Turkish, "auto" for detection, or ISO code.

        Returns:
            TranscriptionResult with .srt ready for Creatomate.

        Raises:
            RuntimeError on submission/polling failures.
            TimeoutError if polling exceeds max_attempts.
        """
        if self._client is None:
            raise RuntimeError("WiroWhisperClient must be used as async context manager")
        if not self.api_key:
            raise RuntimeError("WIRO_API_KEY is not configured")
        if not audio_url:
            raise ValueError("audio_url is required")

        params: dict[str, Any] = {
            "inputAudioUrl": audio_url,
            "language": language,
            "maxNewTokens": max_new_tokens,
            "chunkLength": chunk_length,
            "batchSize": batch_size,
            "numSpeakers": num_speakers,
        }

        headers = self._headers()

        # 1. Submit
        t0 = time.perf_counter()
        submit = await self._client.post(
            f"{self.base_url}/Run/{self.slug}",
            headers=headers,
            json=params,
        )
        submit.raise_for_status()
        submit_data = submit.json()
        _raise_if_wiro_error(submit_data, context="whisper.submit")
        task_token = _extract_task_token(submit_data)
        task_uuid = _extract_task_id(submit_data) or task_token
        if not task_token:
            raise RuntimeError(f"Wiro Whisper submit returned no task token: {submit_data}")

        logger.info(f"wiro_whisper.submit slug={self.slug} task={task_uuid}")

        # 2. Poll
        final_task: dict[str, Any] | None = None
        detail_data: dict[str, Any] | None = None
        for attempt in range(self.poll_max_attempts):
            await asyncio.sleep(self.poll_interval)
            status_resp = await self._client.post(
                f"{self.base_url}/Task/Detail",
                headers=headers,
                json={"tasktoken": task_token},
            )
            status_resp.raise_for_status()
            detail_data = status_resp.json()
            _raise_if_wiro_error(detail_data, context="whisper.detail")
            task = _extract_task(detail_data)
            status = str(task.get("status", "")).lower()
            if status == "task_postprocess_end":
                pexit = str(task.get("pexit", ""))
                if pexit == "0":
                    final_task = task
                    break
                raise RuntimeError(f"Wiro Whisper task {task_uuid} failed: {task}")
            if status in ("completed", "success", "succeeded"):
                final_task = task
                break
            if status in ("failed", "error", "cancelled", "task_cancel"):
                raise RuntimeError(f"Wiro Whisper task {task_uuid} failed: {task}")
        else:
            raise TimeoutError(f"Wiro Whisper task {task_uuid} did not complete in time")

        result_data = final_task or {}
        latency_ms = int((time.perf_counter() - t0) * 1000)
        cost = _extract_cost_usd(result_data)

        # 3. Parse segments from response (multiple possible shapes)
        segments = _extract_segments(result_data)
        plain_text = " ".join(s["text"] for s in segments).strip()
        srt = _segments_to_srt(segments)
        duration_sec = segments[-1]["end"] if segments else 0.0

        logger.info(
            f"wiro_whisper.complete task={task_uuid} segments={len(segments)} "
            f"duration={duration_sec:.1f}s cost={cost} latency_ms={latency_ms}"
        )

        return TranscriptionResult(
            srt=srt,
            plain_text=plain_text,
            segment_count=len(segments),
            language=language,
            duration_sec=duration_sec,
            task_uuid=task_uuid,
            cost_usd=cost,
            latency_ms=latency_ms,
            raw_response=detail_data or result_data,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        if self.api_key and self.api_secret:
            nonce = str(int(time.time() * 1000))
            signature = hmac.new(
                self.api_key.encode("utf-8"),
                f"{self.api_secret}{nonce}".encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["x-nonce"] = nonce
            headers["x-signature"] = signature
        return headers


# ---------------------------------------------------------------------------
# Response parsing — flexible to handle different Whisper output shapes
# ---------------------------------------------------------------------------


def _extract_segments(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract list of {start, end, text} segments from Wiro Whisper response.

    Tries multiple shapes:
    1. task["outputs"] = list of {start, end, text} (preferred)
    2. task["output"] = JSON string containing segments
    3. task["responseData"] = nested dict with segments
    4. task["output"] = plain text → single segment fallback
    """
    # Shape 1: outputs as list of segment dicts
    outputs = task.get("outputs")
    if isinstance(outputs, list) and outputs:
        if isinstance(outputs[0], dict) and ("start" in outputs[0] or "text" in outputs[0]):
            return [_normalize_segment(s) for s in outputs if isinstance(s, dict)]
        # Sometimes outputs contains a single URL — try fetching it? V2.
        # For now, fall through.

    # Shape 2: output is a JSON string
    output = task.get("output")
    if isinstance(output, str):
        stripped = output.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [_normalize_segment(s) for s in parsed if isinstance(s, dict)]
                if isinstance(parsed, dict):
                    chunks = parsed.get("chunks") or parsed.get("segments") or parsed.get("output")
                    if isinstance(chunks, list):
                        return [_normalize_segment(s) for s in chunks if isinstance(s, dict)]
            except json.JSONDecodeError:
                pass

    # Shape 3: responseData nested
    response_data = task.get("responseData")
    if isinstance(response_data, dict):
        chunks = response_data.get("chunks") or response_data.get("segments")
        if isinstance(chunks, list):
            return [_normalize_segment(s) for s in chunks if isinstance(s, dict)]
        text = response_data.get("text")
        if isinstance(text, str) and text.strip():
            return [{"start": 0.0, "end": 0.0, "text": text.strip()}]

    # Shape 4: plain text fallback
    if isinstance(output, str) and output.strip():
        return [{"start": 0.0, "end": 0.0, "text": output.strip()}]

    return []


def _normalize_segment(seg: dict[str, Any]) -> dict[str, Any]:
    """Coerce a segment dict to {start: float, end: float, text: str}."""
    text = seg.get("text") or seg.get("transcript") or ""
    text = str(text).strip()

    # Timestamp may be flat (start/end) or nested (timestamp: [start, end])
    timestamp = seg.get("timestamp")
    start: float = 0.0
    end: float = 0.0
    if isinstance(timestamp, (list, tuple)) and len(timestamp) >= 2:
        start = float(timestamp[0] or 0.0)
        end = float(timestamp[1] or 0.0)
    else:
        try:
            start = float(seg.get("start") or seg.get("start_time") or 0.0)
        except (TypeError, ValueError):
            start = 0.0
        try:
            end = float(seg.get("end") or seg.get("end_time") or 0.0)
        except (TypeError, ValueError):
            end = 0.0

    if end < start:
        end = start

    return {"start": start, "end": end, "text": text}


def _segments_to_srt(segments: list[dict[str, Any]]) -> str:
    """Convert segment list → SRT text format.

    Format per entry:
        1
        00:00:00,000 --> 00:00:05,200
        Segment text here.

        2
        ...
    """
    lines: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        if not seg["text"]:
            continue
        start_ts = _format_srt_timestamp(seg["start"])
        end_ts = _format_srt_timestamp(seg["end"] if seg["end"] > seg["start"] else seg["start"] + 2.5)
        lines.append(str(idx))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(seg["text"])
        lines.append("")  # blank line separator
    return "\n".join(lines).strip() + "\n" if lines else ""


def _format_srt_timestamp(sec: float) -> str:
    """0.5 → 00:00:00,500; 65.123 → 00:01:05,123."""
    if sec < 0:
        sec = 0.0
    total_ms = int(round(sec * 1000))
    hours, rem_ms = divmod(total_ms, 3600 * 1000)
    minutes, rem_ms = divmod(rem_ms, 60 * 1000)
    seconds, ms = divmod(rem_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


# ---------------------------------------------------------------------------
# Wiro response helpers (copied from wiro_client.py to keep this module
# self-contained and avoid touching the stable Phase 21 client)
# ---------------------------------------------------------------------------


def _normalize_base_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    if url.endswith("/api"):
        return f"{url}/v1"
    return f"{url}/v1"


def _extract_task_token(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    candidates = [
        payload.get("socketaccesstoken"),
        payload.get("tasktoken"),
        payload.get("task_token"),
    ]
    if isinstance(data, dict):
        candidates.extend(
            [data.get("socketaccesstoken"), data.get("tasktoken"), data.get("task_token")]
        )
    return next((str(value) for value in candidates if value), "")


def _extract_task_id(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    candidates = [payload.get("taskid"), payload.get("task_id"), payload.get("id")]
    if isinstance(data, dict):
        candidates.extend([data.get("taskid"), data.get("task_id"), data.get("id")])
    return next((str(value) for value in candidates if value), "")


def _extract_task(payload: dict[str, Any]) -> dict[str, Any]:
    tasklist = payload.get("tasklist")
    if isinstance(tasklist, list) and tasklist and isinstance(tasklist[0], dict):
        return tasklist[0]
    data = payload.get("data")
    if isinstance(data, dict):
        nested = data.get("tasklist")
        if isinstance(nested, list) and nested and isinstance(nested[0], dict):
            return nested[0]
        return data
    return payload


def _extract_cost_usd(task: dict[str, Any]) -> float:
    value = task.get("totalcost") or task.get("cost_usd") or 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _raise_if_wiro_error(payload: dict[str, Any], *, context: str) -> None:
    """Raise if Wiro response indicates an error."""
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        raise RuntimeError(f"Wiro {context} error: {errors[:3]}")
    error = payload.get("error")
    if error and not str(error).lower() in {"none", "null", "false", ""}:
        raise RuntimeError(f"Wiro {context} error: {error}")
    message = payload.get("message") or ""
    msg_lower = str(message).lower()
    if any(token in msg_lower for token in ("denied", "unauthorized", "invalid api", "failed")):
        raise RuntimeError(f"Wiro {context} error message: {message}")
