"""Shared harness for the publish double-post safety GATES (G1/G2/G3).

Reuses the proven Test-B mock pattern (real publish_to_drafts code, mocked edges):
  - GuardedPostizClient.schedule_posts / PostizClient.schedule_posts → RECORDER
    (records requested platforms per call, returns fake real-shaped ids). NO real
    Postiz. Counts calls per platform so we can prove "scheduled exactly once".
  - faithfulness gate (assert_publishable) + clarity gate → stubbed PASS (NO LLM cost).
  - shadow gate + companion cards → no-op (NO cost/side-effects).
  - persona → visual/video OFF, all autonomy unlocked (no deferred path).
  - hype_account_config read → wrapped IN-PROCESS to auto_publish_enabled=true,
    allowlist=None. Cansu's LIVE config row is NEVER written.
  - tools.alerter.send_alert → spied into ALERTS (no real Slack/email).

content_type is fixed to the synthetic plan's content_type ('model_launch') so
seeded SCHEDULING/real rows match the (hype_run_id, platform, content_type)
partial-unique key the run writes against.

NO production code edited. All monkeypatches are in-process only.
"""
from __future__ import annotations

import uuid

CONTENT_TYPE = "model_launch"  # == synthetic plan.content_type

# schedule_posts call recorder: each entry is the list of platforms requested
# in one schedule_posts call. Use platform_call_count() to count per platform.
RECORDER: dict = {"calls": []}
# send_alert spy: each entry is the kwargs+title of one alert.
ALERTS: list = []


def platform_call_count(platform: str) -> int:
    """How many times schedule_posts was asked to schedule `platform` (across
    all calls / all crash+resume cycles since the last clear)."""
    p = platform.lower()
    return sum(call.count(p) for call in RECORDER["calls"])


def install_publish_mocks(flowmod, platforms=("twitter", "linkedin")):
    import flow as _f
    import tools.guarded_postiz as _gp
    import tools.postiz_client as _pc
    from tools.guarded_postiz import GateOutcome
    import tools.clarity_gate as _cg
    import tools.alerter as _al
    from tools.supabase_client import make_supabase as _real_make_sb
    from scripts.lg_faz2_idem_testlib import (
        neutralize_shadow_gate, neutralize_companion_cards,
    )

    neutralize_shadow_gate()
    neutralize_companion_cards()

    # 1) persona — visual/video OFF, all modality unlocks ON (no deferred path)
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
            "default_target_platforms": list(platforms),
        }
    _f.AutonomousContentFlow._resolve_persona = _stub_persona

    # 2) config read — auto_publish_enabled=true, allowlist=None. Cansu's REAL
    #    config row is untouched; only THIS process's read of
    #    hype_account_config is wrapped. All other tables pass through to real DB.
    class _FakeCfgResp:
        data = [{"auto_publish_enabled": True, "allowed_publish_platforms": None}]

    class _FakeCfgTable:
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return _FakeCfgResp()

    class _SBWrap:
        def __init__(self, real):
            self._real = real

        def table(self, name):
            if name == "hype_account_config":
                return _FakeCfgTable()
            return self._real.table(name)

        def __getattr__(self, item):
            return getattr(self._real, item)

    def _wrapped_make_sb():
        return _SBWrap(_real_make_sb())

    _f.make_supabase = _wrapped_make_sb

    # 3) faithfulness gate → PASS (no LLM)
    async def _stub_assert_publishable(*, draft_text, source_raw_content, path, draft_id):
        return GateOutcome(
            draft_id=draft_id, path=path, verdict="PASS",
            token="STUB_TOKEN", content_hash="stub", reasoning="stub PASS")
    _gp.assert_publishable = _stub_assert_publishable

    # 4) clarity gate → always clear (no LLM)
    async def _stub_check_clarity(text, platform=""):
        return {"clear": True, "reason": "stub clear"}
    _cg.check_clarity = _stub_check_clarity

    # 5) schedule_posts RECORDER — NO real Postiz. Record requested platforms,
    #    return fake real-shaped ids. Patch BOTH Guarded + base client so even
    #    super().schedule_posts() can never hit the network.
    def _recorder_schedule_posts(self, posts, scheduled_at, *args, **kwargs):
        plats = [getattr(p, "provider", None) or getattr(p, "platform", "?") for p in posts]
        RECORDER["calls"].append([str(p).lower() for p in plats])
        return [{"postId": f"FAKE_{p}_{uuid.uuid4().hex[:6]}"} for p in plats]
    _gp.GuardedPostizClient.schedule_posts = _recorder_schedule_posts
    _pc.PostizClient.schedule_posts = _recorder_schedule_posts

    # 6) alerter spy — capture CRITICAL alerts, no real Slack/email/journald.
    def _spy_send_alert(title, *, severity="info", platform=None, draft_id=None,
                        postiz_post_id=None, reason=None, action=None, extra=None):
        ALERTS.append({
            "title": title, "severity": severity, "platform": platform,
            "draft_id": draft_id, "postiz_post_id": postiz_post_id,
            "reason": reason, "action": action, "extra": extra,
        })
        return {"journald": True, "slack": False, "email": False}
    _al.send_alert = _spy_send_alert


def build_publish_state(flowmod, run_id: str, tid: str, platforms):
    """Minimal valid state to drive publish_to_drafts directly."""
    from flow import HypeFlowState, PlatformDraft
    from schemas import WriterOutput, TrendScoutOutput, PlannerOutput
    cf = flowmod.AutonomousContentFlow()
    st = HypeFlowState(account_id="2b731bf7-8c24-40c5-8237-d348ee822d51",
                       triggered_by="manual")
    st.run_id = run_id
    st.dry_run = False
    body = "OpenAI yeni modelini duyurdu; API erişimi açıldı. (faz2 gate test)"
    st.draft = WriterOutput(
        content=body, character_count=len(body), hook_type="result",
        line_count=1, has_em_dash=False, has_corporate_words=[],
        voice_alignment_score=90)
    st.trend = TrendScoutOutput(
        trend_id=tid, topic="OpenAI yeni model", score=92,
        category="model_launch", urgency_hours=12, reasoning="gate test")
    st.plan = PlannerOutput(
        etki="patlassin", karakter="haberci", uzunluk="punch",
        brief="OpenAI yeni model + ucuz API duyurusunu net aktar (faz2 gate brief)",
        hook_type="result", angle="API artık ucuz", content_type=CONTENT_TYPE,
        voice_mode="hybrid", target_engagement="mixed", reasoning="gate plan")
    st.trend_raw_content_cache[tid] = "## KAYNAK: OpenAI yeni model. (gate test)"
    st.platform_drafts = [
        PlatformDraft(platform=p, integration_id=f"intg-{p}",
                      account_id=st.account_id, content=body, tokens_used=0,
                      model_used="stub", char_count=len(body),
                      compliance_passed=True)
        for p in platforms
    ]
    st.target_platforms = list(platforms)
    object.__setattr__(cf, "_state", st)
    return cf
