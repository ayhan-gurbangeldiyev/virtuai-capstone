"""LG node-coverage — visual+video+publish NODE'ları (canlıda hiç koşmamış) kanıtı.

BAĞLAM: LangGraph cutover yapıldı (ana akış LangGraph'ta). Kuraklık nedeniyle
visual(Wiro)/video(HeyGen)/publish(Postiz) node'ları LangGraph ÜZERİNDEN hiç
koşmadı. Kanıtlanmamış = NODE-SARMALAMASI + routing zinciri
(route_after_compliance→visual→route_after_visual→video→route_after_video→publish)
+ state-akışı. METODLAR (generate_visual/generate_video/publish_to_drafts) CrewAI'da
her gün koşuyor, kanıtlı — bu test SADECE node-wrapping+routing+state'i kanıtlar.

GÜVENLİK (critic kuralları):
  - GERÇEK YAYIN YOK: install_publish_mocks HEM GuardedPostizClient HEM PostizClient
    .schedule_posts'u RECORDER'a bağlar (super() sızması engellenir).
  - PAHALI RENDER YOK: generate_visual + generate_video SPY (state set eder; gerçek
    Wiro/HeyGen YOK — video maliyet disiplini). Metotlar zaten kanıtlı.
  - uuid id'ler (lgtest-* 22P02 yok). try/finally cleanup. Cansu canlı config'e dokunulmaz.
  - dry_run=False (config'ten) gerekir ki routing publish'e gitsin (dry_run_complete'e değil).

Çalıştır (cron DURDURULMUŞ, prod):
  cd /opt/hype-crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_node_coverage_test
"""
from __future__ import annotations

import os
import uuid

from scripts.lg_faz2_idem_testlib import (
    CANSU, synthetic_trend_plan, neutralize_shadow_gate,
    neutralize_companion_cards, cleanup_run, draft_rows, seed_trend, delete_trend,
)
from scripts.lg_faz2_gate_common import (
    install_publish_mocks, RECORDER, ALERTS, platform_call_count,
)

PLATFORMS = ("youtube", "twitter")
VIDEO_PLATFORM = "youtube"

COUNTERS = {"initialize": 0, "run_crew": 0, "write": 0, "compliance": 0,
            "visual": 0, "video": 0, "publish": 0, "finalize": 0}
ORDER: list = []


def main() -> int:  # noqa: C901
    import flow as flowmod
    from schemas import WriterOutput, ComplianceOutput
    from schemas.visual import VisualDirectorOutput
    from flow import PlatformDraft, VideoOutput

    failures: list[str] = []
    run_id = str(uuid.uuid4())
    tid = str(uuid.uuid4())

    # 1) Postiz spy + gate PASS + auto_publish in-process true (persona OFF — aşağıda EZİLİR)
    install_publish_mocks(flowmod, platforms=PLATFORMS)
    neutralize_shadow_gate()
    neutralize_companion_cards()

    # GÜVENLİK KAPISI (env yerine MOCK doğrulaması — gerçek koruma bu): her iki Postiz
    # sınıfının schedule_posts'u recorder ile DEĞİŞTİRİLMİŞ olmalı. Değilse gerçek yayın
    # riski → DUR (run_or_resume çağrılmadan, yani hiçbir publish denemesi olmadan).
    import tools.guarded_postiz as _gp
    import tools.postiz_client as _pc
    _g_ok = getattr(_gp.GuardedPostizClient.schedule_posts, "__name__", "") == "_recorder_schedule_posts"
    _b_ok = getattr(_pc.PostizClient.schedule_posts, "__name__", "") == "_recorder_schedule_posts"
    if not (_g_ok and _b_ok):
        print(f"❌ GÜVENLİK: Postiz schedule_posts mock eksik (Guarded={_g_ok} base={_b_ok}) — DUR.")
        return 2

    # Medya yükleme de GERÇEK Postiz çağrısı (upload_image_url/upload_from_url) —
    # install_publish_mocks bunları mock'lamıyor. Fake URL'lerle gerçek api.postiz.com'a
    # gider (400). Mock'la: hiç gerçek Postiz teması olmasın + video path schedule'a ulaşsın.
    def _fake_upload_image(self, image_url, timeout=60.0):
        return {"id": "FAKE_img_" + uuid.uuid4().hex[:6]}

    def _fake_upload_from_url(self, public_url):
        return {"id": "FAKE_media_" + uuid.uuid4().hex[:6]}
    _pc.PostizClient.upload_image_url = _fake_upload_image
    _pc.PostizClient.upload_from_url = _fake_upload_from_url
    _u_ok = (_pc.PostizClient.upload_image_url.__name__ == "_fake_upload_image"
             and _pc.PostizClient.upload_from_url.__name__ == "_fake_upload_from_url")
    if not _u_ok:
        print("❌ GÜVENLİK: Postiz upload mock eksik — DUR.")
        return 2
    print("[güvenlik] Postiz schedule_posts + upload HER İKİ sınıfta da mock — sıfır gerçek Postiz teması.")

    trend, plan, src = synthetic_trend_plan(tid)

    def _stub_run_crew(self, account_id):
        self.state.trend = trend
        self.state.plan = plan
        self.state.trend_raw_content_cache[tid] = src
        self.state.total_tokens = 0
        self.state.editor_decision = "lg_node_coverage_test"
        return None

    def _stub_write(self):
        body = ("OpenAI yeni modelini duyurdu; API erişimi açıldı, token "
                "fiyatları düştü. (lg node-coverage test draftı)")
        self.state.draft = WriterOutput(
            content=body, character_count=len(body), hook_type="result",
            line_count=1, has_em_dash=False, has_corporate_words=[],
            voice_alignment_score=90)
        self.state.platform_drafts = [
            PlatformDraft(platform=p, integration_id=f"intg-{p}",
                          account_id=self.state.account_id, content=body,
                          tokens_used=0, model_used="stub", char_count=len(body),
                          compliance_passed=True)
            for p in PLATFORMS]
        self.state.target_platforms = list(PLATFORMS)
        return None

    def _stub_compliance(self):
        self.state.compliance = ComplianceOutput(
            approved=True, dedup_passed=True, similarity_to_recent=0.0,
            rejection_reason=None, hard_rules_violated=[],
            forbidden_topics_detected=[], brand_voice_score=90, confidence=95)
        return None

    _orig_persona = flowmod.AutonomousContentFlow._resolve_persona

    def _persona_render_on(self):
        try:
            p = dict(_orig_persona(self) or {})
        except Exception:
            p = {}
        p.setdefault("slug", "cansu")
        p.setdefault("display_name", "Cansu")
        p["default_target_platforms"] = list(PLATFORMS)
        p["visual_enabled"] = True
        p["video_enabled"] = True
        p["text_autonomy_unlocked"] = True
        p["image_autonomy_unlocked"] = True
        p["video_autonomy_unlocked"] = True
        return p

    def _spy_visual(self):
        COUNTERS["visual"] += 1
        ORDER.append("visual")
        self.state.visual = VisualDirectorOutput(
            needs_visual=True, visual_mode="face",
            image_url="https://example.invalid/lg-node-coverage.png",
            asset_id=None,  # uuid kolonu — sahte string 22P02 verir; None=NULL güvenli
            model_slug="spy/seedream", cost_usd=0.0,
            compliance_verdict="PASS", compliance_reasoning="spy (node-coverage)")
        return None

    def _spy_video(self):
        COUNTERS["video"] += 1
        ORDER.append("video")
        self.state.video = VideoOutput(
            pipeline_used="spy", video_url="https://example.invalid/lg-node-coverage.mp4",
            thumbnail_url="https://example.invalid/lg-node-coverage.jpg",
            duration_sec=20.0, file_size_bytes=1_000_000, cost_usd=0.0,
            generation_latency_ms=0, target_platform=VIDEO_PLATFORM)
        return None

    def _wrap(name, fn):
        def _w(self, *a, **k):
            COUNTERS[name] += 1
            ORDER.append(name)
            return fn(self, *a, **k)
        return _w

    AF = flowmod.AutonomousContentFlow
    _orig_init, _orig_pub, _orig_fin = AF.initialize, AF.publish_to_drafts, AF._finalize
    AF.run_crew = _wrap("run_crew", _stub_run_crew)
    AF.write_via_typehype = _wrap("write", _stub_write)
    AF.run_compliance = _wrap("compliance", _stub_compliance)
    AF.generate_visual = _spy_visual
    AF.generate_video = _spy_video
    AF._resolve_persona = _persona_render_on
    AF.initialize = _wrap("initialize", _orig_init)
    AF.publish_to_drafts = _wrap("publish", _orig_pub)
    AF._finalize = _wrap("finalize", _orig_fin)

    RECORDER["calls"].clear()
    ALERTS.clear()
    seed_trend(tid)

    from lg.graph import run_or_resume
    print(f"[test] run_id={run_id} trend={tid} platforms={PLATFORMS} — "
          f"node-coverage (visual+video+publish; render SPY, Postiz SPY)")
    final = None
    try:
        final = run_or_resume(CANSU, triggered_by="manual", run_id=run_id)

        if final is None:
            failures.append("run_or_resume None (advisory lock BUSY?) — akış koşmadı")
        elif final.dry_run:
            failures.append("final.dry_run=True — routing publish yerine dry_run_complete'e gitti "
                            "(Cansu config dry_run_mode açık?)")

        for node, mn in (("initialize", 1), ("run_crew", 1), ("write", 1), ("compliance", 1),
                         ("visual", 1), ("video", 1), ("publish", 1), ("finalize", 1)):
            if COUNTERS[node] < mn:
                failures.append(f"node '{node}' çağrılmadı (count={COUNTERS[node]})")

        def _idx(n):
            return ORDER.index(n) if n in ORDER else -1
        ic, iv, ivd, ip = _idx("compliance"), _idx("visual"), _idx("video"), _idx("publish")
        if not (0 <= ic < iv < ivd < ip):
            failures.append(f"routing sırası yanlış: compliance={ic} visual={iv} video={ivd} publish={ip}")

        if final is not None:
            if not (final.visual and final.visual.image_url):
                failures.append("state.visual publish'e taşınmadı")
            if not (final.video and final.video.video_url):
                failures.append("state.video publish'e taşınmadı")

        total = len(RECORDER["calls"])
        yt = platform_call_count(VIDEO_PLATFORM)
        print(f"[kanıt] schedule_posts spy batch={total} | youtube platform-call={yt} | RECORDER={RECORDER['calls']}")
        if total < 1:
            failures.append("schedule_posts spy çağrılmadı — publish Postiz yoluna girmedi (auto_publish?)")
        if yt < 1:
            failures.append("schedule_posts(youtube) çağrılmadı — video draft publish edilmedi")

        rows = [r for r in draft_rows(run_id) if not r.get("deleted_at")]
        plats = [r.get("platform") for r in rows]
        print(f"[kanıt] daily_drafts (canlı): {plats} | postiz_id'ler: "
              f"{[(r.get('platform'), r.get('postiz_post_id')) for r in rows]}")
        if not rows:
            failures.append("daily_drafts yazılmadı (write-ahead/publish koşmadı)")
        seen: dict = {}
        for r in rows:
            seen[r.get("platform")] = seen.get(r.get("platform"), 0) + 1
        if any(v > 1 for v in seen.values()):
            failures.append(f"ÇİFT-SATIR: {{k:v for k,v in seen.items() if v>1}}")
        stuck = [r.get("platform") for r in rows if r.get("postiz_post_id") == "SCHEDULING"]
        if stuck:
            failures.append(f"SCHEDULING writeback olmadı: {stuck} (publish yarıda kaldı)")

        print("\n[node sayaçları] " + ", ".join(f"{k}={v}" for k, v in COUNTERS.items()))
        print(f"[routing] {ORDER}")
    finally:
        try:
            print(f"[cleanup] {cleanup_run(run_id)}")
        except Exception as ce:  # noqa: BLE001
            print(f"[cleanup][warn] {run_id}: {ce}")
        try:
            delete_trend(tid)
        except Exception:  # noqa: BLE001
            pass
        print(f"[cleanup] NOT: checkpoint thread={run_id} MANUEL silinmeli (langgraph.*).")

    ok = not failures
    print("\n" + "=" * 64)
    if ok:
        print("✅ NODE-COVERAGE PASS — visual+video+publish node'ları LangGraph üzerinden koştu: "
              "routing compliance→visual→video→publish doğru, state aktı, schedule_posts SPY "
              "çağrıldı (gerçek Postiz=0), daily_drafts write-ahead→writeback tamam, çift-satır YOK.")
    else:
        print("❌ NODE-COVERAGE FAIL:")
        for f in failures:
            print("   -", f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
