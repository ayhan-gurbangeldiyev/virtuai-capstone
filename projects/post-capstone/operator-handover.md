# Operator Handover — Cansu Autonomy

One page. Read end-to-end. If you're operating Cansu while Berkay is away, this is the contract.

## Product identity (locked 2026-06-04)

**Cansu is an autonomous editorial system whose choices are visible.**

She is not a content factory. She is a selective editor with publishing infrastructure. Most days she chooses to stay quiet because the trend pool does not produce a story she would tell. That selectivity is the product, not a bug.

Implication for operations: a quiet day with the banner GREEN is the expected outcome, not a failure mode. The dashboard's job is to make the difference between "quiet because Cansu refused" and "quiet because something broke" obvious in 5 seconds.

## State as of 2026-06-04

| dimension | value |
|---|---|
| Persona | `cansu_dut` (id `653cea63-…`) |
| Active accounts | 2 (twitter runner `2b731bf7`, linkedin runner `4f13b200`) |
| Auto-publish ON | account `2b731bf7` only |
| Auto-publish allowlist | `["twitter","devto"]` (Option C scoped activation) |
| Cost cap (active) | $1.00/day on `2b731bf7` |
| Cost cap (linkedin) | NULL (must be set before activating LinkedIn) |
| Dry-run mode | true on `4f13b200` (linkedin runner) |
| Executive freeze | false everywhere |
| 42.B brand visual flag | OFF (`BRAND_BRIEF_BUILDER_ENABLED` not set) |
| Soak window | 24h started ~12:39 UTC 2026-06-04 |

## What's autonomous right now

The twitter runner cron (account `2b731bf7`) fires every hour. Each run:
1. TrendScout picks a trend (or skips if none qualify).
2. Persona Gate + Content Strategist + Writer + Visual + (optional Video) build per-platform drafts.
3. Drafts fan out to twitter + linkedin + devto + instagram + youtube (per persona config).
4. Option C filter: only `twitter` + `devto` are scheduled to Postiz. Others persist as `pending_review` (visible in UI, never auto-publish).
5. Postiz schedules + publishes at the time chosen by upstream logic.
6. Reconciler (runs every 6h via `hype-engagement.timer`) updates `daily_drafts.postiz_state` + `release_url` and fires alerts on anomalies.

## How to know it's working

```bash
ssh root@46.225.27.85 'journalctl -u hype-crew --since "2 hours ago" | grep -E "Flow|reconciler|ALERT"'
```

Expected: `Flow` lines from runner runs, `reconciler` lines every 6h, `[ALERT]` lines only on real anomalies.

Or query Supabase:
```sql
-- Most recent activity
SELECT id, platform, postiz_state, release_url, scheduled_at
FROM daily_drafts
WHERE created_at > NOW() - INTERVAL '6 hours'
ORDER BY created_at DESC LIMIT 20;
```

## Kill switches (in priority order)

| trigger | what to type | effect |
|---|---|---|
| Single bad post just went live | `UPDATE daily_drafts SET status='dismissed' WHERE id='<uuid>';` + manually delete from platform via Postiz UI | post visible in DB but flagged dismissed |
| Stop next cron firing (this account) | `UPDATE hype_account_config SET executive_freeze=true WHERE account_id='2b731bf7-…';` | next `runner.py` invocation skips the entire account; reversible by setting back to false |
| Stop all auto-publish but keep generation | `UPDATE hype_account_config SET auto_publish_enabled=false WHERE account_id='2b731bf7-…';` | drafts continue to be created (as `pending_review`) but nothing reaches Postiz |
| Stop all activity completely | `sudo systemctl stop hype-crew.timer` on Hetzner | no cron firings until restart |

## Alert types you may see

All alerts are in journald with `[ALERT]` prefix. Slack/email not yet wired — read journald.

| `[ALERT][CRITICAL]` ... | meaning | action |
|---|---|---|
| `Runner failure streak` | 3 consecutive failed runs | check Wiro/LLM/Postiz upstream; usually clears on its own |
| `Postiz reconciliation anomaly — failed_silently` | a post is in our DB but missing from Postiz / has empty analytics | open Postiz UI for that post id; if missing, dismiss the draft |
| `Zero successful publishes in window` | auto-publish ON but no publishes in 24h | check if TrendScout is producing trends; check Postiz API health |

| `[ALERT][WARN]` ... | meaning | action |
|---|---|---|
| `Postiz reconciliation anomaly — scheduled_not_live` | post is QUEUE/PROCESSING and scheduled time has passed | check Postiz UI; usually Postiz internal retry |
| `Stale 'pending' draft (E4 reaper)` | draft stuck in `status='pending'` for >24h | check via UI; if useless, dismiss |

| `[ALERT][INFO]` ... | meaning | action |
|---|---|---|
| `Synthetic E3 test alert` | manual test | ignore |
| `Postiz reconciliation anomaly — queue_late_short` (E1.1) | QUEUE post is 0–2h past `scheduled_at` — still inside Postiz's own ±2h self-heal sweep | none; Postiz Temporal sweep should pick it up |

## Postiz lifecycle reference (E1.1, opt-in)

Postiz uses a 4-state machine: `DRAFT → QUEUE → PUBLISHED | ERROR`. Once a post is in `QUEUE`, a Temporal workflow `post_{postId}` sleeps until the scheduled `publishDate` and then runs the publish activity (typically within seconds of the timer firing). Postiz also runs a periodic self-heal sweep (`searchForMissingThreeHoursPosts`) that re-signals workflows for posts whose `publishDate` is within **±2h** of now. Posts more than ~3h past `publishDate` are beyond Postiz's own self-heal and will not auto-recover.

**Activation**: lifecycle-aware bands are **off by default**. Set `RECONCILER_LIFECYCLE_ALERTS=true` in the timer's environment to opt in. When off, the reconciler uses the pre-E1.1 single-tier WARN classification.

The reconciler maps Postiz lifecycle facts to severity bands (see `hype_crew/scripts/poll_engagement.py` constants `QUEUE_INFO_MAX_HOURS=2.0`, `QUEUE_WARN_MAX_HOURS=4.0`):

| Postiz state | Lateness vs `scheduled_at` | Severity | Category | What it means |
|---|---|---|---|---|
| `QUEUE` / `DRAFT` | future (not yet due) | — | — | normal; counted as `queued` |
| `QUEUE` | 0–2h late | INFO | `queue_late_short` | inside Postiz self-heal window; no action |
| `QUEUE` | 2–4h late | WARN | `queue_late_long` | self-heal sweep should have caught it; investigate during business hours |
| `QUEUE` | ≥4h late | CRITICAL | `queue_stuck` | beyond Postiz self-heal; manual re-queue or dismiss required |
| `ERROR` | any | CRITICAL | `error_terminal` | terminal state — Postiz will not retry; inspect + re-queue or dismiss |
| `PUBLISHED` + `release_url` set | — | — | — | success; counted as `live` |
| `PUBLISHED` + `release_url` NULL >2h | platform ∈ {twitter, linkedin} | WARN | `published_no_url` | Postiz post-publish hiccup; verify in UI |
| Anything else (incl. `PROCESSING` if observed) | — | WARN | `postiz_only_unknown` | undocumented state; log evidence and inspect |
| Missing from Postiz inventory + empty analytics | — | CRITICAL | `failed_silently` | DB has post but Postiz lost it; usually deleted on Postiz side |

`PROCESSING` is not a public Postiz state — it appears nowhere in API responses and is handled only as a defensive fallthrough.

**Off-state (default) behavior**: with `RECONCILER_LIFECYCLE_ALERTS` unset or `false`, the reconciler emits a single WARN for any past-due QUEUE post via the legacy `alert_reconciliation_anomaly` helper, and routes ERROR rows to the same `failed_silently` CRITICAL alert as pre-E1.1. No INFO band, no severity split, no `published_no_url` check.

## Common questions

**Q: how do I see what's live across platforms?**
```sql
SELECT platform, postiz_state, release_url, scheduled_at
FROM daily_drafts
WHERE postiz_state = 'PUBLISHED'
ORDER BY scheduled_at DESC LIMIT 20;
```

**Q: how do I check if a draft from today went live or is still queued?**
```sql
SELECT id, platform, status, postiz_state, postiz_post_id, scheduled_at, release_url
FROM daily_drafts
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY scheduled_at;
```

**Q: how do I activate Instagram / LinkedIn / YouTube?**

DO NOT do this without explicit Berkay direction. The scoping is intentional. To expand:
```sql
-- example: add linkedin to allowlist
UPDATE hype_account_config
SET allowed_publish_platforms = '["twitter","devto","linkedin"]'::jsonb
WHERE account_id = '2b731bf7-…';
```
Then immediately reconciler-check the next firing's outcome.

**Q: how do I do a synthetic alert test?**

```bash
ssh root@46.225.27.85 '/opt/hype-crew/venv/bin/python -c "
import sys; sys.path.insert(0, \"/opt/hype-crew\")
from tools.alerter import alert_synthetic_test
print(alert_synthetic_test()[\"delivery\"])"'
```

## Where things live

| component | location |
|---|---|
| Hetzner host | `46.225.27.85` |
| Runtime venv | `/opt/hype-crew/venv` |
| Code | `/opt/hype-crew/` |
| Cron timer (main loop) | `hype-crew.timer` |
| Cron timer (engagement + reconciler + reaper) | `hype-engagement.timer` (every 6h) |
| Other timers | `hype-image-regen`, `hype-quality-audit`, `hype-regen-watchdog`, `hype-autonomy-gates`, `hype-exec-cleanup`, `hype-sync-curated` |
| Supabase | project URL via `mcporter call 'supabase.get_project_url'` |
| Postiz | `https://api.postiz.com/public/v1/` with `POSTIZ_API_KEY` env |
| Runbook | `projects/post-capstone/runbook.md` |

## Known limitations (as of 2026-06-04)

These are documented gaps that do NOT block autonomous operation but are worth knowing.

| limitation | scope | impact | priority |
|---|---|---|---|
| **Video subtitles appear absent** | All Video Director outputs (avatar_v and split_screen pipelines) | Reduces algorithmic reach on Instagram Reels / YouTube Shorts / LinkedIn Video by an estimated 20–50% at audience scale. Generation and publishing still function; only mute-viewing distribution is impacted. **No effect today because audience is essentially zero.** | P2 — revisit at audience inflection (e.g., >1000 followers on any video platform, OR any single video >100 views) |
| Subtitle root cause | Unclassified | Could be a bug (HeyGen `caption=True` ignored), an unverified assumption (Phase 35.2 comment claimed HeyGen burns native), or a missing feature (split_screen pipeline may strip subtitles via FFmpeg composite). Evidence: 11 of 11 bottom-30% subtitle-zone frames inspected across 2 production videos showed no overlay text. | Defer investigation until P0 |
| **No clickable release URL in UI** | Postiz reconciliation surface (added 2026-06-04) | `daily_drafts.postiz_state` and `release_url` are populated by the reconciler but the UI does not yet render them. Verifying that a draft *actually* published requires SQL or journald inspection. | Closes when Home/Today screen ships |
| **Postiz analytics surface only X (Twitter)** | LinkedIn, Dev.to, Instagram, YouTube | Engagement signal is currently visible only for the X platform via the Postiz analytics endpoint. Other platforms publish successfully but engagement is not measurable through our pipeline. | Defer until video stack distribution work |
| **Persona Gate decisions not visible** | `persona_gate_log` table (730 rows / 44h) has gate verdicts; UI does not surface them | Operator cannot easily explain why a specific trend was rejected pre-LLM | Closes when Draft Lifecycle screen ships |
| **Trend source provenance fragmented** | `raw_signals`, `tweet_feed`, `rss_feeds`, `trend_x_sources` — 4 separate tables | Where each trend came from requires SQL joins | Closes when Trend Timeline ships |
| **3 columns added on 2026-06-04 not in UI** | `postiz_state`, `release_url`, `allowed_publish_platforms` | The most operationally important data for autonomy trust is currently invisible above the SQL layer | Closes with Home/Today + Publishing screens |

## Important DO NOTs

- Do not flip `BRAND_BRIEF_BUILDER_ENABLED` (Phase 42.B) without Berkay's explicit go-ahead. It's a separate experimentation flag.
- Do not enable LinkedIn auto-publish without first setting `daily_cost_cap_usd` on the linkedin account (currently NULL).
- Do not activate Instagram / YouTube without Berkay's go-ahead — the silent-failure history needs review.
- Do not modify `personas.default_target_platforms` to scope publishing. Use the Option C allowlist instead.
- Do not skip the runbook when an alert fires.

## On-call signal

If you can't tell from journald what's wrong, run the reconciler manually:
```bash
ssh root@46.225.27.85 'cd /opt/hype-crew && RECONCILER_WRITE_MODE=false venv/bin/python -m scripts.poll_engagement --dry-run 2>&1 | tail -40'
```

Output should show `[reconciler] DONE — {'candidates': N, 'live': M, 'queued': K, 'anomalies': J, ...}`. If `anomalies > 0`, look at the alert lines above the DONE line.
