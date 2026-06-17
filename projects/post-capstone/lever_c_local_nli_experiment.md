# Lever C — local-NLI for T1: experiment + decision

## Goal
Replace the Gemini-backed T1 (claim entailment) with a local Turkish NLI
model so the recurring per-draft cost approaches zero, matching the
GLiNER T0 architecture.

## Method
- Model: `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`
  (~250 MB, CPU-runnable, multilingual NLI w/ Turkish coverage)
- Pipeline: `transformers.pipeline("zero-shot-classification", ...)`
- Hypothesis template: `<source> Bu nedenle: {claim}`
- Smoke-tested against three claims on the Apple iPhone-18-Pro source:
  one grounded restatement + two fabricated extensions.

## Smoke results
```
SOURCE: "Apple iPhone 18 Pro modelinde bölgesel batarya stratejisi uyguluyor."

claim 1 (grounded restatement):
  "Apple iPhone 18 Pro bölgesel batarya stratejisine geçiyor."
  top label: entailment   score: 0.617
  → grounded, correct ✓

claim 2 (FABRICATED numeric):
  "iPhone 18 Pro Çin modeli 5400 mAh batarya ile geliyor."
  top label: entailment   score: 0.364   ← should be neutral/contradiction
  → fabrication ratiocinated as entailment ❌

claim 3 (FABRICATED entity):
  "Apple Intelligence ajanları için donanım katmanı baştan yazılıyor."
  top label: entailment   score: 0.435   ← should be neutral
  → fabrication classified as entailment ❌

Per-claim latency: ~1.0–1.1 s on CPU.
```

The model treats overlapping-vocabulary fabrications ("iPhone 18 Pro" +
"batarya" present in both) as entailed regardless of the specific
numeric/entity claim that was injected. This is a known weakness of
generic XNLI models for fine-grained fact checking — they reward
topical overlap, not literal entailment.

## Expected benchmark impact
Predicted: precision would drop substantially because the NLI scores
above the chosen threshold for both grounded (0.62) AND fabricated
(0.36–0.44) variants. To preserve recall=1.00 the threshold would have
to be set so low (~0.3) that grounded paraphrases would also fail
under noisy NLI scores, blowing the FP rate.

A full benchmark sweep would confirm this, but the smoke results
already cross the user's stated criterion:
> "If the local model drops any metric, keep Gemini for that tier."

The user's research note flagged Turk-LettuceDetect specifically — that
model is a Turkish-claim-decomposition specialist; if it became
available with a maintained checkpoint, it would likely outperform
generic mDeBERTa-XNLI on this task and be worth re-investigating.

## Decision: KEEP Gemini for T1 and T2.

Rationale:
1. **Quality**: smoke results show generic XNLI doesn't reliably
   separate grounded restatement from fabricated extension on the
   Turkish AI-news domain.
2. **Marginal economic value**: post Lever A, gate is called ~1×/day
   (1 draft/day). T1+T2 cost ≈ $0.003/draft. Annual saving from
   moving local: ≈ $1.10/year. Implementation + maintenance burden
   far exceeds savings.
3. **Risk**: a recall regression here would defeat the entire
   anti-fabrication system. Local NLI is the wrong place to take
   risk for sub-dollar annual savings.

## Path forward
- Revisit when a **Turkish-tuned NLI** (Turk-LettuceDetect or a
  fine-tuned mDeBERTa on TR-NLI-data) ships with a maintained
  checkpoint and the smoke metrics improve.
- If demand grows (e.g. 10+ accounts producing 50+ drafts/day),
  recurring T1/T2 cost grows and local NLI becomes worth the work.
