"""Gate parity test — one grounded + one fabricated draft through the
hype-crew faithfulness gate (tier0 entity grounding).

Backend's /approve route delegates to the same faithfulness_gate module
(it imports tools.faithfulness_gate from /opt/hype-crew). If both
interpreters can import gliner and the module is identical, both should
produce identical verdicts for the same input.

NO publish. NO DB writes. Pure function evaluation.
"""
import os, sys, json
sys.path.insert(0, "/opt/hype-crew")

from tools.faithfulness_gate import tier0_entity_grounding

# Source URL + extracted "trend_topic" + the draft body to score.
GROUNDED = {
    "label": "GROUNDED",
    "source_url": "https://x.com/OpenAI/status/2062653758178549798",
    "trend_topic": "OpenAI announces ChatGPT memory improvements",
    "raw_signal": (
        "OpenAI's ChatGPT now has improved memory. The system remembers user "
        "preferences across conversations using a new memory system. "
        "Kullanıcı tercihlerini ChatGPT artık daha iyi hatırlıyor."
    ),
    "content": (
        "OpenAI bugün ChatGPT'nin hafıza sistemine yeni güncelleme getirdi."
    ),
}
FABRICATED = {
    "label": "FABRICATED",
    "source_url": "https://x.com/OpenAI/status/2062653758178549798",
    "trend_topic": "OpenAI announces ChatGPT memory improvements",
    "raw_signal": "OpenAI's ChatGPT can now better remember user preferences across conversations using a new memory system.",
    "content": (
        "Microsoft bugün Anthropic ile birlikte yeni bir kuantum bilgisayar "
        "geliştirdiğini duyurdu. Cihaz, ChatGPT'nin yerini alacak ve "
        "Google'ın yapay zeka birimini satın alacak."
    ),
}


def run(case):
    print(f"\n=== {case['label']} ===")
    print(f"content:    {case['content'][:120]}…")
    blocked, missing = tier0_entity_grounding(
        draft_text=case["content"],
        source_raw_content=case["raw_signal"],
        source_url=case["source_url"],
    )
    print(f"  blocked          = {blocked}")
    print(f"  hallucinated_set = {missing}")
    return {
        "label": case["label"],
        "blocked": blocked,
        "hallucinated": list(missing),
    }


verdicts = [run(GROUNDED), run(FABRICATED)]
print("\n=== SUMMARY ===")
print(json.dumps(verdicts, indent=2, ensure_ascii=False, default=str))

# Assert the parity contract
assert verdicts[0]["blocked"] is False, f"GROUNDED must PASS, got blocked={verdicts[0]['blocked']}"
assert verdicts[1]["blocked"] is True,  f"FABRICATED must BLOCK, got blocked={verdicts[1]['blocked']}"
print("\n✅ Parity assertion: GROUNDED→PASS, FABRICATED→BLOCK")
