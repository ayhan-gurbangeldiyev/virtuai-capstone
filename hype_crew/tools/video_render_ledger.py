"""Video render defteri — "ödenen render asla çöpe gitmez" katmanı.

2026-06-10 (Berkay: "video işi çok pahalı, 3 defa generate etme lüksümüz
yok"). O günkü kaza: temiz script'le render TAMAMLANDI ($2-3 ödendi) ama
süreç persist'ten önce öldürüldü → video HeyGen'de öksüz kaldı, sistem
sıfırdan yeni render başlattı. Bu modül üç şeyi garanti eder:

1. SUBMIT ANINDA KAYIT: HeyGen'e giden her render, script hash'i +
   narration URL'siyle video_render_log'a yazılır. Süreç ölse bile iz var.
2. SALVAGE-FIRST: produce_video render başlatmadan önce deftere bakar —
   aynı persona+pipeline+script_sha için son 24 saatte submitted/completed
   kayıt varsa YENİ RENDER YOK: mevcut HeyGen video_id'si poll edilir
   (tamamlanmışsa anında döner) ve boru hattı oradan devam eder.
3. BÜTÇE GÖRÜNÜRLÜĞÜ: günlük video bütçesi yalnız biten run'ları sayıyordu;
   ölen denemelerin harcaması görünmezdi. Defterdeki consumed-olmayan
   kayıtlar bütçeye dahil edilir (consumed olanlar run maliyetine girer,
   çift sayım olmaz).

Tüm fonksiyonlar best-effort: defter hatası render'ı ASLA durdurmaz
(eski davranışa düşer), sadece loglanır.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from loguru import logger

from .supabase_client import make_supabase

_TABLE = "video_render_log"


def script_sha(script_text: str) -> str:
    return hashlib.sha256((script_text or "").strip().encode("utf-8")).hexdigest()


def log_submit(
    *,
    persona_id: str,
    pipeline: str,
    sha: str,
    heygen_video_id: str,
    narration_url: Optional[str],
    est_cost_usd: float,
) -> None:
    try:
        make_supabase().table(_TABLE).insert({
            "persona_id": persona_id,
            "pipeline": pipeline,
            "script_sha": sha,
            "heygen_video_id": heygen_video_id,
            "narration_url": narration_url,
            "status": "submitted",
            "est_cost_usd": round(float(est_cost_usd), 4),
        }).execute()
        logger.info(f"[render-ledger] submit kaydı: {heygen_video_id[:12]} est=${est_cost_usd:.2f}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[render-ledger] submit kaydı başarısız (devam): {e}")


def mark_completed(heygen_video_id: str, *, duration_sec: float, cost_usd: float) -> None:
    try:
        make_supabase().table(_TABLE).update({
            "status": "completed",
            "duration_sec": round(float(duration_sec), 2),
            "est_cost_usd": round(float(cost_usd), 4),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("heygen_video_id", heygen_video_id).execute()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[render-ledger] completed güncellemesi başarısız: {e}")


def mark_consumed(heygen_video_id: str) -> None:
    """Render bir draft'a/run'a başarıyla bağlandı — maliyeti artık run
    tarafında sayılır, defterden bütçe çift-sayımı düşer."""
    try:
        make_supabase().table(_TABLE).update({
            "status": "consumed",
            "consumed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("heygen_video_id", heygen_video_id).execute()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[render-ledger] consumed güncellemesi başarısız: {e}")


def find_salvageable(
    *, persona_id: str, pipeline: str, sha: str, hours: int = 24,
) -> Optional[dict[str, Any]]:
    """Aynı script için ödenmiş/yolda render var mı? En yenisini döndürür."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = (
            make_supabase().table(_TABLE)
            .select("heygen_video_id, narration_url, status, est_cost_usd, created_at")
            .eq("persona_id", persona_id)
            .eq("pipeline", pipeline)
            .eq("script_sha", sha)
            .in_("status", ["submitted", "completed"])
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ).data or []
        return rows[0] if rows else None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[render-ledger] salvage sorgusu başarısız (yeni render): {e}")
        return None


def unconsumed_spend_today(persona_id: str) -> float:
    """Bugünün consumed-OLMAYAN render harcaması (bütçe görünürlüğü).
    Consumed kayıtlar run maliyetinde zaten sayılır — çift sayım yok."""
    try:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        rows = (
            make_supabase().table(_TABLE)
            .select("est_cost_usd")
            .eq("persona_id", persona_id)
            .in_("status", ["submitted", "completed", "failed"])
            .gte("created_at", start)
            .execute()
        ).data or []
        return sum(float(r.get("est_cost_usd") or 0) for r in rows)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[render-ledger] bütçe sorgusu başarısız (0 sayılır): {e}")
        return 0.0
