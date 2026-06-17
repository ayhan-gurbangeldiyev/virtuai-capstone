"""TEST B — Postiz IDEMPOTENCY partition (unit, MOCKED, no real posting).

publish_to_drafts'in resume-idempotency partition'ını GERÇEK kodla test eder; ama
HİÇBİR gerçek Postiz çağrısı yapmaz: GuardedPostizClient.schedule_posts bir RECORDER
ile değiştirilir (hangi platformların schedule istendiğini kaydeder, sahte id döner).
Faithfulness + clarity gate'leri ve auto_publish/persona okumaları da stub'lanır
(LLM maliyeti YOK, Cansu canlı config'ine DOKUNULMAZ — config okuması in-process
sarmalanır).

İki senaryo:
  B1 (RESUME): run zaten twitter'ı schedule etmiş (daily_drafts'ta gerçek
     postiz_post_id var); linkedin schedule edilmemiş. publish_to_drafts çağrılır →
     schedule_posts YALNIZ linkedin için çağrılmalı; twitter var olan id'yi yeniden
     kullanmalı; final post_id hizası doğru olmalı (çift LIVE post YOK).
  B2 (FRESH): hiç ön-schedule yok → schedule_posts TÜM platformlar için çağrılır
     (no-op davranış korunur).

Çalıştır:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_test_b_postiz
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from scripts.lg_faz2_idem_testlib import (
    CANSU, draft_rows, cleanup_run, seed_trend, delete_trend,
    insert_test_draft, neutralize_shadow_gate, seed_hype_run,
    neutralize_companion_cards,
)

PLATFORMS = ("twitter", "linkedin")
RECORDER = {"calls": []}  # her schedule_posts çağrısında istenen platformlar


# ─────────────────────────────────────────────────────────────────────────
# Mock kurulumu — REAL partition kodu, MOCK kenarlar
# ─────────────────────────────────────────────────────────────────────────
def install_publish_mocks(flowmod):
    import flow as _f
    import tools.guarded_postiz as _gp
    from tools.guarded_postiz import GateOutcome
    import tools.clarity_gate as _cg
    from tools.supabase_client import make_supabase as _real_make_sb

    neutralize_shadow_gate()
    neutralize_companion_cards()  # publish sonrası kart yan-etkisi YOK

    # 1) persona — visual/video kapalı, tüm modality unlock'lar AÇIK (deferred YOK)
    def _stub_persona(self):
        return {
            "id": None, "slug": "cansu", "display_name": "Cansu",
            "owner_user_id": None,
            "visual_enabled": False, "video_enabled": False,
            "video_pipeline_default": None, "daily_video_budget_usd": 0,
            "video_min_trend_score": 999,
            "text_autonomy_unlocked": True, "image_autonomy_unlocked": True,
            "video_autonomy_unlocked": True,
            "topics_focus": None, "forbidden_topics": None,
            "default_target_platforms": list(PLATFORMS),
        }
    _f.AutonomousContentFlow._resolve_persona = _stub_persona

    # 2) config okuması — auto_publish_enabled=true, allowlist=None (hepsi).
    #    Cansu'nun GERÇEK config'i DEĞİŞMEZ; yalnız bu process'in OKUMA sonucu
    #    hype_account_config select'i için sarmalanır.
    class _SBWrap:
        def __init__(self, real):
            self._real = real

        def table(self, name):
            if name == "hype_account_config":
                return _FakeCfgTable()
            return self._real.table(name)

        def __getattr__(self, item):
            return getattr(self._real, item)

    class _FakeCfgResp:
        data = [{"auto_publish_enabled": True, "allowed_publish_platforms": None}]

    class _FakeCfgTable:
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return _FakeCfgResp()

    def _wrapped_make_sb():
        return _SBWrap(_real_make_sb())

    # flow.py içindeki make_supabase adına bağlan
    _f.make_supabase = _wrapped_make_sb

    # 3) faithfulness gate — PASS (LLM YOK). token gerçek olmalı değil çünkü
    #    schedule_posts'u tamamen recorder'la değiştiriyoruz (token doğrulaması yok).
    async def _stub_assert_publishable(*, draft_text, source_raw_content, path, draft_id):
        return GateOutcome(
            draft_id=draft_id, path=path, verdict="PASS",
            token="STUB_TOKEN", content_hash="stub", reasoning="stub PASS")
    _gp.assert_publishable = _stub_assert_publishable
    # flow.py içe-import ediyor (from tools.guarded_postiz import assert_publishable
    # as _assert_publishable) → publish_to_drafts içinde import edildiği için
    # modül-attr patch'i yeterli (publish_to_drafts her çağrıda import eder).

    # 4) clarity gate — her zaman "clear" (LLM YOK)
    async def _stub_check_clarity(text, platform=""):
        return {"clear": True, "reason": "stub clear"}
    _cg.check_clarity = _stub_check_clarity

    # 5) schedule_posts RECORDER — gerçek Postiz YOK; istenen platformları kaydet,
    #    sahte postId döndür. SEV-1 guard + token verify tamamen baypas (override).
    def _recorder_schedule_posts(self, posts, scheduled_at, *, gate_outcomes=None):
        plats = [getattr(p, "provider", None) or getattr(p, "platform", "?") for p in posts]
        RECORDER["calls"].append([str(p).lower() for p in plats])
        return [{"postId": f"FAKE_{p}_{uuid.uuid4().hex[:6]}"} for p in plats]
    _gp.GuardedPostizClient.schedule_posts = _recorder_schedule_posts


def build_state(flowmod, run_id: str, tid: str):
    """publish_to_drafts'ı sürmek için minimal geçerli state kur."""
    from flow import HypeFlowState, PlatformDraft
    from schemas import WriterOutput, TrendScoutOutput, PlannerOutput
    cf = flowmod.AutonomousContentFlow()
    st = HypeFlowState(account_id=CANSU, triggered_by="manual")
    st.run_id = run_id
    st.dry_run = False
    body = "OpenAI yeni modelini duyurdu; API erişimi açıldı. (faz2 B test)"
    st.draft = WriterOutput(
        content=body, character_count=len(body), hook_type="result",
        line_count=1, has_em_dash=False, has_corporate_words=[],
        voice_alignment_score=90)
    st.trend = TrendScoutOutput(
        trend_id=tid, topic="OpenAI yeni model", score=92,
        category="model_launch", urgency_hours=12, reasoning="B test")
    st.plan = PlannerOutput(
        etki="patlassin", karakter="haberci", uzunluk="punch",
        brief="OpenAI yeni model + ucuz API duyurusunu net aktar (faz2 b test brief)",
        hook_type="result", angle="API artık ucuz", content_type="model_launch",
        voice_mode="hybrid", target_engagement="mixed", reasoning="b test plan")
    st.trend_raw_content_cache[tid] = "## KAYNAK: OpenAI yeni model. (b test)"
    st.platform_drafts = [
        PlatformDraft(platform=p, integration_id=f"intg-{p}", account_id=CANSU,
                      content=body, tokens_used=0, model_used="stub",
                      char_count=len(body), compliance_passed=True)
        for p in PLATFORMS
    ]
    st.target_platforms = list(PLATFORMS)
    object.__setattr__(cf, "_state", st)
    return cf


def run_b1_resume(flowmod) -> tuple[bool, list]:
    """RESUME: twitter zaten schedule edilmiş → yalnız linkedin schedule edilmeli."""
    failures = []
    run_id = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    seed_trend(tid)
    seed_hype_run(run_id, CANSU, tid)  # daily_drafts.hype_run_id FK'sini karşıla
    # twitter için GERÇEK postiz_post_id'li satır (resume = zaten schedule edilmiş)
    PRE_TW_PID = "REAL_TW_" + uuid.uuid4().hex[:8]
    insert_test_draft(run_id, CANSU, "twitter", "model_launch", "pending", PRE_TW_PID)
    # linkedin için satır YOK → schedule edilmeli

    RECORDER["calls"].clear()
    cf = build_state(flowmod, run_id, tid)
    cf.publish_to_drafts()

    # ── Assert 1: schedule_posts YALNIZ linkedin için çağrıldı (twitter atlandı)
    flat_called = [p for call in RECORDER["calls"] for p in call]
    print(f"[B1] schedule_posts çağrı(lar)ı: {RECORDER['calls']}")
    print(f"[B1] schedule edilen platformlar (twitter ATLANMALI): {flat_called}")
    if "twitter" in flat_called:
        failures.append("B1 twitter schedule_posts'a verildi — ÇİFT LIVE POST riski "
                        "(idempotency partition twitter'ı çıkarmadı)")
    if "linkedin" not in flat_called:
        failures.append("B1 linkedin schedule edilmedi (edilmeliydi)")

    # ── Assert 2: final daily_drafts post_id hizası
    rows = {r["platform"]: r for r in draft_rows(run_id) if not r.get("deleted_at")}
    tw_pid = rows.get("twitter", {}).get("postiz_post_id")
    li_pid = rows.get("linkedin", {}).get("postiz_post_id")
    print(f"[B1] final post_ids: twitter={tw_pid} linkedin={li_pid}")
    if tw_pid != PRE_TW_PID:
        failures.append(f"B1 twitter post_id reused olmadı: beklenen {PRE_TW_PID}, "
                        f"gelen {tw_pid} (mis-alignment / yeniden schedule)")
    if not (li_pid and li_pid.startswith("FAKE_")):
        failures.append(f"B1 linkedin taze post_id almadı: {li_pid}")
    # çapraz kontrol: twitter'a linkedin'in id'si yazılmadı (hizalama hatası)
    if tw_pid == li_pid:
        failures.append("B1 twitter ve linkedin AYNI post_id aldı — zip mis-alignment")

    cleanup_run(run_id)
    delete_trend(tid)
    return (not failures), failures


def run_b2_fresh(flowmod) -> tuple[bool, list]:
    """FRESH: hiç ön-schedule yok → schedule_posts TÜM platformlar için çağrılmalı."""
    failures = []
    run_id = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    seed_trend(tid)
    seed_hype_run(run_id, CANSU, tid)

    RECORDER["calls"].clear()
    cf = build_state(flowmod, run_id, tid)
    cf.publish_to_drafts()

    flat_called = sorted(set(p for call in RECORDER["calls"] for p in call))
    print(f"[B2] schedule_posts çağrı(lar)ı: {RECORDER['calls']}")
    print(f"[B2] schedule edilen platformlar (HEPSİ olmalı): {flat_called}")
    for p in PLATFORMS:
        if p not in flat_called:
            failures.append(f"B2 fresh run'da {p} schedule edilmedi (hepsi olmalıydı)")

    rows = {r["platform"]: r for r in draft_rows(run_id) if not r.get("deleted_at")}
    for p in PLATFORMS:
        pid = rows.get(p, {}).get("postiz_post_id")
        if not (pid and pid.startswith("FAKE_")):
            failures.append(f"B2 {p} taze post_id almadı: {pid}")
    print(f"[B2] final post_ids: "
          f"{ {p: rows.get(p, {}).get('postiz_post_id') for p in PLATFORMS} }")

    cleanup_run(run_id)
    delete_trend(tid)
    return (not failures), failures


def main() -> int:
    import flow as flowmod
    install_publish_mocks(flowmod)

    ok1, f1 = run_b1_resume(flowmod)
    print()
    ok2, f2 = run_b2_fresh(flowmod)

    ok = ok1 and ok2
    print("\n" + ("=" * 60))
    if ok:
        print("✅ TEST B PASS — RESUME: yalnız schedule edilmemiş platform "
              "(linkedin) Postiz'e gitti, twitter var olan id'yi yeniden kullandı "
              "(çift LIVE post önlendi); FRESH: tüm platformlar schedule edildi "
              "(no-op davranış korundu); post_id hizası doğru.")
    else:
        print("❌ TEST B FAIL:")
        for f in (f1 + f2):
            print("   -", f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
