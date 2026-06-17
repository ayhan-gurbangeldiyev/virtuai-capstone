"""Spine trace for draft a8bac287 — the first fresh story ingested via
the STAGE 1 supply expansion (@perplexity_ai)."""
import os, re, json
from supabase import create_client
sb = create_client(os.environ["SUPABASE_URL"], os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY"))

DID = "a8bac287-eb02-4000-8f9c-d143e028215d"
TID_URL = "https://x.com/perplexity_ai/status/2062556000394379710"

# (1) tweet_feed — source signal
print("=== 1) TWEET_FEED (source signal) ===")
tf = sb.table("tweet_feed").select("tweet_id, username, batch_type, content, tweet_created_at, collected_at").eq("tweet_url", TID_URL).limit(1).execute().data
for r in tf:
    print(f"  username      = @{r['username']} (batch={r['batch_type']})")
    print(f"  tweet_id      = {r['tweet_id']}")
    print(f"  tweet_created = {r['tweet_created_at']}")
    print(f"  collected_at  = {r['collected_at']}")
    print(f"  content       = {(r['content'] or '')[:150]!r}")

# (2) trends — clustered topic
print("\n=== 2) TRENDS (clustered topic, post-persona-gate + semantic_rescue) ===")
tr = sb.table("trends").select("id, topic, category, score, signal_count, source_count, semantic_triggers, created_at").ilike("topic", "%Perplexity%25 milyon%").limit(1).execute().data
for r in tr:
    print(f"  id            = {r['id']}")
    print(f"  topic         = {r['topic']}")
    print(f"  category      = {r['category']}  (semantic_rescue accepts cross-cat AI)")
    print(f"  score         = {r['score']}")
    print(f"  signal_count  = {r['signal_count']}")
    print(f"  semantic_triggers = {r.get('semantic_triggers')}")
    print(f"  created_at    = {r['created_at']}")

# (3) editorial_lead_judgments — editor-led pick
print("\n=== 3) EDITORIAL_LEAD_JUDGMENT (editor's-desk dry_run=false pick) ===")
elj = sb.table("editorial_lead_judgments").select("id, judgment_date, dry_run, lead_topic, lead_outcome, operator_sentence, created_at, account_id").eq("lead_trend_id", tr[0]["id"] if tr else "x").execute().data if tr else []
for r in elj:
    print(f"  judgment_id   = {r['id']}")
    print(f"  dry_run       = {r['dry_run']}  (false = live)")
    print(f"  lead_topic    = {r.get('lead_topic')}")
    print(f"  lead_outcome  = {r.get('lead_outcome')}")
    print(f"  operator_sentence = {r.get('operator_sentence', '')[:140]!r}")
    print(f"  created_at    = {r['created_at']}")
if not elj:
    print("  (no editorial_lead_judgment row — story selected by Lever-A path)")

# (4) daily_drafts — the written draft
print("\n=== 4) DAILY_DRAFTS (the actual draft) ===")
d = sb.table("daily_drafts").select("*").eq("id", DID).limit(1).execute().data[0]
print(f"  draft_id      = {d['id']}")
print(f"  status        = {d['status']}")
print(f"  platform      = {d['platform']}")
print(f"  trend_topic   = {d['trend_topic']}")
print(f"  source_url    = {d['source_url']}")
print(f"  content_thread_id = {d.get('content_thread_id')}")
print(f"  hype_run_id   = {d.get('hype_run_id')}")
print(f"  created_at    = {d['created_at']}")
print()
print(f"  CONTENT (VERBATIM):")
print(f"  ┌─────────────────────────────────────────────")
for line in (d['content'] or '').splitlines():
    print(f"  │ {line}")
print(f"  └─────────────────────────────────────────────")
print()
content = (d.get("content") or "").strip().lower()[:300]
FORMULA = [
    r"bence\s+as[ıi]l\s+olay",
    r"herkes\s+(?:bunu\s+)?(?:\S+\s+){0,8}?san[ıi]yor",
    r"ço[ğg]u\s+ki[şs]i\s+(?:bunu\s+)?(?:\S+\s+){0,8}?san[ıi]yor",
    r"as[ıi]l\s+olay\s+(?:bu|şu)",
    r"kimse\s+bunu\s+konu[şs]m[ıi]yor",
    r"as[ıi]l\s+mesele",
    r"ama\s+bence\s+as[ıi]l",
]
formulaic = any(re.search(p, content) for p in FORMULA)
print(f"  FORMULAIC opener? {'🔴 YES' if formulaic else '🟢 NO — variety code shipped'}")

# (5) faithfulness_verdicts — gate verdict
print("\n=== 5) FAITHFULNESS_VERDICTS (NER gate result) ===")
fv = sb.table("faithfulness_verdicts").select("verdict, final_action, path, gate_version, tier0_blocked, reasoning, created_at").eq("draft_id", DID).execute().data
if fv:
    for r in fv:
        print(f"  verdict       = {r.get('verdict')} / action={r.get('final_action')}")
        print(f"  path          = {r.get('path')}")
        print(f"  gate_version  = {r.get('gate_version')}")
        print(f"  tier0_blocked = {r.get('tier0_blocked')}")
        print(f"  reasoning     = {(r.get('reasoning') or '')[:200]!r}")
        print(f"  created_at    = {r.get('created_at')}")
else:
    print("  (no verdict yet — operator has not opened approve; gate runs at approve-click)")

# (6) video
print("\n=== 6) VIDEO ===")
print(f"  video_url     = {d.get('video_url') or '(no video — text-only platform)'}")
print(f"  video_integrity_ok = {d.get('video_integrity_ok')}")
print(f"  video_duration_s   = {d.get('video_duration_s')}")
print(f"  expected_duration_s = {d.get('expected_duration_s')}")

# (7) hype_runs
print("\n=== 7) HYPE_RUN (cron firing) ===")
hr = sb.table("hype_runs").select("id, status, started_at, completed_at, error, total_cost_usd, trend_id").eq("id", d.get("hype_run_id")).limit(1).execute().data
if hr:
    r = hr[0]
    print(f"  run_id        = {r['id']}")
    print(f"  status        = {r['status']}")
    print(f"  started_at    = {r['started_at']}")
    print(f"  completed_at  = {r['completed_at']}")
    print(f"  error         = {r.get('error') or '(none)'}")
    print(f"  total_cost    = ${r.get('total_cost_usd')}")
