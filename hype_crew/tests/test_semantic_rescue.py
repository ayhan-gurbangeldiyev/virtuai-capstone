"""A2 — semantic_rescue unit smoke.

Run: cd /opt/hype-crew && venv/bin/python tests/test_semantic_rescue.py

Verifies the two anchor cases Berkay called out:
  - "botlar insanları geçti" → rescued
  - "iPhone 18 batarya" → still rejected

Plus the persona-gate integration: an L4-ambiguous trend with AI-adjacent
text comes back as `persona_gate=semantic_rescue` (not `ambiguous`).
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Allow running directly OR via pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.semantic_rescue import evaluate_semantic_rescue  # noqa: E402
from tools.persona_gate import evaluate_persona_gate         # noqa: E402


EMPTY_CONFIG = {
    "blocked_keywords": [],
    "positive_ai_signals": [],
    "tier_1_brands": [],
    "conditional_brands": {},
}


def _check(name: str, cond: bool, detail: str = "") -> bool:
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}{(' — ' + detail) if detail else ''}")
    return cond


def main() -> int:
    print("\n=== semantic_rescue direct smoke ===")
    ok = True

    r1 = evaluate_semantic_rescue(
        topic="Internet trafiğinde botlar insanları geçti",
        raw_content="Otomatik bot trafiği insanları geçti, web trafiğinin yarısından fazlası bot.",
    )
    ok &= _check(
        "bot traffic story is RESCUED",
        r1.rescued and r1.score >= 0.55,
        f"score={r1.score:.3f} threshold={r1.threshold}",
    )

    r2 = evaluate_semantic_rescue(
        topic="iPhone 18 batarya kapasitesi sızdırıldı",
        raw_content="Yeni iPhone'un batarya kapasitesi 3700 mAh olacak, Geekbench skoru paylaşıldı.",
    )
    ok &= _check(
        "iPhone battery noise is NOT rescued",
        not r2.rescued and r2.score < 0.55,
        f"score={r2.score:.3f}",
    )

    r3 = evaluate_semantic_rescue(
        topic="Galatasaray Fenerbahçe derbisi sonuçlandı",
        raw_content="Derbi maçında Galatasaray 2-1 kazandı, taraftarlar coşkulu.",
    )
    ok &= _check(
        "sports noise is NOT rescued",
        not r3.rescued,
        f"score={r3.score:.3f}",
    )

    print("\n=== persona_gate L4 integration ===")
    # L4 routes through semantic_rescue.
    d_rescue = evaluate_persona_gate(
        topic="Internet trafiğinde botlar insanları geçti",
        raw_content="Bot trafiği insanları geçti.",
        category="News",
        config=EMPTY_CONFIG,
    )
    ok &= _check(
        "bot-story persona_gate == 'semantic_rescue'",
        d_rescue.persona_gate == "semantic_rescue" and d_rescue.passed,
        f"persona_gate={d_rescue.persona_gate} decision={d_rescue.decision}",
    )

    d_noise = evaluate_persona_gate(
        topic="iPhone 18 batarya kapasitesi sızdırıldı",
        raw_content="Yeni iPhone 3700 mAh.",
        category="News",
        config=EMPTY_CONFIG,
    )
    ok &= _check(
        "iPhone-noise persona_gate == 'ambiguous' (still rejected)",
        d_noise.persona_gate == "ambiguous" and not d_noise.passed,
        f"persona_gate={d_noise.persona_gate}",
    )

    print("\n=== summary ===")
    print(f"  {'ALL TESTS PASSED' if ok else 'SOME TESTS FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
