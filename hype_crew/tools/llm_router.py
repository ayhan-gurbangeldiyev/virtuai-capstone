"""LiteLLM Router — direct LLM çağrıları için dayanıklılık + telemetri katmanı.

Amaç (kırılganlık kök-neden fix): çıplak httpx/SDK LLM çağrılarını tek bir Router
arkasına alıp **uniform timeout + bounded retry + per-deployment cooldown
(devre-kesici) + gerçek per-call cost/latency telemetri** sağlamak.

Flag'li: `settings.litellm_router_enabled` (default OFF). Kapalıyken mevcut httpx/SDK
yolları AYNEN çalışır → sıfır davranış değişikliği / anında rollback. Açıkken her
call-site fail-open: router hata verirse çıplak yola düşülür (içerik akışı durmaz).

NOT: crewai 1.14 kendi LLM'ini kullanır (litellm DEĞİL); bu Router yalnız DIRECT
çağrılar içindir, crew agent'larına dokunmaz.

Mimari: tek çekirdek `router_chat_messages` + ince sarmalar (json / json_sync / vision).
model_name yönlendirme: gate-fast / gate-smart / writer / vision → her site kendi modelini
çağırır. Dayanıklılık: retry+timeout(<gate'lerin 40s'i)+cooldown. GATE'lerde cross-model
fallback YOK (kalite-kritik JSON; farklı model JSON şemasını bozabilir) — model_fast==
model_smart (ikisi de gemini-flash) olduğundan ayrı fallback modeli zaten yok; retry yeter.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from loguru import logger

_ROUTER = None

# Site → model_name → settings model string eşlemesi (lazy, _build_router'da çözülür).
_MODEL_NAMES = ("gate-fast", "gate-smart", "writer", "vision")

# Dayanıklılık parametreleri (risk-agent: timeout gate'lerin 40s httpx'inin ALTINDA
# olmalı ki LangGraph node timeout'u ile çakışmasın → 35).
_NUM_RETRIES = 2
_TIMEOUT_S = 35
_ALLOWED_FAILS = 3       # /dakika eşik → sağlıksız deployment cooldown'a alınır
_COOLDOWN_S = 30


def router_enabled() -> bool:
    try:
        from config import settings
        return bool(getattr(settings, "litellm_router_enabled", False))
    except Exception:  # noqa: BLE001
        return False


def _build_router():
    from litellm import Router
    from config import settings
    key = settings.openrouter_api_key
    fast = settings.model_fast       # openrouter/google/gemini-3-flash-preview
    smart = settings.model_smart
    writer = getattr(settings, "writer_model", "") or smart
    if writer and not writer.startswith("openrouter/"):
        writer = f"openrouter/{writer}"   # OpenRouter key'i kullanılsın
    model_list = [
        {"model_name": "gate-fast",  "litellm_params": {"model": fast,   "api_key": key, "timeout": _TIMEOUT_S}},
        {"model_name": "gate-smart", "litellm_params": {"model": smart,  "api_key": key, "timeout": _TIMEOUT_S}},
        {"model_name": "writer",     "litellm_params": {"model": writer, "api_key": key, "timeout": 60}},
        {"model_name": "vision",     "litellm_params": {"model": fast,   "api_key": key, "timeout": 45}},
    ]
    return Router(
        model_list=model_list,
        num_retries=_NUM_RETRIES,
        timeout=_TIMEOUT_S,
        allowed_fails=_ALLOWED_FAILS,
        cooldown_time=_COOLDOWN_S,
    )


def get_router():
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = _build_router()
    return _ROUTER


def _meta_from(resp, t0: float, fallback_model: str) -> dict:
    latency_ms = int((time.perf_counter() - t0) * 1000)
    usage = getattr(resp, "usage", None)
    tokens = int(getattr(usage, "total_tokens", 0) or 0)
    cost = 0.0
    try:
        from litellm import completion_cost
        cost = float(completion_cost(completion_response=resp) or 0.0)
    except Exception:  # noqa: BLE001
        pass
    return {"model": getattr(resp, "model", None) or fallback_model,
            "tokens": tokens, "cost_usd": cost, "latency_ms": latency_ms}


def _strip_fence(txt: str) -> str:
    txt = (txt or "").strip()
    if txt.startswith("```"):
        txt = "\n".join(txt.split("\n")[1:])
        if txt.rstrip().endswith("```"):
            txt = "\n".join(txt.rstrip().split("\n")[:-1])
    return txt.strip()


async def router_chat_messages(
    messages: list[dict[str, Any]], *, model_name: str = "gate-fast",
    temperature: float = 0.0, max_tokens: int = 500,
    response_format: Optional[dict] = None,
) -> tuple[str, dict]:
    """ÇEKİRDEK — OpenAI-uyumlu messages (vision image_url içerik blokları dahil) ile
    Router üzerinden async completion. Döner: (ham_metin, meta). Tüm sarmalar bunu çağırır."""
    r = get_router()
    t0 = time.perf_counter()
    kw: dict[str, Any] = {"model": model_name, "messages": messages,
                          "temperature": temperature, "max_tokens": max_tokens}
    if response_format is not None:
        kw["response_format"] = response_format
    resp = await r.acompletion(**kw)
    return (resp.choices[0].message.content or ""), _meta_from(resp, t0, model_name)


async def router_chat_json(system: str, user: str, *, temperature: float = 0.0,
                           max_tokens: int = 500, model: Optional[str] = None,
                           model_name: str = "gate-fast") -> tuple[dict, dict]:
    """card_gates.chat_json ile AYNI imza + dönüş: (parsed_json, meta). Async, JSON gate'ler."""
    txt, meta = await router_chat_messages(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model_name=model_name, temperature=temperature, max_tokens=max_tokens,
        response_format={"type": "json_object"})
    return json.loads(_strip_fence(txt)), meta


def router_chat_json_sync(system: str, user: str, *, temperature: float = 0.0,
                          max_tokens: int = 500, model_name: str = "gate-fast") -> tuple[dict, dict]:
    """Sync call-site'lar için (httpx.Client / openai sync SDK kullananlar). Router.completion (sync)."""
    r = get_router()
    t0 = time.perf_counter()
    resp = r.completion(
        model=model_name,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature, max_tokens=max_tokens,
        response_format={"type": "json_object"})
    txt = resp.choices[0].message.content or ""
    return json.loads(_strip_fence(txt)), _meta_from(resp, t0, model_name)
