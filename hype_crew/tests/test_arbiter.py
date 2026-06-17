"""Arbiter (blok temyiz hakimi) plumbing testleri — LLM stub'lı.

2026-06-10: fp/minor → blok kalkar (reasoning'e ARBITER notu düşer),
fabrication → blok kalır + ihlal listesi onaylanmış kalemlere filtrelenir,
error → orijinal blok korunur (fail-closed), kill-switch env çalışır.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.faithfulness_gate as fg  # noqa: E402


SOURCE = "Apple: Our most powerful on-device AI model runs on iPhone 17 Pro."
DRAFT = "Apple Intelligence iOS 27'de geliyor. En güçlü model iPhone 17 Pro'da."


def _run_gate_with(arbiter_result, t0=(True, ["apple intelligence"]),
                   t1=(False, 1.0, [], 0.0)):
    """run_faithfulness_gate'i tier0/tier1/tier2/arbiter stub'larıyla çalıştır."""
    async def fake_arbiter(draft, src, violations):
        return arbiter_result

    async def fake_t1(draft, src, *, claim_grounding_floor=0.9):
        return t1

    async def fake_t2(draft, src):
        return (False, "SKIPPED", [], 0.0)

    with patch.object(fg, "tier0_entity_grounding", return_value=t0), \
         patch.object(fg, "tier1_claim_entailment", side_effect=fake_t1), \
         patch.object(fg, "tier2_thesis_judge", side_effect=fake_t2), \
         patch.object(fg, "arbiter_review", side_effect=fake_arbiter):
        return asyncio.run(fg.run_faithfulness_gate(
            draft_text=DRAFT, source_raw_content=SOURCE,
        ))


def test_arbiter_fp_overrules_block():
    v = _run_gate_with((
        "fp",
        [{"item": "kaynakta geçmeyen unsur: apple intelligence",
          "class": "fp", "why": "kaynakta çeviri karşılığı var"}],
        0.002,
    ))
    assert v.overall == "PASS"
    assert "ARBITER_FP_OVERRULE" in v.reasoning


def test_arbiter_minor_passes_with_note():
    v = _run_gate_with((
        "minor",
        [{"item": "kaynakta geçmeyen unsur: apple intelligence",
          "class": "minor", "why": "zararsız parafraz"}],
        0.002,
    ))
    assert v.overall == "PASS"
    assert "ARBITER_MINOR_PASS" in v.reasoning


def test_arbiter_fabrication_keeps_block_and_filters():
    v = _run_gate_with(
        (
            "fabrication",
            [{"item": "kaynakta geçmeyen unsur: apple intelligence",
              "class": "fabrication", "why": "kaynakta yok"},
             {"item": "kaynakta geçmeyen unsur: ios 27",
              "class": "fp", "why": "kaynakta var"}],
            0.002,
        ),
        t0=(True, ["apple intelligence", "ios 27"]),
    )
    assert v.overall == "HARD_BLOCK"
    # fp olan kalem filtrelendi, yalnız onaylanmış fabrication kaldı
    assert v.tier0_entities_missing == ["apple intelligence"]
    assert "ARBITER_CONFIRMED_FABRICATION" in v.reasoning


def test_arbiter_error_fails_closed():
    v = _run_gate_with(("error", [], 0.0))
    assert v.overall == "HARD_BLOCK"
    assert "ARBITER_ERROR" in v.reasoning


def test_kill_switch_disables_arbiter():
    os.environ["FAITHFULNESS_ARBITER_DISABLED"] = "1"
    try:
        async def boom(*a, **k):
            raise AssertionError("arbiter çağrılmamalıydı")
        async def fake_t1(draft, src, *, claim_grounding_floor=0.9):
            return (False, 1.0, [], 0.0)
        async def fake_t2(draft, src):
            return (False, "SKIPPED", [], 0.0)
        with patch.object(fg, "tier0_entity_grounding",
                          return_value=(True, ["x"])), \
             patch.object(fg, "tier1_claim_entailment", side_effect=fake_t1), \
             patch.object(fg, "tier2_thesis_judge", side_effect=fake_t2), \
             patch.object(fg, "arbiter_review", side_effect=boom):
            v = asyncio.run(fg.run_faithfulness_gate(
                draft_text=DRAFT, source_raw_content=SOURCE,
            ))
        assert v.overall == "HARD_BLOCK"
        assert "ARBITER" not in v.reasoning
    finally:
        del os.environ["FAITHFULNESS_ARBITER_DISABLED"]
