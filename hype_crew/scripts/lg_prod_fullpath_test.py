"""Kontrollü prod-dry full-path teyit — sentetik aday enjekte (drought baypas).

ÖNKOŞUL (dışarıda ayarlanır, sonra geri alınır): Cansu persona visual/video KAPALI
+ hype_account_config.dry_run_mode=true + hype-crew.timer durdurulmuş.

run_crew stub'lanır (drought'ta da garantili full-path): sentetik passed=True trend +
plan + trend_raw_content_cache. Sonra LangGraph run_or_resume → gerçek write
(TypeHype LLM) → gerçek compliance → (visual/video kapalı + dry) → dry_run_complete.
Postgres checkpoint langgraph şemasına yazılır. Dış-yayın YOK (dry).

Çalıştır:  cd /opt/hype-crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_prod_fullpath_test
"""
from __future__ import annotations

import uuid

CANSU = "2b731bf7-8c24-40c5-8237-d348ee822d51"
TID = "lgtest-" + uuid.uuid4().hex[:12]
SRC = ("## KAYNAK METİN: OpenAI bugün yeni bir model duyurdu; geliştiricilere API "
       "erişimi açıldı ve token fiyatları düşürüldü. (lg full-path test kaynağı)")


def main() -> int:
    from schemas import TrendScoutOutput, PlannerOutput
    import flow as flowmod

    def _stub_run_crew(self, account_id):
        # Sentetik passed=True aday → route_after_crew write_step'e gider (drought baypas)
        self.state.trend = TrendScoutOutput(
            trend_id=TID, topic="OpenAI yeni model duyurdu, API erişimi açıldı",
            score=92, category="model_launch", urgency_hours=12,
            reasoning="lg full-path test (sentetik aday)")
        self.state.plan = PlannerOutput(
            etki="patlassin", karakter="haberci", uzunluk="punch",
            brief="OpenAI'nin yeni model + ucuzlayan API duyurusunu net ve sade aktar",
            hook_type="result", angle="API artık daha ucuz ve herkese açık",
            content_type="model_launch", voice_mode="hybrid",
            target_engagement="mixed", reasoning="lg full-path test plan")
        self.state.trend_raw_content_cache[TID] = SRC      # R6: kaynak metin (state'te)
        self.state.total_tokens = 0
        self.state.editor_decision = "lg_fullpath_test"
        return None

    flowmod.AutonomousContentFlow.run_crew = _stub_run_crew   # monkeypatch (sadece bu process)

    # KENDİ-KENDİNE YETERLİ (DB config'e DOKUNMA): in-process dry + persona render-off.
    # Dış dry_run_mode/persona DB mutasyonu (revert riski) GEREKMEZ.
    from scripts.lg_faz2_idem_testlib import force_dry_run_config, cleanup_run, delete_trend
    force_dry_run_config(flowmod)   # state.dry_run=True (DB'siz)
    _orig_persona = flowmod.AutonomousContentFlow._resolve_persona
    def _persona_no_render(self):   # gerçek persona alanlarını koru, sadece render'ı kapat
        p = dict(_orig_persona(self) or {})
        p["visual_enabled"] = False
        p["video_enabled"] = False
        return p
    flowmod.AutonomousContentFlow._resolve_persona = _persona_no_render

    from lg.graph import run_or_resume
    print(f"[test] sentetik trend={TID} — LangGraph full-path (dry, render kapalı, DB dokunulmaz)")
    final = None
    try:
        final = run_or_resume(CANSU, triggered_by="manual")
        print("\n=== SONUÇ ===")
        print("run_id:", final.run_id)
        print("final_status:", final.final_status)
        print("dry_run:", final.dry_run)
        print("trend.topic:", final.trend.topic if final.trend else None)
        print("draft var mı:", bool(final.draft))
        print("platform_drafts sayısı:", len(final.platform_drafts or []))
        print("compliance.approved:", final.compliance.approved if final.compliance else None)
        print("publish (dry → boş olmalı):", bool(final.publish))
        print("editor_decision (state'ten promote):", final.editor_decision)
        reached = bool(final.draft) and final.compliance is not None
        ok = reached and final.final_status in ("completed", "auto_scheduled", "") and not final.publish
        print(f"\n{'✅ FULL-PATH OK' if ok else '❌ FULL-PATH FAIL'} — write+compliance çalıştı, "
              f"dry-terminal'e indi, YAYIN YOK.")
    finally:
        # TEMİZLİK (try/finally — hata olsa da çalışır): run + sentetik trend sil
        rid = getattr(final, "run_id", None) if final else None
        if rid:
            try:
                print(f"[cleanup] {cleanup_run(rid)}")
            except Exception as _ce:
                print(f"[cleanup][warn] run {rid}: {_ce}")
        try:
            delete_trend(TID)
        except Exception:
            pass
        print(f"[cleanup] NOT: checkpoint thread={rid} MANUEL silinmeli (langgraph.*).")
    return 0 if (final and final.draft and final.compliance is not None and not final.publish) else 1


if __name__ == "__main__":
    raise SystemExit(main())
