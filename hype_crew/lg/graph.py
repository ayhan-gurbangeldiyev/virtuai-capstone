"""Faz 1 — ana hype pipeline'ının LangGraph portu (strangler/wrap-first).

flow.py'daki CrewAI Flow'un SIRALI kopyası: aynı metodlar, aynı router string'leri,
aynı kenarlar — yalnızca orkestrasyon CrewAI yerine LangGraph StateGraph. Mantık
yeniden yazılmaz (nodes.py sarmalayıcıları çağırır). State şeması = mevcut
`HypeFlowState` pydantic modeli (flow.py); graph sıralı → reducer gerekmez.

NODE/EDGE HARİTASI:
    START → initialize → run_crew
    run_crew  --route_after_crew-->      skip_branch→skip_complete
                                         fail_branch→fail_complete
                                         write_step →write
    write     --route_after_write-->     fail_branch→fail_complete
                                         compliance_step→compliance
    compliance--route_after_compliance-->fail_branch→fail_complete
                                         skip_branch→skip_complete
                                         visual_branch→visual
                                         video_branch→video
                                         dry_run_branch→dry_run_complete
                                         publish_branch→publish
    visual    --route_after_visual-->    fail_branch→fail_complete
                                         video_branch→video
                                         dry_run_branch→dry_run_complete
                                         publish_branch→publish
    video     --route_after_video-->     fail_branch→fail_complete
                                         dry_run_branch→dry_run_complete
                                         publish_branch→publish
    publish          → END
    dry_run_complete → END
    skip_complete    → END
    fail_complete    → END

SYNC zorunlu: node metodları içinde asyncio.run() adacıkları var → graph.invoke
(ainvoke DEĞİL) + sync checkpointer (checkpointer.sync_checkpointer).
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Optional

from loguru import logger

from flow import HypeFlowState, AutonomousContentFlow
from .checkpointer import sync_checkpointer
from .nodes import make_nodes

# MED-4 — poison-run koruması. Bir run bu kadar kez resume edilip hâlâ
# tamamlanamıyorsa (her seferinde aynı node'da crash) sonsuz resume döngüsünü
# kır: run'ı failed işaretle, yetim draftları temizle, CRITICAL alarm at.
MAX_RESUME_ATTEMPTS = 3


def build_state_graph(cf: Optional[AutonomousContentFlow] = None):
    """Derlenmemiş StateGraph'ı kur. State şeması = HypeFlowState (sıralı, reducersız).
    node/router'lar `cf` (run başına TEK Flow örneği) üstüne bağlanır; verilmezse
    inceleme/smoke için bir örnek kurulur (run_or_resume çalıştırma için kendi cf'sini verir)."""
    from langgraph.graph import StateGraph, START, END

    cf = cf or AutonomousContentFlow()
    n = make_nodes(cf)

    g = StateGraph(HypeFlowState)

    # iş node'ları
    g.add_node("initialize", n["node_initialize"])
    g.add_node("run_crew", n["node_run_crew"])
    g.add_node("write", n["node_write"])
    g.add_node("compliance", n["node_compliance"])
    g.add_node("visual", n["node_visual"])
    g.add_node("video", n["node_video"])
    g.add_node("publish", n["node_publish"])
    g.add_node("dry_run_complete", n["node_dry_run_complete"])
    g.add_node("skip_complete", n["node_skip_complete"])
    g.add_node("fail_complete", n["node_fail_complete"])

    # düz kenarlar
    g.add_edge(START, "initialize")
    g.add_edge("initialize", "run_crew")

    # koşullu kenarlar — string→node map'leri spec'le birebir
    g.add_conditional_edges(
        "run_crew",
        n["route_after_crew"],
        {
            "skip_branch": "skip_complete",
            "fail_branch": "fail_complete",
            "write_step": "write",
        },
    )
    g.add_conditional_edges(
        "write",
        n["route_after_write"],
        {
            "fail_branch": "fail_complete",
            "compliance_step": "compliance",
        },
    )
    g.add_conditional_edges(
        "compliance",
        n["route_after_compliance"],
        {
            "fail_branch": "fail_complete",
            "skip_branch": "skip_complete",
            "visual_branch": "visual",
            "video_branch": "video",
            "dry_run_branch": "dry_run_complete",
            "publish_branch": "publish",
        },
    )
    g.add_conditional_edges(
        "visual",
        n["route_after_visual"],
        {
            "fail_branch": "fail_complete",
            "video_branch": "video",
            "dry_run_branch": "dry_run_complete",
            "publish_branch": "publish",
        },
    )
    g.add_conditional_edges(
        "video",
        n["route_after_video"],
        {
            "fail_branch": "fail_complete",
            "dry_run_branch": "dry_run_complete",
            "publish_branch": "publish",
        },
    )

    # terminal node'lar → END
    g.add_edge("publish", END)
    g.add_edge("dry_run_complete", END)
    g.add_edge("skip_complete", END)
    g.add_edge("fail_complete", END)

    return g


def build_graph():
    """Derlenmiş graph'ı checkpointer OLMADAN döndür — smoke STEP5 statik denetimi
    (get_graph().nodes/.edges) ve genel inceleme için. Çalıştırma için run_or_resume
    checkpointer ile derler. LangGraph compile sırasında conditional-edge hedeflerini
    doğrular → eksik/yanlış hedef burada patlar."""
    return build_state_graph().compile()


@contextmanager
def _advisory_lock(run_id: str):
    """Faz 2 — eşzamanlılık koruması. Resume edilebilir bir run'ı AYNI ANDA iki
    timer firing'inin yeniden başlatmasını engeller (çift LIVE post riski).

    `pg_try_advisory_lock(hashtext(run_id))` ile session-bazlı bir kilit dener;
    alınamazsa (`acquired=False`) caller run'ı atlar. Kilit kısa-ömürlü ayrı bir
    psycopg bağlantısında tutulur (checkpoint pool'undan bağımsız) ve `finally`'de
    `pg_advisory_unlock` + conn.close ile bırakılır.

    checkpoint_db_url boşsa (dev/SQLite modu) advisory lock anlamsız → her zaman
    `acquired=True` döner (no-op), davranış değişmez.
    """
    url = ""
    try:
        from config import settings
        url = (getattr(settings, "checkpoint_db_url", "") or "").strip()
    except Exception:  # noqa: BLE001
        import os
        url = (os.environ.get("HYPE_CHECKPOINT_DB_URL", "") or "").strip()

    if not url:
        # Dev/SQLite — Postgres advisory lock yok; no-op (her zaman alındı say).
        yield True
        return

    import psycopg
    conn = None
    acquired = False
    try:
        conn = psycopg.connect(url, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (run_id,))
            row = cur.fetchone()
            acquired = bool(row and row[0])
        yield acquired
    finally:
        if conn is not None:
            try:
                if acquired:
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (run_id,))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[lg-flow] advisory unlock failed (run={run_id}): {e}")
            try:
                conn.close()
            except Exception:
                pass


def _checkpoint_db_url() -> str:
    """checkpoint_db_url'ü _advisory_lock ile AYNI sırayla çöz (settings →
    env). Boşsa dev/SQLite modu."""
    try:
        from config import settings
        return (getattr(settings, "checkpoint_db_url", "") or "").strip()
    except Exception:  # noqa: BLE001
        import os
        return (os.environ.get("HYPE_CHECKPOINT_DB_URL", "") or "").strip()


def _bump_resume_attempts(run_id: str) -> Optional[int]:
    """MED-4 — resume_attempts'i ATOMİK olarak +1 yapıp YENİ değeri döndür.

    `UPDATE hype_runs SET resume_attempts = resume_attempts + 1 WHERE id=:id
    RETURNING resume_attempts` — tek statement, atomik. Çağrı SADECE resume
    branch'inde ve advisory-lock kritik bölgesi İÇİNDE yapılır; advisory lock
    aynı run'ı iki process'in eşzamanlı resume etmesini zaten serialize eder,
    bu yüzden artış yarış-koşulsuzdur.

    Dev/SQLite modunda (checkpoint_db_url boş) Postgres yok → gate anlamsız;
    None döner ve caller gate'i atlar (no-op, davranış değişmez).
    """
    url = _checkpoint_db_url()
    if not url:
        return None
    import psycopg
    conn = None
    try:
        conn = psycopg.connect(url, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hype_runs SET resume_attempts = resume_attempts + 1 "
                "WHERE id = %s RETURNING resume_attempts",
                (run_id,),
            )
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[lg-flow] resume_attempts bump failed (run={run_id}): {e}")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _force_fail_poison_run(run_id: str, account_id: str, attempts: int) -> None:
    """MED-4 — poison run'ı kapat: status='failed' + error yaz, yetim draftları
    temizle (paylaşılan reap_orphan_drafts), CRITICAL alarm at. Hepsi
    best-effort/izole — biri patlasa diğeri çalışır."""
    err = "max resume attempts exceeded (poison run)"
    try:
        from tools.supabase_client import make_supabase
        sb = make_supabase()
        try:
            sb.table("hype_runs").update({
                "status": "failed",
                "error": err,
            }).eq("id", run_id).execute()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[lg-flow] poison-run status update failed: {e}")
        try:
            from runner import reap_orphan_drafts
            reap_orphan_drafts(sb, run_id, "orphan of poison run (max resume attempts)")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[lg-flow] poison-run orphan cleanup failed: {e}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[lg-flow] poison-run supabase access failed: {e}")
    try:
        from tools.alerter import send_alert
        send_alert(
            "Poison run — max resume denemesi aşıldı, run failed",
            severity="CRITICAL",
            reason=(
                f"run={run_id} account={account_id[:8]} {attempts} kez resume "
                f"edildi (sınır={MAX_RESUME_ATTEMPTS}) ve hâlâ tamamlanamadı; "
                "sonsuz resume döngüsünü kırmak için failed işaretlendi."
            ),
            action=(
                "Checkpoint'i ve son crash log'unu incele; takılan node'u "
                "düzelt. Run otomatik yeniden seçilmeyecek (cap aşıldı)."
            ),
            extra={"hype_run_id": run_id, "resume_attempts": attempts},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[lg-flow] poison-run CRITICAL alert failed: {e}")


def run_or_resume(
    account_id: str,
    triggered_by: str = "cron",
    run_id: Optional[str] = None,
) -> Optional[HypeFlowState]:
    """Ana pipeline'ı LangGraph ile SYNC çalıştır/RESUME et.

    Faz 2 — STABLE thread_id (load-bearing):
      `run_id` verilirse thread_id = run_id (hype_runs PK == LangGraph thread_id),
      böylece resume cross-process korelasyon yapar. init_state.run_id da bu
      değere set edilir → flow.initialize bunu KORUR (yeniden mint etmez), init_run
      idempotent davranır (resume'da çift hype_runs satırı YOK). `run_id` verilmezse
      backward-compat: taze uuid mint edilir (Faz 1 davranışı).

    Eşzamanlılık: invoke'tan ÖNCE pg_try_advisory_lock(hashtext(run_id)) alınır;
    alınamazsa başka bir process bu run'ı tutuyordur → log + None döner.

    SYNC zorunlu: node'lar içinde asyncio.run() adacıkları → graph.invoke + sync cp.
    """
    thread_id = run_id or uuid.uuid4().hex
    init_state = HypeFlowState(account_id=account_id, triggered_by=triggered_by)
    if run_id:
        # flow.initialize bunu KORUR (truthy → yeniden mint etmez, init_run'a geçirir).
        init_state.run_id = run_id

    _t0 = time.time()
    cf = AutonomousContentFlow()   # run başına TEK Flow örneği (tüm node'lar paylaşır)

    with _advisory_lock(thread_id) as acquired:
        if not acquired:
            logger.warning(
                f"[lg-flow] advisory lock BUSY thread={thread_id} "
                f"account={account_id[:8]} — başka bir process bu run'ı tutuyor; atlanıyor"
            )
            return None

        with sync_checkpointer() as cp:
            graph = build_state_graph(cf).compile(checkpointer=cp)
            cfg = {"configurable": {"thread_id": thread_id}}
            snap = graph.get_state(cfg)
            if snap.next:  # resume — bu thread'de yarım checkpoint var
                # ── MED-4 — max-resume gate (poison-run force-fail) ────────
                # invoke'tan ÖNCE resume_attempts'i atomik +1. Sınır aşıldıysa
                # invoke ETME: run'ı failed yap, yetim draftları temizle,
                # CRITICAL alarm at, None dön. Advisory lock artışı serialize
                # ettiği için sayım güvenli. (Dev/SQLite: bump None döner →
                # gate atlanır, davranış değişmez.)
                _attempts = _bump_resume_attempts(thread_id)
                if _attempts is not None and _attempts > MAX_RESUME_ATTEMPTS:
                    logger.error(
                        f"[lg-flow] POISON RUN thread={thread_id} "
                        f"resume_attempts={_attempts} > {MAX_RESUME_ATTEMPTS} "
                        f"— invoke EDİLMEYECEK, run failed işaretleniyor"
                    )
                    _force_fail_poison_run(thread_id, account_id, _attempts)
                    return None
                logger.info(
                    f"[lg-flow] RESUME thread={thread_id} pending={snap.next} "
                    f"attempt={_attempts if _attempts is not None else 'n/a'}"
                )
                result = graph.invoke(None, cfg, durability="sync")
            else:
                logger.info(
                    f"[lg-flow] FRESH thread={thread_id} account={account_id[:8]} "
                    f"triggered_by={triggered_by}"
                )
                result = graph.invoke(init_state, cfg, durability="sync")

    # LangGraph dict döndürebilir; HypeFlowState'e normalize et (caller .state.* okur)
    final: HypeFlowState = (
        result if isinstance(result, HypeFlowState) else HypeFlowState(**result)
    )
    logger.info(
        f"[lg-flow] complete thread={thread_id} run_id={final.run_id} "
        f"final_status={final.final_status} elapsed={time.time() - _t0:.1f}s"
    )
    return final


def get_resumable_run_id(account_id: str) -> Optional[str]:
    """Faz 2 — resume-vs-fresh tespiti (runner çağırır).

    Bu hesap için RESUME edilebilir bir prior run var mı? Kriter:
      hype_runs.status='running' + LangGraph checkpoint'i YARIM
      (graph.get_state({thread_id: run_id}).next boş DEĞİL).

    İlk uygun run_id döner; yoksa None (→ fresh run). Checkpoint'i olmayan ya da
    tamamlanmış (.next boş) running satırlar resume edilmez (reaper'a bırakılır).
    En yeni running satırdan eskiye doğru bakar; ilk canlı-checkpoint'i seçer.
    """
    try:
        from tools.supabase_client import make_supabase
        sb = make_supabase()
        r = (
            sb.table("hype_runs").select("id, started_at, resume_attempts")
            .eq("account_id", account_id)
            .eq("status", "running")
            .order("started_at", desc=True)
            .limit(10)
            .execute()
        )
        running = []
        for row in (r.data or []):
            if not (isinstance(row, dict) and row.get("id")):
                continue
            # MED-4 — cap'i aşmış (ya da tam cap'te) bir run'ı resume aday
            # listesine ALMA: yeniden seçilmesi yalnız force-fail'e yol açar
            # ya da (force-fail status update başarısızsa) sonsuz döngü kalır.
            # Reaper bunları (>2h) zaten failed yapar; biz erken eleriz.
            _ra = row.get("resume_attempts")
            if isinstance(_ra, int) and _ra >= MAX_RESUME_ATTEMPTS:
                logger.info(
                    f"[lg-flow] resumable atlandı (poison): {str(row['id'])[:8]} "
                    f"resume_attempts={_ra} >= {MAX_RESUME_ATTEMPTS}"
                )
                continue
            running.append(row)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[lg-flow] get_resumable_run_id query failed: {e}")
        return None

    if not running:
        return None

    # Tek checkpointer/compile ile tüm aday thread'leri yokla (ucuz get_state).
    try:
        with sync_checkpointer() as cp:
            graph = build_state_graph(cf=None).compile(checkpointer=cp)
            for row in running:
                rid = str(row["id"])
                try:
                    snap = graph.get_state({"configurable": {"thread_id": rid}})
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[lg-flow] get_state failed for {rid}: {e}")
                    continue
                if snap.next:
                    logger.info(f"[lg-flow] resumable run bulundu: {rid} pending={snap.next}")
                    return rid
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[lg-flow] get_resumable_run_id checkpoint probe failed: {e}")
        return None

    return None
