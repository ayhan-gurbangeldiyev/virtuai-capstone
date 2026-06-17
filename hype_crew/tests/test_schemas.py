"""Schema validation tests — happy path + edge cases."""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from schemas import (
    TrendScoutOutput,
    PlannerOutput,
    WriterOutput,
    ComplianceOutput,
    PublisherOutput,
    FlowState,
)


# ─── TrendScoutOutput ──────────────────────────────────────────────────────


def test_trendscout_happy():
    out = TrendScoutOutput(
        trend_id="abc-123",
        topic="GPT-5 leak",
        score=95,
        is_vip=True,
        category="ai",
        semantic_triggers=["launch", "breaking"],
        urgency_hours=6,
        angle_hint="indie devs için pratik anlamı",
        reasoning="vip+launch+yüksek skor",
        passed=True,
    )
    assert out.passed
    assert out.score == 95


def test_trendscout_pass_with_reason():
    out = TrendScoutOutput(
        trend_id="xyz",
        topic="cat photo trend",
        score=55,
        is_vip=False,
        category="other",
        semantic_triggers=[],
        urgency_hours=24,
        angle_hint="",
        reasoning="skor düşük + niche dışı",
        passed=False,
        skip_reason="off-niche, low score",
    )
    assert not out.passed
    assert out.skip_reason


def test_trendscout_score_bounds():
    with pytest.raises(ValidationError):
        TrendScoutOutput(
            trend_id="x", topic="y", score=150, is_vip=False,
            category="ai", urgency_hours=6, angle_hint="z",
            reasoning="r",
        )


# ─── PlannerOutput ─────────────────────────────────────────────────────────


def test_planner_happy():
    out = PlannerOutput(
        etki="patlassin",
        karakter="uzman",
        uzunluk="punch",
        hook_type="contrast",
        brief="GPT-5 release'inin solo dev için pratik anlamı, mevcut workflow'a ne katar",
        angle="herkes 'agi' diyor, ben 'workflow değişimi' diyorum",
        target_engagement="bookmarks",
        reasoning="kullanıcı bookmark-heavy bir audience'a sahip",
    )
    assert out.etki == "patlassin"


def test_planner_invalid_etki():
    with pytest.raises(ValidationError):
        PlannerOutput(
            etki="abc",  # invalid literal
            karakter="uzman",
            uzunluk="punch",
            hook_type="contrast",
            brief="x" * 25,
            angle="y" * 15,
            target_engagement="mixed",
            reasoning="r",
        )


# ─── WriterOutput ──────────────────────────────────────────────────────────


def test_writer_happy():
    content = "hook satırı.\n\nbody.\n\npunchline."
    out = WriterOutput(
        content=content,
        character_count=len(content),
        hook_type="story",
        line_count=5,
        has_em_dash=False,
        has_corporate_words=[],
        voice_alignment_score=85,
    )
    assert not out.has_em_dash
    assert out.voice_alignment_score == 85


def test_writer_too_long():
    # Schema now allows up to 4000 (storm/thread). >4000 still rejected.
    with pytest.raises(ValidationError):
        WriterOutput(
            content="x" * 5000,
            character_count=5000,
            hook_type="story",
            line_count=1,
            voice_alignment_score=50,
        )


# ─── ComplianceOutput ──────────────────────────────────────────────────────


def test_compliance_approved():
    out = ComplianceOutput(
        approved=True,
        dedup_passed=True,
        similarity_to_recent=0.15,
        forbidden_topics_detected=[],
        hard_rules_violated=[],
        brand_voice_score=88,
        rejection_reason=None,
        confidence=92,
    )
    assert out.approved


def test_compliance_rejected():
    out = ComplianceOutput(
        approved=False,
        dedup_passed=False,
        similarity_to_recent=0.95,
        forbidden_topics_detected=["politics"],
        hard_rules_violated=["em-dash detected"],
        brand_voice_score=40,
        rejection_reason="High similarity + forbidden topic + voice drift",
        confidence=85,
    )
    assert not out.approved
    assert out.rejection_reason


# ─── PublisherOutput ───────────────────────────────────────────────────────


def test_publisher_dry_run():
    out = PublisherOutput(
        postiz_post_id="DRY_RUN_abc",
        integration_id="int_xyz",
        scheduled_at=datetime.now(timezone.utc),
        dry_run=True,
    )
    assert out.dry_run
    assert out.postiz_post_id.startswith("DRY_RUN_")


# ─── FlowState ─────────────────────────────────────────────────────────────


def test_flowstate_init_empty():
    state = FlowState(account_id="acc-123")
    assert state.trend is None
    assert state.user_action is None


def test_flowstate_fully_populated():
    state = FlowState(
        account_id="acc-123",
        run_id="run-456",
        trend=TrendScoutOutput(
            trend_id="t1", topic="GPT-5", score=95, is_vip=True, category="ai",
            urgency_hours=4, angle_hint="z", reasoning="r",
        ),
        user_action="approved",
        user_feedback="great",
    )
    assert state.trend.score == 95
    assert state.user_action == "approved"
