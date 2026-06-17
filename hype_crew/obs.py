"""Phoenix/OpenInference observability — opsiyonel, observe-only, flag-gated.

Katman B (gözlemlenebilirlik). Self-host Phoenix'e (veri VM'de kalır) LLM/agent
trace'i gönderir. CrewAI + LangGraph + OpenAI-SDK→OpenRouter çağrıları
openinference auto-instrument ile yakalanır.

GÜVENLİK:
- `PHOENIX_TRACING_ENABLED` (default "0") → tamamen KAPALI: register() hiç çağrılmaz,
  hiçbir instrumentor patch etmez → sıfır overhead, sıfır davranış değişikliği.
- batch=True → BatchSpanProcessor (arka planda, non-blocking export) → pipeline asla
  Phoenix I/O'da bloklanmaz.
- init_tracing() tamamen try/except içinde → Phoenix paketi yoksa / endpoint bozuksa /
  collector down ise pipeline ETKİLENMEZ (fail-open).

Kullanım: runner girişinde bir kez `from obs import init_tracing; init_tracing()`.
"""
from __future__ import annotations

import os

from loguru import logger

_INITED = False


def tracing_enabled() -> bool:
    return os.getenv("PHOENIX_TRACING_ENABLED", "0") == "1"


def init_tracing():
    """Phoenix tracing'i başlat (flag açıksa). Hata = sessiz no-op (fail-open).
    İdempotent: birden fazla çağrı zararsız."""
    global _INITED
    if _INITED or not tracing_enabled():
        return None
    try:
        # KRİTİK: config.py OTEL_SDK_DISABLED=true set ediyor (crewai anonim telemetrisini
        # kısmak için). Bu generic OTel kill-switch'i, AÇIK tracing'de auto-instrument
        # span'lerini de no-op'lar (NonRecordingSpan → hiçbir şey export edilmez). Tracing
        # flag'i açıkken kaldır; crewai'nin KENDİ ürün telemetrisi CREWAI_DISABLE_TELEMETRY
        # ile ayrıca kapalı kalır (ona dokunmuyoruz).
        import os as _os
        _os.environ.pop("OTEL_SDK_DISABLED", None)
        from phoenix.otel import register
        endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT",
                             "http://localhost:6006/v1/traces")
        project = os.getenv("PHOENIX_PROJECT_NAME", "cansu-hype-crew")
        tp = register(
            project_name=project,
            endpoint=endpoint,
            auto_instrument=True,   # yüklü openinference-* instrumentor'larını açar
            batch=True,             # non-blocking arka plan export
        )
        _INITED = True
        logger.info(f"[obs] Phoenix tracing AÇIK → {endpoint} (project={project})")
        return tp
    except Exception as e:  # noqa: BLE001 — gözlemlenebilirlik ASLA pipeline'ı bloklamaz
        logger.warning(f"[obs] Phoenix tracing başlatılamadı (no-op, pipeline etkilenmez): {e}")
        return None
