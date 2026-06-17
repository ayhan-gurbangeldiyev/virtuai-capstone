# Auto-publish — Graduation Readiness (CORRECTED METHODOLOGY)

**Generated**: 2026-06-06T15:17:52.916770+00:00  
**Window**: shadow + shadow_backfill rows from last 90 days  
**First row**: 2026-06-06T14:32:01.702552+00:00  
**Last row**: 2026-06-06T14:33:18.211657+00:00  
**Days of data**: 0  
**Total verdicts (shadow paths)**: 100  
**Faithfulness-relevant paired rows**: 11  
**Quality/tone rejections excluded**: 68

> **Methodology note**: the previous version used the lax historical operator's `daily_drafts.status` as ground truth. That operator approved fabrications and rejected for tone, so their decisions are NOT a valid gate-accuracy signal. This version uses ONLY rows tagged faithfulness/real_fabrication/marginal_fab/true_fp/lax_approval, and reads the backfill audit's reclassification of approve→lax_approval as the corrected ground truth.

> **The hand-labeled benchmark (`hype_crew/tests/fixtures/faithfulness_benchmark.jsonl`, recall = 1.00 on calibrated cases, FP = 0.00) remains the authoritative gate-accuracy reference.** Shadow rows below are the live-drift signal.

## Corrected confusion matrix (faithfulness-only)

|             | human PASS | human BLOCK |
|-------------|-----------:|------------:|
| gate PASS   | TN = 0       | **FN = 3** |
| gate BLOCK  | FP = 2       | TP = 6 |

- **FN rate**: 0.3333  (of 9 confirmed fabrications, gate missed 3)
- **FP rate**: 1.0000  (of 2 confirmed-grounded drafts, gate wrongly held 2)
- **Cohen's κ**: -0.2791
- **Gate ERROR verdicts (in window)**: 0

## Graduation checklist

| Criterion | Current | Target | OK? |
|---|---:|---:|:--:|
| Days of data | `0` | `30` | ❌ |
| Faithfulness-paired rows | `11` | `50` | ❌ |
| FN count | `3` | `0` | ❌ |
| FP rate | `1.0` | `0.05` | ❌ |
| Cohen's κ | `-0.2791` | `0.8` | ❌ |
| Gate errors | `0` | `0` | ✅ |

## ❌ NOT YET READY  —  keep manual approval ON.

Note: the FN above (if any) is a REAL gate-recall gap; investigate before re-enabling.


## Backfill-audit reclassification (the 25 rows of corrected ground truth)

Source: `projects/post-capstone/shadow_fn_fp_hand_audit.md`

- `lax_approval` (gate caught, operator wrongly approved): 6
- `true_fp`       (gate wrongly blocked grounded content): 2
- `marginal_fab`  (external true-world fact not in source): 2
- `real_fabrication` (gate missed; benchmark regression added): 1
- `quality`       (excluded — operator tone reject, not gate signal): 13