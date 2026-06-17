# Faithfulness Gate — Baseline Report

- Total cases: **225**
- Fabrication: 58 | Overreach: 6 | Grounded: 161

## Headline metrics

| Metric | Value | Target | Meets? |
|---|---|---|---|
| Fabrication recall | **1.0000** | ≥ 0.95 | ✅ |
| Fabrication precision | **0.8788** | ≥ 0.85 | ✅ |
| False-positive rate (grounded blocked) | **0.0124** | ≤ 0.05 | ✅ |
| Tier-0 entity-recall | **0.9821** (55/56) | = 1.00 | ❌ |

- Total cost: **$0.613**  (0.00272/case)
- Avg latency: **6133.1 ms/case**

## Gold-25 per-case (Phase 0 audit)

| id | label | blocked? | correct? | T0 | T1 | T2 | reasoning |
|---|---|---|---|---|---|---|---|
| gold-01-starlink-fabrication | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['starlink'] \| Tier 1: claim grounding ratio 0.50 below floor 0.9; ungrounded: ['asıl hikaye Starlin |
| gold-02-recursive-self-improvement-contradiction | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['opus'] \| Tier 1: claim grounding ratio 0.00 below floor 0.9; ungrounded: ["Anthropic'in son Opus g |
| gold-03-cve-fabrication | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['cve-2026-48095', 'cve-2026-48095'] \| Tier 1: claim grounding ratio 0.50 below floor 0.9; ungrounde |
| gold-04-llama3-injection | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['llama', 'llama 3'] \| Tier 1: claim grounding ratio 0.50 below floor 0.9; ungrounded: ["Llama 3'ün  |
| gold-05-iphone-battery-number | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['__pct_23__'] \| Tier 1: claim grounding ratio 0.00 below floor 0.9; ungrounded: ['iPhone 18 Pro %23 |
| gold-06-spacex-ipo-overstate | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['tesla', '__usd_850__'] \| Tier 1: claim grounding ratio 0.33 below floor 0.9; ungrounded: ['Şirket  |
| gold-07-mythos-benchmark-fabrication | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['mmlu', 'swe-bench verified', '__pct_78.3__', 'mmlu', 'swe-bench'] \| Tier 1: claim grounding ratio  |
| gold-08-google-deepmind-substitution | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['alphafold', 'crispr'] \| Tier 1: claim grounding ratio 0.00 below floor 0.9; ungrounded: ["Google D |
| gold-09-meta-limitless-acquisition-date | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['__num_100000000__', '__usd_1__'] \| Tier 1: claim grounding ratio 0.00 below floor 0.9; ungrounded: |
| gold-10-gemini-quota-numeric | fabrication | YES | ✅ | . | B | . | Tier 1: claim grounding ratio 0.00 below floor 0.9; ungrounded: ["Gemini ücretsiz kotası 50'den 200 mesaj/güne çıktı. → Kaynak metin kullanı |
| gold-11-starship-orbit-fabrication | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['starlink'] \| Tier 1: claim grounding ratio 0.50 below floor 0.9; ungrounded: ['250 km yörüngede St |
| gold-12-claude-opus-speedup-attribution | fabrication | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['nvidia', '__mult_8__', 'h200'] \| Tier 1: claim grounding ratio 0.00 below floor 0.9; ungrounded: [ |
| gold-13-meta-ai-asistan-overreach | overreach | YES | ✅ | B | . | . | Tier 0: ungrounded entities/specifics: ['dashboard'] |
| gold-14-reels-series-overreach | overreach | YES | ✅ | B | . | . | Tier 0: ungrounded entities/specifics: ['youtube'] |
| gold-15-mythos-overreach | overreach | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['__pct_40__'] \| Tier 1: claim grounding ratio 0.00 below floor 0.9; ungrounded: ["Claude Mythos güv |
| gold-16-singapore-overreach | overreach | YES | ✅ | . | . | B | Tier 2: fabricated thesis(es) detected: ["ASEAN'ın AI başkenti seçimi", "Çin'in bölgedeki AI etkisine karşı doğrudan bir blok kurma hamlesi" |
| gold-17-synthid-overreach | overreach | YES | ✅ | . | B | . | Tier 1: claim grounding ratio 0.00 below floor 0.9; ungrounded: ["Google bu watermark'la sektörün de-facto standardını kurdu. → Kaynak metin |
| gold-18-ad-formats-overreach | overreach | YES | ✅ | B | B | . | Tier 0: ungrounded entities/specifics: ['ai overview', 'google', '__usd_200000000000__'] \| Tier 1: claim grounding ratio 0.50 below floor 0 |
| gold-19-opus48-grounded | grounded | no | ✅ | . | . | . | All tiers PASS |
| gold-20-google-spacex-grounded | grounded | no | ✅ | . | . | . | All tiers PASS |
| gold-21-meta-ai-bot-grounded | grounded | no | ✅ | . | . | . | All tiers PASS |
| gold-22-iphone-battery-grounded | grounded | no | ✅ | . | . | . | All tiers PASS |
| gold-23-spacex-ipo-grounded | grounded | no | ✅ | . | . | . | All tiers PASS |
| gold-24-recursive-self-improvement-grounded | grounded | no | ✅ | . | . | . | All tiers PASS |
| gold-25-singapore-grounded | grounded | no | ✅ | . | . | . | All tiers PASS |
| gold-26-apple-intelligence-vs-gemini-substitution | fabrication | YES | ✅ | . | . | B | Tier 2: fabricated thesis(es) detected: ['evdeki agent arayüzü alanını kapatma savaşı'] |
| gold-27-meta-ai-hashtag-concat | grounded | no | ✅ | . | . | . | All tiers PASS |

## False negatives (0)  — fabrications/overreaches the gate MISSED

(none)

## False positives (2)  — grounded drafts the gate WRONGLY blocked

| id | category | T0 missing | T1 ratio | T2 angles | reasoning |
|---|---|---|---|---|---|
| hp-049-suffix_spacex-src-spacex-ipo | synthetic_positive_suffix_spacex | [] | 1.0 | ["SpaceX'in halka açıldığı (IPO/going public) iddiası kaynakta doğrulanmıyor; kaynak sadece hisse fiyatının belirlendiği bir ikincil satışı ifade ediyor."] | Tier 2: fabricated thesis(es) detected: ["SpaceX'in halka açıldığı (IPO/going public) iddiası kaynakta doğrulanmıyor; kaynak sadece hisse fi |
| hp-107-strong_opinion_on_grounded-src-spacex-ipo | synthetic_positive_strong_opinion_on_grounded | [] | 1.0 | ['geliştirici tarafında pratik etki var'] | Tier 2: fabricated thesis(es) detected: ['geliştirici tarafında pratik etki var'] |
