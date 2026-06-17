# Shadow scoreboard — hand audit of the 17 FN + 8 FP

The naïve scoreboard treated `daily_drafts.status` as ground-truth for the
human label. That operator was the lax operator who let the 52 % fabrication
leak through — so the backfill confusion matrix is structurally invalid as
a graduation signal.

This file is the hand-audit that splits each case by what actually happened.

---

## 8 false-positives  (gate BLOCK, "human approved")

| # | draft_id | gate-flagged thing | actual classification | rationale |
|---|---|---|---|---|
| FP-1 | `91e1ffe7` | T0: `llama` not in source | **LAX_APPROVAL** | Source: Meta's new AI assistant in IG/WA. Draft: "Llama 3 ile otomasyon katmanına çevirmesi" — Llama 3 NOT in source. The Phase-0 Llama-3 fabrication exactly. Gate correctly caught; lax operator approved. |
| FP-2 | `62490262` | T1: `ucuzladı` claim ungrounded | **LAX_APPROVAL** | Source: Codex plugins expanded. Draft adds "OpenAI'ın yeni kaldıraçla çok ucuzladı" — source doesn't claim cost change. Gate correctly caught added cost claim. |
| FP-3 | `de7f6c6c` | T1: "prompt injection" technical inference | **LAX_APPROVAL (borderline)** | Source describes verification-code-misroute; draft calls it "Prompt injection açığı" — a specific technical attribution the source doesn't make. Technically the attack vector IS prompt-injection-style; gate's strictness was correct. |
| FP-4 | `19962d2e` | T1: "mod yapımcıları vs milyon dolarlık stüdyolar" framing | **LAX_APPROVAL** | Source: GTA 5 Turkey atmosphere. Draft introduces "mod makers vs million-dollar studios" framing not in source. Gate correctly caught extrapolation. |
| FP-5 | `3d3daec9` | T1: "Apple Intelligence" + "donanım katmanını baştan yazıyorlar" ungrounded | **LAX_APPROVAL** | Source: Apple iPhone 18 Pro regional battery strategy only. Draft adds "Apple Intelligence ajanları" + "donanım katmanını baştan yazıyorlar". Both unsupported. This is one of the LIVE tweets we already flagged as borderline. Gate correctly caught. |
| FP-6 | `138b0411` | T0+T1: `cve-2026-48095` | **LAX_APPROVAL — PHASE-0 FAB** | Source: "7-Zip kritik güvenlik açığı" — NO CVE number. Draft fabricates `CVE-2026-48095`. The exact Phase-0 fabricated identifier. Operator approved. Gate correctly caught. |
| FP-7 | `ed526c7b` | T0: `meta` not in source | **TRUE_FP** | Source: Apple smart glasses postponed. Draft: "Meta Ray-Ban ile sokakları ele geçirmişken" — uses Meta as a comparison point, not a factual claim about Meta. Gate's strict-entity-presence check over-blocked a comparison reference. |
| FP-8 | `1059be68` | T2: "Microsoft tekeli bitti" framing | **TRUE_FP** | Source: "OpenAI models now generally available on AWS Bedrock" — the source's central claim. Draft: "Microsoft tekeli bitti" is the exact entailment of "now generally available on AWS". Gate's T2 over-blocked a correct sharp summary. |

**FP split: 6 LAX_APPROVAL · 2 TRUE_FP.**
- True gate-precision on this 8-case slice = 6/8 captured fabrications + 2/8 over-blocks = **gate was right 6×, wrong 2×.**
- The lax-operator-baseline implies precision = 0/8 (every "FP" was an approval). Real precision after audit ≈ 75%+.

---

## 17 false-negatives  (gate PASS, "human rejected")

| # | draft_id | reject reason class | classification rationale |
|---|---|---|---|
| FN-1  | `95f680fa` | **QUALITY** | GTA hack — analogy/cliché. No fabrication. Operator rejected for tone. |
| FN-2  | `89d55125` | **QUALITY** | Samsung One UI — soft "OS-layer convergence" overreach but no entity/numeric fab. Tone rejection. |
| FN-3  | `24313746` | **QUALITY** | Windows + Codex — "lokalde çalışan agent" is reasonable interpretation of "computer use on Windows". Tone reject. |
| FN-4  | `e87b7641` | **QUALITY** | Tesla FSD Estonia — "AI agentlar regülasyon duvarlarını yıkıyor" rhetorical overreach, not entity fab. |
| FN-5  | `8b763b07` | **QUALITY** | Ripple RLUSD Turkey — "ödeme sistemleri otoban" cliché. |
| FN-6  | `47f4000d` | **QUALITY** | RTX Spark — "Intel/AMD CPU kalesine giriyor" supported by source; rejection was style. |
| FN-7  | `e4427164` | **QUALITY** | Euro-Office — tone. |
| FN-8  | `b7361d41` | **QUALITY** | Ferrari electric tax math — content correct, tone style reject. |
| FN-9  | `b0fb0339` | **MARGINAL_FAB** | Meta Limitless — adds "Ray-Ban başarısından sonra" as context. Ray-Ban Meta is a real product, but the source is about Limitless specifically. Borderline external-fact import. |
| FN-10 | `1f3a4062` | **MARGINAL_FAB** | Google sivrisinek — draft credits "Verily aracılığıyla". Verily IS Google's life-sciences subsidiary doing this work — externally correct, but the source attributes only to "Google". External-fact correction. |
| FN-11 | `7f95d1e5` | **QUALITY** | NVIDIA CPU — "veri merkezi omurgası" overreach but no entity fab. |
| FN-12 | `83144074` | **QUALITY** | Ferrari manual — stance/style. |
| FN-13 | `76718177` | **QUALITY** | Tofaş Doblo — stance. |
| FN-14 | `839e91de` | **QUALITY** | Tesla FSD Estonia #2 — overreach framing. |
| FN-15 | `16b5a42d` | **QUALITY** | Tesla FSD Estonia #3 — "Elonın askerleri her yerde" cringe reject. |
| FN-16 | `5731a523` | **REAL_FABRICATION ❗** | Apple HomePod/TV — source SPECIFICALLY says "Google Gemini destekli yeni Siri". Draft says "Apple Intelligence için her odaya fiziksel bir kulak yerleştiriyorlar" — substitutes Apple Intelligence for Gemini. Gate missed this because (a) "Apple Intelligence" not in alias map, (b) T1 didn't flag as substitution because the draft doesn't explicitly contradict, it just omits Gemini and introduces Apple Intelligence as the agent. **Genuine recall gap — must add to benchmark.** |
| FN-17 | `96e8dd88` | **QUALITY** | Euro-Office #2 — tone. |

**FN split: 14 QUALITY · 2 MARGINAL_FAB · 1 REAL_FABRICATION.**

---

## Real-world gate recall (corrected)

- **Real fabrications the gate MISSED in this 100-draft slice: 1** (FN-16 Apple Intelligence vs Gemini substitution).
- **Real fabrications the gate CAUGHT but lax operator approved: 6** (the FP_LAX cases — CVE-2026-48095, Llama 3, Apple Intelligence ajanları, ucuzladı claim, prompt-injection, mod-vs-studios framing).
- **Total real fabrications in the 100-draft sample: 7** (1 missed, 6 caught).
- **True recall on this real-world slice: 6/7 = 0.857.**

That's lower than the 1.00 benchmark recall because the benchmark didn't yet
include the Apple-Intelligence-vs-Gemini substitution pattern. Adding it as
a regression case in the benchmark.

## True false-positive on real-world data

- **True_FPs: 2** (Meta Ray-Ban contextual reference, AWS Bedrock entailment).
- **Real-world FP rate on grounded content: 2 / (2 + 14_quality + 9_actually_grounded_passed_silently)** ≈ very low; the published benchmark FP=0.00 stays a fair upper-bound reference.

## Methodology fix being applied

1. The lax-operator backfill confusion matrix is NOT a valid graduation signal.
2. `record_human_decision` now records a `reject_reason_class` so future
   reject decisions are typed (faithfulness / quality / fit / other).
3. The graduation scoreboard is recomputed using ONLY rows where
   `reject_reason_class` is faithfulness-relevant. The clean hand-labeled
   benchmark (`hype_crew/tests/fixtures/faithfulness_benchmark.jsonl`,
   recall 1.00 / FP 0.00) remains the authoritative gate-accuracy reference;
   shadow rows are the live-drift signal.
4. The Apple-Intelligence-vs-Gemini substitution pattern is added to the
   benchmark as a hand-labeled gold regression case so the recall floor
   reflects this real-world failure mode.
