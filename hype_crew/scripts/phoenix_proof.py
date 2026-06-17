"""Phoenix yerel kanıt — obs.init_tracing + openai SDK çağrısı → trace export.

YEREL TEST AMAÇLI (prod'a dokunmaz). Çalıştırma:
  PHOENIX_TRACING_ENABLED=1 PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces \
  PHOENIX_PROJECT_NAME=cansu-phoenix-proof venv/bin/python -m scripts.phoenix_proof
"""
from __future__ import annotations

import os
import sys

# hype_crew kökünü sys.path'e ekle (obs.py top-level import için)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# .env'den sadece OPENROUTER_API_KEY (değer ekrana basılmaz)
from dotenv import dotenv_values

_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
_key = _env.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
if not _key:
    print("HATA: OPENROUTER_API_KEY yok"); sys.exit(1)

from obs import init_tracing  # noqa: E402

tp = init_tracing()
if tp is None:
    print("HATA: init_tracing None döndü (flag kapalı?)"); sys.exit(1)
print("[proof] tracing init OK")

# openai SDK → OpenRouter (OpenAIInstrumentor bu çağrıyı auto-instrument yakalar)
from openai import OpenAI  # noqa: E402

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=_key)
resp = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Reply with exactly one word: pong"}],
    max_tokens=5,
    temperature=0,
)
out = resp.choices[0].message.content
print(f"[proof] LLM yanıtı: {out!r}")
print(f"[proof] token usage: {resp.usage}")

# BatchSpanProcessor'ı zorla flush et (çıkmadan önce span'ler gitsin)
try:
    tp.force_flush()
    print("[proof] span force_flush OK")
except Exception as e:
    print(f"[proof] force_flush uyarı: {e}")
print("[proof] DONE")
