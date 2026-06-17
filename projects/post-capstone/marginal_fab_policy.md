# Marginal-fab policy decision

## The cases
Two shadow-backfill rows surfaced as "borderline external-fact import":

- **FN-9 Meta Limitless + "Ray-Ban başarısından sonra"** — source is about
  Meta's Limitless wearables; the draft references Ray-Ban Meta as
  established context. Ray-Ban Meta is a real Meta product line, but
  source doesn't mention it.
- **FN-10 Google sivrisinek + "Verily aracılığıyla"** — source attributes
  the mosquito project to "Google". The actual operator is Verily,
  Alphabet's life-sciences subsidiary. World-fact true but source
  doesn't mention Verily.

## Policy: **strict — block.**

Both cases get BLOCKED. The whole point of the faithfulness gate is
"every claim must be supported by the source." Allowing external
world-facts opens the door to "but it's true!" justification, which is
exactly how the Phase-0 leak happened (the writer "knew" Starlink was
a SpaceX product line and silently injected it).

The hard rule is: **if the operator wants to credit Verily / mention
Ray-Ban Stories, the SOURCE has to mention them.** Otherwise it's
external-fact injection. The faithfulness layer doesn't care if the
external fact is correct; it cares whether it is sourced.

The only carve-out we accept is the COMPARISON CONTEXT (Meta Ray-Ban
referenced as a competitor in a contrast clause — FP-7) because the
draft is making a claim about Apple (the in-source subject), not about
Meta. Adding "Meta did X" in a contrast clause doesn't assert a fact
about Meta; it just establishes context for the Apple claim.

## Implementation
- T0 GLiNER extractor + canonicalize + fuzzy match (`token_set_ratio ≥
  85`). Missing entity → BLOCK.
- Comparison-context allowance (`_is_comparator_context` in
  `tools/faithfulness_gate.py`) covers FP-7 ONLY when the missing entity
  appears in a Turkish comparison clause (`X-ile-Y-mişken`, `X gibi`,
  `X karşısında`, `X başarısından sonra`, etc.).
- Verily / Ray-Ban / AlphaFold are added to the curated alias map so
  they're recognized when they DO appear in source (and so the alias
  map normalizes them to canonical). Not adding them as "always-allowed
  fabrications".
- Marginal-fab shadow rows continue to be tagged `marginal_fab` in the
  backfill audit, but the gate's behavior is to BLOCK them in
  production. The audit-tag was descriptive, not a policy carve-out.

## Operator workflow
When the gate blocks a marginal-fab case, the operator sees the
ungrounded entity in the verdict reasoning. If they want to keep the
external attribution, they edit the source citation OR remove the
external entity. They never override the gate without a source change.

## Why not allow Verily=Google specifically?
Because the gate already handles the Google→Google relationship via
product→maker (`_PRODUCT_TO_MAKER`). If a source says "Verily", drafts
can say "Google" (and vice-versa via maker→product). But if source
only says "Google", drafts can't say "Verily" — there's no way to
guarantee correctness of subsidiary-level attribution from a coarse
"Google" source.
