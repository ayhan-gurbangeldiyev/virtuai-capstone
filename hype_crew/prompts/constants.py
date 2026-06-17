"""Shared prompt constants — hard rules, formatting rules, hook types.

These are embedded into agent backstories and enforced by guardrails.
"""

HARD_RULES = """
HARD RULES (non-negotiable, violation = automatic rejection):

1. Never draft without consulting memory first (voice_examples, approved_drafts, rejected_drafts).
2. Never repeat an angle that appears in rejected-drafts memory.
3. Always reference real stories, real numbers, or real experiences — never invent stats or claims.
4. No em dashes in any output, ever. Use commas, periods, or line breaks.
5. Every reactive draft must answer "what can I actually do with this?" (practical value).
6. Output is written to be read aloud — if it sounds stiff or generic, rewrite it.
7. Never produce content on forbidden topics (politics, health advice, financial advice unless user opts in).
8. Respect the creator's voice description literally — match tone, casing, rhythm.
""".strip()


FORMATTING_RULES = """
FORMATTING RULES:

- Max 1-2 short sentences per line block.
- Blank line between every thought (use \\n\\n).
- Max 12 words per line (guide, not hard limit).
- If it looks like a paragraph, break it up.
- No em dashes (—). Use commas, periods, or line breaks only.
- Avoid corporate language: "leverage", "exciting", "game-changing", "synergy",
  "unlock potential", "in the era of", "in today's fast-paced", "deep dive",
  "moving forward", "circle back", "low-hanging fruit", "robust", "scalable solution".
- Capitalization: follow the creator's authentic style (from style profile
  or brand voice). Do NOT default to all-lowercase — sentence case is the
  norm unless the creator's fingerprint says otherwise.
- Tweet max length: schema allows up to 4000 (X Premium long-form); shorter
  is usually better for engagement.
""".strip()


HOOK_TYPES = """
HOOK STYLES (pick one that fits the angle):

- curiosity: "most people miss this..." / "nobody talks about..."
- first-person: "I shipped X and learned Y..." / "I just tested..."
- result: "my agent did X in 2 weeks..." / "this saved me 4 hours..."
- contrast: "everyone says X. here's why that's wrong..." / "the obvious move is X. the better move is Y."
- question: "what if we built X differently?" / "what's the cheapest version of X that still works?"
- story: "a year ago I tried X. today..." / "last week a user asked me..."
""".strip()


MEMORY_PROTOCOL = """
MEMORY PROTOCOL (System 8 — Learning Loop, runs silently before drafting):

Before producing any output, you receive memory context with these sections:

1. VOICE EXAMPLES — the creator's authentic past tweets (match tone, rhythm, phrasing).
2. APPROVED DRAFTS — recently approved content (do more of this kind).
3. REJECTED DRAFTS — recently rejected + reason (NEVER repeat these angles or formats).
4. RECENT PERFORMANCE — engagement signals (weight toward what worked).

Rules:
- Skip producing output if the angle/hook is similar to anything in REJECTED DRAFTS.
- Prefer formats and phrasings that appear in VOICE EXAMPLES + APPROVED DRAFTS.
- If memory is empty (first runs), fall back to creator's voice_description from config.
""".strip()
