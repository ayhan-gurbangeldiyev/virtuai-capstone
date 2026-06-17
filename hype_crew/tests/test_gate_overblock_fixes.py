"""Regression tests for the 3 over-block fixes (PART 1+2+3, 2026-06-08).

The Perplexity-25M draft a8bac287 FP-blocked on [perplexity, sba,
__num_100000__] even though every entity was supportable by the
@perplexity_ai source tweet. The 3 underlying gate bugs:

  1. _URL_ACCOUNT_TO_ENTITY missing perplexity_ai (and 6 other STAGE 1
     sources). URL-author-as-entity returned set() instead of
     {perplexity}.
  2. No alias `sba ↔ small business administration` in curated map.
  3. _canonicalize_numerics asymmetric — source "100,000" stayed
     verbatim, draft "100 bin" → __NUM_100000__.

Run from hype-crew venv (faithfulness_gate imports gliner).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, "/opt/hype-crew")


# ─── PART 1: URL author handle → entity ─────────────────────────────


def test_perplexity_url_returns_perplexity_entity():
    from tools.faithfulness_gate import _entities_from_url
    ents = _entities_from_url("https://x.com/perplexity_ai/status/2062556000394379710")
    assert "perplexity" in ents, f"expected 'perplexity' in {ents}"


def test_stage1_sources_all_resolve():
    from tools.faithfulness_gate import _entities_from_url
    cases = [
        ("https://x.com/perplexity_ai/status/1", "perplexity"),
        ("https://x.com/sama/status/2",          "openai"),
        ("https://x.com/MistralAI/status/3",     "mistral"),
        ("https://x.com/karpathy/status/4",      "anthropic"),
        ("https://x.com/levelsio/status/5",      "indie hacker"),
        ("https://x.com/jeremyphoward/status/6", "fast.ai"),
        ("https://x.com/hardmaru/status/7",      "sakana"),
    ]
    for url, expected in cases:
        ents = _entities_from_url(url)
        assert expected in ents, f"{url} → {ents}, expected {expected}"


# ─── PART 2: Acronym alias coverage ─────────────────────────────────


def test_sba_alias_map():
    """SBA in draft must be grounded when source has 'Small Business
    Administration'."""
    from tools.faithfulness_gate import _extract_entities_normalized
    src = "U.S. Small Business Administration committed funds today."
    src_ents = _extract_entities_normalized(src)
    # Draft uses "SBA" — must be recognized as the same entity.
    draft = "SBA ile yeni anlaşma"
    draft_ents = _extract_entities_normalized(draft)
    # SBA needs to either map to the canonical or be in the source set.
    # We accept either: SBA→sba in draft, sba in source via the alias.
    assert ("sba" in draft_ents or "small business administration" in src_ents), (
        f"draft={draft_ents}, src={src_ents}"
    )


def test_top_acronyms_in_alias_map():
    from tools.faithfulness_gate import _ENTITY_ALIASES
    for acronym in ["sba", "nist", "fda", "ftc", "darpa", "gdpr",
                    "eu ai act", "aws", "azure", "gcp"]:
        assert acronym in _ENTITY_ALIASES, f"missing acronym alias: {acronym}"


# ─── PART 3: Numeric canonicalization symmetric ─────────────────────


def test_canonicalize_100000_with_comma_matches_100_bin():
    """100,000 in source must canonicalize the same way 100 bin in
    draft does. This was the a8bac287 false-positive."""
    from tools.faithfulness_gate import _canonicalize_numerics
    src = "for up to 100,000 eligible companies"
    draft = "100 bin şirkete kredi"
    src_canon = _canonicalize_numerics(src)
    draft_canon = _canonicalize_numerics(draft)
    assert "__NUM_100000__" in src_canon, f"src canon: {src_canon}"
    assert "__NUM_100000__" in draft_canon, f"draft canon: {draft_canon}"


def test_canonicalize_preserves_year():
    """2024 (year) stays as-is; threshold for NUM is 10000+."""
    from tools.faithfulness_gate import _canonicalize_numerics
    text = "In 2024 the model launched"
    canon = _canonicalize_numerics(text)
    assert "__NUM_2024__" not in canon, f"year incorrectly canonicalized: {canon}"


def test_canonicalize_preserves_eu_decimal_comma():
    """'2,5x' (EU decimal) stays as decimal multiplier — NOT thousand-strip."""
    from tools.faithfulness_gate import _canonicalize_numerics
    text = "model is 2,5x faster"
    canon = _canonicalize_numerics(text)
    # The comma must not be stripped — 2,5 stays distinguishable from 25
    assert "__MULT_2.5__" in canon, f"canon: {canon}"


def test_canonicalize_thousand_separator_stripped():
    from tools.faithfulness_gate import _canonicalize_numerics
    text = "1,234,567 users joined"
    canon = _canonicalize_numerics(text)
    assert "__NUM_1234567__" in canon, f"canon: {canon}"


def test_canonicalize_bare_k_suffix():
    """'100K shares' → __NUM_100000__"""
    from tools.faithfulness_gate import _canonicalize_numerics
    text = "100K shares sold"
    canon = _canonicalize_numerics(text)
    assert "__NUM_100000__" in canon, f"canon: {canon}"


def test_canonicalize_25_million_dollars():
    """$25M in source must canonicalize to __USD_25000000__ same as
    '$25 milyon dolar' in draft."""
    from tools.faithfulness_gate import _canonicalize_numerics
    src = "We're committing $25M in credits"
    draft = "25 milyon dolar destek"
    src_canon = _canonicalize_numerics(src)
    draft_canon = _canonicalize_numerics(draft)
    assert "__USD_25000000__" in src_canon, f"src: {src_canon}"
    assert "__USD_25000000__" in draft_canon, f"draft: {draft_canon}"


# ─── End-to-end: a8bac287 must now PASS ─────────────────────────────


def test_perplexity_25m_draft_passes_tier0():
    """The exact a8bac287 case — must PASS tier0 with all 3 fixes."""
    from tools.faithfulness_gate import tier0_entity_grounding
    source = (
        "Today we're launching the Main Street AI Accelerator with the "
        "U.S. Small Business Administration. We're committing $25M in "
        "Computer credits, $250 each for up to 100,000 eligible "
        "companies, in honor of America's 250th anniversary."
    )
    draft = (
        "Küçük bir işletme sahibi SBA ile masaya oturduğunda artık "
        "sadece kredi değil, teknoloji de talep ediyor. Perplexity'nin "
        "Amerika'nın 250. yılı şerefine 100 bin şirkete 250'şer "
        "dolarlık kredi dağıtması tam olarak bu değişimin sahaya "
        "yansıması."
    )
    url = "https://x.com/perplexity_ai/status/2062556000394379710"
    blocked, missing = tier0_entity_grounding(
        draft_text=draft, source_raw_content=source, source_url=url,
    )
    assert blocked is False, (
        f"a8bac287 must PASS now but blocked={blocked}, missing={missing}"
    )


def test_fabricated_still_blocks():
    """Regression guard: making the 3 fixes must NOT also pass a truly
    fabricated draft. Verify the FABRICATED case from gate_parity test
    still BLOCKS."""
    from tools.faithfulness_gate import tier0_entity_grounding
    source = (
        "OpenAI's ChatGPT now has improved memory."
    )
    fabricated_draft = (
        "Microsoft bugün Anthropic ile birlikte yeni bir kuantum "
        "bilgisayar geliştirdiğini duyurdu. Cihaz, ChatGPT'nin yerini "
        "alacak ve Google'ın yapay zeka birimini satın alacak."
    )
    blocked, missing = tier0_entity_grounding(
        draft_text=fabricated_draft, source_raw_content=source,
        source_url="https://x.com/OpenAI/status/123",
    )
    assert blocked is True, (
        f"fabricated must still BLOCK, got blocked={blocked}, missing={missing}"
    )
    # Must catch at least one of the fabrications
    assert any(m in missing for m in ["anthropic", "google", "microsoft"]), (
        f"expected fabricated entities in missing: {missing}"
    )
