"""End-to-end self-heal demo: fabricating draft → blocked → corrected → re-gated → PASS.

Uses the actual Phase 0 gold-01 case (Google–SpaceX $920M with Starlink
fabrication) and a real gemini-3-flash writer call to produce the
correction. No mocks. Runs against the live FAITHFULNESS_GATE_SECRET
on the deploy host.

Run on Hetzner:
    cd /opt/hype-crew && venv/bin/python scripts/demo_self_heal.py

Expected: 3 attempts at most, healed=True final.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Make tools.* importable from hype_crew root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.guarded_postiz import assert_publishable_with_healing  # type: ignore


# The real Phase 0 audit case
SOURCE_RAW = (
    "Google, artan yapay zeka talebini karşılamak için SpaceX ile aylık "
    "920 milyon dolarlık işlem gücü anlaşması imzaladı."
)
FABRICATING_DRAFT = (
    "Google'ın SpaceX ile $920M aylık anlaşması — asıl hikaye Starlink "
    "üzerinden veri merkezlerine fiziksel uplink kurmak. Bu sadece "
    "compute alımı değil, jeo-stratejik bir hamle."
)
DRAFT_ID = "demo-google-spacex-starlink-fab"


WRITER_SYSTEM = """Sen Cansu Dut adlı persona için Türkçe X postu yazıyorsun.
Üslup: sade, doğrudan, gözlemsel. Maksimum ~280 karakter.
Görüş yazabilirsin; fakat YALNIZCA kaynak metinde geçen entity / sayı / olayı
kullan. Yeni entity uydurma. Sadece taslak metnini ver."""


async def gemini_writer(correction_instruction: str, attempt: int) -> tuple[str, float]:
    """Real gemini-3-flash call. Returns (new_draft, cost_usd)."""
    from openai import AsyncOpenAI                 # type: ignore
    from config import settings                    # type: ignore

    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    temp = max(0.2 - 0.1 * (attempt - 1), 0.05)
    resp = await client.chat.completions.create(
        model="google/gemini-3-flash-preview",
        temperature=temp,
        max_tokens=400,
        messages=[
            {"role": "system", "content": WRITER_SYSTEM},
            {"role": "user", "content": correction_instruction},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    return text, 0.001  # cheap-flash cost approx


async def main() -> None:
    print("=" * 72)
    print("Self-heal demo — Phase 5")
    print("=" * 72)
    print(f"Source raw_content:\n  {SOURCE_RAW}\n")
    print(f"INITIAL fabricating draft:\n  {FABRICATING_DRAFT}\n")
    print("Running assert_publishable_with_healing (max_retries=2, cap=$0.05)...\n")

    result = await assert_publishable_with_healing(
        draft_text=FABRICATING_DRAFT,
        source_raw_content=SOURCE_RAW,
        path="demo",
        draft_id=DRAFT_ID,
        regenerate_callback=gemini_writer,
        max_retries=2,
        cost_cap_usd=0.05,
    )

    for a in result.attempts:
        tag = "INITIAL" if a.iteration == 0 else f"REGEN #{a.iteration}"
        print(f"── {tag} ────────────────────────────────────────────────")
        print(f"  draft       : {a.draft_text[:200]!r}")
        print(f"  verdict     : {a.outcome.verdict}")
        if a.outcome.raw_verdict:
            v = a.outcome.raw_verdict
            print(f"  T0 blocked  : {v.tier0_blocked}  missing={v.tier0_entities_missing}")
            print(f"  T1 blocked  : {v.tier1_blocked}  pass_ratio={v.tier1_claim_pass_ratio}")
            print(f"  T2 blocked  : {v.tier2_blocked}  angles={v.tier2_ungrounded_angles[:2]}")
        print(f"  reasoning   : {a.outcome.reasoning[:160]}")
        print(f"  regen_cost  : ${a.regen_cost_usd:.4f}")
        print(f"  gate_cost   : ${a.gate_cost_usd:.4f}")
        print(f"  elapsed_ms  : {a.elapsed_ms}")
        print(f"  halt_reason : {a.halt_reason}")
        print()

    print("=" * 72)
    print("FINAL")
    print("=" * 72)
    print(f"  healed         : {result.healed}")
    print(f"  halt_reason    : {result.halt_reason}")
    print(f"  final_verdict  : {result.final_outcome.verdict}")
    print(f"  attempts       : {len(result.attempts)}")
    print(f"  total_cost_usd : ${result.total_cost_usd:.4f}")
    print(f"  total_elapsed  : {result.total_elapsed_ms} ms")
    print(f"  final_draft    : {result.final_draft!r}")
    print()
    if result.final_outcome.verdict == "PASS":
        print("✅ SAFE TO PUBLISH — token signed, content_hash bound to draft.")
        print(f"   token[:16]   : {result.final_outcome.token[:16]}…")
    else:
        print("⛔  HOLD AS needs_human — gate refused after retries.")


if __name__ == "__main__":
    asyncio.run(main())
