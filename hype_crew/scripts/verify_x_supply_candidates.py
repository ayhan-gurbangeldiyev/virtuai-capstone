"""Verify each candidate X handle via the prod XQuik client.

Per-handle verdict: exists / active / posts-AI-content / recent-tweet-rate.
Drop any dead/noisy account before adding to trend_x_sources.
"""
import os, sys, asyncio, json
sys.path.insert(0, "/opt/contentfactory/backend")

from services.xquik_client import XquikClient

CANDIDATES = {
    "ai_news_en": ["karpathy", "levelsio", "jeremyphoward", "hardmaru", "nearcyan"],
    "ai_core":    ["sama", "perplexity_ai", "MistralAI"],
    "ai_news_tr": ["deeplearningtr", "aiturkiye"],
}

AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "openai", "anthropic", "model", "agent",
    "fine-tune", "transformer", "neural", "ml ", "machine learning",
    "embedding", "rag", "yapay zeka", "model", "veri", "deep learning",
]

async def verify_one(client, handle):
    info = await client.get_user_info(handle)
    if not info:
        return {"handle": handle, "verdict": "NOT_FOUND"}
    tweets = await client.search_user_tweets(handle, limit=15)
    if not tweets or (isinstance(tweets, dict) and tweets.get("error")):
        return {"handle": handle, "verdict": "NO_TWEETS", "info": info}
    if isinstance(tweets, dict):
        tw_list = tweets.get("tweets") or tweets.get("results") or tweets.get("data") or []
    elif isinstance(tweets, list):
        tw_list = tweets
    else:
        tw_list = []
    ai_hits = 0
    from datetime import datetime, timezone, timedelta
    week = datetime.now(timezone.utc) - timedelta(days=7)
    recent_count = 0
    for t in tw_list[:15]:
        text = (t.get("tweetText") or t.get("text") or t.get("content") or "").lower()
        if any(k in text for k in AI_KEYWORDS):
            ai_hits += 1
        ts = t.get("tweetCreatedAt") or t.get("created_at") or t.get("createdAt")
        try:
            if ts and datetime.fromisoformat(str(ts).replace("Z","+00:00")) > week:
                recent_count += 1
        except Exception:
            pass
    sample = (tw_list[0] if tw_list else {})
    sample_text = (sample.get("tweetText") or sample.get("text") or sample.get("content") or "")[:140]
    sample_at = sample.get("tweetCreatedAt") or sample.get("created_at") or sample.get("createdAt")
    return {
        "handle": handle,
        "verdict": "OK" if (len(tw_list) >= 3 and ai_hits >= 2 and recent_count >= 2) else "WEAK",
        "tweets_seen": len(tw_list),
        "ai_hits_in_15": ai_hits,
        "recent_7d": recent_count,
        "sample_text": sample_text,
        "sample_at": sample_at,
        "followers": info.get("followers"),
        "verified": info.get("verified"),
        "description": (info.get("description") or "")[:80],
    }


async def main():
    client = XquikClient()
    results = []
    for batch, handles in CANDIDATES.items():
        for h in handles:
            print(f"--- verifying @{h} ({batch}) ---")
            try:
                r = await verify_one(client, h)
                r["batch"] = batch
                results.append(r)
                print(json.dumps({k: v for k, v in r.items() if k != "info"}, ensure_ascii=False))
            except Exception as e:
                print(f"  EXC: {e}")
                results.append({"handle": h, "batch": batch, "verdict": f"EXC: {e}"})
            print()
    print("=== SUMMARY ===")
    for r in results:
        print(f"  {r['batch']:13} @{r['handle']:18} → {r.get('verdict')}  (ai={r.get('ai_hits_in_15')}/{r.get('tweets_seen')})")
    with open("/tmp/handle_verify.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


asyncio.run(main())
