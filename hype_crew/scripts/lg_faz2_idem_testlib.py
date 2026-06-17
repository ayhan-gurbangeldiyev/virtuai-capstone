"""Faz 2 resume-safety test suite — paylaşılan yardımcılar (mock + temizlik).

NO production change. NO real posting. NO paid render. Checkpointer = LOKAL SQLite
(sync_checkpointer(db_url="")) → paylaşılan Postgres langgraph şemasına DOKUNULMAZ.
daily_drafts/hype_runs satırları gerçek Supabase'e yazılır AMA her test sonunda
run_id ile silinir.

Bu modül flow.py / graph.py / runner.py / resume-core'u DEĞİŞTİRMEZ; yalnız test
süreci içinde monkeypatch uygular (in-process, kalıcı değil).
"""
from __future__ import annotations

import uuid
from typing import Optional

CANSU = "2b731bf7-8c24-40c5-8237-d348ee822d51"


# ─────────────────────────────────────────────────────────────────────────
# Sentetik aday enjeksiyonu (drought baypas) — LLM ÇAĞRISI YOK
# ─────────────────────────────────────────────────────────────────────────
def synthetic_trend_plan(tid: str):
    """run_crew stub'unun kullanacağı sentetik passed=True trend + plan döndür."""
    from schemas import TrendScoutOutput, PlannerOutput
    src = ("## KAYNAK METİN: OpenAI bugün yeni bir model duyurdu; geliştiricilere "
           "API erişimi açıldı ve token fiyatları düşürüldü. (faz2 idem test kaynağı)")
    trend = TrendScoutOutput(
        trend_id=tid, topic="OpenAI yeni model duyurdu, API erişimi açıldı",
        score=92, category="model_launch", urgency_hours=12,
        reasoning="faz2 idem test (sentetik aday)")
    plan = PlannerOutput(
        etki="patlassin", karakter="haberci", uzunluk="punch",
        brief="OpenAI'nin yeni model + ucuzlayan API duyurusunu net ve sade aktar",
        hook_type="result", angle="API artık daha ucuz ve herkese açık",
        content_type="model_launch", voice_mode="hybrid",
        target_engagement="mixed", reasoning="faz2 idem test plan")
    return trend, plan, src


def install_dry_path_mocks(flowmod, tid: str, platforms=("twitter", "linkedin")):
    """run_crew + write_via_typehype + _resolve_persona'yı LLM/render'sız stub'la.

    Sonuç: graph initialize→run_crew(sentetik)→write(sentetik draft)→compliance
    (gerçek? hayır — onu da stub'larız)→route(dry, visual/video kapalı)→
    dry_run_complete yolu, HİÇBİR ücretli çağrı olmadan koşar.
    """
    from schemas import WriterOutput, ComplianceOutput
    from flow import PlatformDraft

    trend, plan, src = synthetic_trend_plan(tid)

    def _stub_run_crew(self, account_id):
        self.state.trend = trend
        self.state.plan = plan
        self.state.trend_raw_content_cache[tid] = src
        self.state.total_tokens = 0
        self.state.editor_decision = "faz2_idem_test"
        return None

    def _stub_write(self):
        body = ("OpenAI yeni modelini duyurdu; API erişimi açıldı, token "
                "fiyatları düştü. (faz2 idem test draftı)")
        self.state.draft = WriterOutput(
            content=body, character_count=len(body),
            hook_type="result", line_count=1,
            has_em_dash=False, has_corporate_words=[],
            voice_alignment_score=90)
        pds = []
        for p in platforms:
            pds.append(PlatformDraft(
                platform=p,
                integration_id=f"intg-{p}",
                account_id=self.state.account_id,
                content=body,
                tokens_used=0, model_used="stub", char_count=len(body),
                compliance_passed=True,
            ))
        self.state.platform_drafts = pds
        self.state.target_platforms = list(platforms)
        return None

    def _stub_compliance(self):
        self.state.compliance = ComplianceOutput(
            approved=True, dedup_passed=True, similarity_to_recent=0.0,
            rejection_reason=None, hard_rules_violated=[],
            forbidden_topics_detected=[], brand_voice_score=90, confidence=95)
        return None

    def _stub_persona(self):
        # visual_enabled/video_enabled FALSE → route dry_run_branch'e iner,
        # paid Wiro/HeyGen ASLA çağrılmaz. Gerçek persona DB'sine dokunmaz.
        return {
            "id": None, "slug": "cansu", "display_name": "Cansu",
            "owner_user_id": None,
            "visual_enabled": False, "video_enabled": False,
            "video_pipeline_default": None, "daily_video_budget_usd": 0,
            "video_min_trend_score": 999,
            "text_autonomy_unlocked": True, "image_autonomy_unlocked": False,
            "video_autonomy_unlocked": False,
            "topics_focus": None, "forbidden_topics": None,
            "default_target_platforms": list(platforms),
        }

    flowmod.AutonomousContentFlow.run_crew = _stub_run_crew
    flowmod.AutonomousContentFlow.write_via_typehype = _stub_write
    flowmod.AutonomousContentFlow.run_compliance = _stub_compliance
    flowmod.AutonomousContentFlow._resolve_persona = _stub_persona

    # _write_daily_draft INSERT yolunda shadow_gate (LLM faithfulness yargısı)
    # tetikleniyor → maliyet. No-op'la (test ücretsiz kalsın).
    neutralize_shadow_gate()


def neutralize_shadow_gate():
    """tools.guarded_postiz.shadow_gate'i no-op async'e çevir — LLM maliyeti YOK."""
    import tools.guarded_postiz as _gp

    async def _noop_shadow(*a, **k):
        return None

    _gp.shadow_gate = _noop_shadow


def force_dry_run_config(flowmod):
    """initialize() içindeki load_account_config çağrısını dry_run_mode=true'ya
    sabitle — Cansu'nun CANLI config'ine DOKUNMADAN (sadece bu process'te okuma
    sonucunu stub'lar)."""
    import flow as _f

    def _stub_cfg(account_id):
        return {"dry_run_mode": True}

    # load_account_config bir crew tool; .func ile sarılı olabilir.
    if hasattr(_f, "load_account_config"):
        try:
            _f.load_account_config.func = _stub_cfg  # tool wrapper varsa
        except Exception:
            pass
    # initialize() `config_fn = load_account_config.func if hasattr ... else load_account_config`
    # diyor; .func set edilemezse modüldeki adı da değiştir.
    try:
        _f.load_account_config = type("T", (), {"func": staticmethod(_stub_cfg)})()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# Temizlik — test artefaktlarını run_id ile sil
# ─────────────────────────────────────────────────────────────────────────
def seed_trend(trend_id: str, topic: str = "faz2 idem test trend") -> bool:
    """daily_drafts.trend_id → trends.id FK'sini karşılamak için geçici trends
    satırı ekle. Cleanup'ta delete_trend ile silinir."""
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    try:
        sb.table("trends").insert({"id": trend_id, "topic": topic}).execute()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[seed_trend] failed: {str(e)[:200]}")
        return False


def delete_trend(trend_id: str) -> int:
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    try:
        r = sb.table("trends").delete().eq("id", trend_id).execute()
        return len(r.data or [])
    except Exception as e:  # noqa: BLE001
        print(f"[delete_trend] failed: {str(e)[:200]}")
        return 0


def seed_hype_run(run_id: str, account_id: str, trend_id: Optional[str] = None) -> bool:
    """daily_drafts.hype_run_id → hype_runs.id FK'sini karşılamak için minimal
    hype_runs satırı oluştur (TEST B publish_to_drafts'ı initialize'sız sürer)."""
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    row = {"id": run_id, "account_id": account_id, "status": "running",
           "triggered_by": "manual", "dry_run": False}
    if trend_id is not None:
        row["trend_id"] = trend_id
    try:
        sb.table("hype_runs").insert(row).execute()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[seed_hype_run] failed: {str(e)[:200]}")
        return False


def neutralize_companion_cards():
    """flow.publish_to_drafts sonunda çağrılan schedule_companion_cards'ı no-op'la
    (yan-etki/maliyet YOK)."""
    import tools.card_scheduler as _cs

    async def _noop(*a, **k):
        return 0

    _cs.schedule_companion_cards = _noop


def count_drafts(run_id: str) -> int:
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    r = (sb.table("daily_drafts").select("id", count="exact")
         .eq("hype_run_id", run_id).is_("deleted_at", "null").execute())
    return r.count or 0


def draft_rows(run_id: str):
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    r = (sb.table("daily_drafts")
         .select("id, platform, content_type, status, postiz_post_id, deleted_at")
         .eq("hype_run_id", run_id).execute())
    return r.data or []


def cleanup_run(run_id: str) -> dict:
    """Bu run'a ait daily_drafts + hype_runs satırlarını HARD DELETE et.

    Dairesel FK var: hype_runs.daily_draft_id → daily_drafts.id VE
    daily_drafts.hype_run_id → hype_runs.id. Döngüyü kırmak için ÖNCE
    hype_runs'taki referansları (daily_draft_id, trend_id) NULL'la, SONRA
    daily_drafts'ı, en son hype_runs'ı sil. Test izole (yalnız bizim run_id)."""
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    out = {"daily_drafts_deleted": 0, "hype_runs_deleted": 0}
    # 1) hype_runs'taki ileri-referansları kopar (FK döngüsünü aç)
    try:
        sb.table("hype_runs").update(
            {"daily_draft_id": None, "trend_id": None}
        ).eq("id", run_id).execute()
    except Exception as e:  # noqa: BLE001
        out["hype_runs_unlink_error"] = str(e)[:200]
    # 2) daily_drafts sil
    try:
        d = sb.table("daily_drafts").delete().eq("hype_run_id", run_id).execute()
        out["daily_drafts_deleted"] = len(d.data or [])
    except Exception as e:  # noqa: BLE001
        out["daily_drafts_error"] = str(e)[:200]
    # 3) hype_runs sil
    try:
        h = sb.table("hype_runs").delete().eq("id", run_id).execute()
        out["hype_runs_deleted"] = len(h.data or [])
    except Exception as e:  # noqa: BLE001
        out["hype_runs_error"] = str(e)[:200]
    return out


def lookup_account_user_id(account_id: str) -> Optional[str]:
    """daily_drafts.user_id NOT NULL → bu hesabın owner user_id'sini var olan bir
    daily_drafts satırından çek (FK-güvenli seed için)."""
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    try:
        r = (sb.table("daily_drafts").select("user_id")
             .eq("account_id", account_id).not_.is_("user_id", "null")
             .limit(1).execute())
        rows = r.data or []
        if rows and isinstance(rows[0], dict):
            return rows[0].get("user_id")
    except Exception as e:  # noqa: BLE001
        print(f"[lookup_user_id] failed: {str(e)[:160]}")
    return None


def insert_test_draft(run_id: str, account_id: str, platform: str,
                      content_type: Optional[str], status: str,
                      postiz_post_id: Optional[str]) -> Optional[str]:
    """TEST B için: var olan bir schedule durumunu simüle eden satır insert et."""
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    row = {
        "account_id": account_id,
        "user_id": lookup_account_user_id(account_id),
        "content": f"faz2 idem test seed ({platform})",
        "platform": platform,
        "status": status,
        "source": "hype_auto",
        "hype_run_id": run_id,
        "postiz_post_id": postiz_post_id,
    }
    if content_type is not None:
        row["content_type"] = content_type
    try:
        r = sb.table("daily_drafts").insert(row).execute()
        rows = r.data if isinstance(r.data, list) else []
        if rows and isinstance(rows[0], dict):
            return rows[0].get("id")
    except Exception as e:  # noqa: BLE001
        print(f"[seed] insert failed: {e}")
    return None
