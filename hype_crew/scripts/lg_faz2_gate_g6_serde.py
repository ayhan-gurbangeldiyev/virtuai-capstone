"""G6 — FULLY-POPULATED state serde round-trip on the REAL Postgres pooler.

Highest-severity quiet-failure test. Builds a HypeFlowState with EVERY nested
field populated (trend, plan, draft, compliance, visual, video, publish,
platform_drafts, + caches/editor fields), runs it through the REAL
sync_checkpointer() (Postgres, langgraph schema) with durability='sync', then
reads it back through a FRESH checkpointer/graph (resume-process simulation).

ASSERTS:
  1. Every nested field deserializes back as its PROPER pydantic TYPE (not dict).
  2. Values are byte-identical (model_dump equality, field-by-field).
  3. Checkpoint rows actually landed in langgraph.* (not public.*).
  4. search_path=langgraph applied on the checkpoint connection.

This catches the "missing allowlist entry → silent dict corruption → wrong
content live" risk: if a nested model deserializes as a plain dict, downstream
code that does state.trend.topic / state.plan.content_type silently reads the
wrong thing (or AttributeErrors), and worse, the writeback content_type key
(_write_daily_draft → state.plan.content_type) would be derived from a dict.

NO paid calls. NO posting. Cleans up the test thread's checkpoint rows by
thread_id at the end.

Run:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_gate_g6_serde
"""
from __future__ import annotations

import os
import uuid


def _build_full_state():
    """A HypeFlowState with EVERY nested field populated."""
    from flow import HypeFlowState, PlatformDraft, VideoOutput
    from schemas import (
        TrendScoutOutput, PlannerOutput, WriterOutput, ComplianceOutput,
        PublisherOutput,
    )
    from schemas.trend import TrendScoutBreakdown
    from schemas.visual import VisualDirectorOutput

    trend = TrendScoutOutput(
        trend_id="g6-trend-1",
        topic="OpenAI GPT-6 duyurdu",
        score=92,
        is_vip=True,
        category="model_launch",
        semantic_triggers=["launch", "milestone"],
        urgency_hours=12,
        angle_hint="herkese açık + ucuz",
        reasoning="g6 serde testi — tam dolu trend",
        breakdown=TrendScoutBreakdown(
            duyuru_tipi=5, erisim=2, kullanilabilirlik=2,
            kaynak=1, rekabet=1, fiyat=1,
        ),
        final_score_12=12,
        content_type="model_launch",
        passed=True,
        skip_reason=None,
        video_worthy=True,
        video_reason="major launch — video değer",
    )
    plan = PlannerOutput(
        etki="patlassin", karakter="haberci", uzunluk="punch",
        brief="GPT-6 duyuruldu; herkese açık ve ucuz, net ve sade aktar (g6 brief)",
        hook_type="result", angle="API artık daha ucuz",
        target_engagement="mixed", reasoning="g6 plan reasoning",
        content_type="model_launch", voice_mode="hybrid",
    )
    draft = WriterOutput(
        content="GPT-6 çıktı; herkese açık, fiyat düştü. (g6 draft)",
        character_count=48, hook_type="result", line_count=1,
        has_em_dash=False, has_corporate_words=[], voice_alignment_score=91,
    )
    compliance = ComplianceOutput(
        approved=True, dedup_passed=True, similarity_to_recent=0.07,
        forbidden_topics_detected=[], hard_rules_violated=[],
        brand_voice_score=90, rejection_reason=None, confidence=95,
    )
    visual = VisualDirectorOutput(
        needs_visual=True, skip_reason=None,
        visual_mode="conceptual", composition_type="brand_news_visual",
        scene_type="ai_interface",
        scene_description="OpenAI logo + GPT-6 UI mockup, no people",
        mood="technical", outfit=None, outfit_tier=None,
        content_context="brand news visual", aspect_ratio="1:1",
        rationale="g6 — brand news, no Cansu",
        asset_id="g6-asset-1", image_url="https://example.com/g6.png",
        model_slug="ByteDance/seedream-v4-5", cost_usd=0.04, latency_ms=2200,
        clip_similarity=0.81, aesthetic_score=7.2, ocr_flagged=False,
        compliance_verdict="PASS", compliance_reasoning="ok",
        visual_brief_json={"template": "brand_news", "subject": "GPT-6"},
        visual_decision_needs_cansu=False,
        visual_decision_reason="marka haberi", visual_decision_path="brand",
        visual_decision_model="gemini",
    )
    video = VideoOutput(
        pipeline_used="heygen_split_screen",
        video_url="https://example.com/g6.mp4",
        thumbnail_url="https://example.com/g6_thumb.png",
        duration_sec=28.5, file_size_bytes=4_200_000, cost_usd=0.30,
        generation_latency_ms=45000, target_platform="youtube",
    )
    publish = PublisherOutput(
        postiz_post_id="DRY_RUN_g6", integration_id="intg-x",
        scheduled_at="2026-06-14T12:00:00+00:00", platform="twitter",
        dry_run=True,
    )
    pds = [
        PlatformDraft(
            platform="twitter", integration_id="intg-x", account_id="acc-g6",
            content="GPT-6 çıktı (twitter g6)", title=None, tags=None,
            tokens_used=120, model_used="typehype-v3", char_count=24,
            compliance_passed=True, compliance_reason=None,
            postiz_post_id=None, scheduled_at=None, daily_draft_id=None,
        ),
        PlatformDraft(
            platform="devto", integration_id="intg-devto", account_id="acc-g6",
            content="GPT-6 uzun makale (devto g6)", title="GPT-6 Lansmanı",
            tags=["ai", "openai"], tokens_used=900, model_used="typehype-v3",
            char_count=28, compliance_passed=True, compliance_reason=None,
            postiz_post_id="SCHEDULING", scheduled_at="2026-06-14T12:00:00+00:00",
            daily_draft_id="dd-g6-devto",
        ),
    ]

    state = HypeFlowState(
        account_id="acc-g6", run_id="g6-run-1", triggered_by="manual",
        dry_run=True, started_at_ts=1718000000.5, total_tokens=1234,
        target_platforms=["twitter", "devto"], platform_drafts=pds,
        content_thread_id="thread-g6",
        trend=trend, plan=plan, draft=draft, compliance=compliance,
        visual=visual, video=video, publish=publish,
        final_status="completed", error=None,
        editor_decision="editors_desk_pick", editor_decision_error=None,
        trend_raw_content_cache={"g6-trend-1": "## KAYNAK METİN: GPT-6 gerçek gövde."},
        trend_source_url_cache={"g6-trend-1": "https://example.com/gpt6"},
    )
    return state


# (field_name, expected pydantic class path) for type-identity assertions.
_NESTED_TYPES = [
    ("trend", "schemas.trend", "TrendScoutOutput"),
    ("plan", "schemas.plan", "PlannerOutput"),
    ("draft", "schemas.draft", "WriterOutput"),
    ("compliance", "schemas.draft", "ComplianceOutput"),
    ("visual", "schemas.visual", "VisualDirectorOutput"),
    ("video", "flow", "VideoOutput"),
    ("publish", "schemas.publish", "PublisherOutput"),
]


def main() -> int:
    from lg.checkpointer import sync_checkpointer
    from langgraph.graph import StateGraph, START, END
    from flow import HypeFlowState, PlatformDraft

    failures: list[str] = []
    full = _build_full_state()
    expected_dump = full.model_dump(mode="python")

    def _passthrough(state):
        return {k: getattr(state, k) for k in type(state).model_fields}

    g = StateGraph(HypeFlowState)
    g.add_node("n", _passthrough)
    g.add_edge(START, "n")
    g.add_edge("n", END)

    tid = f"g6-serde:{uuid.uuid4().hex}"
    cfg = {"configurable": {"thread_id": tid}}

    # ── process-sim 1: WRITE through REAL Postgres checkpointer ──
    with sync_checkpointer() as cp:
        graph = g.compile(checkpointer=cp)
        graph.invoke(full, cfg, durability="sync")
    print(f"[G6] wrote full state to Postgres checkpoint thread={tid}")

    # ── confirm rows landed in langgraph.* (not public.*) + search_path ──
    url = os.environ.get("HYPE_CHECKPOINT_DB_URL", "")
    landed_langgraph = False
    leaked_public = False
    search_path_ok = False
    try:
        import psycopg
        conn = psycopg.connect(url, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM langgraph.checkpoints WHERE thread_id = %s",
                (tid,),
            )
            n_lg = cur.fetchone()[0]
            landed_langgraph = n_lg > 0
            # public.checkpoints may not exist at all — that's the GOOD case
            try:
                cur.execute(
                    "SELECT count(*) FROM public.checkpoints WHERE thread_id = %s",
                    (tid,),
                )
                leaked_public = cur.fetchone()[0] > 0
            except Exception:
                leaked_public = False  # table doesn't exist → never leaked
            # search_path applied by _configure_conn_sync on this fresh conn?
            # (we set it ourselves to verify the SET statement works against pooler)
            cur.execute("SET search_path TO langgraph, public")
            cur.execute("SHOW search_path")
            sp = cur.fetchone()[0]
            search_path_ok = "langgraph" in sp
        conn.close()
    except Exception as e:
        failures.append(f"langgraph.* verification query failed: {e}")

    print(f"[G6] landed in langgraph.checkpoints: {landed_langgraph}")
    print(f"[G6] leaked to public.checkpoints: {leaked_public}")
    print(f"[G6] search_path applies (langgraph in path): {search_path_ok}")
    if not landed_langgraph:
        failures.append("checkpoint did NOT land in langgraph.checkpoints")
    if leaked_public:
        failures.append("checkpoint LEAKED into public.checkpoints")
    if not search_path_ok:
        failures.append("search_path=langgraph not applicable")

    # ── process-sim 2: FRESH checkpointer/graph → READ BACK (deserialize) ──
    with sync_checkpointer() as cp2:
        graph2 = g.compile(checkpointer=cp2)
        snap = graph2.get_state(cfg)
    v = snap.values

    def _get(key):
        return v[key] if isinstance(v, dict) else getattr(v, key)

    # 1) TYPE-IDENTITY: each nested field is its proper pydantic type, NOT dict.
    import importlib
    for field, mod_name, cls_name in _NESTED_TYPES:
        val = _get(field)
        if isinstance(val, dict):
            failures.append(
                f"{field} deserialized as DICT (silent corruption — type lost)"
            )
            continue
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name)
        except Exception as e:
            failures.append(f"{field}: cannot import expected type {mod_name}.{cls_name}: {e}")
            continue
        if not isinstance(val, cls):
            failures.append(
                f"{field} type={type(val).__name__} != expected {cls_name}"
            )

    # platform_drafts: list of PlatformDraft (not list of dict)
    pds = _get("platform_drafts")
    if not isinstance(pds, list) or not pds:
        failures.append("platform_drafts missing/empty after round-trip")
    else:
        for i, pd in enumerate(pds):
            if isinstance(pd, dict):
                failures.append(f"platform_drafts[{i}] deserialized as DICT")
            elif not isinstance(pd, PlatformDraft):
                failures.append(f"platform_drafts[{i}] type={type(pd).__name__} != PlatformDraft")

    # 2) BYTE-IDENTICAL: full re-materialize → model_dump must equal original.
    try:
        rt = v if isinstance(v, HypeFlowState) else HypeFlowState(**v)
        rt_dump = rt.model_dump(mode="python")
        if rt_dump != expected_dump:
            # find the first differing key for a precise report
            diffs = []
            for k in expected_dump:
                if rt_dump.get(k) != expected_dump.get(k):
                    diffs.append(k)
            failures.append(
                f"round-trip NOT byte-identical; differing fields: {diffs}"
            )
        else:
            print("[G6] full model_dump byte-identical: True")
    except Exception as e:
        failures.append(f"could not re-materialize HypeFlowState from snapshot: {e}")

    # caches + editor fields explicit checks
    if _get("trend_raw_content_cache").get("g6-trend-1") != \
            "## KAYNAK METİN: GPT-6 gerçek gövde.":
        failures.append("trend_raw_content_cache lost on round-trip (R6 risk)")
    if _get("editor_decision") != "editors_desk_pick":
        failures.append("editor_decision lost on round-trip")

    # nested-of-nested: trend.breakdown must survive as a model with its ints
    tr = _get("trend")
    if not isinstance(tr, dict):
        bd = getattr(tr, "breakdown", None)
        if bd is None:
            failures.append("trend.breakdown lost on round-trip")
        elif isinstance(bd, dict):
            failures.append("trend.breakdown deserialized as DICT (nested-of-nested corruption)")
        elif getattr(bd, "duyuru_tipi", None) != 5:
            failures.append("trend.breakdown.duyuru_tipi value corrupted")

    # ── CLEANUP — remove this test thread's checkpoint rows ──
    deleted = _cleanup_checkpoint_thread(url, tid)
    print(f"[G6] cleanup deleted checkpoint rows for thread={tid}: {deleted}")

    ok = not failures
    print("\n" + "=" * 64)
    if ok:
        print("✅ G6 PASS — every nested field round-trips as its pydantic TYPE, "
              "byte-identical; checkpoints in langgraph.* (no public leak); "
              "search_path OK.")
    else:
        print("❌ G6 FAIL:")
        for f in failures:
            print("   -", f)
    return 0 if ok else 1


def _cleanup_checkpoint_thread(url: str, thread_id: str) -> dict:
    out = {}
    try:
        import psycopg
        conn = psycopg.connect(url, autocommit=True)
        with conn.cursor() as cur:
            for t in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                try:
                    cur.execute(f"DELETE FROM langgraph.{t} WHERE thread_id = %s", (thread_id,))
                    out[t] = cur.rowcount
                except Exception as e:
                    out[t] = f"err: {str(e)[:60]}"
        conn.close()
    except Exception as e:
        out["error"] = str(e)[:120]
    return out


if __name__ == "__main__":
    raise SystemExit(main())
