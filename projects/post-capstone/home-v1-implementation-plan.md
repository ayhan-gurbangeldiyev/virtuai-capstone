# Home v1 — Implementation Plan

Source of truth: [product-structure.md](product-structure.md). Anything
in this document that contradicts the locked product structure is a bug
in this document, not in the structure.

This is the plan that gets built. It is scoped to Home v1 only. Choices
and Lifecycle remain scope-locked but unbuilt.

---

## 1. Backend contract

### 1.1 `GET /api/hype/home-summary`

Single read endpoint. No-cache. Recomputed on each fetch (cheap because
all aggregations are over the trailing 24h). Response shape:

```json
{
  "as_of": "2026-06-04T16:00:00Z",
  "hero": {
    "kind": "decision_pair | closest_call | status_only",
    "sentence": "Cansu covered NVIDIA's AI laptop launch but skipped Apple's iPhone update because NVIDIA materially changed AI workstation capabilities and Apple did not.",
    "covered": {
      "title": "NVIDIA RTX Spark AI workstation",
      "platform": "twitter",
      "release_url": "https://x.com/cansudut/status/...",
      "published_at": "2026-06-04T15:22:00Z"
    } | null,
    "skipped": {
      "title": "Apple iPhone 17 update",
      "source_url": "https://...",
      "category_hint": "consumer hardware"
    } | null,
    "reason": "NVIDIA's announcement materially changed AI workstation capabilities and Apple's update did not."
  },
  "latest_published": {
    "title": "NVIDIA RTX Spark AI workstation",
    "platform": "twitter",
    "release_url": "https://x.com/cansudut/status/...",
    "published_at": "2026-06-04T15:22:00Z",
    "relative_time": "38 minutes ago"
  } | null,
  "considered_today": {
    "evaluated": 16,
    "published": 1,
    "skipped": 15
  },
  "pause": {
    "is_paused": false,
    "can_pause": true
  },
  "liveness": {
    "status": "green | yellow | red",
    "reconciler_last_run_iso": "2026-06-04T15:48:00Z",
    "reconciler_relative": "12 minutes ago",
    "cron_last_run_iso": "2026-06-04T15:56:00Z",
    "cron_relative": "4 minutes ago",
    "platforms_reachable": { "twitter": true, "linkedin": true, "devto": true },
    "issues": []
  }
}
```

### 1.2 `POST /api/hype/kill-switch`

Body: `{ "paused": true | false }`.
Returns: the new pause state (`pause` block of the summary).
Idempotent. Authenticated. Toggles `hype_account_config.executive_freeze`.

### 1.3 Hero kinds (exhaustive — no fourth)

| `hero.kind` | When | Sentence template (server composes prose, never client) |
|---|---|---|
| `decision_pair` | ≥1 covered today AND ≥1 skipped today with usable pairing | "Cansu covered [covered.title] but skipped [skipped.title] because [reason]." |
| `closest_call` | 0 covered today AND ≥1 skipped today | "Cansu didn't write today. The closest call was [skipped.title] — she passed because [reason]." |
| `status_only` | 0 covered AND 0 skipped (early morning, system silent, or true edge case) | One of: "Cansu is still reviewing today's stories." / "Cansu hasn't started evaluating stories yet." / "The system hasn't checked in for the last hour." (chosen by which condition applies) |

`status_only` is the only kind where the hero does not name a specific
story. It is treated as an edge case and logged when it fires more than
once per day.

### 1.4 Sentence composition

Composed server-side, never on the client.

**Input** to the composer:
- Covered item: title, source summary, gate rationale snippet
- Skipped item: title, source summary, gate rationale snippet
- The selection algorithm's reason for pairing them

**Output requirements** (validated; retry on failure):
1. Both `covered.title` and `skipped.title` appear verbatim in the
   sentence
2. The reason clause names a property of the items themselves (not of
   Cansu)
3. No internal system names appear (Persona Gate, TrendScout, Visual
   Director, Content Strategist, Compliance, Postiz, Wiro, HeyGen,
   Nano Banana)
4. 1–3 sentences total, ≤ 80 words
5. Reads as natural prose — no bullets, no colons-as-headers

**Validation pass:**
- Regex check for verbatim titles → reject if missing
- Word-list check for internal terms → reject if any match
- Length check → reject if > 80 words

**Failure handling:** retry once with stronger prompt. If still fails,
fall back to a deterministic template (`"Cansu covered [X]. She skipped
[Y]. Reason: [Z]."`) and emit a `[ALERT][WARN]` so the operator knows
the page is in fallback mode. The fallback sentence is uglier but
still valid — it does not break the page.

### 1.5 Selection algorithm for the pairing

For `decision_pair` kind:

1. Pull today's published items from `daily_drafts` where
   `postiz_state = 'PUBLISHED'` AND `scheduled_at >= today_utc_start`
2. Pull today's skipped items from `persona_gate_log` where
   `verdict = 'reject'` AND `evaluated_at >= today_utc_start`
3. For each (covered × skipped) pair, compute pairing score:
   - Same category match → +3
   - Same source domain (e.g., both Apple-related) → +2
   - Same week of news cycle → +1
   - Bonus: skipped item has high external salience (trend signal volume) → +2
4. Pick the highest-scoring pair
5. If no pair scores > 0, fall back to: highest-salience covered + highest-salience skipped (ungated pairing)
6. If still nothing pairs → `closest_call`

For `closest_call` kind: rank today's skipped items by gate score
descending (the ones Cansu came closest to accepting), pick top 1.

The selection rule is documented to the operator in `product-structure.md`
under Choices v1. The operator can audit it. It is not a black box.

### 1.6 Liveness checks

Three probes, all read-only:

| Check | Source | Yellow threshold | Red threshold |
|---|---|---|---|
| Reconciler liveness | `MAX(hype_runs.completed_at WHERE agent_name = 'reconciler')` or, simpler, last successful `[reconciler] DONE` line | > 12h ago | > 24h ago |
| Cron liveness | `MAX(hype_runs.started_at)` | > 90 min ago | > 6h ago |
| Per-platform reachability | Cached probe result, refreshed on each `home-summary` call only if last probe > 5 min old | any platform false | ≥2 platforms false |

`liveness.status` is the worst of the three. `issues` array contains
short operator-facing strings: `"truth_checker_stale"`,
`"system_quiet_longer_than_usual"`, `"linkedin_not_responding"`.

### 1.7 What this endpoint does NOT return

- No engagement counts
- No cost figures
- No per-platform breakdowns beyond reachability bool
- No multi-day history
- No persona/account selector data
- No anything that doesn't render on a documented v1 surface

If the endpoint returns a field that nothing on the page consumes, the
endpoint is overscoped.

---

## 2. Frontend component tree

Route: `/control` (separate from existing `/` DashboardHome).

```
HomePage (route handler at /control)
├── EditorialHero
│   ├── HeroSentence      // renders home.hero.sentence as prose
│   ├── AsOfTimestamp     // small, under hero
│   └── PauseSentence     // appended when home.pause.is_paused
├── LatestPublishedLine   // single line, clickable release URL
├── ConsideredLine        // muted text: "Cansu also considered N other stories today"
│                         // → link to /choices if it exists; otherwise plain text
├── KillSwitchButton      // neutral-styled button, current state inline
└── LivenessFooter
    ├── LivenessStrip     // single line of reconciler / cron / platforms status
    └── IssueLine         // shown only when liveness.status != green
```

Eight components total. ~150–200 lines of JSX in aggregate.

### 2.1 What's deliberately not there

- No `<Card>`, `<Tile>`, `<Panel>`, `<KPIBox>`, `<Stat>` components
- No `<Tabs>`, `<Dropdown>`, `<DatePicker>`
- No charting library imports
- No skeleton-card loading states (text placeholders only)
- No header/nav above the hero in v1 (the wordmark only)

### 2.2 Loading state

Text placeholder, not skeleton shimmer:

> *Loading today's choices…*

That's it. One muted line. The page does not animate empty cards.

### 2.3 Error state

If `home-summary` returns 5xx:

> *Something is wrong with this page. The system itself may still be
> working — check the operator runbook.*

Single sentence. No traceback, no retry button (the page is no-cache,
refresh works). Link to `projects/post-capstone/runbook.md`.

### 2.4 Reuse from existing codebase

- `useAccount` hook for account context
- `useTranslation` hook for i18n (TR/EN — Home v1 ships TR-only with EN
  strings stubbed)
- `formatRelativeTime(iso)` utility
- Existing `Button` and `Badge` primitives from shadcn/ui

No new design system primitives. No new shared layout.

---

## 3. Acceptance criteria

Home v1 ships when all of the following are true:

1. **The skeptical-journalist test passes.** Open Home, read for 15s,
   open both items named in the hero in new tabs, read both,
   independently agree with the distinction. If the agreement event
   does not happen, the page is not done.
2. **Hero sentence reads as natural prose** — not as bulleted output,
   not as template stuffing. A monolingual reader cannot tell it was
   generated.
3. **Both `hero.covered.title` and `hero.skipped.title` appear
   verbatim** in `hero.sentence`. Server-validated; client also
   defensively renders titles separately as clickable links below the
   sentence in case the sentence itself doesn't render.
4. **No internal system name appears anywhere** on the page in any
   state, including liveness messages and errors.
5. **Quiet-day rendering** produces a `closest_call` hero, not a
   `status_only` hero, in any case where ≥1 skipped item exists for the
   day.
6. **Liveness footer reflects truth.** If reconciler hasn't run in 13h,
   the footer says so and turns yellow. Verified by deliberately
   stopping `hype-engagement.timer` and confirming the page reflects
   it within one fetch.
7. **Kill switch flips state in <2s** and shows the new state without
   a confirmation dialog.
8. **Cold-load latency p95 < 1s** on the production Hetzner endpoint
   under expected concurrency (1–2 concurrent operators).
9. **HTTP no-cache headers** on the API response and the page itself.
   Manual verification: same operator, two browser tabs, same minute —
   if a new gate decision lands between the two opens, the second tab
   reflects it.
10. **Mobile viewport** (≤375px wide): hero still readable in a single
    column, no horizontal scroll, kill switch still tappable.

No engagement metric, throughput counter, cost figure, or system gauge
is part of the acceptance criteria. None of those are part of the
product.

---

## 4. Edge cases

| Edge case | Resolution |
|---|---|
| Covered exists today, no skipped same-category | Fall back to highest-salience skipped today; if none, `closest_call` |
| Skipped today, no covered today | `closest_call` kind |
| Neither today (early morning, system silent) | `status_only`, sentence chosen by which condition fired |
| Today has runs but no gate decisions yet | `status_only` with sentence "Cansu is still reviewing today's stories" |
| Sentence composer LLM call fails twice | Deterministic template fallback + `[ALERT][WARN]` |
| Composed sentence fails validation (missing title or contains internal term) | Retry with stronger prompt once → fallback template |
| Pause state during composition | Compose normally from pre-pause data, append "Cansu is currently paused." as a separate sentence |
| Liveness probe fails (network glitch) | Treat as unreachable for this fetch only; do not persist; next fetch retries |
| Multiple operators click kill switch simultaneously | Idempotent (DB transaction); both see the same end state |
| User clicks kill switch then refreshes before 200 response | Server is source of truth; refresh shows whatever DB has |
| `release_url` is null on the latest published item (e.g., reconciler hasn't populated yet) | `LatestPublishedLine` renders the title + platform + relative time without a hyperlink. Footer adds an `issue` entry: `release_url_pending` |
| Two pieces published in same minute, both qualifying as "latest" | Order by `scheduled_at DESC, created_at DESC`, pick first |
| Today's only covered item failed compliance and never published | Treat as skipped (it didn't land); hero pulls from a different pair if available |
| All today's runs failed (`error` not null on every `hype_runs` row) | `status_only` sentence "The system hasn't successfully evaluated a story today." Banner red |

---

## 5. Empty-state behavior

Two distinct empties:

### 5.1 System has never produced content (cold install)

Hero: *"Cansu hasn't started evaluating stories yet."*
LatestPublishedLine: hidden.
ConsideredLine: hidden.
Liveness: rendered normally.
Kill switch: rendered normally.

### 5.2 Today is genuinely empty (no runs yet today)

Hero: *"Cansu is still reviewing today's stories. The most recent
decision was [yesterday's hero]."*
LatestPublishedLine: the most recent published item across any day.
ConsideredLine: hidden.
Liveness: rendered normally.

The page never shows zero-state cards or "no data" messages. There is
always prose.

---

## 6. Quiet-day behavior

The most important non-default case. Spec:

- `hero.kind = "closest_call"` (not `status_only`, unless no skipped exists)
- `hero.covered = null`
- `hero.skipped` = the item Cansu came closest to accepting today (highest gate score among rejects)
- `hero.sentence` form:
  *"Cansu didn't write today. The closest call was [skipped.title] — she passed because [reason about the item, not about Cansu]."*
- `latest_published` still populated with the most recent published
  piece across any day (proves publishing still works)
- `considered_today.published = 0` is part of the response but is **not
  displayed numerically** on the page. The muted ConsideredLine reads:
  *"Cansu also considered N other stories today"* using
  `considered_today.evaluated`. No "0 published" wording.

The quiet-day sentence is the trust-anchor sentence of the entire
product. It must read as deliberate editorial choice, not as a system
report. The composer's prompt is tuned specifically for this case.

---

## 7. Failure-state behavior

Three failure modes, all rendered without changing the hero text:

### 7.1 Single platform unreachable (e.g., LinkedIn down)

- Hero: unchanged, no marker
- LivenessFooter:
  *"X and Dev.to are responding. LinkedIn is not."*
- IssueLine (small, below footer):
  *"One channel is having trouble. Cansu is otherwise behaving normally."*
- Banner color: yellow dot

### 7.2 Truth-checker stale (reconciler > 12h since last run)

- Hero: unchanged, small yellow dot prepended to hero block
- LivenessFooter:
  *"Last check was longer ago than usual."*
- IssueLine:
  *"The system hasn't double-checked itself recently. We're aware."*
- Banner color: yellow

### 7.3 System dark (no cron firings > 90 min)

- Hero: shows yesterday's last known decision pair with a sentence
  appended:
  *"The system hasn't checked in for the last hour."*
- AsOfTimestamp: shows the *actual* age of the data, not "now"
- LivenessFooter:
  *"Last evaluation: [time] ago."*
- IssueLine:
  *"Cansu hasn't been active recently."*
- Banner color: red

In all three cases, the kill switch remains functional, the page does
not throw, and no metric tile appears.

---

## 8. What gets built, in order

1. Backend endpoint scaffold (`GET /api/hype/home-summary` returning
   `status_only` hardcoded). Frontend renders it. Smoke test.
2. Selection algorithm (covered × skipped pairing). Endpoint returns
   real `decision_pair` and `closest_call` kinds. Sentence still
   templated, not LLM-composed.
3. Sentence composer (LLM call + validation + fallback). Endpoint
   returns prose sentences.
4. Kill switch endpoint + frontend wiring.
5. Liveness probes + footer rendering.
6. Failure-state rendering for all three modes.
7. Acceptance criteria sweep — manual run through each of the 10 items.

Steps 1–4 are the minimum viable Home. Steps 5–6 are required for the
trust mechanism to be honest (defends against false-GREEN). Step 7 is
the gate to declaring Home v1 shipped.

---

## 9. What this plan does not cover

- Choices implementation (scope-locked in `product-structure.md`,
  not built)
- Lifecycle implementation (same)
- Persona Gate decision rationale improvements (separate phase)
- Engineer-mode debug view (separate; not part of operator product)
- Mobile-specific layouts beyond the single-column reflow requirement
- Internationalization beyond Turkish (English strings stubbed only)
- Analytics, telemetry, or click tracking on the Home page itself

Anything in this list is a future phase. Reopen only when v1 ships.
