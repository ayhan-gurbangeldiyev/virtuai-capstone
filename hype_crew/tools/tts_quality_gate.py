"""TTS kalite kapısı — narration sesini render'dan ÖNCE denetler (13 Haz 2026).

Akış: TTS sesini Whisper'la yazıya çevir → amaçlanan script ile karşılaştır.
Kötüyse (kelime düşmüş/garbled, sayı/özel ad/yabancı kelime yanlış telaffuz) →
çağıran script'i yenileyip yeniden TTS dener ya da video'yu atlar.

FAIL-OPEN: her hata → ok=True (video'yu engelleme; bu güvenlik değil, kalite).
Transcribe: OpenAI Whisper (settings.openai_api_key varsa) → yoksa fal-whisper.
Hakem: OpenRouter gemini-flash (clarity_gate ile aynı patern).
"""
import json
import logging
import re

import httpx
from config import settings

logger = logging.getLogger(__name__)

_JUDGE_SYS = (
    "Sen bir TTS kalite denetçisisin. Sana (1) bir videonun AMAÇLANAN narration "
    "script'i ve (2) o sesin Whisper transkripti verilir. Karşılaştır:\n"
    "- Aynı içeriği mi söylüyor? Cümle/kelime DÜŞMÜŞ ya da GARBLED mı?\n"
    "- SAYILAR, ÖZEL ADLAR (OpenAI, Codex...), yabancı kelimeler YANLIŞ "
    "telaffuz/transkript olmuş mu (transkriptte saçma ya da yanlış kelime)?\n"
    "Whisper'ın küçük imla/noktalama farkları SORUN DEĞİL — onları yok say. "
    "SADECE anlamı bozan, kelime düşüren ya da bariz yanlış telaffuz KÖTÜdür.\n"
    'SADECE JSON döndür: {"ok": true/false, "reason": "kısa Türkçe", '
    '"bad_terms": ["sorunlu kelime/ifade", ...]}'
)

_WORD_RE = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)


def _coverage(script: str, transcript: str) -> float:
    sw = set(_WORD_RE.findall((script or "").lower()))
    tw = set(_WORD_RE.findall((transcript or "").lower()))
    if not sw:
        return 1.0
    return len(sw & tw) / len(sw)


async def _judge(script: str, transcript: str) -> dict:
    key = (settings.openrouter_api_key or "").strip()
    if not key:
        return {"ok": True, "reason": "hakem yok (fail-open)", "bad_terms": []}
    model = getattr(
        settings, "model_fast", "openrouter/google/gemini-3-flash-preview"
    ).removeprefix("openrouter/")
    user = f"AMAÇLANAN SCRIPT:\n{script[:1500]}\n\nWHISPER TRANSKRİPT:\n{transcript[:1500]}"

    # LiteLLM Router dalı (flag-gated, fail-open). JSON gate (model_fast) → router_chat_json
    # model_name="gate-fast"; parsed dict alınıp aşağıdaki MEVCUT dönüş şekline (ok/reason/
    # bad_terms) çevrilir. Kapalı/hatalı iken aşağıdaki httpx yolu byte-identical çalışır.
    try:
        from .llm_router import router_enabled, router_chat_json
        if router_enabled():
            try:
                d, _meta = await router_chat_json(
                    _JUDGE_SYS, user,
                    temperature=0, max_tokens=200, model_name="gate-fast",
                )
                return {
                    "ok": bool(d.get("ok", True)),
                    "reason": str(d.get("reason", ""))[:200],
                    "bad_terms": [str(x)[:60] for x in (d.get("bad_terms") or [])][:10],
                }
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[tts-gate] router atlandı, httpx'e düşülüyor: {type(e).__name__}: {str(e)[:90]}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[tts-gate] router import hatası, httpx'e düşülüyor: {str(e)[:90]}")

    try:
        async with httpx.AsyncClient(timeout=40.0) as c:
            r = await c.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": 0,
                    "max_tokens": 200,
                    "messages": [
                        {"role": "system", "content": _JUDGE_SYS},
                        {"role": "user", "content": user},
                    ],
                },
            )
            r.raise_for_status()
            out = (r.json()["choices"][0]["message"]["content"] or "").strip()
        if out.startswith("```"):
            out = "\n".join(out.split("\n")[1:])
            if out.endswith("```"):
                out = out.rsplit("```", 1)[0]
            out = out.strip()
        d = json.loads(out)
        return {
            "ok": bool(d.get("ok", True)),
            "reason": str(d.get("reason", ""))[:200],
            "bad_terms": [str(x)[:60] for x in (d.get("bad_terms") or [])][:10],
        }
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[tts-gate] hakem hata (fail-open): {type(e).__name__}: {str(e)[:90]}")
        return {"ok": True, "reason": "hakem hata (fail-open)", "bad_terms": []}


async def _transcribe_openai(audio_bytes: bytes) -> str:
    key = (getattr(settings, "openai_api_key", "") or "").strip()
    if not key or not audio_bytes:
        return ""
    try:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": ("narration.mp3", audio_bytes, "audio/mpeg")},
                data={"model": "whisper-1", "language": "tr"},
            )
            r.raise_for_status()
            return (r.json().get("text") or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[tts-gate] OpenAI Whisper hata: {type(e).__name__}: {str(e)[:90]}")
        return ""


async def _transcribe_fal(narration_url: str) -> str:
    if not narration_url:
        return ""
    try:
        from tools.fal_whisper_client import FalWizperClient
        async with FalWizperClient() as w:
            res = await w.transcribe(narration_url, language="tr")
        return (getattr(res, "plain_text", "") or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[tts-gate] fal-whisper hata: {type(e).__name__}: {str(e)[:90]}")
        return ""


async def transcribe(audio_bytes: bytes, narration_url: str) -> tuple[str, str]:
    """(transkript, kaynak). OpenAI key varsa OpenAI Whisper, yoksa fal-whisper."""
    if (getattr(settings, "openai_api_key", "") or "").strip():
        t = await _transcribe_openai(audio_bytes)
        if t:
            return t, "openai"
    t = await _transcribe_fal(narration_url)
    return t, "fal"


async def run_tts_gate(audio_bytes: bytes, narration_url: str, script: str) -> dict:
    """Sesi denetle. {ok, reason, bad_terms, transcript, source}. FAIL-OPEN."""
    mode = (getattr(settings, "cansu_tts_gate_mode", "balanced") or "balanced").lower()
    cov_floor = 0.78 if mode == "strict" else 0.70
    try:
        transcript, src = await transcribe(audio_bytes, narration_url)
        if not transcript:
            return {"ok": True, "reason": "transkript alınamadı (fail-open)",
                    "bad_terms": [], "transcript": "", "source": src}
        cov = _coverage(script, transcript)
        if cov < cov_floor:
            return {"ok": False, "reason": f"kelime kapsama düşük ({cov:.0%} < {cov_floor:.0%})",
                    "bad_terms": [], "transcript": transcript, "source": src}
        j = await _judge(script, transcript)
        j["transcript"] = transcript
        j["source"] = src
        return j
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[tts-gate] gate hata (fail-open): {type(e).__name__}: {str(e)[:90]}")
        return {"ok": True, "reason": "gate hata (fail-open)", "bad_terms": [], "transcript": "", "source": ""}
