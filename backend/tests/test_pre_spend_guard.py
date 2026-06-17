"""Proof: the pre-spend guard refuses HeyGen render for bad scripts and
accepts good ones — BEFORE any spend happens.

⚠️ NEVER PUBLISH OR RENDER FROM A TEST. ⚠️
Mocked client only. No HeyGen, no MiniMax, no Postiz reach.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))
sys.path.insert(0, "/opt/hype-crew")


# ──────────────────────── pure helper tests ──────────────────────────

_GOOD_SCRIPT = (
    "OpenAI bugün ChatGPT'nin hafıza sistemine ciddi bir güncelleme getirdi. "
    "Sistem artık kullanıcının önceki konuşmalarındaki tercihleri ve "
    "bağlam bilgisini otomatik olarak hatırlayıp ilgili tüm parçaları "
    "bir sonraki sohbete taşıyabiliyor. Bu özellik ücretsiz kullanıcılar "
    "için de aktif edildi. Bence asıl önemli olan şu: kişisel bağlamın "
    "kalıcılaşması, asistan modelinde köklü bir değişim demek. Artık her "
    "sohbet sıfırdan başlamayacak ve kullanıcı yıllar boyu kurduğu bağlamı "
    "kaybetmeden devam edebilecek. Sence bu, asistan ile ilişkimizi nasıl "
    "değiştirir? Yorumlarda paylaşmayı unutmayın."
)


def test_good_600char_script_passes():
    from tools.pre_spend_guard import validate_script_before_spend
    assert 510 <= len(_GOOD_SCRIPT.strip()) <= 1000, len(_GOOD_SCRIPT.strip())
    r = validate_script_before_spend(_GOOD_SCRIPT)
    assert r.ok, f"good script should pass, got {r.reason}: {r.detail}"
    assert 510 <= r.chars <= 1000


def test_butchered_too_short_refused():
    from tools.pre_spend_guard import validate_script_before_spend
    r = validate_script_before_spend("kısa bir cümle, çok kısa.")
    assert r.ok is False
    assert r.reason == "script_too_short"


def test_too_long_refused():
    from tools.pre_spend_guard import validate_script_before_spend
    r = validate_script_before_spend("Çok uzun. " * 200)
    assert r.ok is False
    assert r.reason == "script_too_long"


_TRUNCATED_SCRIPT = _GOOD_SCRIPT.rstrip(".!? ") + " ve kullanıcı için bağlamın"


def test_mid_clause_truncation_refused():
    """The exact failure mode the SEV-1 follow-up surfaced: in-band length
    but ends mid-clause (no terminal punctuation)."""
    from tools.pre_spend_guard import validate_script_before_spend
    assert 510 <= len(_TRUNCATED_SCRIPT.strip()) <= 1000
    r = validate_script_before_spend(_TRUNCATED_SCRIPT)
    assert r.ok is False
    assert r.reason == "mid_clause_truncation"


def test_empty_script_refused():
    from tools.pre_spend_guard import validate_script_before_spend
    r = validate_script_before_spend("")
    assert r.ok is False
    assert r.reason == "empty_script"


def test_none_script_refused():
    from tools.pre_spend_guard import validate_script_before_spend
    r = validate_script_before_spend(None)  # type: ignore[arg-type]
    assert r.ok is False
    assert r.reason == "empty_script"


def test_quoted_ending_accepted():
    """A script ending on `...sözleri.»` (close-quote after period) is fine."""
    from tools.pre_spend_guard import validate_script_before_spend
    script = (
        "ChatGPT'nin yeni hafıza güncellemesi kullanıcı deneyimini "
        "kökten değiştiriyor. " * 5
    ).strip() + " OpenAI sözcüsü bunu \"yıllık en önemli güncelleme\" olarak nitelendirdi."
    r = validate_script_before_spend(script)
    if 510 <= len(script.strip()) <= 1000:
        assert r.ok is True, r.detail


# ─────────────── pipeline-level: HeyGen is NOT called ───────────────


@pytest.mark.asyncio
async def test_pipeline_refuses_bad_script_before_heygen_called():
    """The big one: feed a butchered script to the pipeline; HeyGen client
    must never be instantiated. Spend = $0."""
    from tools.pre_spend_guard import PreSpendRejected
    from tools.video_pipeline import HeyGenAvatarVPipeline, VideoBrief

    pipe = HeyGenAvatarVPipeline()

    bad_brief = VideoBrief(
        persona_id="00000000-0000-4000-8000-000000000001",
        anchor_image_url="https://example.invalid/x.jpg",
        script_text="çok kısa, render etmeye değmez.",  # too short
        target_aspect="9:16",
        target_duration=30,
        action_prompt=None,
        daily_draft_id="22222222-2222-4222-8222-222222222222",
    )

    with patch("tools.heygen_client.HeyGenClient") as MockHG, \
         patch("tools.minimax_tts_client.MinimaxTTSClient") as MockMM:
        MockHG.return_value = MagicMock()
        MockMM.return_value = MagicMock()

        with pytest.raises(PreSpendRejected) as exc:
            await pipe.produce_video(bad_brief)

        assert exc.value.reason == "script_too_short"
        # The guard fires BEFORE either client is constructed.
        MockHG.assert_not_called()
        MockMM.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_refuses_truncated_script_before_heygen_called():
    """Mid-clause truncation (the SEV-1 failure mode) is refused too."""
    from tools.pre_spend_guard import PreSpendRejected
    from tools.video_pipeline import HeyGenAvatarVPipeline, VideoBrief

    pipe = HeyGenAvatarVPipeline()

    bad_brief = VideoBrief(
        persona_id="00000000-0000-4000-8000-000000000001",
        anchor_image_url="https://example.invalid/x.jpg",
        script_text=_TRUNCATED_SCRIPT,
        target_aspect="9:16",
        target_duration=40,
        action_prompt=None,
        daily_draft_id="33333333-3333-4333-8333-333333333333",
    )

    with patch("tools.heygen_client.HeyGenClient") as MockHG, \
         patch("tools.minimax_tts_client.MinimaxTTSClient") as MockMM:
        with pytest.raises(PreSpendRejected) as exc:
            await pipe.produce_video(bad_brief)
        assert exc.value.reason == "mid_clause_truncation"
        MockHG.assert_not_called()
        MockMM.assert_not_called()
