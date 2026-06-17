"""MiniMax Text-to-Audio v2 (Speech-02-HD) — thin async client.

We use MiniMax directly (not via Wiro) because Cansu's voice clone is registered
in MiniMax (voice_id) and proven working there. Wiro has MiniMax video models
(Hailuo) but not TTS, so this client bypasses Wiro for the speech step.

API ref: https://platform.minimax.io/docs/api-reference/speech-t2a-http

Endpoint:
    POST {MINIMAX_API_BASE}/t2a_v2?GroupId={group_id}
    Auth: Bearer {api_key}
    Body: {model, text, voice_setting{voice_id, speed, vol, pitch},
           audio_setting{sample_rate, bitrate, format, channel}}

Response variants (we handle all):
    a) `{data: {audio: "<hex_or_base64>"}}` — inline binary
    b) `{data: {audio_url: "https://..."}}` — download URL
    c) `{audio_file: "https://..."}` — alternate key
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, Optional

import httpx
from loguru import logger

from config import settings


@dataclass(frozen=True)
class MinimaxTTSResult:
    """Normalized output — either bytes downloaded or buffered inline."""

    audio_bytes: bytes
    audio_format: str           # "mp3" | "wav" | "pcm"
    sample_rate: int
    bitrate: int
    latency_ms: int
    cost_usd: float             # MiniMax returns extra_info.usage_characters; we approximate cost
    raw_response: dict[str, Any]


def _resolve_audio_bytes(data: dict[str, Any]) -> Optional[bytes]:
    """MiniMax response is inconsistent; try every shape."""
    # Shape A: data.audio (hex string)
    audio_hex = data.get("data", {}).get("audio") if isinstance(data.get("data"), dict) else None
    if isinstance(audio_hex, str) and audio_hex:
        try:
            return binascii.unhexlify(audio_hex)
        except (binascii.Error, ValueError):
            # maybe base64 instead
            try:
                return base64.b64decode(audio_hex)
            except Exception:
                pass

    # Shape B: data.audio_url
    url = None
    if isinstance(data.get("data"), dict):
        url = data["data"].get("audio_url") or data["data"].get("audio_file")
    url = url or data.get("audio_file") or data.get("audio_url")
    if isinstance(url, str) and url.startswith("http"):
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.content

    return None


# Phase 35.1.F — Soft-ending mitigation helpers
# Phase 35.1.G — Multi-chunk concat support (split + parallel synthesize + ffmpeg concat)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ])")


def _split_last_sentence(text: str) -> tuple[str, str]:
    """Split text at the LAST Turkish sentence boundary.

    Returns: (head, tail). If only one sentence, returns (text, "").

    Used by `synthesize_multi_chunk()` so the punchline closer gets a
    fresh prosody budget (Agent 1 / Phase 35.1.F nuclear option).
    """
    if not text or not text.strip():
        return text, ""
    parts = _SENTENCE_BOUNDARY.split(text.strip())
    if len(parts) < 2:
        return text, ""
    return " ".join(p.strip() for p in parts[:-1]), parts[-1].strip()


def _inject_closing_pause(text: str, pause_sec: float = 0.35) -> str:
    """Insert MiniMax inline `<#PAUSE#>` marker BEFORE the last sentence.

    Phase 35.1.F-Layer2 — Agent 1 (autoregressive prosody drift) mitigation.
    Pause resets MiniMax's energy budget so the closer stays decisive instead
    of trailing off.

    Args:
        text: Original Turkish text (multi-sentence).
        pause_sec: Pause duration. 0.35s is the research-recommended sweet spot.

    Returns:
        Text with `<#0.35#>` inserted before the final sentence, or original
        text unchanged if only one sentence.
    """
    if not text or "<#" in text:
        # Already has pause markers — don't double-inject.
        return text
    parts = _SENTENCE_BOUNDARY.split(text.strip())
    if len(parts) < 2:
        return text
    last = parts[-1].strip()
    if not last:
        return text
    head = " ".join(p.strip() for p in parts[:-1])
    return f"{head} <#{pause_sec}#> {last}"


def _estimate_cost(usage_chars: int, model: str) -> float:
    """MiniMax speech-02-hd is ~$0.001 per 1k chars (rough estimate from public pricing).

    Real billing comes from MiniMax dashboard; this is for monitoring only.
    """
    per_char = 0.000001  # $0.000001/char ≈ $0.001/1k chars
    return round(usage_chars * per_char, 6)


class MinimaxTTSClient:
    """Async MiniMax T2A v2 client.

    Usage:
        client = MinimaxTTSClient()
        result = await client.synthesize(
            text="Merhaba, ben Cansu.",
            voice_id=settings.minimax_voice_id_cansu,
        )
        # result.audio_bytes → MP3 binary
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        group_id: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.minimax_api_key
        self.group_id = group_id or settings.minimax_group_id
        self.api_base = (api_base or settings.minimax_api_base).rstrip("/")
        self.model = model or settings.minimax_model

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: Optional[str] = None,
        speed: float = 1.0,
        vol: float = 1.0,
        pitch: int = 0,
        sample_rate: int = 32000,
        bitrate: int = 128000,
        audio_format: Literal["mp3", "wav", "pcm"] = "mp3",
        channel: int = 1,
        emotion: Optional[str] = None,
        timeout: float = 60.0,
        pronunciation_dict: Optional[dict[str, Any]] = None,
        auto_resolve_pronunciation: bool = True,
        closing_emphasis: bool = True,
    ) -> MinimaxTTSResult:
        """Call MiniMax T2A v2 with Cansu's cloned voice_id by default.

        Phase 35.1.E — pronunciation control:
        - If `pronunciation_dict` provided: forwarded as-is.
        - Else if `auto_resolve_pronunciation=True`: invokes
          `pronunciation_resolver.build_pronunciation_dict(text)` to merge
          static dict + Supabase cache + Gemini resolver → MiniMax tone list.
        - Pass `auto_resolve_pronunciation=False` to bypass (legacy paths).
        """
        if not self.api_key:
            raise RuntimeError("MINIMAX_API_KEY env missing")
        if not self.group_id:
            raise RuntimeError("MINIMAX_GROUP_ID env missing")
        voice = voice_id or settings.minimax_voice_id_cansu
        if not voice:
            raise RuntimeError(
                "voice_id required (set MINIMAX_VOICE_ID_CANSU or pass voice_id=)"
            )

        # Phase 35.1.F — Closing emphasis (soft-ending mitigation)
        # 1) Inject <#0.35#> pause before final sentence (Agent 1 recommendation)
        # 2) Boost vol slightly (mask softness without distorting timbre)
        # 3) Set emotion="fluent" for neutral news (Agent 1: calm makes it worse)
        effective_text = text
        effective_vol = vol
        effective_emotion = emotion
        if closing_emphasis:
            effective_text = _inject_closing_pause(text)
            # Only bump vol if caller left it at default (1.0).
            if vol == 1.0:
                effective_vol = 1.2
            # Only force fluent if caller didn't pick an emotion.
            if not emotion:
                effective_emotion = "fluent"

        body: dict[str, Any] = {
            "model": self.model,
            "text": effective_text,
            "voice_setting": {
                "voice_id": voice,
                "speed": speed,
                "vol": effective_vol,
                "pitch": pitch,
            },
            "audio_setting": {
                "sample_rate": sample_rate,
                "bitrate": bitrate,
                "format": audio_format,
                "channel": channel,
            },
            "language_boost": "Turkish",  # boost Türkçe pronunciation
        }
        if effective_emotion:
            body["voice_setting"]["emotion"] = effective_emotion

        # Phase 35.1.E — pronunciation_dict (static + cache + resolver)
        resolved_dict: Optional[dict[str, Any]] = None
        if pronunciation_dict is not None:
            resolved_dict = pronunciation_dict
        elif auto_resolve_pronunciation:
            try:
                from .pronunciation_resolver import build_pronunciation_dict
                resolved_dict = await build_pronunciation_dict(text)
            except Exception as e:
                logger.warning(
                    f"minimax.synthesize: pronunciation_dict resolve failed "
                    f"({type(e).__name__}: {e}); continuing without"
                )
                resolved_dict = None
        if resolved_dict and resolved_dict.get("tone"):
            body["pronunciation_dict"] = resolved_dict
            logger.info(
                f"minimax.synthesize: pronunciation_dict applied "
                f"({len(resolved_dict.get('tone', []))} tone entries)"
            )

        url = f"{self.api_base}/t2a_v2?GroupId={self.group_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            f"minimax.synthesize model={self.model} voice={voice} "
            f"chars={len(text)} fmt={audio_format}"
        )

        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Check for MiniMax-style error envelope
        if isinstance(data, dict) and data.get("base_resp", {}).get("status_code", 0) != 0:
            err = data.get("base_resp", {}).get("status_msg", "unknown")
            raise RuntimeError(f"MiniMax error: {err}")

        audio_bytes = _resolve_audio_bytes(data)
        if not audio_bytes:
            raise RuntimeError(
                f"MiniMax returned no audio bytes/url in response: {str(data)[:300]}"
            )

        usage_chars = 0
        try:
            usage_chars = int(
                data.get("extra_info", {}).get("usage_characters", len(text))
            )
        except (TypeError, ValueError):
            usage_chars = len(text)

        cost = _estimate_cost(usage_chars, self.model)
        logger.info(
            f"minimax.complete bytes={len(audio_bytes)} latency_ms={latency_ms} "
            f"chars={usage_chars} cost=${cost}"
        )

        return MinimaxTTSResult(
            audio_bytes=audio_bytes,
            audio_format=audio_format,
            sample_rate=sample_rate,
            bitrate=bitrate,
            latency_ms=latency_ms,
            cost_usd=cost,
            raw_response=data,
        )

    async def synthesize_multi_chunk(
        self,
        text: str,
        *,
        voice_id: Optional[str] = None,
        speed: float = 1.0,
        vol: float = 1.0,
        pitch: int = 0,
        emotion: Optional[str] = None,
        sample_rate: int = 32000,
        bitrate: int = 128000,
        channel: int = 1,
        silence_ms: int = 250,
        pronunciation_dict: Optional[dict[str, Any]] = None,
        auto_resolve_pronunciation: bool = True,
        timeout: float = 60.0,
        tail_speed: Optional[float] = 0.92,
        tail_vol: Optional[float] = 1.15,
        tail_emotion: Optional[str] = "fluent",
    ) -> "MinimaxTTSResult":
        """Phase 35.1.G nuclear option — split + dual call + concat.

        Splits text at the LAST Turkish sentence boundary, calls
        `synthesize()` TWICE in parallel, then concatenates the two MP3s
        with a `silence_ms` gap via FFmpeg's concat demuxer.

        Why: Single-call MiniMax Speech-02 HD exhibits "soft ending" —
        accumulated autoregressive prosody drift causes the last 3-4
        sentences to trail off in Turkish. Splitting gives the punchline
        (final sentence) its own fresh prosody budget.

        Per-character billing (verified): two calls cost the same as one.
        Latency via asyncio.gather: ~max(call1, call2) + ~150ms concat.

        Falls back to single-call `synthesize()` if the text is only one
        sentence or FFmpeg is unavailable.
        """
        import os
        import subprocess
        import tempfile

        head, tail = _split_last_sentence(text)
        if not tail:
            logger.info("synthesize_multi_chunk: single sentence, fallback to synthesize()")
            return await self.synthesize(
                text,
                voice_id=voice_id,
                speed=speed,
                vol=vol,
                pitch=pitch,
                emotion=emotion,
                sample_rate=sample_rate,
                bitrate=bitrate,
                channel=channel,
                pronunciation_dict=pronunciation_dict,
                auto_resolve_pronunciation=auto_resolve_pronunciation,
                closing_emphasis=False,  # don't double-pause
                timeout=timeout,
            )

        # Resolve pronunciation_dict ONCE — passed verbatim to both calls.
        # MiniMax tolerates unused dict entries; same dict avoids
        # cross-chunk pronunciation drift on recurring proper nouns.
        resolved_dict: Optional[dict[str, Any]] = pronunciation_dict
        if resolved_dict is None and auto_resolve_pronunciation:
            try:
                from .pronunciation_resolver import build_pronunciation_dict
                resolved_dict = await build_pronunciation_dict(text)
            except Exception as e:
                logger.warning(
                    f"synthesize_multi_chunk: pronunciation resolve failed: {e}"
                )
                resolved_dict = None

        logger.info(
            f"synthesize_multi_chunk: split head={len(head)}c tail={len(tail)}c "
            f"silence={silence_ms}ms"
        )

        # 2 parallel synthesize calls.
        # HEAD: caller's defaults (full body content, neutral pacing).
        # TAIL: override speed/vol/emotion so the closer lands deliberate
        # instead of rushed. MiniMax tends to "rush" a fresh-context
        # single-sentence call because no prior prosody anchor exists;
        # tail_speed=0.92 + tail_vol=1.15 + emotion="fluent" forces a
        # measured, decisive delivery.
        # closing_emphasis=False on both — pause would double up with
        # the silence_ms gap we inject between chunks.
        common_base: dict[str, Any] = dict(
            voice_id=voice_id,
            pitch=pitch,
            sample_rate=sample_rate,
            bitrate=bitrate,
            channel=channel,
            pronunciation_dict=resolved_dict,
            auto_resolve_pronunciation=False,  # we already resolved
            closing_emphasis=False,
            timeout=timeout,
        )
        head_kwargs = {
            **common_base,
            "speed": speed,
            "vol": vol,
            "emotion": emotion,
        }
        # Tail override (None = inherit caller's value).
        effective_tail_speed = tail_speed if tail_speed is not None else speed
        effective_tail_vol = tail_vol if tail_vol is not None else vol
        effective_tail_emotion = tail_emotion if tail_emotion is not None else emotion
        tail_kwargs = {
            **common_base,
            "speed": effective_tail_speed,
            "vol": effective_tail_vol,
            "emotion": effective_tail_emotion,
        }
        logger.info(
            f"synthesize_multi_chunk tail overrides: speed={effective_tail_speed} "
            f"vol={effective_tail_vol} emotion={effective_tail_emotion}"
        )

        t0 = time.perf_counter()
        head_res, tail_res = await asyncio.gather(
            self.synthesize(head, **head_kwargs),
            self.synthesize(tail, **tail_kwargs),
        )
        parallel_ms = int((time.perf_counter() - t0) * 1000)

        # Concat via FFmpeg concat demuxer (re-encode mode for safety;
        # `-c copy` requires identical bit-stream params which we lock
        # via sample_rate+bitrate+channel above, but re-encode adds ~50ms
        # and eliminates click/pop risk at boundaries).
        with tempfile.TemporaryDirectory(prefix="mm_concat_") as d:
            head_path = os.path.join(d, "head.mp3")
            tail_path = os.path.join(d, "tail.mp3")
            silence_path = os.path.join(d, "silence.mp3")
            list_path = os.path.join(d, "list.txt")
            out_path = os.path.join(d, "out.mp3")

            with open(head_path, "wb") as f:
                f.write(head_res.audio_bytes)
            with open(tail_path, "wb") as f:
                f.write(tail_res.audio_bytes)

            # Generate silence MP3 (in-memory generation is harder via subprocess)
            silence_sec = silence_ms / 1000.0
            silence_cmd = [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi",
                "-i", f"anullsrc=channel_layout=mono:sample_rate={sample_rate}",
                "-t", str(silence_sec),
                "-b:a", f"{bitrate}",
                silence_path,
            ]
            silence_proc = await asyncio.to_thread(
                subprocess.run, silence_cmd,
                capture_output=True, check=False,
            )
            if silence_proc.returncode != 0:
                logger.error(
                    f"synthesize_multi_chunk: silence gen failed: "
                    f"{silence_proc.stderr.decode('utf-8', 'ignore')[:300]}"
                )
                # Fallback: glue without silence
                with open(list_path, "w") as f:
                    f.write(f"file '{head_path}'\nfile '{tail_path}'\n")
            else:
                with open(list_path, "w") as f:
                    f.write(
                        f"file '{head_path}'\n"
                        f"file '{silence_path}'\n"
                        f"file '{tail_path}'\n"
                    )

            # Concat — re-encode for safe boundary handling.
            concat_cmd = [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "concat", "-safe", "0",
                "-i", list_path,
                "-ar", str(sample_rate),
                "-ac", str(channel),
                "-b:a", f"{bitrate}",
                "-f", "mp3",
                out_path,
            ]
            concat_proc = await asyncio.to_thread(
                subprocess.run, concat_cmd,
                capture_output=True, check=False,
            )
            if concat_proc.returncode != 0:
                logger.error(
                    f"synthesize_multi_chunk: concat failed: "
                    f"{concat_proc.stderr.decode('utf-8', 'ignore')[:500]}; "
                    f"falling back to single-call synthesize()"
                )
                return await self.synthesize(
                    text,
                    voice_id=voice_id,
                    speed=speed,
                    vol=vol,
                    pitch=pitch,
                    emotion=emotion,
                    sample_rate=sample_rate,
                    bitrate=bitrate,
                    channel=channel,
                    pronunciation_dict=resolved_dict,
                    auto_resolve_pronunciation=False,
                    closing_emphasis=True,
                    timeout=timeout,
                )

            with open(out_path, "rb") as f:
                combined_bytes = f.read()

        total_latency_ms = int((time.perf_counter() - t0) * 1000)
        combined_cost = float(head_res.cost_usd) + float(tail_res.cost_usd)
        logger.info(
            f"synthesize_multi_chunk: head_ms={head_res.latency_ms} "
            f"tail_ms={tail_res.latency_ms} parallel_ms={parallel_ms} "
            f"total_ms={total_latency_ms} bytes={len(combined_bytes)} "
            f"cost=${combined_cost:.6f}"
        )

        return MinimaxTTSResult(
            audio_bytes=combined_bytes,
            audio_format="mp3",
            sample_rate=sample_rate,
            bitrate=bitrate,
            latency_ms=total_latency_ms,
            cost_usd=combined_cost,
            raw_response={
                "head": head_res.raw_response,
                "tail": tail_res.raw_response,
                "silence_ms": silence_ms,
            },
        )

    async def synthesize_and_upload(
        self,
        text: str,
        *,
        persona_id: str,
        voice_id: Optional[str] = None,
        **synth_kwargs: Any,
    ) -> tuple[MinimaxTTSResult, str]:
        """Convenience: synthesize → upload bytes to Supabase → return (result, public_url).

        Wiro talking-head models (MEMO/Pruna/Live-Avatar) take audio via URL, so
        we have to host the MP3 somewhere public.
        """
        from .supabase_storage import SupabaseStorage
        from datetime import datetime, timezone
        import uuid

        result = await self.synthesize(text, voice_id=voice_id, **synth_kwargs)

        # Map MiniMax format → standard MIME (Supabase rejects audio/mp3).
        _MIME_MAP = {"mp3": "audio/mpeg", "wav": "audio/wav", "pcm": "audio/L16"}
        mime = _MIME_MAP.get(result.audio_format, "application/octet-stream")

        day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        key = f"{persona_id}/{day}/tts/{uuid.uuid4().hex[:10]}.{result.audio_format}"
        storage = SupabaseStorage()
        upload = await storage.upload_bytes(
            bucket=settings.supabase_videos_bucket,
            key=key,
            data=result.audio_bytes,
            content_type=mime,
            upsert=True,
        )
        return result, upload.public_url
