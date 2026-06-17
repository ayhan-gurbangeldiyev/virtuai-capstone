"""LangGraph checkpoint GC — terminal + eski thread'lerin checkpoint'lerini prune et.

NEDEN: PostgresSaver'da TTL YOK (langgraph-checkpoint-postgres 3.1; docs doğrulandı) →
checkpoint'ler delete_thread/manuel DELETE'e kadar sonsuza dek birikir. durability="sync"
+ büyük nested HypeFlowState → TEK run ~172 satır (Stage B gözlemi) bırakıyor. Flag-on
sonrası bu birikir → langgraph.checkpoint_blobs şişer.

RESUME-SAFETY INVARIANT (ihlal edilemez): bir thread YALNIZCA
  hype_runs.status ∈ {completed, failed}  VE  graph.get_state(cfg).next == ()  (boş)
iken silinir. `.next` dolu = kesilmiş, resume bekliyor → ASLA SİLME. (Bu, get_resumable_run_id'nin
resume için kullandığı `.next` koşulunun negatifi — prune ve resume mantıksal olarak ayrık.)

RETENTION: terminal run'lara RETENTION_DAYS gün tolerans (debug/inceleme penceresi);
yalnız bundan eski + terminal + .next-boş thread'ler silinir. delete_thread (resmî API)
3 tabloyu da (checkpoints/checkpoint_blobs/checkpoint_writes) langgraph şemasında siler.

Çalıştır (günlük systemd timer önerilir):
  cd /opt/hype-crew && set -a && . ./.env && set +a && venv/bin/python -m scripts.lg_checkpoint_gc
  --dry-run  → silmeden ne silineceğini raporla
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from loguru import logger

from config import settings

RETENTION_DAYS = 2


def main() -> int:
    ap = argparse.ArgumentParser(description="LangGraph checkpoint GC")
    ap.add_argument("--dry-run", action="store_true", help="silme, sadece raporla")
    ap.add_argument("--retention-days", type=int, default=RETENTION_DAYS)
    args = ap.parse_args()

    if not getattr(settings, "checkpoint_db_url", ""):
        logger.info("[gc] HYPE_CHECKPOINT_DB_URL boş (lokal SQLite/dev) — GC atlanıyor.")
        return 0

    import psycopg
    from tools.supabase_client import make_supabase
    from flow import AutonomousContentFlow
    from lg.graph import build_state_graph
    from lg.checkpointer import sync_checkpointer

    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.retention_days)).isoformat()
    sb = make_supabase()

    # 1) GERÇEK checkpoint'i olan thread_id'ler (langgraph şeması). CrewAI run'ları
    #    checkpoint'siz olduğundan tüm hype_runs'ı taramaktan KAÇINIRIZ — yalnız
    #    langgraph.checkpoints'te var olanlara bakarız (bounded by gerçek hacim).
    with psycopg.connect(settings.checkpoint_db_url, autocommit=True) as _c:
        _cur = _c.cursor()
        _cur.execute("SET search_path TO langgraph")
        _cur.execute("SELECT DISTINCT thread_id FROM checkpoints")
        thread_ids = [r[0] for r in _cur.fetchall()]
    logger.info(f"[gc] langgraph.checkpoints'te {len(thread_ids)} distinct thread")
    if not thread_ids:
        logger.info("[gc] checkpoint yok — TAMAM.")
        return 0

    # Pipeline thread_id == hype_runs.id (uuid). UUID-olmayan thread'ler (örn.
    # lg_pg_conntest 'conntest:...' veya başka sistemler) hype_runs'ta DEĞİL →
    # uuid kolonuna .in_() 22P02 fırlatır. Bunları ayır: yalnız geçerli-UUID
    # thread'leri hype_runs'a karşı sorgula; UUID-olmayanları DOKUNMA (bizim
    # pipeline'ımız değil) sadece logla.
    import uuid as _uuidmod

    def _is_uuid(s: str) -> bool:
        try:
            _uuidmod.UUID(str(s)); return True
        except (ValueError, AttributeError, TypeError):
            return False

    non_uuid = [t for t in thread_ids if not _is_uuid(t)]
    thread_ids = [t for t in thread_ids if _is_uuid(t)]
    if non_uuid:
        logger.info(f"[gc] {len(non_uuid)} UUID-olmayan thread atlandı (pipeline değil): {non_uuid[:5]}")
    if not thread_ids:
        logger.info("[gc] geçerli-UUID pipeline thread yok — TAMAM.")
        return 0

    # 2) Bunlardan TERMINAL (completed/failed) + completed_at eski olanları seç
    #    (tek-kaynak = hype_runs; thread_id == hype_runs.id, Faz2 stable-thread).
    terminal_old = set()
    for i in range(0, len(thread_ids), 200):
        chunk = thread_ids[i:i + 200]
        rows = (
            sb.table("hype_runs")
            .select("id, status, completed_at")
            .in_("id", chunk)
            .in_("status", ["completed", "failed"])
            .lt("completed_at", cutoff)
            .execute()
        ).data or []
        terminal_old.update(r["id"] for r in rows if r.get("id"))
    logger.info(
        f"[gc] {len(terminal_old)} aday (terminal + completed_at<{cutoff[:10]}); "
        f"{len(thread_ids) - len(terminal_old)} thread KORUNUYOR (running/yeni/orphan)"
    )

    deleted = 0
    skipped_pending = 0
    with sync_checkpointer() as cp:
        graph = build_state_graph(AutonomousContentFlow()).compile(checkpointer=cp)
        for tid in terminal_old:
            try:
                snap = graph.get_state({"configurable": {"thread_id": tid}})
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[gc] get_state hata {tid}: {e}; atlanıyor")
                continue
            if snap.next:  # INVARIANT: kesilmiş/resume-bekleyen → KORU
                skipped_pending += 1
                logger.warning(f"[gc] terminal-DB ama .next={snap.next} dolu — KORUNDU: {tid}")
                continue
            if args.dry_run:
                logger.info(f"[gc][dry-run] silinecek: {tid}")
                deleted += 1
                continue
            try:
                cp.delete_thread(tid)   # resmî API: 3 tabloyu da langgraph şemasında siler
                deleted += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[gc] delete_thread hata {tid}: {e}")

    verb = "silinecek (dry-run)" if args.dry_run else "silindi"
    logger.info(f"[gc] TAMAM — {deleted} thread {verb}, {skipped_pending} korundu (.next dolu).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
