# Faithfulness gate diagnosis — Perplexity draft `a8bac287`

**Date:** 2026-06-07
**Verdict:** **C2 — gate over-blocks genuinely-grounded content.**
**Recommendation:** tune the gate. Do NOT change fail-closed behavior.

---

## Source vs draft (raw, side-by-side)

**Source `raw_content`** (from `trends.raw_content` for trend
`ba4451ff…`, posted by `@perplexity_ai`):

> Today we're launching the **Main Street AI Accelerator** with the
> **U.S. Small Business Administration**. We're committing **$25M** in
> Computer credits, **$250 each** for up to **100,000 eligible
> companies**, in honor of America's **250th anniversary**.

**Draft content** (`a8bac287`, twitter, status=pending_review):

> Küçük bir işletme sahibi **SBA** ile masaya oturduğunda artık sadece
> kredi değil, teknoloji de talep ediyor. **Perplexity**'nin
> Amerika'nın **250. yılı** şerefine **100 bin** şirkete **250'şer
> dolarlık** kredi dağıtması tam olarak bu değişimin sahaya yansıması.

## Per-entity audit (what the gate flagged as `tier0_blocked`)

| Entity flagged | In source? | Why gate missed it |
|---|---|---|
| `perplexity` | Author handle `@perplexity_ai` in source URL; brand verbatim NOT in source text. | `_URL_ACCOUNT_TO_ENTITY` dict ([faithfulness_gate.py:297](hype_crew/tools/faithfulness_gate.py#L297)) does NOT contain `"perplexity_ai"`. Probe confirmed: `_entities_from_url("https://x.com/perplexity_ai/...")` returns `set()`. |
| `sba` | "Small Business Administration" verbatim in source. | No acronym alias `sba ↔ small business administration` in the curated alias map. |
| `__num_100000__` | "100,000" verbatim in source. | `_canonicalize_numerics` is asymmetric. Source's `"100,000"` stays as `"100,000"` (the comma defeats the canonicalizer). Draft's `"100 bin"` becomes `__NUM_100000__`. Two different tokens for the same number → no match. |

### Direct probe (run on prod)

```
_entities_from_url("https://x.com/perplexity_ai/status/...") → set()       ← BUG
canonical numerics (source) : "...for up to 100,000 eligible..."           ← unnormalized
canonical numerics (draft)  : "... __NUM_100000__ şirkete 250'şer..."      ← normalized
```

## Verdict

**The writer is faithful.** Every "fact" in the draft is supportable
by the source:
- "Perplexity" — source URL author + the @perplexity_ai handle is the
  speaker
- "SBA" — the well-known acronym for "U.S. Small Business
  Administration" which IS in the source verbatim
- "100 bin şirkete 250'şer dolarlık" — directly maps to source's
  "$250 each for up to 100,000 eligible companies"
- "Amerika'nın 250. yılı" — directly maps to "America's 250th
  anniversary"

**The gate is over-strict on three specific patterns** unrelated to
the writer:

1. **URL-author-as-entity is incomplete**: the new STAGE 1 sources
   (`perplexity_ai`, `sama`, `mistralai`, `karpathy`, `levelsio`,
   `jeremyphoward`, `hardmaru`) are not in `_URL_ACCOUNT_TO_ENTITY`.
   Any draft sourced from these accounts will FP-block on the brand
   even when the brand IS the entity speaking.

2. **Acronym alias gap**: well-known agency acronyms (`SBA`, `NIST`,
   `EU AI Act` → `European Union AI Act`, `FDA`, `FTC`, etc.) aren't
   mapped. News content uses acronyms freely.

3. **Numeric canonicalization asymmetric**: source-side numbers with
   thousand separators (`100,000`, `25,000`) don't normalize the same
   way draft-side `"100 bin"` / `"25 bin"` does. Cross-language matches
   fail.

## Recommended tuning (NOT applied — diagnosis only per scope)

1. **Add the STAGE 1 sources to `_URL_ACCOUNT_TO_ENTITY`**:
   ```python
   "perplexity_ai":   "perplexity",
   "sama":            "openai",
   "mistralai":       "mistral",
   "karpathy":        "anthropic",   # joined Anthropic 2026-05-19
   "levelsio":        "indie hacker",
   "jeremyphoward":   "fast.ai",
   "hardmaru":        "sakana",
   ```

2. **Extend the curated alias map** with the top-50 common acronyms in
   AI news: SBA, NIST, FTC, FDA, EU AI Act, GDPR, DARPA, NHTSA, NSA,
   CISA, etc.

3. **Make `_canonicalize_numerics` symmetric**:
   - Strip thousand-separators from source-side ("100,000" → "100000")
     before canonicalization
   - Ensure draft-side "100 bin" / "yüz bin" / "100K" all normalize to
     the same token

4. **DO NOT loosen fail-closed**: tier0 stays a hard refuse. The cure
   is reducing FP rate by improving entity recognition, not by relaxing
   the gate.

## Yield impact estimate (back-of-envelope)

The 4 entities/URL-handles missing from the dict cover ~7 of the new
STAGE 1 sources. Until the dict is extended, the editor's-desk will
keep producing drafts that get HARD_BLOCKED at the operator's approve
click because the brand-from-URL grounding fails. Expected publishable
yield from those sources: low until tuned.

## Action items (separate PR)

- Extend `_URL_ACCOUNT_TO_ENTITY` (one-line per source, low risk)
- Extend curated alias map with acronyms (medium effort)
- Fix `_canonicalize_numerics` symmetry (low effort — strip commas
  pre-canonicalize)
- Add a regression test: each of the 7 new sources' URLs returns the
  expected entity from `_entities_from_url`.
