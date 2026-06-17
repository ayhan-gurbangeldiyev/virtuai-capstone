"""Wiro AI async client — image generation (Nano Banana Pro / Nano Banana 2 / GPT Image 2).

Ported from VirtuAI/backend/src/virtuai/providers/wiro_client.py.
Adapted for Hype Crew: settings via hype_crew.config, logging via loguru, no mock mode
(real Wiro calls always — user decision in Phase 21).

API shape (per Wiro docs, verified 2026-05-10):
    POST /v1/Run/{owner-slug}/{model-slug}  — submit job (returns taskid + socketaccesstoken)
    POST /v1/Task/Detail                    — poll tasktoken until task_postprocess_end

Auth:
    x-api-key always
    + HMAC-SHA256 signature with secret + nonce (if api_secret set)

Models (verified slugs from Wiro Tool/Detail):
    google/nano-banana-pro   — primary
    google/nano-banana-2     — alternate
    openai/gpt-image-2       — test/realism
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any, Literal, Optional

import httpx
from loguru import logger

from config import settings


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerationResult:
    """Normalized Wiro generation result."""

    asset_url: str
    asset_type: Literal["image", "video", "voice"]
    model_slug: str
    task_uuid: str
    cost_usd: float
    latency_ms: int
    raw_response: dict[str, Any] | None = None


@dataclass(frozen=True)
class WiroImageModelSpec:
    aspect_ratios: frozenset[str]
    resolutions: frozenset[str]
    max_input_images: int = 14
    max_total_images: int = 15


_NANO_BANANA_PRO_ASPECT_RATIOS = frozenset(
    {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
)
_SEEDREAM_V4_5_ASPECT_RATIOS = frozenset(
    {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "16:9", "9:16", "21:9", "9:21"}
)
_NANO_BANANA_2_ASPECT_RATIOS = frozenset(
    {"1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3", "4:5", "5:4",
     "8:1", "9:16", "16:9", "21:9"}
)
_GPT_IMAGE_2_ASPECT_RATIOS = frozenset({"1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9"})

_WIRO_IMAGE_MODEL_SPECS: dict[str, WiroImageModelSpec] = {
    "google/nano-banana-2": WiroImageModelSpec(
        aspect_ratios=_NANO_BANANA_2_ASPECT_RATIOS,
        resolutions=frozenset({"512", "1K", "2K", "4K"}),
    ),
    "google/nano-banana-pro": WiroImageModelSpec(
        aspect_ratios=_NANO_BANANA_PRO_ASPECT_RATIOS,
        resolutions=frozenset({"1K", "2K", "4K"}),
    ),
    "openai/gpt-image-2": WiroImageModelSpec(
        aspect_ratios=_GPT_IMAGE_2_ASPECT_RATIOS,
        resolutions=frozenset({"1K", "2K", "4K"}),
        max_input_images=16,
        max_total_images=26,
    ),
    "bytedance/seedream-v4-5": WiroImageModelSpec(
        aspect_ratios=_SEEDREAM_V4_5_ASPECT_RATIOS,
        resolutions=frozenset({"2k", "4k"}),
        max_input_images=10,
        max_total_images=15,
    ),
}

_DEFAULT_IMAGE_MODEL_SPEC = WiroImageModelSpec(
    aspect_ratios=frozenset({*_NANO_BANANA_2_ASPECT_RATIOS, *_NANO_BANANA_PRO_ASPECT_RATIOS}),
    resolutions=frozenset({"512", "1K", "2K", "4K"}),
)


def supported_wiro_image_aspect_ratios(slug: str) -> frozenset[str]:
    return _image_model_spec(slug).aspect_ratios


def supported_wiro_image_resolutions(slug: str) -> frozenset[str]:
    return _image_model_spec(slug).resolutions


def validate_wiro_image_input_budget(
    *,
    slug: str,
    input_image: str | list[str] | None,
    max_images: int,
) -> None:
    spec = _image_model_spec(slug)
    input_count = _input_image_count(input_image)
    if input_count > spec.max_input_images:
        raise ValueError(
            f"{slug} accepts at most {spec.max_input_images} inputImage references; "
            f"received {input_count}."
        )
    if input_count + max_images > spec.max_total_images:
        raise ValueError(
            f"{slug} supports at most {spec.max_total_images} inputImage references plus outputs; "
            f"received {input_count} references and {max_images} requested outputs."
        )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class WiroClient:
    """Async Wiro AI client.

    Usage:
        async with WiroClient() as client:
            result = await client.generate_image(
                slug="google/nano-banana-pro",
                prompt="...",
                input_image=["https://signed-url-1", "https://signed-url-2"],
            )
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
        poll_max_attempts: int = 300,  # 10 minutes max
    ):
        self.api_key = api_key or settings.wiro_api_key
        self.api_secret = api_secret if api_secret is not None else settings.wiro_api_secret
        self.base_url = _normalize_base_url(base_url or settings.wiro_base_url)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.poll_max_attempts = poll_max_attempts
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> WiroClient:
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def generate_image(
        self,
        slug: str,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        negative_prompt: str | None = None,
        resolution: str = "2K",
        max_images: int = 1,
        watermark: bool = False,
        input_image: str | list[str] | None = None,
        seed: int | None = None,
        **extra: Any,
    ) -> GenerationResult:
        """Submit image generation job and wait for the rendered URL."""
        validate_wiro_image_input_budget(
            slug=slug,
            input_image=input_image,
            max_images=max_images,
        )
        params = _image_run_params(
            slug=slug,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
            resolution=resolution,
            max_images=max_images,
            watermark=watermark,
            input_image=input_image,
            seed=seed,
            extra=extra,
        )
        return await self._run(slug=slug, asset_type="image", params=params)

    # ─── Phase 23 — Voice + Talking Head + Action Video ────────────────────

    async def generate_voice(
        self,
        text: str,
        *,
        language: str = "Turkish",
        voice_clone_audio_url: Optional[str] = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        temperature: float = 0.8,
        slug: str = "resemble-ai/chatterbox-multilingual",
        **extra: Any,
    ) -> "GenerationResult":
        """Generate Türkçe (or other language) TTS via Chatterbox Multilingual.

        Voice cloning supported: provide a short reference audio URL via
        `voice_clone_audio_url` (any Turkish sample of Cansu's intended voice)
        and the model will clone its timbre + speak the provided `text`.
        """
        params: dict[str, Any] = {
            "prompt": text,
            "language": language,
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
            "temperature": temperature,
            "topP": extra.pop("topP", 1.0),
        }
        if voice_clone_audio_url:
            params["inputAudio"] = voice_clone_audio_url
        params.update(extra)
        return await self._run(slug=slug, asset_type="voice", params=params)

    async def generate_talking_avatar(
        self,
        portrait_url: str,
        audio_url: str,
        *,
        slug: str = "wiro/memo",
        resolution: int = 720,
        fps: int = 24,
        seed: Optional[int] = None,
        **extra: Any,
    ) -> "GenerationResult":
        """Audio-driven talking avatar — single portrait + audio → lip-synced video.

        Supported slugs (in order of preference):
        - `wiro/memo`         — Memory-Guided Diffusion for Expressive Talking
        - `pruna/p-video-avatar` — Pruna talking avatar (60s compute)
        - `Alibaba-Quark/Live-Avatar` — Streaming audio-driven avatar
        """
        slug_l = slug.lower()
        # Per-slug param dispatch (verified via Wiro Tool/Detail 2026-05-17).
        if "memo" in slug_l:
            # MEMO accepts URL via the fileinput field directly (multipart-string).
            params: dict[str, Any] = {
                "inputImage": portrait_url,
                "inputAudio": audio_url,
                "resolution": resolution,
                "fps": fps,
            }
            if seed is not None:
                params["seed"] = str(seed)
        elif "live-avatar" in slug_l:
            # Alibaba-Quark/Live-Avatar — has BOTH `inputImage` (fileinput) and
            # `inputImageUrl` (text) variants. When passing remote URLs we must
            # use the *Url fields, otherwise Wiro returns 'request-files-required'.
            params = {
                "inputImageUrl": portrait_url,
                "inputAudioUrl": audio_url,
                "prompt": extra.pop("prompt", "Person is talking, calm focused"),
                "seed": str(seed) if seed is not None else "42",
            }
        elif "p-video-avatar" in slug_l:
            params = {
                "inputImage": portrait_url,
                "inputAudio": audio_url,
                "resolution": f"{resolution}p",
                "videoPrompt": extra.pop("videoPrompt", "The person is talking."),
                "voicePrompt": extra.pop("voicePrompt", "Say the following."),
                "disableSafetyFilter": "true",
                "seed": str(seed) if seed is not None else "0",
            }
        else:
            raise ValueError(f"unknown talking-avatar slug: {slug}")
        params.update(extra)
        return await self._run(slug=slug, asset_type="video", params=params)

    async def generate_action_video(
        self,
        prompt: str,
        *,
        slug: str = "bytedance/seedance-2-0",
        input_image_url: Optional[str] = None,
        aspect_ratio: str = "9:16",
        duration: str = "5",
        resolution: str = "720p",
        generate_audio: bool = False,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        **extra: Any,
    ) -> "GenerationResult":
        """Action / motion video gen — Cansu's anchor image + motion prompt.

        Slug families and their param flavours (verified via Wiro Tool/Detail):
        - ByteDance Seedance: `ratio`, `duration`, `generateAudio`, snake-ish
        - Kling V3:           `ratio`, `duration`, `sound`, `mode` (std/pro/4k)
        - Google Veo3:        `aspectRatio`, `durationSeconds`, `generateAudio`,
                              `inputImage` (start frame)
        """
        slug_l = slug.lower()

        if "veo3" in slug_l or slug_l.startswith("google/"):
            # Veo family — camelCase params
            params: dict[str, Any] = {
                "prompt": prompt,
                "aspectRatio": aspect_ratio,
                "durationSeconds": str(duration),
                "resolution": resolution,
            }
            if generate_audio:
                params["generateAudio"] = "true"
            else:
                params["generateAudio"] = "false"
            if input_image_url:
                params["inputImage"] = input_image_url
            if negative_prompt:
                params["negativePrompt"] = negative_prompt
            if seed is not None:
                params["seed"] = str(seed)

        elif "kling" in slug_l:
            # Kling V3 / V3 Omni family — supports up to 3 reference images
            # (inputImage + inputImage2 + inputImage3) for identity consistency.
            # `referType="feature"` tells Kling to preserve facial identity.
            params = {
                "prompt": prompt,
                "ratio": aspect_ratio,
                "duration": str(duration),
                "mode": extra.pop("mode", "std"),
                "sound": "on" if generate_audio else "off",
                "referType": extra.pop("refer_type", "feature"),
                "originalSound": extra.pop("original_sound", "no"),
                "multiShot": "true" if extra.pop("multi_shot", False) else "false",
            }
            if input_image_url:
                params["inputImage"] = input_image_url
            img2 = extra.pop("input_image_url_2", None)
            img3 = extra.pop("input_image_url_3", None)
            if img2:
                params["inputImage2"] = img2
            if img3:
                params["inputImage3"] = img3
            if negative_prompt:
                params["negativePrompt"] = negative_prompt
            if seed is not None:
                params["seed"] = str(seed)

        elif "seedance" in slug_l or slug_l.startswith("bytedance/"):
            # Seedance family — uses `ratio` + `duration` (snake-ish/inconsistent)
            params = {
                "prompt": prompt,
                "ratio": aspect_ratio,
                "duration": str(duration),
                "resolution": resolution,
            }
            if "seedance-2" in slug_l or "seedance 2" in slug_l:
                params["generateAudio"] = "true" if generate_audio else "false"
            if input_image_url:
                # Note: lite-v1 prefers inputImageUrl; pro-fast uses inputImage
                if "lite-v1" in slug_l:
                    params["inputImageUrl"] = input_image_url
                else:
                    params["inputImage"] = input_image_url
            if seed is not None:
                params["seed"] = str(seed)

        else:
            # Fallback — pass through Wiro-style params
            params = {
                "prompt": prompt,
                "aspectRatio": aspect_ratio,
                "duration": str(duration),
            }
            if input_image_url:
                params["inputImage"] = input_image_url

        params.update(extra)
        return await self._run(slug=slug, asset_type="video", params=params)

    async def _run(
        self,
        slug: str,
        asset_type: Literal["image", "video", "voice"],
        params: dict[str, Any],
    ) -> GenerationResult:
        if self._client is None:
            raise RuntimeError("WiroClient must be used as async context manager")

        if not self.api_key:
            raise RuntimeError("WIRO_API_KEY is not configured")

        payload = {k: v for k, v in params.items() if v is not None}
        has_file_input = _has_file_input(payload)
        headers = self._headers(json_content_type=not has_file_input)

        # 1. Submit
        t0 = time.perf_counter()
        if has_file_input:
            submit = await self._client.post(
                f"{self.base_url}/Run/{slug}",
                headers=headers,
                files=_multipart_form_fields(payload),
            )
        else:
            submit = await self._client.post(
                f"{self.base_url}/Run/{slug}",
                headers=headers,
                json=payload,
            )
        submit.raise_for_status()
        submit_data = submit.json()
        _raise_if_wiro_error(submit_data, context="submit")
        task_token = _extract_task_token(submit_data)
        task_uuid = _extract_task_id(submit_data) or task_token
        if not task_token:
            raise RuntimeError(
                f"Wiro submit returned no task token: {_sanitize_wiro_payload(submit_data)}"
            )

        logger.info(f"wiro.submit slug={slug} task={task_uuid}")

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
            _raise_if_wiro_error(detail_data, context="task detail")
            task = _extract_task(detail_data)
            status = str(task.get("status", "")).lower()
            if status == "task_postprocess_end":
                pexit = str(task.get("pexit", ""))
                if pexit == "0":
                    final_task = task
                    break
                raise RuntimeError(
                    f"Wiro task {task_uuid} failed: {_sanitize_wiro_payload(task)}"
                )
            if status in ("completed", "success", "succeeded"):
                final_task = task
                break
            if status in ("failed", "error", "cancelled", "task_cancel"):
                raise RuntimeError(
                    f"Wiro task {task_uuid} failed: {_sanitize_wiro_payload(task)}"
                )
        else:
            raise TimeoutError(f"Wiro task {task_uuid} did not complete in time")

        result_data = final_task or {}
        asset_url = _extract_asset_url(result_data)
        if not asset_url:
            raise RuntimeError(
                f"Wiro result missing asset URL: {_sanitize_wiro_payload(result_data)}"
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)
        cost = _extract_cost_usd(result_data)
        logger.info(
            f"wiro.complete slug={slug} task={task_uuid} latency_ms={latency_ms} cost_usd={cost}"
        )

        return GenerationResult(
            asset_url=asset_url,
            asset_type=asset_type,
            model_slug=slug,
            task_uuid=task_uuid,
            cost_usd=cost,
            latency_ms=latency_ms,
            raw_response=detail_data or result_data,
        )

    def _headers(self, *, json_content_type: bool = True) -> dict[str, str]:
        headers = {"Content-Type": "application/json"} if json_content_type else {}
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


def _normalize_base_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    if url.endswith("/api"):
        return f"{url}/v1"
    return f"{url}/v1"


def _raise_if_wiro_error(payload: dict[str, Any], *, context: str) -> None:
    if payload.get("result") is False:
        detail = payload.get("errors") or payload
        raise RuntimeError(f"Wiro {context} failed: {_sanitize_wiro_payload(detail)}")


def _has_file_input(payload: dict[str, Any]) -> bool:
    # Models that accept inputImage / inputImage2 / inputImage3 / inputAudio
    # (with fileinput type) need multipart submission. Some models also expose
    # *Url text variants — Wiro accepts these via multipart but rejects them
    # via JSON (returns 'request-files-required').
    file_keys = (
        "inputImage", "inputImage2", "inputImage3",
        "inputImageUrl", "inputImageUrl2", "inputImageUrl3",
        "inputAudio", "inputAudioUrl",
        "inputVideo", "inputVideoUrl",
    )
    return any(k in payload for k in file_keys)


def _multipart_form_fields(payload: dict[str, Any]) -> list[tuple[str, tuple[None, str]]]:
    fields: list[tuple[str, tuple[None, str]]] = []
    for key, value in payload.items():
        if isinstance(value, list):
            fields.extend((key, (None, str(item))) for item in value)
        else:
            fields.append((key, (None, str(value))))
    return fields


def _image_run_params(
    *,
    slug: str,
    prompt: str,
    aspect_ratio: str,
    negative_prompt: str | None,
    resolution: str,
    max_images: int,
    watermark: bool,
    input_image: str | list[str] | None,
    seed: int | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    if slug == "openai/gpt-image-2":
        output_format = extra.pop("output_format", extra.pop("outputFormat", "jpeg"))
        output_compression = extra.pop(
            "output_compression",
            extra.pop("outputCompression", 95),
        )
        return {
            "prompt": prompt,
            "inputImage": input_image,
            "inputImageMask": extra.pop(
                "input_image_mask",
                extra.pop("inputImageMask", None),
            ),
            "resolution": _normalize_wiro_resolution(resolution, slug=slug),
            "ratio": _normalize_wiro_aspect_ratio(aspect_ratio, slug=slug),
            "quality": extra.pop("quality", "high"),
            "background": extra.pop("background", "auto"),
            "outputFormat": output_format,
            "outputCompression": output_compression,
            "samples": max_images,
            "moderation": extra.pop("moderation", "low"),
            **extra,
        }
    return {
        "prompt": prompt,
        "aspectRatio": _normalize_wiro_aspect_ratio(aspect_ratio, slug=slug),
        "resolution": _normalize_wiro_resolution(resolution, slug=slug),
        "maxImages": max_images,
        "watermark": str(watermark).lower(),
        "inputImage": input_image,
        "negativePrompt": negative_prompt,
        "seed": seed,
        **extra,
    }


def _image_model_spec(slug: str) -> WiroImageModelSpec:
    return _WIRO_IMAGE_MODEL_SPECS.get(slug.lower(), _DEFAULT_IMAGE_MODEL_SPEC)


def _input_image_count(input_image: str | list[str] | None) -> int:
    if input_image is None:
        return 0
    if isinstance(input_image, list):
        return len(input_image)
    return 1


def _normalize_wiro_aspect_ratio(aspect_ratio: str, *, slug: str) -> str:
    aliases = {"1.91:1": "16:9"}
    return aliases.get(aspect_ratio, aspect_ratio)


def _normalize_wiro_resolution(resolution: str, *, slug: str) -> str:
    if slug == "openai/gpt-image-2":
        return resolution.lower()
    if slug.lower().startswith("bytedance/seedream"):
        return resolution.lower()
    return resolution


_REDACTED_WIRO_VALUE = "[redacted-sensitive-provider-value]"
_SENSITIVE_WIRO_KEYS = {
    "authorization",
    "inputimage",
    "input_image",
    "signed_reference_urls",
    "socketaccesstoken",
    "tasktoken",
    "token",
    "x-api-key",
}
_SENSITIVE_WIRO_MARKERS = (
    "/object/sign/",
    "reference-anchors",
    "service_role",
    "signed_reference_urls",
    "socketaccesstoken",
    "token=",
)


def _sanitize_wiro_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_WIRO_KEYS:
                sanitized[key] = _REDACTED_WIRO_VALUE
            else:
                sanitized[key] = _sanitize_wiro_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_wiro_payload(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in _SENSITIVE_WIRO_MARKERS):
            return _REDACTED_WIRO_VALUE
    return value


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


def _extract_asset_url(task: dict[str, Any]) -> str:
    candidates = [task.get("output_url"), task.get("url"), task.get("output")]
    outputs = task.get("outputs")
    if isinstance(outputs, list):
        for output in outputs:
            if isinstance(output, dict):
                candidates.extend([output.get("url"), output.get("path")])
            elif isinstance(output, str):
                candidates.append(output)
    return next((str(value) for value in candidates if value), "")


def _extract_cost_usd(task: dict[str, Any]) -> float:
    value = task.get("totalcost") or task.get("cost_usd") or 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
