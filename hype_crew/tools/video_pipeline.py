"""Phase 23 — Video pipeline: 4 modular strategies.

End-to-end: Türkçe TTS + (talking-head OR action OR hybrid OR Veo3 native)
→ FFmpeg composition (aspect + watermark + captions + encode + thumbnail)
→ Supabase Storage upload → return public URLs.

Strategies (all implement VideoPipeline protocol):
  A. TalkingHeadPipeline       — MEMO/Pruna + Chatterbox TTS Türkçe
  B. HybridCompositePipeline    — Seedance/Kling action + talking head, FFmpeg concat
  C. Veo3NativePipeline         — Google Veo3 sound=on (Türkçe support test)
  D. MemoSeedanceHybridPipeline — MEMO talking head + Seedance B-roll composite

Pilot experiment (PART 23.6): run all 4 with same script + anchor; side-by-side review.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

import httpx
from loguru import logger

from config import settings
from .minimax_tts_client import MinimaxTTSClient
from .supabase_storage import SupabaseStorage, UploadResult
from .wiro_client import WiroClient


# ─── TTS adapter (MiniMax direct — Cansu voice clone) ────────────────────────


@dataclass(frozen=True)
class TTSAsset:
    """Normalized TTS output used by every pipeline."""

    local_path: Path
    public_url: str          # Wiro talking-head needs HTTP URL
    duration_hint_sec: float  # Heuristic before ffprobe (caption fallback)
    cost_usd: float
    latency_ms: int


def _inject_pause_markers(text: str) -> str:
    """Insert MiniMax inline pause markers for cleaner pacing.

    Berkay 6 Haz 2026 — TTS rushed through sentence boundaries and the
    conclusion's final beat landed without breath.
    Berkay 10 Haz 2026 — 0.4/0.5 was too choppy on top of MiniMax's own
    natural period-pause; the narration felt halting. Trimmed to a light
    breath that ends the choppiness but keeps sentences from gluing:
      - `<#0.15#>` after each non-final sentence boundary
      - `<#0.2#>` immediately before the final sentence (the gavel)
    Idempotent: if `<#` already present in `text`, return unchanged.
    """
    import re as _re_pause
    if not text or "<#" in text:
        return text
    parts = [p.strip() for p in _re_pause.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    if len(parts) < 2:
        return text
    pieces: list[str] = []
    for i, p in enumerate(parts):
        if i == 0:
            pieces.append(p)
        elif i == len(parts) - 1:
            pieces.append(" <#0.2#> ")  # gavel pause (light)
            pieces.append(p)
        else:
            pieces.append(" <#0.15#> ")
            pieces.append(p)
    return "".join(pieces)


async def _synthesize_turkish_voice(
    *,
    text: str,
    persona_id: str,
    work_dir: Path,
    emotion: Optional[str] = None,
    speed: float = 1.0,
    inject_pauses: bool = True,
) -> TTSAsset:
    """Single source of truth for Türkçe Cansu voice.

    Uses MiniMax T2A v2 with the registered voice_id clone (proven working).
    Uploads the MP3 to Supabase so Wiro talking-head models can fetch it.

    Berkay 6 Haz 2026:
      - `speed` threads through to `synthesize_and_upload`. Default 1.0
        for compat; the video pipeline passes 0.9 (slower, more authoritative).
      - `inject_pauses` adds `<#0.4#>`/`<#0.5#>` markers at sentence
        boundaries + before the conclusion final line.
    """
    client = MinimaxTTSClient()
    effective_text = _inject_pause_markers(text) if inject_pauses else text
    result, public_url = await client.synthesize_and_upload(
        text=effective_text,
        persona_id=persona_id,
        emotion=emotion,
        speed=speed,
    )
    local_path = work_dir / "narration.mp3"
    local_path.write_bytes(result.audio_bytes)
    # Heuristic: ~4.5 words/sec Türkçe; refined later by ffprobe on final.
    words = len(text.split())
    duration_hint = max(2.0, words / 4.5)
    return TTSAsset(
        local_path=local_path,
        public_url=public_url,
        duration_hint_sec=duration_hint,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
    )


# ─── Dataclasses ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VideoBrief:
    """Input spec for any pipeline."""

    script_text: str                    # Türkçe narration text (TTS source)
    persona_id: str                     # personas.id (for storage path + DB linkage)
    anchor_image_url: str               # Cansu signed reference URL (talking head input)
    action_prompt: Optional[str] = None  # For action-video pipelines (Seedance/Kling/Veo)
    target_aspect: str = "9:16"          # 1080×1920 for Shorts/Reels
    target_duration: int = 15            # seconds total (action+talk)
    voice_clone_audio_url: Optional[str] = None  # If we want voice cloning
    daily_draft_id: Optional[str] = None
    # Optional pre-spend band override (cansu_video_v2 complete-news uses a
    # tighter ≤40s band than the legacy 510-1000). None → pre_spend defaults.
    script_min_chars: Optional[int] = None
    script_max_chars: Optional[int] = None
    # TTS kalite kapısı kötü ses bulursa script'i yeniden üretmek için (13 Haz 2026).
    topic: str = ""
    source: str = ""


@dataclass(frozen=True)
class StoredVideoAsset:
    """Output — uploaded video + thumbnail + cost metadata."""

    pipeline_used: str
    video_url: str                       # public Supabase URL
    thumbnail_url: str
    storage_key: str
    duration_sec: float
    file_size_bytes: int
    cost_usd: float                      # Sum of Wiro calls
    generation_latency_ms: int           # Total elapsed (TTS + video gen + FFmpeg + upload)
    raw_components: dict[str, Any] = field(default_factory=dict)


class VideoPipeline(Protocol):
    """Strategy protocol — produce_video(brief) → StoredVideoAsset."""
    pipeline_id: str

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset: ...


# ─── Common helpers ──────────────────────────────────────────────────────────


async def _download_asset(url: str, dest: Path, timeout: float = 90.0) -> Path:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(url)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


async def _regen_video_script(topic: str, source: str, bad_terms: list) -> Optional[str]:
    """TTS kalite kapısı kötü ses bulunca script'i feedback'le yeniden üret +
    assemble + lint — flow._resolve_complete_news_script ile aynı montaj.
    None → yenilenemedi (çağıran video'yu atlar). (13 Haz 2026)"""
    if not (topic and source):
        return None
    try:
        from .video_script_writer import (
            build_complete_news_script, assemble_complete_news, pick_outro,
        )
        from .tts_normalize import normalize_for_tts
        from .video_script_lint import lint_video_script
        fb = ", ".join(str(t) for t in (bad_terms or [])) or None
        body = await build_complete_news_script(topic=topic, source=source, avoid_feedback=fb)
        if not body:
            return None
        outro = pick_outro(topic)
        script = normalize_for_tts(assemble_complete_news(body, topic))
        if not lint_video_script(script, outro=outro).ok:
            return None
        return script
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[tts-gate] script yeniden üretim hata: {type(e).__name__}: {e}")
        return None


async def _run_ffmpeg(cmd: list[str], *, step: str, work_dir: Path) -> None:
    """Run FFmpeg sync via thread; raise on non-zero exit with stderr tail."""
    full_cmd = [settings.ffmpeg_path] + cmd
    logger.debug(f"ffmpeg.{step}: {' '.join(full_cmd[:6])} ...")
    result = await asyncio.to_thread(
        subprocess.run, full_cmd, capture_output=True, cwd=str(work_dir)
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="ignore")[-2000:]
        logger.error(f"ffmpeg.{step} FAILED rc={result.returncode}: {stderr}")
        raise RuntimeError(f"ffmpeg {step} failed: {stderr[-500:]}")


def _generate_turkish_srt(
    *, script_text: str, audio_duration_sec: float, output_srt: Path
) -> None:
    """Heuristic SRT: split script into ~3-sec chunks, distribute over audio duration."""
    words = script_text.split()
    if not words:
        output_srt.write_text("", encoding="utf-8")
        return
    chunk_size = max(3, min(10, int(len(words) / max(1, int(audio_duration_sec / 3.0)))))
    chunks = [words[i : i + chunk_size] for i in range(0, len(words), chunk_size)]
    n = len(chunks)
    lines = []
    for idx, chunk in enumerate(chunks):
        start_sec = (idx / n) * audio_duration_sec
        end_sec = ((idx + 1) / n) * audio_duration_sec
        start_ts = _format_srt_ts(start_sec)
        end_ts = _format_srt_ts(end_sec)
        lines.append(f"{idx + 1}")
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(" ".join(chunk))
        lines.append("")
    output_srt.write_text("\n".join(lines), encoding="utf-8")


def _format_srt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


async def _ffmpeg_force_9_16(src: Path, dst: Path, *, work_dir: Path) -> None:
    """Force 1080×1920 aspect — scale to fit then pad with black."""
    cmd = [
        "-i", str(src),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1",
        "-c:a", "copy",
        "-y", str(dst),
    ]
    await _run_ffmpeg(cmd, step="aspect_9_16", work_dir=work_dir)


async def _ffmpeg_replace_audio(
    video: Path, audio: Path, dst: Path, *, work_dir: Path
) -> None:
    """Replace video's audio track with the given audio (keep video stream)."""
    cmd = [
        "-i", str(video),
        "-i", str(audio),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-y", str(dst),
    ]
    await _run_ffmpeg(cmd, step="replace_audio", work_dir=work_dir)


async def _ffmpeg_concat_clips(
    clips: list[Path], dst: Path, *, work_dir: Path, re_encode: bool = True
) -> None:
    """Sequential concat via concat demuxer."""
    list_file = work_dir / "concat_list.txt"
    list_file.write_text(
        "\n".join(f"file '{c.absolute()}'" for c in clips),
        encoding="utf-8",
    )
    if re_encode:
        # Safer: re-encode (handles clips with different params)
        cmd = [
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264",
            "-preset", settings.ffmpeg_preset,
            "-c:a", "aac",
            "-b:a", "128k",
            "-y", str(dst),
        ]
    else:
        cmd = [
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            "-y", str(dst),
        ]
    await _run_ffmpeg(cmd, step="concat", work_dir=work_dir)


async def _ffmpeg_burn_watermark(src: Path, dst: Path, *, work_dir: Path) -> None:
    """Phase 35.3 / Berkay 30 May 2026 — Watermark removed ("asla istemiyorum").

    Kept as a no-op pass-through so existing callers (TalkingHead, Hybrid,
    Veo3, MemoSeedance, HeyGenAvatarV pipelines) keep working without edits.
    Simply copies src → dst without modification.
    """
    # Use shutil.copyfile via run-in-thread for symmetry with other ffmpeg ops.
    await asyncio.to_thread(shutil.copyfile, str(src), str(dst))


async def _ffmpeg_burn_captions(
    src: Path, srt: Path, dst: Path, *, work_dir: Path
) -> None:
    """Burn Türkçe captions into a 9:16 1080×1920 video.

    Locked Cansu spec (Berkay 5 Haz 2026):
      - PlayResX=1080, PlayResY=1920 — design canvas == video resolution
        so FontSize is honored 1:1 (libass otherwise auto-scales and the
        text becomes huge at 22pt).
      - FontSize=54 Bold — ~2.8% frame-height per line, readable on
        portrait mobile.
      - MarginV=400 anchors the bottom-line baseline at y≈1520, the clear
        band just above the laptop and well below the chin/lapel-mic.
      - WrapStyle=0 forces smart 2-line wrapping.
      - White text + 2px black outline, no shadow.
    """
    style = (
        "PlayResX=1080,PlayResY=1920,"
        "FontName=DejaVuSans,FontSize=54,Bold=1,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BackColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=0,"
        "MarginL=80,MarginR=80,MarginV=400,Alignment=2,"
        "WrapStyle=0"
    )
    # Run ffmpeg from the SRT's parent dir so we pass the basename — this
    # sidesteps libass's colon-escape requirement that mangles absolute
    # paths on some filesystems.
    cmd = [
        "-i", src.name,
        "-vf", f"subtitles={srt.name}:force_style='{style}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        "-y", dst.name,
    ]
    await _run_ffmpeg(cmd, step="captions", work_dir=srt.parent)


async def _ffmpeg_final_encode(src: Path, dst: Path, *, work_dir: Path) -> None:
    """H.264 final, 6.5 Mbps target, faststart for streaming."""
    bitrate_kbps = settings.video_bitrate_kbps
    cmd = [
        "-i", str(src),
        "-c:v", "libx264",
        "-preset", settings.ffmpeg_preset,
        "-profile:v", "high",
        "-level:v", "4.1",
        "-b:v", f"{bitrate_kbps}k",
        "-maxrate", f"{int(bitrate_kbps * 1.3)}k",
        "-bufsize", f"{bitrate_kbps * 2}k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-y", str(dst),
    ]
    await _run_ffmpeg(cmd, step="final_encode", work_dir=work_dir)


async def _ffmpeg_split_screen_vstack(
    heygen_video: Path,
    image_paths: list[Path],
    dst: Path,
    *,
    work_dir: Path,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    target_duration: Optional[float] = None,
    ken_burns_zoom_step: float = 0.0008,
    fps: int = 30,
) -> None:
    """Phase 35.3 — Compose split-screen video: image slideshow (top) + HeyGen video (bottom).

    Layout (canvas_w × canvas_h, default 1080×1920):
      - Top half (canvas_w × canvas_h/2): N image slideshow with Ken Burns zoom
      - Bottom half (canvas_w × canvas_h/2): HeyGen Avatar V Cansu video (audio preserved)

    Args:
        heygen_video: HeyGen Avatar V MP4 (provides audio + bottom visual).
        image_paths: 1-5 image files (jpg/png). Each will display equally for
            target_duration/N seconds with subtle Ken Burns zoom-in.
        target_duration: Optional override (sec); if None, derive from HeyGen
            audio duration via ffprobe.
        ken_burns_zoom_step: Per-frame zoom increment (~0.0008 = slow cinematic).

    Raises:
        ValueError if image_paths is empty.
        RuntimeError on FFmpeg failure.
    """
    if not image_paths:
        raise ValueError("split_screen_vstack: image_paths must not be empty")

    if target_duration is None or target_duration <= 0:
        target_duration = _probe_duration(heygen_video) or 15.0

    half_h = canvas_h // 2  # 960 for 1080×1920
    n_images = len(image_paths)
    # Phase 35.3 — Berkay 30 May 2026 requested 1sec freeze after audio ends.
    # We extend the visual track by `tail_freeze_sec` while audio plays its
    # normal length; the last frame holds for the extra second.
    tail_freeze_sec = 1.0
    visual_total = target_duration + tail_freeze_sec
    per_image_sec = max(1.5, visual_total / n_images)

    # Build FFmpeg inputs: heygen first (index 0), then images.
    inputs: list[str] = ["-i", str(heygen_video)]
    for img in image_paths:
        inputs.extend([
            "-framerate", str(fps),
            "-loop", "1",
            "-t", f"{per_image_sec:.3f}",
            "-i", str(img),
        ])

    # Build filter_complex
    filter_parts: list[str] = []

    # Top slideshow: per image scale-to-cover + crop + uniform format/SAR/fps.
    # `pad=...:color=black` guarantees no white edges if scale leaves any
    # fractional gap (was the "beyaz boşluklar" bug).
    for idx in range(n_images):
        input_idx = idx + 1  # heygen is 0
        filter_parts.append(
            f"[{input_idx}:v]"
            f"scale={canvas_w}:{half_h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={canvas_w}:{half_h}:exact=1,"
            f"pad={canvas_w}:{half_h}:0:0:color=black,"
            f"format=yuv420p,setsar=1,fps={fps},"
            f"trim=duration={per_image_sec:.3f},"
            f"setpts=PTS-STARTPTS[img{idx}]"
        )
    # Concat images
    concat_inputs = "".join(f"[img{idx}]" for idx in range(n_images))
    filter_parts.append(f"{concat_inputs}concat=n={n_images}:v=1:a=0[top]")

    # Bottom: HeyGen video scale+crop to canvas_w×half_h (cover fit) +
    # tpad freezes the last frame for `tail_freeze_sec` to match the top
    # slideshow's extended duration.
    filter_parts.append(
        f"[0:v]"
        f"scale={canvas_w}:{half_h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={canvas_w}:{half_h}:exact=1,"
        f"pad={canvas_w}:{half_h}:0:0:color=black,"
        f"format=yuv420p,setsar=1,fps={fps},"
        f"tpad=stop_mode=clone:stop_duration={tail_freeze_sec:.3f},"
        f"setpts=PTS-STARTPTS[bottom]"
    )

    # Audio: also pad with 1sec silence at the end so it stays in sync with
    # the extended video track.
    filter_parts.append(
        f"[0:a]apad=pad_dur={tail_freeze_sec:.3f}[outa]"
    )

    # Vstack top + bottom → final canvas
    filter_parts.append("[top][bottom]vstack=inputs=2[v]")

    filter_complex = ";".join(filter_parts)

    cmd = [
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", settings.ffmpeg_preset,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-r", str(fps),
        "-t", f"{visual_total:.3f}",
        "-movflags", "+faststart",
        "-y", str(dst),
    ]
    await _run_ffmpeg(cmd, step="split_screen_vstack", work_dir=work_dir)


async def _ffmpeg_thumbnail(src: Path, dst: Path, *, work_dir: Path) -> None:
    """Extract frame at 1.5 sec as 1280×720 JPG."""
    cmd = [
        "-i", str(src),
        "-ss", "1.5",
        "-vframes", "1",
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black",
        "-q:v", "5",
        "-y", str(dst),
    ]
    await _run_ffmpeg(cmd, step="thumbnail", work_dir=work_dir)


def _probe_duration(path: Path) -> float:
    """Use ffprobe to get duration in seconds."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, check=True,
        )
        return float(result.stdout.decode().strip())
    except Exception as e:
        logger.warning(f"ffprobe duration failed: {e}; returning 0")
        return 0.0


async def _upload_video_assets(
    *,
    persona_id: str,
    video_file: Path,
    thumbnail_file: Path,
    pipeline_id: str,
    storage: Optional[SupabaseStorage] = None,
) -> tuple[UploadResult, UploadResult]:
    """Upload final video + thumbnail to Supabase persona-videos bucket."""
    storage_client = storage or SupabaseStorage()
    day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    vid_uuid = str(uuid.uuid4())[:8]
    video_key = f"{persona_id}/{day}/{pipeline_id}_{vid_uuid}.mp4"
    thumb_key = f"{persona_id}/{day}/{pipeline_id}_{vid_uuid}_thumb.jpg"

    video_bytes = video_file.read_bytes()
    thumb_bytes = thumbnail_file.read_bytes()

    upload_v = await storage_client.upload_bytes(
        bucket=settings.supabase_videos_bucket,
        key=video_key,
        data=video_bytes,
        content_type="video/mp4",
        upsert=True,
    )
    upload_t = await storage_client.upload_bytes(
        bucket=settings.supabase_videos_bucket,
        key=thumb_key,
        data=thumb_bytes,
        content_type="image/jpeg",
        upsert=True,
    )
    return upload_v, upload_t


# ─── Strategy A — Talking Head Only ──────────────────────────────────────────


class TalkingHeadPipeline:
    """Pipeline A — single talking head video, lip-synced to Türkçe TTS.

    Steps:
      1. Wiro Chatterbox TTS → .mp3 (Türkçe)
      2. Wiro MEMO/Pruna → talking video (anchor + .mp3)
      3. FFmpeg 9:16 force + watermark + captions + final encode + thumbnail
      4. Supabase upload
    """

    pipeline_id = "talking_head_memo"

    # NOTE: Despite the pipeline_id retaining "memo" for historical / DB-key
    # reasons, the default slug is now Pruna because MEMO crashes on Wiro
    # workers (pexit=-999, observed 2026-05-17 task 1887734). Override via
    # constructor arg to force MEMO if/when fixed upstream.
    def __init__(self, talking_head_slug: str = "pruna/p-video-avatar"):
        self.talking_head_slug = talking_head_slug

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset:
        t0 = time.perf_counter()
        work_dir = Path(tempfile.mkdtemp(prefix=f"hype_video_a_{brief.persona_id[:8]}_"))
        total_cost = 0.0
        components: dict[str, Any] = {}

        try:
            # 1. TTS — MiniMax Cansu voice clone (Türkçe)
            logger.info(f"[pipeline=A] step 1/4 TTS → MiniMax (Cansu voice clone)")
            tts = await _synthesize_turkish_voice(
                text=brief.script_text,
                persona_id=brief.persona_id,
                work_dir=work_dir,
            )
            total_cost += tts.cost_usd
            components["tts"] = {
                "public_url": tts.public_url,
                "cost": tts.cost_usd,
                "latency_ms": tts.latency_ms,
                "provider": "minimax",
                "voice_id": settings.minimax_voice_id_cansu,
            }

            # 2. Talking-head video (anchor + audio → lip-synced).
            # videoPrompt = scene/style direction for Pruna; defaults to a
            # cinematic Cansu-flavoured setting if caller didn't override.
            default_video_prompt = (
                brief.action_prompt or
                "Young woman speaking to camera in soft natural daylight, "
                "warm cinematic tones, candid documentary feel, subtle "
                "expression changes, no rapid motion, 1080p sharp focus, "
                "shallow depth of field, real-skin texture, no overly smooth "
                "AI-look, no plastic skin"
            )
            logger.info(f"[pipeline=A] step 2/4 talking head ({self.talking_head_slug}) @1080p")
            async with WiroClient() as client:
                avatar_result = await client.generate_talking_avatar(
                    portrait_url=brief.anchor_image_url,
                    audio_url=tts.public_url,
                    slug=self.talking_head_slug,
                    resolution=1080,
                    videoPrompt=default_video_prompt,
                )
                total_cost += avatar_result.cost_usd
                components["talking_head"] = {
                    "asset_url": avatar_result.asset_url,
                    "cost": avatar_result.cost_usd,
                    "latency_ms": avatar_result.latency_ms,
                    "slug": self.talking_head_slug,
                }
                raw_video = work_dir / "raw_talking.mp4"
                await _download_asset(avatar_result.asset_url, raw_video)

            duration = _probe_duration(raw_video)

            # 3. FFmpeg: 9:16 → watermark → captions → final encode
            logger.info(f"[pipeline=A] step 3/4 FFmpeg composition")
            aspect_out = work_dir / "step_aspect.mp4"
            await _ffmpeg_force_9_16(raw_video, aspect_out, work_dir=work_dir)

            srt_file = work_dir / "captions.srt"
            _generate_turkish_srt(
                script_text=brief.script_text,
                audio_duration_sec=duration,
                output_srt=srt_file,
            )

            current = aspect_out
            try:
                watermarked = work_dir / "step_watermark.mp4"
                await _ffmpeg_burn_watermark(current, watermarked, work_dir=work_dir)
                current = watermarked
            except RuntimeError as e:
                logger.warning(f"[pipeline=A] watermark skipped (drawtext unavailable): {e}")
            try:
                captioned = work_dir / "step_captions.mp4"
                await _ffmpeg_burn_captions(current, srt_file, captioned, work_dir=work_dir)
                current = captioned
            except RuntimeError as e:
                logger.warning(f"[pipeline=A] captions skipped: {e}")

            final_video = work_dir / "final.mp4"
            await _ffmpeg_final_encode(current, final_video, work_dir=work_dir)

            thumbnail = work_dir / "thumbnail.jpg"
            await _ffmpeg_thumbnail(final_video, thumbnail, work_dir=work_dir)

            # 4. Upload
            logger.info(f"[pipeline=A] step 4/4 Supabase upload")
            upload_v, upload_t = await _upload_video_assets(
                persona_id=brief.persona_id,
                video_file=final_video,
                thumbnail_file=thumbnail,
                pipeline_id=self.pipeline_id,
            )

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.success(
                f"[pipeline=A] DONE cost=${total_cost:.3f} elapsed={elapsed_ms / 1000:.1f}s"
            )

            return StoredVideoAsset(
                pipeline_used=self.pipeline_id,
                video_url=upload_v.public_url,
                thumbnail_url=upload_t.public_url,
                storage_key=upload_v.storage_key,
                duration_sec=duration,
                file_size_bytes=upload_v.size_bytes,
                cost_usd=total_cost,
                generation_latency_ms=elapsed_ms,
                raw_components=components,
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


# ─── Strategy B — Hybrid (Seedance action + talking head composite) ──────────


class HybridCompositePipeline:
    """Pipeline B — action B-roll opening (Seedance) + talking head closing (MEMO).

    Sequence: [Seedance action ~7s, no audio] → [MEMO talking head ~8s with audio]
    Total: ~15s
    """

    pipeline_id = "hybrid_seedance_memo"

    def __init__(
        self,
        action_slug: str = "bytedance/seedance-2-0",
        talking_head_slug: str = "pruna/p-video-avatar",
    ):
        self.action_slug = action_slug
        self.talking_head_slug = talking_head_slug

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset:
        t0 = time.perf_counter()
        work_dir = Path(tempfile.mkdtemp(prefix=f"hype_video_b_{brief.persona_id[:8]}_"))
        total_cost = 0.0
        components: dict[str, Any] = {}

        try:
            # Parallel: MiniMax TTS + Wiro action clip
            tts_task = _synthesize_turkish_voice(
                text=brief.script_text,
                persona_id=brief.persona_id,
                work_dir=work_dir,
            )
            async with WiroClient() as client:
                action_task = client.generate_action_video(
                    prompt=brief.action_prompt or
                          "casual workspace shot, soft natural light, intimate documentary feel",
                    slug=self.action_slug,
                    input_image_url=brief.anchor_image_url,
                    aspect_ratio="9:16",
                    duration="5",
                    generate_audio=False,
                )
                tts, action_result = await asyncio.gather(tts_task, action_task)

            total_cost += tts.cost_usd + action_result.cost_usd
            components["tts"] = {
                "public_url": tts.public_url,
                "cost": tts.cost_usd,
                "provider": "minimax",
            }
            components["action"] = {
                "asset_url": action_result.asset_url,
                "cost": action_result.cost_usd,
                "slug": self.action_slug,
            }

            action_file = work_dir / "action.mp4"
            await _download_asset(action_result.asset_url, action_file)

            # Talking head — MiniMax audio already uploaded to Supabase
            async with WiroClient() as client:
                avatar_result = await client.generate_talking_avatar(
                    portrait_url=brief.anchor_image_url,
                    audio_url=tts.public_url,
                    slug=self.talking_head_slug,
                    resolution=720,
                )
            total_cost += avatar_result.cost_usd
            components["talking_head"] = {
                "asset_url": avatar_result.asset_url,
                "cost": avatar_result.cost_usd,
                "slug": self.talking_head_slug,
            }
            talking_file = work_dir / "talking.mp4"
            await _download_asset(avatar_result.asset_url, talking_file)

            # Force both clips to 9:16
            action_916 = work_dir / "action_916.mp4"
            talking_916 = work_dir / "talking_916.mp4"
            await _ffmpeg_force_9_16(action_file, action_916, work_dir=work_dir)
            await _ffmpeg_force_9_16(talking_file, talking_916, work_dir=work_dir)

            # Concat (re-encode to harmonize streams)
            composite = work_dir / "composite.mp4"
            await _ffmpeg_concat_clips(
                [action_916, talking_916], composite, work_dir=work_dir, re_encode=True
            )

            # Watermark + captions + final
            duration = _probe_duration(composite)
            srt_file = work_dir / "captions.srt"
            # Captions only over the talking-head portion (last ~50% of composite)
            _generate_turkish_srt(
                script_text=brief.script_text,
                audio_duration_sec=duration * 0.55,  # rough — talking head dominates
                output_srt=srt_file,
            )

            current = composite
            try:
                watermarked = work_dir / "step_wm.mp4"
                await _ffmpeg_burn_watermark(current, watermarked, work_dir=work_dir)
                current = watermarked
            except RuntimeError as e:
                logger.warning(f"[pipeline=B] watermark skipped: {e}")
            try:
                captioned = work_dir / "step_cap.mp4"
                await _ffmpeg_burn_captions(current, srt_file, captioned, work_dir=work_dir)
                current = captioned
            except RuntimeError as e:
                logger.warning(f"[pipeline=B] captions skipped: {e}")
            final_video = work_dir / "final.mp4"
            await _ffmpeg_final_encode(current, final_video, work_dir=work_dir)
            thumbnail = work_dir / "thumbnail.jpg"
            await _ffmpeg_thumbnail(final_video, thumbnail, work_dir=work_dir)

            upload_v, upload_t = await _upload_video_assets(
                persona_id=brief.persona_id,
                video_file=final_video,
                thumbnail_file=thumbnail,
                pipeline_id=self.pipeline_id,
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.success(
                f"[pipeline=B] DONE cost=${total_cost:.3f} elapsed={elapsed_ms / 1000:.1f}s"
            )

            return StoredVideoAsset(
                pipeline_used=self.pipeline_id,
                video_url=upload_v.public_url,
                thumbnail_url=upload_t.public_url,
                storage_key=upload_v.storage_key,
                duration_sec=duration,
                file_size_bytes=upload_v.size_bytes,
                cost_usd=total_cost,
                generation_latency_ms=elapsed_ms,
                raw_components=components,
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


# ─── Strategy C — Veo3 native ────────────────────────────────────────────────


class Veo3NativePipeline:
    """Pipeline C — Google Veo3 sound=on, generate audio+video natively.

    Türkçe support is unverified — pilot test will reveal whether Veo3 voices
    Türkçe acceptably. If not, we fall back to A/B/D.
    """

    pipeline_id = "veo3_native"

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset:
        t0 = time.perf_counter()
        work_dir = Path(tempfile.mkdtemp(prefix=f"hype_video_c_{brief.persona_id[:8]}_"))
        total_cost = 0.0
        components: dict[str, Any] = {}

        try:
            # Veo3 dialogue colon format prompt
            full_prompt = (
                f"{brief.action_prompt or 'natural workspace setting'}. "
                f"Cansu says: \"{brief.script_text}\""
            )
            logger.info(f"[pipeline=C] Veo3 sound=on")
            async with WiroClient() as client:
                veo_result = await client.generate_action_video(
                    prompt=full_prompt,
                    slug="google/veo3",
                    input_image_url=brief.anchor_image_url,
                    aspect_ratio="9:16",
                    duration="8",
                    resolution="1080p",
                    generate_audio=True,
                )
            total_cost += veo_result.cost_usd
            components["veo3"] = {
                "asset_url": veo_result.asset_url,
                "cost": veo_result.cost_usd,
                "prompt": full_prompt[:300],
            }
            raw_video = work_dir / "veo3.mp4"
            await _download_asset(veo_result.asset_url, raw_video)

            duration = _probe_duration(raw_video)

            # Aspect + watermark + final
            aspect_out = work_dir / "step_aspect.mp4"
            await _ffmpeg_force_9_16(raw_video, aspect_out, work_dir=work_dir)

            srt_file = work_dir / "captions.srt"
            _generate_turkish_srt(
                script_text=brief.script_text,
                audio_duration_sec=duration,
                output_srt=srt_file,
            )

            current = aspect_out
            try:
                watermarked = work_dir / "step_wm.mp4"
                await _ffmpeg_burn_watermark(current, watermarked, work_dir=work_dir)
                current = watermarked
            except RuntimeError as e:
                logger.warning(f"[pipeline=C] watermark skipped: {e}")
            try:
                captioned = work_dir / "step_cap.mp4"
                await _ffmpeg_burn_captions(current, srt_file, captioned, work_dir=work_dir)
                current = captioned
            except RuntimeError as e:
                logger.warning(f"[pipeline=C] captions skipped: {e}")
            final_video = work_dir / "final.mp4"
            await _ffmpeg_final_encode(current, final_video, work_dir=work_dir)
            thumbnail = work_dir / "thumbnail.jpg"
            await _ffmpeg_thumbnail(final_video, thumbnail, work_dir=work_dir)

            upload_v, upload_t = await _upload_video_assets(
                persona_id=brief.persona_id,
                video_file=final_video,
                thumbnail_file=thumbnail,
                pipeline_id=self.pipeline_id,
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.success(
                f"[pipeline=C] DONE cost=${total_cost:.3f} elapsed={elapsed_ms / 1000:.1f}s"
            )

            return StoredVideoAsset(
                pipeline_used=self.pipeline_id,
                video_url=upload_v.public_url,
                thumbnail_url=upload_t.public_url,
                storage_key=upload_v.storage_key,
                duration_sec=duration,
                file_size_bytes=upload_v.size_bytes,
                cost_usd=total_cost,
                generation_latency_ms=elapsed_ms,
                raw_components=components,
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


# ─── Strategy D — MEMO + Seedance hybrid (more aggressive) ───────────────────


class MemoSeedanceHybridPipeline(HybridCompositePipeline):
    """Pipeline D — same as B but talking head first, action B-roll second.

    Useful if voiceover should start immediately and B-roll visualises after.
    """

    pipeline_id = "memo_seedance_v2"

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset:
        t0 = time.perf_counter()
        work_dir = Path(tempfile.mkdtemp(prefix=f"hype_video_d_{brief.persona_id[:8]}_"))
        total_cost = 0.0
        components: dict[str, Any] = {}

        try:
            # Reverse of B: talking head first, action after (parallel TTS + action)
            tts_task = _synthesize_turkish_voice(
                text=brief.script_text,
                persona_id=brief.persona_id,
                work_dir=work_dir,
            )
            async with WiroClient() as client:
                action_task = client.generate_action_video(
                    prompt=brief.action_prompt or
                          "cinematic close-up of laptop screen, hands typing, soft ambient light",
                    slug=self.action_slug,
                    input_image_url=brief.anchor_image_url,
                    aspect_ratio="9:16",
                    duration="5",
                    generate_audio=False,
                )
                tts, action_result = await asyncio.gather(tts_task, action_task)
            total_cost += tts.cost_usd + action_result.cost_usd
            components["tts"] = {
                "public_url": tts.public_url,
                "cost": tts.cost_usd,
                "provider": "minimax",
            }
            components["action"] = {
                "asset_url": action_result.asset_url,
                "cost": action_result.cost_usd,
            }

            action_file = work_dir / "action.mp4"
            await _download_asset(action_result.asset_url, action_file)

            async with WiroClient() as client:
                avatar_result = await client.generate_talking_avatar(
                    portrait_url=brief.anchor_image_url,
                    audio_url=tts.public_url,
                    slug=self.talking_head_slug,
                    resolution=720,
                )
            total_cost += avatar_result.cost_usd
            components["talking_head"] = {"asset_url": avatar_result.asset_url, "cost": avatar_result.cost_usd}
            talking_file = work_dir / "talking.mp4"
            await _download_asset(avatar_result.asset_url, talking_file)

            action_916 = work_dir / "action_916.mp4"
            talking_916 = work_dir / "talking_916.mp4"
            await _ffmpeg_force_9_16(action_file, action_916, work_dir=work_dir)
            await _ffmpeg_force_9_16(talking_file, talking_916, work_dir=work_dir)

            # Reverse order: talking head first, action last
            composite = work_dir / "composite.mp4"
            await _ffmpeg_concat_clips(
                [talking_916, action_916], composite, work_dir=work_dir, re_encode=True
            )

            duration = _probe_duration(composite)
            srt_file = work_dir / "captions.srt"
            _generate_turkish_srt(
                script_text=brief.script_text,
                audio_duration_sec=duration * 0.55,
                output_srt=srt_file,
            )

            current = composite
            try:
                watermarked = work_dir / "step_wm.mp4"
                await _ffmpeg_burn_watermark(current, watermarked, work_dir=work_dir)
                current = watermarked
            except RuntimeError as e:
                logger.warning(f"[pipeline=D] watermark skipped: {e}")
            try:
                captioned = work_dir / "step_cap.mp4"
                await _ffmpeg_burn_captions(current, srt_file, captioned, work_dir=work_dir)
                current = captioned
            except RuntimeError as e:
                logger.warning(f"[pipeline=D] captions skipped: {e}")
            final_video = work_dir / "final.mp4"
            await _ffmpeg_final_encode(current, final_video, work_dir=work_dir)
            thumbnail = work_dir / "thumbnail.jpg"
            await _ffmpeg_thumbnail(final_video, thumbnail, work_dir=work_dir)

            upload_v, upload_t = await _upload_video_assets(
                persona_id=brief.persona_id,
                video_file=final_video,
                thumbnail_file=thumbnail,
                pipeline_id=self.pipeline_id,
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.success(
                f"[pipeline=D] DONE cost=${total_cost:.3f} elapsed={elapsed_ms / 1000:.1f}s"
            )

            return StoredVideoAsset(
                pipeline_used=self.pipeline_id,
                video_url=upload_v.public_url,
                thumbnail_url=upload_t.public_url,
                storage_key=upload_v.storage_key,
                duration_sec=duration,
                file_size_bytes=upload_v.size_bytes,
                cost_usd=total_cost,
                generation_latency_ms=elapsed_ms,
                raw_components=components,
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


# ─── Strategy E — Kling V3 Omni Voice-Over (PIVOT primary 2026-05-17) ────────


class KlingVoiceoverPipeline:
    """Voice-over architecture — Kling silent action + MiniMax TTS overlay.

    No lip-sync. Cansu appears on camera with ambient motion (no talking).
    MiniMax Türkçe voice plays over, Türkçe captions burn-in. Avoids the
    "obviously AI" face distortion of lip-sync models.

    Steps:
      1. PARALLEL: MiniMax TTS (Türkçe) + Kling V3 Omni action (silent)
      2. Replace Kling's silent track with MiniMax MP3
      3. Force 9:16 + watermark + Türkçe captions + final encode
      4. Supabase upload
    """

    pipeline_id = "kling_voiceover"

    def __init__(
        self,
        kling_slug: str = "klingai/kling-v3-omni",
        kling_mode: str = "std",         # std / pro / 4k — std = $0.42/5s 1080p
        kling_duration: str = "5",       # 5 or 10
    ):
        self.kling_slug = kling_slug
        self.kling_mode = kling_mode
        self.kling_duration = kling_duration

    async def _resolve_anchor_urls(self, persona_id: str) -> list[str]:
        """Up to 3 anchor signed URLs (Kling supports inputImage + 2 + 3 for
        identity consistency). Returns the deterministic selection from
        reference_anchors heuristic."""
        from .reference_anchors import (
            load_persona_anchors, prepare_reference_prompt_inputs,
        )
        anchors = await load_persona_anchors(persona_id)
        if not anchors:
            raise RuntimeError(f"persona {persona_id} has no reference anchors")
        refs = await prepare_reference_prompt_inputs(anchors, max_prompt_inputs=3)
        return list(refs.signed_reference_urls)

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset:
        t0 = time.perf_counter()
        work_dir = Path(tempfile.mkdtemp(prefix=f"hype_video_kvo_{brief.persona_id[:8]}_"))
        total_cost = 0.0
        components: dict[str, Any] = {}

        try:
            # 1. PARALLEL: TTS + Kling action gen
            #    TTS uploads itself to Supabase (public URL — but we only need
            #    the MP3 bytes for ffmpeg, not for Kling). Kling generates
            #    silent video — we'll overlay TTS audio in step 2.
            logger.info(f"[pipeline=kling_voiceover] step 1/3 TTS + Kling action (parallel)")

            tts_task = _synthesize_turkish_voice(
                text=brief.script_text,
                persona_id=brief.persona_id,
                work_dir=work_dir,
            )

            # Resolve up to 3 anchor URLs for Kling identity consistency
            anchor_urls = await self._resolve_anchor_urls(brief.persona_id)
            anchor_1 = anchor_urls[0]
            anchor_2 = anchor_urls[1] if len(anchor_urls) > 1 else None
            anchor_3 = anchor_urls[2] if len(anchor_urls) > 2 else None

            # Scene-only prompt (NO dialogue, NO "X says" — Kling produces
            # action video, MiniMax handles the speech audio).
            scene_prompt = brief.action_prompt or (
                "Young Turkish woman quietly working at her home office desk, "
                "soft natural daylight, subtle hand gesture, looking thoughtfully "
                "at her MacBook, warm cinematic tones, candid documentary feel, "
                "photoreal skin texture, gentle micro-expressions only"
            )
            kling_negative = (
                "talking, speaking, mouth moving, lip sync, dialogue, "
                "distorted face, melting features, warped identity, "
                "low quality, watermark, text overlay, jittery motion"
            )

            async with WiroClient() as client:
                kling_task = client.generate_action_video(
                    prompt=scene_prompt,
                    slug=self.kling_slug,
                    input_image_url=anchor_1,
                    aspect_ratio="9:16",
                    duration=self.kling_duration,
                    generate_audio=False,           # silent — TTS overlays
                    negative_prompt=kling_negative,
                    mode=self.kling_mode,
                    refer_type="feature",
                    original_sound="no",
                    input_image_url_2=anchor_2,
                    input_image_url_3=anchor_3,
                )
                tts, kling_result = await asyncio.gather(tts_task, kling_task)

            total_cost += tts.cost_usd + kling_result.cost_usd
            components["tts"] = {
                "public_url": tts.public_url,
                "cost": tts.cost_usd,
                "provider": "minimax",
            }
            components["kling"] = {
                "asset_url": kling_result.asset_url,
                "cost": kling_result.cost_usd,
                "slug": self.kling_slug,
                "mode": self.kling_mode,
                "duration": self.kling_duration,
                "anchor_count": len(anchor_urls),
            }

            # 2. Download Kling silent video
            raw_video = work_dir / "kling_raw.mp4"
            await _download_asset(kling_result.asset_url, raw_video)

            # 3. FFmpeg composition
            logger.info(f"[pipeline=kling_voiceover] step 2/3 FFmpeg composition")

            # 3a. Replace Kling's silent audio track with MiniMax narration
            with_audio = work_dir / "with_audio.mp4"
            await _ffmpeg_replace_audio(
                raw_video, tts.local_path, with_audio, work_dir=work_dir,
            )

            # 3b. Ensure 9:16 (Kling should already be 9:16, but enforce)
            aspect_out = work_dir / "step_aspect.mp4"
            await _ffmpeg_force_9_16(with_audio, aspect_out, work_dir=work_dir)

            # 3c. Generate Türkçe SRT timed to final video duration
            duration = _probe_duration(aspect_out)
            srt_file = work_dir / "captions.srt"
            _generate_turkish_srt(
                script_text=brief.script_text,
                audio_duration_sec=duration,
                output_srt=srt_file,
            )

            current = aspect_out
            try:
                watermarked = work_dir / "step_wm.mp4"
                await _ffmpeg_burn_watermark(current, watermarked, work_dir=work_dir)
                current = watermarked
            except RuntimeError as e:
                logger.warning(f"[pipeline=kling_voiceover] watermark skipped: {e}")
            try:
                captioned = work_dir / "step_cap.mp4"
                await _ffmpeg_burn_captions(current, srt_file, captioned, work_dir=work_dir)
                current = captioned
            except RuntimeError as e:
                logger.warning(f"[pipeline=kling_voiceover] captions skipped: {e}")

            final_video = work_dir / "final.mp4"
            await _ffmpeg_final_encode(current, final_video, work_dir=work_dir)
            thumbnail = work_dir / "thumbnail.jpg"
            await _ffmpeg_thumbnail(final_video, thumbnail, work_dir=work_dir)

            # 4. Upload to Supabase persona-videos
            logger.info(f"[pipeline=kling_voiceover] step 3/3 Supabase upload")
            upload_v, upload_t = await _upload_video_assets(
                persona_id=brief.persona_id,
                video_file=final_video,
                thumbnail_file=thumbnail,
                pipeline_id=self.pipeline_id,
            )

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.success(
                f"[pipeline=kling_voiceover] DONE cost=${total_cost:.3f} "
                f"elapsed={elapsed_ms / 1000:.1f}s"
            )

            return StoredVideoAsset(
                pipeline_used=self.pipeline_id,
                video_url=upload_v.public_url,
                thumbnail_url=upload_t.public_url,
                storage_key=upload_v.storage_key,
                duration_sec=duration,
                file_size_bytes=upload_v.size_bytes,
                cost_usd=total_cost,
                generation_latency_ms=elapsed_ms,
                raw_components=components,
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


# ─── Strategy F — Seedance Voice-Over Fallback (AI-image input) ──────────────


class SeedanceVoiceoverPipeline:
    """Fallback pipeline — Seedance with AI-generated Cansu image to bypass
    ByteDance's real-person privacy filter.

    Uses the most recent generated_image from persona_assets (Phase 21
    visual_director output) as the inputImage. AI-rendered faces pass the
    Seedance detector, real photo references do not.

    Same voice-over architecture as KlingVoiceoverPipeline: silent Seedance
    action + MiniMax TTS overlay + Türkçe captions.
    """

    pipeline_id = "seedance_voiceover"

    def __init__(
        self,
        seedance_slug: str = "bytedance/seedance-2-0",
        duration: str = "5",
    ):
        self.seedance_slug = seedance_slug
        self.duration = duration

    async def _resolve_ai_image_url(self, persona_id: str) -> Optional[str]:
        """Pull most recent AI-generated Cansu image (public_url, compliance
        passed preferred, NEEDS_REVIEW acceptable). None means no usable image
        — caller can fall back to KlingVoiceoverPipeline."""
        from .supabase_client import make_supabase
        sb = make_supabase()
        try:
            r = (
                sb.table("persona_assets")
                .select("public_url, llm_judge_verdict, compliance_passed, aesthetic_score, created_at")
                .eq("persona_id", persona_id)
                .eq("asset_type", "generated_image")
                .not_.is_("public_url", "null")
                .order("compliance_passed", desc=True)
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            rows = r.data or []
            # Prefer compliance_passed True with highest aesthetic
            passed = [it for it in rows if it.get("compliance_passed")]
            if passed:
                return passed[0]["public_url"]
            # Fallback NEEDS_REVIEW with usable public_url
            for it in rows:
                if it.get("public_url") and it.get("llm_judge_verdict") in ("NEEDS_REVIEW", "PASS"):
                    return it["public_url"]
            if rows:
                return rows[0]["public_url"]
        except Exception as e:
            logger.warning(f"[seedance_voiceover] _resolve_ai_image_url failed: {e}")
        return None

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset:
        t0 = time.perf_counter()
        work_dir = Path(tempfile.mkdtemp(prefix=f"hype_video_svo_{brief.persona_id[:8]}_"))
        total_cost = 0.0
        components: dict[str, Any] = {}

        try:
            # 1. Get AI-generated Cansu image (NOT real anchor — Seedance filters real persons)
            ai_image_url = await self._resolve_ai_image_url(brief.persona_id)
            if not ai_image_url:
                raise RuntimeError(
                    "seedance_voiceover requires an AI-generated persona image "
                    "(persona_assets.asset_type='generated_image'); none found"
                )
            logger.info(f"[pipeline=seedance_voiceover] using AI image (public URL)")

            # 2. PARALLEL: TTS + Seedance action
            scene_prompt = brief.action_prompt or (
                "Young woman quietly working at her home office, soft natural daylight, "
                "subtle hand gesture, candid documentary feel, photoreal skin texture, "
                "no talking, no speech, gentle micro-expressions only"
            )

            tts_task = _synthesize_turkish_voice(
                text=brief.script_text,
                persona_id=brief.persona_id,
                work_dir=work_dir,
            )
            async with WiroClient() as client:
                action_task = client.generate_action_video(
                    prompt=scene_prompt,
                    slug=self.seedance_slug,
                    input_image_url=ai_image_url,
                    aspect_ratio="9:16",
                    duration=self.duration,
                    resolution="1080p",
                    generate_audio=False,
                )
                tts, action_result = await asyncio.gather(tts_task, action_task)

            total_cost += tts.cost_usd + action_result.cost_usd
            components["tts"] = {"public_url": tts.public_url, "cost": tts.cost_usd}
            components["seedance"] = {
                "asset_url": action_result.asset_url,
                "cost": action_result.cost_usd,
                "slug": self.seedance_slug,
                "ai_image_input": ai_image_url[:90] + "...",
            }

            # 3. FFmpeg compose (same as Kling voice-over)
            raw_video = work_dir / "seedance_raw.mp4"
            await _download_asset(action_result.asset_url, raw_video)

            with_audio = work_dir / "with_audio.mp4"
            await _ffmpeg_replace_audio(
                raw_video, tts.local_path, with_audio, work_dir=work_dir,
            )
            aspect_out = work_dir / "step_aspect.mp4"
            await _ffmpeg_force_9_16(with_audio, aspect_out, work_dir=work_dir)

            duration = _probe_duration(aspect_out)
            srt_file = work_dir / "captions.srt"
            _generate_turkish_srt(
                script_text=brief.script_text,
                audio_duration_sec=duration,
                output_srt=srt_file,
            )

            current = aspect_out
            try:
                watermarked = work_dir / "step_wm.mp4"
                await _ffmpeg_burn_watermark(current, watermarked, work_dir=work_dir)
                current = watermarked
            except RuntimeError as e:
                logger.warning(f"[pipeline=seedance_voiceover] watermark skipped: {e}")
            try:
                captioned = work_dir / "step_cap.mp4"
                await _ffmpeg_burn_captions(current, srt_file, captioned, work_dir=work_dir)
                current = captioned
            except RuntimeError as e:
                logger.warning(f"[pipeline=seedance_voiceover] captions skipped: {e}")

            final_video = work_dir / "final.mp4"
            await _ffmpeg_final_encode(current, final_video, work_dir=work_dir)
            thumbnail = work_dir / "thumbnail.jpg"
            await _ffmpeg_thumbnail(final_video, thumbnail, work_dir=work_dir)

            upload_v, upload_t = await _upload_video_assets(
                persona_id=brief.persona_id,
                video_file=final_video,
                thumbnail_file=thumbnail,
                pipeline_id=self.pipeline_id,
            )

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.success(
                f"[pipeline=seedance_voiceover] DONE cost=${total_cost:.3f} "
                f"elapsed={elapsed_ms / 1000:.1f}s"
            )

            return StoredVideoAsset(
                pipeline_used=self.pipeline_id,
                video_url=upload_v.public_url,
                thumbnail_url=upload_t.public_url,
                storage_key=upload_v.storage_key,
                duration_sec=duration,
                file_size_bytes=upload_v.size_bytes,
                cost_usd=total_cost,
                generation_latency_ms=elapsed_ms,
                raw_components=components,
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


# ─── Strategy G — Static Photo + Voice-Over (zero-distortion guaranteed) ─────


class StaticPhotoVoiceoverPipeline:
    """Static-photo voice-over — anchor photo as still frame + MiniMax TTS + captions.

    ZERO face distortion because the face is literally a JPG image projected
    onto a video. No AI gen on the visual side. Cheapest pipeline ($0.0001 TTS only).
    Latency ~10s (FFmpeg only).

    Steps:
      1. MiniMax TTS Türkçe → MP3
      2. FFmpeg: photo → looped silent video matching MP3 duration
      3. Merge audio + photo video, force 9:16 1080×1920
      4. Burn Türkçe captions + watermark
      5. Final encode + thumbnail + Supabase upload
    """

    pipeline_id = "static_photo_voiceover"

    async def _resolve_anchor_url(self, persona_id: str) -> str:
        """Single anchor signed URL — uses reference_anchors deterministic pick."""
        from .reference_anchors import (
            load_persona_anchors, prepare_reference_prompt_inputs,
        )
        anchors = await load_persona_anchors(persona_id)
        if not anchors:
            raise RuntimeError(f"persona {persona_id} has no reference anchors")
        refs = await prepare_reference_prompt_inputs(anchors, max_prompt_inputs=1)
        if not refs.signed_reference_urls:
            raise RuntimeError("no anchor signed URL available")
        return refs.signed_reference_urls[0]

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset:
        t0 = time.perf_counter()
        work_dir = Path(tempfile.mkdtemp(prefix=f"hype_video_spv_{brief.persona_id[:8]}_"))
        total_cost = 0.0
        components: dict[str, Any] = {}

        try:
            # 1. PARALLEL: TTS + anchor download
            logger.info("[pipeline=static_photo_voiceover] step 1/3 TTS + anchor")
            tts_task = _synthesize_turkish_voice(
                text=brief.script_text,
                persona_id=brief.persona_id,
                work_dir=work_dir,
            )

            # Use brief.anchor_image_url if provided, else resolve from persona
            if brief.anchor_image_url:
                anchor_url = brief.anchor_image_url
            else:
                anchor_url = await self._resolve_anchor_url(brief.persona_id)

            tts = await tts_task
            total_cost += tts.cost_usd
            components["tts"] = {
                "public_url": tts.public_url,
                "cost": tts.cost_usd,
                "provider": "minimax",
            }

            # Download anchor JPG
            anchor_local = work_dir / "anchor.jpg"
            await _download_asset(anchor_url, anchor_local)

            # 2. FFmpeg: build static-photo video matching audio duration
            logger.info("[pipeline=static_photo_voiceover] step 2/3 FFmpeg compose")

            audio_duration = _probe_duration(tts.local_path)
            if audio_duration <= 0:
                audio_duration = tts.duration_hint_sec

            # Create silent 9:16 video of photo at audio duration
            silent_video = work_dir / "silent.mp4"
            silent_cmd = [
                "-loop", "1",
                "-i", str(anchor_local),
                "-t", f"{audio_duration:.2f}",
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
                "format=yuv420p",
                "-r", "24",
                "-y", str(silent_video),
            ]
            await _run_ffmpeg(silent_cmd, step="photo_to_silent_video", work_dir=work_dir)

            # Add audio
            with_audio = work_dir / "with_audio.mp4"
            await _ffmpeg_replace_audio(silent_video, tts.local_path, with_audio, work_dir=work_dir)

            duration = _probe_duration(with_audio)
            srt_file = work_dir / "captions.srt"
            _generate_turkish_srt(
                script_text=brief.script_text,
                audio_duration_sec=duration,
                output_srt=srt_file,
            )

            current = with_audio
            try:
                watermarked = work_dir / "step_wm.mp4"
                await _ffmpeg_burn_watermark(current, watermarked, work_dir=work_dir)
                current = watermarked
            except RuntimeError as e:
                logger.warning(f"[pipeline=static_photo_voiceover] watermark skipped: {e}")
            try:
                captioned = work_dir / "step_cap.mp4"
                await _ffmpeg_burn_captions(current, srt_file, captioned, work_dir=work_dir)
                current = captioned
            except RuntimeError as e:
                logger.warning(f"[pipeline=static_photo_voiceover] captions skipped: {e}")

            final_video = work_dir / "final.mp4"
            await _ffmpeg_final_encode(current, final_video, work_dir=work_dir)
            thumbnail = work_dir / "thumbnail.jpg"
            await _ffmpeg_thumbnail(final_video, thumbnail, work_dir=work_dir)

            # 3. Upload
            logger.info("[pipeline=static_photo_voiceover] step 3/3 Supabase upload")
            upload_v, upload_t = await _upload_video_assets(
                persona_id=brief.persona_id,
                video_file=final_video,
                thumbnail_file=thumbnail,
                pipeline_id=self.pipeline_id,
            )

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.success(
                f"[pipeline=static_photo_voiceover] DONE cost=${total_cost:.4f} "
                f"elapsed={elapsed_ms / 1000:.1f}s"
            )

            return StoredVideoAsset(
                pipeline_used=self.pipeline_id,
                video_url=upload_v.public_url,
                thumbnail_url=upload_t.public_url,
                storage_key=upload_v.storage_key,
                duration_sec=duration,
                file_size_bytes=upload_v.size_bytes,
                cost_usd=total_cost,
                generation_latency_ms=elapsed_ms,
                raw_components=components,
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


# ─── Phase 35.2 — HeyGen Avatar V pipeline ────────────────────────────────


class HeyGenAvatarVPipeline:
    """Phase 35.2 — HeyGen Avatar V + MiniMax multi-chunk voice.

    Pipeline (V1, photar look gen DEVRE DIŞI — Berkay 30 May 2026 reddi):

      1. MiniMax TTS multi-chunk (tail emphasis) → MP3 bytes
      2. HeyGen audio asset upload → asset_id
      3. Persona.heygen_default_look_id lookup (sabit look, photar yok)
      4. HeyGen Avatar V video gen + poll → MP4 URL
      5. Download MP4 → local
      6. FFmpeg: force 9:16 if look orient was landscape + captions + watermark
      7. Final encode + thumbnail extract
      8. Supabase persona-videos upload + return StoredVideoAsset

    Cost target: ~$2 per 20s script
      - MiniMax multi-chunk: $0.0004
      - HeyGen Avatar V ($0.10/sec × 20s): $2.00
      - LLM + storage: marginal

    Failure modes (all graceful — pipeline raises, Flow catches and skips
    video stage, text+image akışı devam eder):
      - MiniMax kota: raises RuntimeError, Flow logs + skips
      - HeyGen upload 413: pre-flight size check + raises
      - Avatar V timeout: poll exhausts, raises
      - FFmpeg fail per-step: try/except + continue without that step
    """

    pipeline_id = "heygen_avatar_v"

    async def _resolve_persona_heygen_config(self, persona_id: str) -> dict[str, Any]:
        """Look up persona's HeyGen settings (Phase 35.2 personas cols)."""
        from .supabase_client import make_supabase

        sb = make_supabase()
        rows = (
            sb.table("personas")
            .select(
                "heygen_avatar_group_id,heygen_default_look_id,"
                "video_aspect_ratio,video_resolution,daily_video_budget_usd"
            )
            .eq("id", persona_id)
            .limit(1)
            .execute()
        ).data or []
        if not rows:
            raise RuntimeError(f"persona {persona_id} not found")
        cfg = rows[0]
        if not cfg.get("heygen_default_look_id"):
            raise RuntimeError(
                f"persona {persona_id} missing heygen_default_look_id "
                f"(seed Phase 35.2.2 first)"
            )
        return cfg

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset:
        from .heygen_client import HeyGenClient, HeyGenError
        from .minimax_tts_client import MinimaxTTSClient
        from .pre_spend_guard import assert_render_safe, PreSpendRejected

        # Pre-spend gate: validate the canonical script BEFORE we pay MiniMax
        # or HeyGen. Cheap text check; saves $3-6 per bad render.
        try:
            assert_render_safe(
                brief.script_text,
                draft_id=getattr(brief, "daily_draft_id", "?") or "?",
                min_chars=getattr(brief, "script_min_chars", None),
                max_chars=getattr(brief, "script_max_chars", None),
            )
        except PreSpendRejected:
            raise

        t0 = time.perf_counter()
        work_dir = Path(
            tempfile.mkdtemp(prefix=f"hype_video_hgv_{brief.persona_id[:8]}_")
        )
        total_cost = 0.0
        components: dict[str, Any] = {}

        try:
            # 0. Persona HeyGen config + cost cap pre-flight
            cfg = await self._resolve_persona_heygen_config(brief.persona_id)
            # Avatar gate (the explicit-ID-wins fix): when the persona has
            # an explicit `heygen_default_look_id` configured, use it
            # verbatim and do NOT call the LRU picker. The picker only
            # runs when no explicit ID is set — for personas that opt
            # into rotation by leaving the default blank.
            explicit_look_id = cfg.get("heygen_default_look_id")
            picked_look: Optional[dict[str, Any]] = None
            if explicit_look_id:
                look_id = explicit_look_id
                logger.info(
                    f"[pipeline=heygen_avatar_v] explicit look_id from "
                    f"persona config: {look_id[:8]} (picker bypassed)"
                )
            else:
                try:
                    from .heygen_look_picker import pick_heygen_look_for_video
                    picked_look = await pick_heygen_look_for_video(brief.persona_id)
                except Exception as e:
                    logger.warning(f"[pipeline=heygen_avatar_v] look picker raised: {e}")
                if picked_look and picked_look.get("heygen_id"):
                    look_id = picked_look["heygen_id"]
                    logger.info(
                        f"[pipeline=heygen_avatar_v] picker chose look "
                        f"{look_id[:8]} '{picked_look['name'][:40]}' "
                        f"(lru={picked_look['was_lru']})"
                    )
                else:
                    raise RuntimeError(
                        f"persona {brief.persona_id} has no explicit "
                        "heygen_default_look_id and the picker returned "
                        "no candidate — cannot proceed"
                    )
            aspect = cfg.get("video_aspect_ratio") or brief.target_aspect or "9:16"
            resolution = cfg.get("video_resolution") or "1080p"

            logger.info(
                f"[pipeline=heygen_avatar_v] start persona={brief.persona_id[:8]} "
                f"look={look_id[:8]} aspect={aspect} resolution={resolution}"
            )

            # 1. MiniMax TTS — single-chunk clean synthesize. The previous
            # multi-chunk path with tail_emotion='fluent' injected Turkish
            # hesitation tokens ("ııı/eee") between the head and tail
            # chunks. Switch to plain synthesize() with emotion=None and
            # closing_emphasis=False so the narration is filler-free.
            # Pronunciation_resolver still runs (handles English-term
            # phonetics: OpenAI, GPT-5.5, AI, etc.).
            # Berkay 6 Haz 2026:
            #   - speed=0.9 (more authoritative pace; Cansu was rushing).
            #   - Inject pause markers at sentence boundaries.
            # Berkay 10 Haz 2026:
            #   - 0.9 felt too slow → speed=1.1 (livelier, still clear).
            #   - Pause markers trimmed to <#0.15#>/<#0.2#> (see
            #     _inject_pause_markers) to kill the choppy inter-sentence gaps.
            # 2026-06-10 — render defteri salvage (Berkay: "3 defa generate
            # etme lüksümüz yok"). Aynı script için son 24 saatte ödenmiş /
            # yolda bir HeyGen render'ı varsa YENİ render başlatılmaz: mevcut
            # video_id poll edilir (tamamlanmışsa anında döner) ve boru hattı
            # 4. adımdan devam eder. Defter hatası eski davranışa düşürür.
            from .video_render_ledger import (
                script_sha as _ledger_sha, find_salvageable as _ledger_find,
                log_submit as _ledger_submit, mark_completed as _ledger_done,
                mark_consumed as _ledger_consume,
            )
            _sha = _ledger_sha(brief.script_text)
            _salvage = _ledger_find(
                persona_id=brief.persona_id, pipeline="heygen_avatar_v", sha=_sha,
            )
            video_id: str
            narration_public_url: Optional[str] = None
            hg = HeyGenClient()
            if _salvage:
                video_id = _salvage["heygen_video_id"]
                narration_public_url = _salvage.get("narration_url")
                components["salvaged_from_ledger"] = video_id
                logger.info(
                    f"[pipeline=heygen_avatar_v] SALVAGE: mevcut render "
                    f"{video_id[:12]} kullanılıyor — yeni HeyGen harcaması YOK"
                )

            if _salvage is None:
                # 2026-06-10 (otonomi D0-3) — render ÖNCESİ bakiye probu.
                # Kredi pipeline ortasında bitince (bugünkü vaka) para+zaman
                # yanıyor. Eşik altındaysa fail-fast: video branşı düşer,
                # run görsel-fallback ile sürer + CRITICAL alert. Probe
                # hatası (None) fail-open: probe kesintisi render'ı durdurmaz.
                import os as _os_q
                _min_quota = float(_os_q.environ.get("HEYGEN_MIN_QUOTA", "150"))
                _quota = await hg.get_remaining_quota()
                if _quota is not None:
                    logger.info(f"[pipeline=heygen_avatar_v] HeyGen quota={_quota:.0f} (eşik {_min_quota:.0f})")
                    if _quota < _min_quota:
                        try:
                            from .alerter import send_alert
                            send_alert(
                                f"HeyGen kredisi eşiğin altında ({_quota:.0f} < {_min_quota:.0f}) — video render atlandı",
                                severity="CRITICAL",
                                reason="insufficient_heygen_quota",
                                action="HeyGen hesabına kredi yükleyin; run görsel-fallback ile sürdü",
                                extra={"remaining_quota": _quota, "threshold": _min_quota},
                            )
                        except Exception:
                            pass
                        raise HeyGenError(
                            f"insufficient HeyGen quota: {_quota:.0f} < {_min_quota:.0f} (fail-fast, render başlatılmadı)",
                        )
                logger.info("[pipeline=heygen_avatar_v] step 1/8 MiniMax TTS (clean, paused)")
                mm = MinimaxTTSClient()
                paced_text = _inject_pause_markers(brief.script_text)
                tts_result = await mm.synthesize(
                    text=paced_text,
                    speed=1.1,
                    vol=1.0,
                    pitch=0,
                    emotion=None,
                    auto_resolve_pronunciation=True,
                    closing_emphasis=False,
                )
                total_cost += float(tts_result.cost_usd or 0.0)
                audio_local = work_dir / "narration.mp3"
                audio_local.write_bytes(tts_result.audio_bytes)
                components["tts"] = {
                    "provider": "minimax_single_clean",
                    "cost": float(tts_result.cost_usd or 0.0),
                    "latency_ms": tts_result.latency_ms,
                    "bytes": len(tts_result.audio_bytes),
                }

                # 1b. Upload the narration MP3 to Supabase so fal-ai/whisper
                # has a public URL to fetch for transcription. Lives in a
                # narration/ namespace; reused once for ASR, then orphaned.
                logger.info("[pipeline=heygen_avatar_v] step 1b/8 upload narration")
                narration_storage_key = (
                    f"narration/{brief.persona_id}/{int(time.time())}.mp3"
                )
                from .supabase_storage import SupabaseStorage
                _storage_for_narration = SupabaseStorage()
                _nar_upload = await _storage_for_narration.upload_bytes(
                    bucket=settings.supabase_videos_bucket,
                    key=narration_storage_key,
                    data=tts_result.audio_bytes,
                    content_type="audio/mpeg",
                )
                narration_public_url = _nar_upload.public_url
                components["narration_url"] = narration_public_url

                # Altyazı GERÇEKTEN seslendirilen script'le üretilmeli. Gate script'i
                # yenilerse (aşağıda) bu _new_script'e döner; yoksa orijinal kalır.
                effective_script = brief.script_text

                # ── TTS KALİTE KAPISI (13 Haz 2026, Berkay) — render ÖNCESİ ──
                # Sesi Whisper'la denetle; kötüyse script'i 1 kez yenileyip re-TTS;
                # hâlâ kötüyse raise → video atlanır (görsel-only, $3 yanmaz).
                # FAIL-OPEN: gate altyapısı hata verirse render'a devam.
                try:
                    from .tts_quality_gate import run_tts_gate
                    _tg = await run_tts_gate(
                        tts_result.audio_bytes, narration_public_url, brief.script_text
                    )
                    if not _tg.get("ok", True):
                        logger.warning(
                            f"[tts-gate] KÖTÜ ({_tg.get('source')}): {_tg.get('reason')} "
                            f"bad_terms={_tg.get('bad_terms')} — script yenilenip 1 kez denenecek"
                        )
                        _new_script = await _regen_video_script(
                            brief.topic, brief.source, _tg.get("bad_terms") or []
                        )
                        if not _new_script:
                            raise RuntimeError(
                                f"tts_gate_blocked: {_tg.get('reason')} (script yenilenemedi)"
                            )
                        effective_script = _new_script   # altyazı yeni script'le üretilsin
                        paced_text = _inject_pause_markers(_new_script)
                        tts_result = await mm.synthesize(
                            text=paced_text, speed=1.1, vol=1.0, pitch=0,
                            emotion=None, auto_resolve_pronunciation=True,
                            closing_emphasis=False,
                        )
                        total_cost += float(tts_result.cost_usd or 0.0)
                        audio_local.write_bytes(tts_result.audio_bytes)
                        components["tts_regenerated"] = True
                        narration_storage_key = (
                            f"narration/{brief.persona_id}/{int(time.time())}.mp3"
                        )
                        _nar2 = await _storage_for_narration.upload_bytes(
                            bucket=settings.supabase_videos_bucket,
                            key=narration_storage_key,
                            data=tts_result.audio_bytes,
                            content_type="audio/mpeg",
                        )
                        narration_public_url = _nar2.public_url
                        components["narration_url"] = narration_public_url
                        _tg2 = await run_tts_gate(
                            tts_result.audio_bytes, narration_public_url, _new_script
                        )
                        if not _tg2.get("ok", True):
                            raise RuntimeError(
                                f"tts_gate_blocked: {_tg2.get('reason')} (yeniden üretim de kötü)"
                            )
                        logger.info("[tts-gate] yeniden üretim sonrası OK — render'a devam")
                    else:
                        logger.info(f"[tts-gate] OK ({_tg.get('source')}) — render'a devam")
                except RuntimeError:
                    raise  # gate-block: çağıran (flow) yakalar → görsel-only
                except Exception as _tge:  # FAIL-OPEN: altyapı hatası → engelleme
                    logger.warning(
                        f"[tts-gate] altyapı hatası (fail-open, render'a devam): "
                        f"{type(_tge).__name__}: {_tge}"
                    )

                # 2. HeyGen audio asset upload
                logger.info("[pipeline=heygen_avatar_v] step 2/8 HeyGen audio upload")
                hg = HeyGenClient()
                asset_id = await hg.upload_audio_asset(tts_result.audio_bytes)
                components["heygen_asset_id"] = asset_id

                # 3. HeyGen Avatar V video generate (caption=True → HeyGen native
                #    captions burn-in by their renderer; replaces FFmpeg heuristic
                #    captions which Berkay rejected for being out of sync — Phase
                #    35.2.11)
                logger.info("[pipeline=heygen_avatar_v] step 3/6 Avatar V generate")
                video_id = await hg.generate_avatar_v_video(
                    talking_photo_id=look_id,
                    audio_asset_id=asset_id,
                    aspect_ratio=aspect,
                    resolution=resolution,
                    title=f"hype-{brief.persona_id[:8]}-{int(time.time())}",
                    caption=True,
                )
                components["heygen_video_id"] = video_id
                # Defter: submit anında kayıt (öksüz kalsa bile iz + bütçe).
                _est = (len(brief.script_text) / 15.5) * 0.10 + float(tts_result.cost_usd or 0.0)
                _ledger_submit(
                    persona_id=brief.persona_id, pipeline="heygen_avatar_v",
                    sha=_sha, heygen_video_id=video_id,
                    narration_url=narration_public_url, est_cost_usd=_est,
                )

            # 4. Poll until completed
            logger.info(
                f"[pipeline=heygen_avatar_v] step 4/6 poll video_id={video_id[:8]}"
            )
            video_status = await hg.wait_for_video(video_id, poll_interval_sec=15.0)
            heygen_cost = float(video_status.duration_sec) * 0.10  # $0.10/sec Avatar V
            if _salvage:
                heygen_cost = 0.0  # zaten ödendi — bu run'a maliyet yazma
            total_cost += heygen_cost
            _ledger_done(
                video_id,
                duration_sec=float(video_status.duration_sec),
                cost_usd=float(video_status.duration_sec) * 0.10,
            )
            components["heygen_video"] = {
                "duration_sec": video_status.duration_sec,
                "cost": heygen_cost,
                "poll_count": video_status.poll_count,
                "latency_ms": video_status.total_latency_ms,
            }

            # 5. Download MP4 from HeyGen signed URL
            logger.info("[pipeline=heygen_avatar_v] step 5/6 download + FFmpeg")
            mp4_bytes = await hg.download(video_status.video_url)
            raw_video = work_dir / "raw.mp4"
            raw_video.write_bytes(mp4_bytes)

            current = raw_video

            # 5a. Force 9:16 only if HeyGen produced wrong aspect
            try:
                # _probe_duration is reliable; for aspect check we trust HeyGen
                # produced the requested aspect (we passed 9:16). If not we'd
                # need ffprobe stream resolution check — keep simple here.
                pass
            except Exception:
                pass

            # 5b. fal-ai/whisper word-level transcription + script-text
            # caption burn-in. Whisper provides REAL time-aligned word
            # timestamps; we display the script-text words (audio-accurate)
            # index-aligned to those timestamps so Whisper mistranscriptions
            # (e.g. "ameleliği" → "ameliyatı") never reach the screen.
            logger.info("[pipeline=heygen_avatar_v] step 5b/8 fal-whisper + burn captions")
            srt_text: Optional[str] = None
            srt_source = "unknown"
            try:
                from .fal_whisper_client import build_subtitle_srt
                srt_text, srt_source = await build_subtitle_srt(
                    narration_url=narration_public_url,
                    script_text=effective_script,
                    audio_duration_sec=float(video_status.duration_sec),
                )
            except Exception as e:
                logger.warning(
                    f"[pipeline=heygen_avatar_v] subtitle generation failed: "
                    f"{e!r} — proceeding without captions"
                )
            if srt_text:
                srt_file = work_dir / "captions.srt"
                srt_file.write_text(srt_text, encoding="utf-8")
                try:
                    captioned = work_dir / "step_cap.mp4"
                    await _ffmpeg_burn_captions(
                        current, srt_file, captioned, work_dir=work_dir
                    )
                    current = captioned
                    components["captions"] = {
                        "source": srt_source,
                        "segments": srt_text.count("\n\n"),
                    }
                except Exception as e:
                    logger.warning(
                        f"[pipeline=heygen_avatar_v] caption burn failed: {e}"
                    )

            # 5c. Watermark — graceful skip on failure
            try:
                watermarked = work_dir / "step_wm.mp4"
                await _ffmpeg_burn_watermark(current, watermarked, work_dir=work_dir)
                current = watermarked
            except Exception as e:
                logger.warning(
                    f"[pipeline=heygen_avatar_v] watermark skipped: {e}"
                )

            # 6. Final encode + thumbnail + Supabase upload
            final_video = work_dir / "final.mp4"
            await _ffmpeg_final_encode(current, final_video, work_dir=work_dir)
            thumbnail = work_dir / "thumbnail.jpg"
            await _ffmpeg_thumbnail(final_video, thumbnail, work_dir=work_dir)

            logger.info("[pipeline=heygen_avatar_v] step 6/6 Supabase upload")
            upload_v, upload_t = await _upload_video_assets(
                persona_id=brief.persona_id,
                video_file=final_video,
                thumbnail_file=thumbnail,
                pipeline_id=self.pipeline_id,
            )

            final_duration = _probe_duration(final_video) or video_status.duration_sec
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.success(
                f"[pipeline=heygen_avatar_v] DONE cost=${total_cost:.4f} "
                f"duration={final_duration:.1f}s elapsed={elapsed_ms / 1000:.1f}s"
            )

            # Phase 40.A — mark the look as used so picker rotates to the next
            # AI-generated photo on the next major-launch video. Failure is
            # non-fatal (video already produced successfully).
            if picked_look and picked_look.get("asset_id"):
                try:
                    from .heygen_look_picker import mark_look_used
                    await mark_look_used(picked_look["asset_id"])
                except Exception as e:
                    logger.warning(f"[pipeline=heygen_avatar_v] mark_look_used failed: {e}")

            # Defter: render başarıyla tüketildi — maliyet artık bu run'da,
            # bütçe çift-sayımı düşer; salvage adayı olmaktan çıkar.
            _ledger_consume(video_id)

            return StoredVideoAsset(
                pipeline_used=self.pipeline_id,
                video_url=upload_v.public_url,
                thumbnail_url=upload_t.public_url,
                storage_key=upload_v.storage_key,
                duration_sec=final_duration,
                file_size_bytes=upload_v.size_bytes,
                cost_usd=total_cost,
                generation_latency_ms=elapsed_ms,
                raw_components=components,
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


# ─── Phase 35.3 — Split-Screen Broadcast Layout ──────────────────────────────


@dataclass(frozen=True)
class SplitScreenBrief:
    """Phase 35.3 — input spec extension for split-screen pipeline.

    Builds on top of VideoBrief: caller (Flow) provides 3 scene_description
    strings (brand-aware, content_type-aware) and the pipeline runs Wiro
    Seedream batch on them while HeyGen Avatar V generates the bottom video.
    """

    base: VideoBrief
    scene_descriptions: list[str]            # 1-5 distinct image prompts
    daily_draft_id: Optional[str] = None
    content_context: Optional[str] = None
    visual_mode: str = "conceptual"          # conceptual (no Cansu) / hybrid


class HeyGenSplitScreenPipeline:
    """Phase 35.3 — HeyGen Avatar V (bottom) + Wiro Seedream slideshow (top).

    Berkay 30 May 2026 kararı:
      - "subtitle olmasın, sadece split-screen" → FFmpeg vstack, no subtitle burn-in
      - "ffmpegi hiç beğenmedim" → minimum FFmpeg (sadece vstack + watermark + encode)

    Pipeline:
      1. MiniMax TTS multi-chunk (tail emphasis) → MP3
      2. HeyGen audio asset upload
      3. PARALLEL fork (asyncio.gather):
         a. Wiro Seedream batch — 3 brand-aware news images (visual_mode='conceptual')
         b. HeyGen Avatar V video generate + poll
      4. Download HeyGen MP4
      5. Download each Seedream image to local
      6. FFmpeg vstack: top slideshow (Ken Burns) + bottom Cansu video
         + watermark + final H.264 encode + thumbnail
      7. Supabase persona-videos upload + return StoredVideoAsset

    Cost target (~20s video):
      - MiniMax multi-chunk: $0.0004
      - HeyGen Avatar V: $2.00
      - Wiro Seedream × 3: ~$0.45
      - FFmpeg + storage: $0
      - Total: ~$2.45/video → ~$74/ay (30 video)

    Fallback (graceful):
      - If <2 Seedream images succeed → raise (Flow catches → falls back to
        HeyGenAvatarVPipeline full-frame).
      - HeyGen failure → raise (Flow skips video stage).
    """

    pipeline_id = "heygen_split_screen"
    min_images_required = 2  # below this, split-screen aesthetic collapses

    async def _resolve_persona_heygen_config(self, persona_id: str) -> dict[str, Any]:
        from .supabase_client import make_supabase

        sb = make_supabase()
        rows = (
            sb.table("personas")
            .select(
                "heygen_avatar_group_id,heygen_default_look_id,"
                "video_aspect_ratio,video_resolution,daily_video_budget_usd,"
                "primary_account_id"
            )
            .eq("id", persona_id)
            .limit(1)
            .execute()
        ).data or []
        if not rows:
            raise RuntimeError(f"persona {persona_id} not found")
        cfg = rows[0]
        if not cfg.get("heygen_default_look_id"):
            raise RuntimeError(
                f"persona {persona_id} missing heygen_default_look_id"
            )
        return cfg

    async def produce_video(self, brief: VideoBrief) -> StoredVideoAsset:
        """Default entry — produces video using scene_descriptions from
        brief.action_prompt if a SplitScreenBrief was not provided.

        Prefer caller to use produce_split_screen_video(SplitScreenBrief) for
        explicit scene control.
        """
        # If action_prompt looks like a JSON list, parse it; otherwise treat
        # as a single scene (replicate to N).
        scenes: list[str] = []
        if brief.action_prompt:
            try:
                import json as _json
                parsed = _json.loads(brief.action_prompt)
                if isinstance(parsed, list):
                    scenes = [str(s) for s in parsed if s]
            except (ValueError, TypeError):
                pass
            if not scenes:
                scenes = [brief.action_prompt]
        if not scenes:
            raise ValueError(
                "HeyGenSplitScreenPipeline requires action_prompt with scene "
                "description(s) — either a JSON list or a single string."
            )
        ss = SplitScreenBrief(
            base=brief,
            scene_descriptions=scenes,
            daily_draft_id=brief.daily_draft_id,
        )
        return await self.produce_split_screen_video(ss)

    async def produce_split_screen_video(
        self, brief: SplitScreenBrief
    ) -> StoredVideoAsset:
        from .heygen_client import HeyGenClient
        from .minimax_tts_client import MinimaxTTSClient
        from .visual_director_tools import generate_news_image_batch
        from .pre_spend_guard import assert_render_safe, PreSpendRejected

        # Pre-spend gate (split-screen variant): same money-side rule.
        try:
            assert_render_safe(
                brief.base.script_text,
                draft_id=getattr(brief, "daily_draft_id", "?") or "?",
            )
        except PreSpendRejected:
            raise

        t0 = time.perf_counter()
        work_dir = Path(
            tempfile.mkdtemp(prefix=f"hype_video_ss_{brief.base.persona_id[:8]}_")
        )
        total_cost = 0.0
        components: dict[str, Any] = {}

        try:
            # 0. Persona config
            cfg = await self._resolve_persona_heygen_config(brief.base.persona_id)
            # Phase 40.A — AI-generated look rotation (Berkay 1 Haz 2026)
            picked_look: Optional[dict[str, Any]] = None
            try:
                from .heygen_look_picker import pick_heygen_look_for_video
                picked_look = await pick_heygen_look_for_video(brief.base.persona_id)
            except Exception as e:
                logger.warning(f"[pipeline=split_screen] look picker raised: {e}")
            if picked_look and picked_look.get("heygen_id"):
                look_id = picked_look["heygen_id"]
                logger.info(
                    f"[pipeline=split_screen] picker chose look "
                    f"{look_id[:8]} '{picked_look['name'][:40]}' "
                    f"(lru={picked_look['was_lru']})"
                )
            else:
                look_id = cfg["heygen_default_look_id"]
                logger.info(
                    f"[pipeline=split_screen] picker empty/failed, fallback to "
                    f"default look {look_id[:8]}"
                )
            aspect = cfg.get("video_aspect_ratio") or brief.base.target_aspect or "9:16"
            resolution = cfg.get("video_resolution") or "1080p"
            logger.info(
                f"[pipeline=split_screen] start persona={brief.base.persona_id[:8]} "
                f"look={look_id[:8]} aspect={aspect} scenes={len(brief.scene_descriptions)}"
            )

            # 1. MiniMax TTS — single-chunk clean. The previous
            # synthesize_multi_chunk path with tail_emotion='fluent'
            # injected Turkish hesitation tokens; mirror the same fix
            # applied to heygen_avatar_v.
            logger.info("[pipeline=split_screen] step 1/7 MiniMax TTS (clean, paused)")
            mm = MinimaxTTSClient()
            _paced = _inject_pause_markers(brief.base.script_text)
            tts_result = await mm.synthesize(
                text=_paced,
                speed=1.1,  # Berkay 10 Haz 2026 — match heygen_avatar_v livelier pace
                vol=1.0,
                pitch=0,
                emotion=None,
                auto_resolve_pronunciation=True,
                closing_emphasis=False,
            )
            total_cost += float(tts_result.cost_usd or 0.0)
            components["tts"] = {
                "provider": "minimax_single_clean",
                "cost": float(tts_result.cost_usd or 0.0),
                "latency_ms": tts_result.latency_ms,
            }

            # 2. HeyGen audio upload
            logger.info("[pipeline=split_screen] step 2/7 HeyGen audio upload")
            hg = HeyGenClient()
            asset_id = await hg.upload_audio_asset(tts_result.audio_bytes)
            components["heygen_asset_id"] = asset_id

            # 3. PARALLEL: HeyGen video gen + Seedream batch
            logger.info(
                f"[pipeline=split_screen] step 3/7 PARALLEL HeyGen + Seedream×{len(brief.scene_descriptions)}"
            )
            heygen_task = asyncio.create_task(
                self._run_heygen_video(
                    hg=hg,
                    look_id=look_id,
                    asset_id=asset_id,
                    aspect=aspect,
                    resolution=resolution,
                    title=f"hype-ss-{brief.base.persona_id[:8]}-{int(time.time())}",
                )
            )
            seedream_task = asyncio.create_task(
                generate_news_image_batch(
                    persona_id=brief.base.persona_id,
                    scene_descriptions=brief.scene_descriptions,
                    daily_draft_id=brief.daily_draft_id,
                    content_context=brief.content_context,
                    aspect_ratio="1:1",
                    visual_mode=brief.visual_mode,
                    # Phase 35.3 / Berkay 30 May 2026 — switch news visuals to
                    # google/nano-banana-2 @ 2K (was seedream-v4-5 @ 4k via
                    # _generate_and_check_async default).
                    model_slug="google/nano-banana-2",
                    resolution="2K",
                )
            )
            heygen_result, image_results = await asyncio.gather(
                heygen_task, seedream_task
            )

            video_status = heygen_result["video_status"]
            heygen_cost = heygen_result["cost"]
            video_id = heygen_result["video_id"]
            total_cost += heygen_cost
            components["heygen_video"] = {
                "video_id": video_id,
                "duration_sec": video_status.duration_sec,
                "cost": heygen_cost,
                "poll_count": video_status.poll_count,
                "latency_ms": video_status.total_latency_ms,
            }

            seedream_cost = sum(float(r.get("cost_usd", 0.0)) for r in image_results)
            total_cost += seedream_cost
            components["news_images"] = {
                "count_generated": len(image_results),
                "count_requested": len(brief.scene_descriptions),
                "cost": seedream_cost,
                "image_urls": [r["image_url"] for r in image_results],
                "asset_ids": [r["asset_id"] for r in image_results],
            }

            if len(image_results) < self.min_images_required:
                raise RuntimeError(
                    f"split-screen requires >= {self.min_images_required} images, "
                    f"got {len(image_results)} (compliance/generation failures)"
                )

            # 4. Download HeyGen MP4
            logger.info("[pipeline=split_screen] step 4/7 download HeyGen MP4")
            mp4_bytes = await hg.download(video_status.video_url)
            raw_video = work_dir / "raw_heygen.mp4"
            raw_video.write_bytes(mp4_bytes)

            # 5. Download Seedream images to local
            logger.info(
                f"[pipeline=split_screen] step 5/7 download {len(image_results)} Seedream images"
            )
            image_paths: list[Path] = []
            for idx, r in enumerate(image_results):
                img_path = work_dir / f"news_img_{idx:02d}.jpg"
                await _download_asset(r["image_url"], img_path)
                image_paths.append(img_path)

            # 6. FFmpeg vstack composition + watermark + final encode + thumbnail
            logger.info("[pipeline=split_screen] step 6/7 FFmpeg vstack composition")
            vstack_out = work_dir / "vstack.mp4"
            await _ffmpeg_split_screen_vstack(
                heygen_video=raw_video,
                image_paths=image_paths,
                dst=vstack_out,
                work_dir=work_dir,
                target_duration=video_status.duration_sec,
            )

            # Watermark removed per Berkay 30 May 2026 — split-screen pilot
            # explicitly should NOT carry the "AI generated" overlay.
            current = vstack_out

            final_video = work_dir / "final.mp4"
            await _ffmpeg_final_encode(current, final_video, work_dir=work_dir)
            thumbnail = work_dir / "thumbnail.jpg"
            await _ffmpeg_thumbnail(final_video, thumbnail, work_dir=work_dir)

            # 7. Supabase upload
            logger.info("[pipeline=split_screen] step 7/7 Supabase upload")
            upload_v, upload_t = await _upload_video_assets(
                persona_id=brief.base.persona_id,
                video_file=final_video,
                thumbnail_file=thumbnail,
                pipeline_id=self.pipeline_id,
            )

            final_duration = _probe_duration(final_video) or video_status.duration_sec
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.success(
                f"[pipeline=split_screen] DONE cost=${total_cost:.4f} "
                f"duration={final_duration:.1f}s elapsed={elapsed_ms / 1000:.1f}s "
                f"images={len(image_results)}"
            )

            # Phase 40.A — mark used (non-fatal)
            if picked_look and picked_look.get("asset_id"):
                try:
                    from .heygen_look_picker import mark_look_used
                    await mark_look_used(picked_look["asset_id"])
                except Exception as e:
                    logger.warning(f"[pipeline=split_screen] mark_look_used failed: {e}")

            return StoredVideoAsset(
                pipeline_used=self.pipeline_id,
                video_url=upload_v.public_url,
                thumbnail_url=upload_t.public_url,
                storage_key=upload_v.storage_key,
                duration_sec=final_duration,
                file_size_bytes=upload_v.size_bytes,
                cost_usd=total_cost,
                generation_latency_ms=elapsed_ms,
                raw_components=components,
            )

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    async def _run_heygen_video(
        self,
        *,
        hg: Any,
        look_id: str,
        asset_id: str,
        aspect: str,
        resolution: str,
        title: str,
    ) -> dict[str, Any]:
        """Helper to encapsulate HeyGen video gen + poll for asyncio.gather."""
        video_id = await hg.generate_avatar_v_video(
            talking_photo_id=look_id,
            audio_asset_id=asset_id,
            aspect_ratio=aspect,
            resolution=resolution,
            title=title,
            caption=False,  # subtitle skip per Berkay 30 May 2026
        )
        video_status = await hg.wait_for_video(video_id, poll_interval_sec=15.0)
        cost = float(video_status.duration_sec) * 0.10  # $0.10/sec Avatar V
        return {"video_id": video_id, "video_status": video_status, "cost": cost}


# ─── Registry ────────────────────────────────────────────────────────────────


PIPELINES: dict[str, type[VideoPipeline]] = {
    # Zero-distortion (Phase 23.7 PIVOT — winner candidate, no AI face gen)
    "static_photo_voiceover": StaticPhotoVoiceoverPipeline,
    # Voice-over with action video (alternative if static feels too flat)
    "kling_voiceover": KlingVoiceoverPipeline,
    "seedance_voiceover": SeedanceVoiceoverPipeline,
    # Lip-sync architecture (legacy fallback — quality "obviously AI")
    "talking_head_memo": TalkingHeadPipeline,
    "hybrid_seedance_memo": HybridCompositePipeline,
    "veo3_native": Veo3NativePipeline,
    "memo_seedance_v2": MemoSeedanceHybridPipeline,
    # Phase 35.2 — HeyGen Avatar V (MiniMax multi-chunk + lip-sync, Cansu pilot)
    "heygen_avatar_v": HeyGenAvatarVPipeline,
    # Phase 35.3 — HeyGen Avatar V + Wiro Seedream slideshow split-screen
    "heygen_split_screen": HeyGenSplitScreenPipeline,
}


def get_pipeline(pipeline_id: str) -> VideoPipeline:
    """Lookup helper — instantiate a pipeline by id."""
    cls = PIPELINES.get(pipeline_id)
    if not cls:
        raise ValueError(f"unknown pipeline_id={pipeline_id}; known={list(PIPELINES)}")
    return cls()  # type: ignore[call-arg]
