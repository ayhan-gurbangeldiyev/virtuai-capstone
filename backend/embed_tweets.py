"""Embed all source_tweets using OpenAI text-embedding-3-small.

Usage:
    python embed_tweets.py                  # Embed all un-embedded tweets
    python embed_tweets.py --force          # Re-embed everything
    python embed_tweets.py --source-id XX   # Only embed tweets from a specific source
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from openai import OpenAI
from supabase import create_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100

supabase_url = os.environ['SUPABASE_URL']
supabase_key = os.environ['SUPABASE_SERVICE_KEY']
supabase = create_client(supabase_url, supabase_key)

openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])


def get_tweets_to_embed(source_id: str = None, force: bool = False) -> list:
    """Fetch tweets that need embedding."""
    query = supabase.table("source_tweets").select("id, content")
    
    if source_id:
        query = query.eq("source_id", source_id)
    
    if not force:
        query = query.is_("embedding", "null")
    
    result = query.limit(5000).execute()
    return result.data or []


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using OpenAI."""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in response.data]


def save_embeddings(tweet_ids: list[str], embeddings: list[list[float]]):
    """Save embeddings to Supabase one by one (pgvector needs special handling)."""
    for tweet_id, embedding in zip(tweet_ids, embeddings):
        try:
            supabase.table("source_tweets").update({
                "embedding": embedding
            }).eq("id", tweet_id).execute()
        except Exception as e:
            logger.error(f"Failed to save embedding for {tweet_id}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Embed source tweets")
    parser.add_argument("--force", action="store_true", help="Re-embed all tweets")
    parser.add_argument("--source-id", type=str, help="Only embed tweets from this source")
    args = parser.parse_args()

    tweets = get_tweets_to_embed(source_id=args.source_id, force=args.force)
    
    if not tweets:
        logger.info("No tweets to embed.")
        return
    
    logger.info(f"Embedding {len(tweets)} tweets...")
    
    total_embedded = 0
    for i in range(0, len(tweets), BATCH_SIZE):
        batch = tweets[i:i + BATCH_SIZE]
        texts = [t['content'] for t in batch]
        ids = [t['id'] for t in batch]
        
        # Skip empty texts
        valid = [(tid, txt) for tid, txt in zip(ids, texts) if txt and txt.strip()]
        if not valid:
            continue
        
        valid_ids, valid_texts = zip(*valid)
        
        try:
            embeddings = embed_batch(list(valid_texts))
            save_embeddings(list(valid_ids), embeddings)
            total_embedded += len(valid_ids)
            logger.info(f"  Batch {i // BATCH_SIZE + 1}: {len(valid_ids)} tweets embedded ({total_embedded}/{len(tweets)})")
        except Exception as e:
            logger.error(f"  Batch {i // BATCH_SIZE + 1} failed: {e}")
    
    logger.info(f"Done! {total_embedded} tweets embedded.")


async def embed_tweets_for_source(source_id: str):
    """Async helper to embed tweets for a specific source. Called after scraping."""
    tweets = get_tweets_to_embed(source_id=source_id, force=True)
    if not tweets:
        return 0
    
    total = 0
    for i in range(0, len(tweets), BATCH_SIZE):
        batch = tweets[i:i + BATCH_SIZE]
        valid = [(t['id'], t['content']) for t in batch if t.get('content', '').strip()]
        if not valid:
            continue
        
        ids, texts = zip(*valid)
        try:
            embeddings = embed_batch(list(texts))
            save_embeddings(list(ids), embeddings)
            total += len(ids)
        except Exception as e:
            logger.error(f"Embedding batch failed for source {source_id}: {e}")
    
    logger.info(f"Embedded {total} tweets for source {source_id}")
    return total


def embed_tweets_for_source_sync(source_id: str) -> int:
    """Sync version for calling from non-async contexts."""
    tweets = get_tweets_to_embed(source_id=source_id, force=True)
    if not tweets:
        return 0
    
    total = 0
    for i in range(0, len(tweets), BATCH_SIZE):
        batch = tweets[i:i + BATCH_SIZE]
        valid = [(t['id'], t['content']) for t in batch if t.get('content', '').strip()]
        if not valid:
            continue
        
        ids, texts = zip(*valid)
        try:
            embeddings = embed_batch(list(texts))
            save_embeddings(list(ids), embeddings)
            total += len(ids)
        except Exception as e:
            logger.error(f"Embedding batch failed for source {source_id}: {e}")
    
    logger.info(f"Embedded {total} tweets for source {source_id}")
    return total


def _compute_combined_score(similarity: float, likes: int, retweets: int) -> float:
    """Combine similarity score with engagement metrics.
    
    Formula: 0.6 * similarity + 0.4 * normalized_engagement
    Engagement is log-scaled to prevent outliers from dominating.
    """
    import math
    engagement = likes + (retweets * 2)  # retweets worth more
    # Log scale: log(1+engagement) / log(1+1000) to normalize roughly 0-1
    norm_engagement = math.log1p(engagement) / math.log1p(1000)
    norm_engagement = min(norm_engagement, 1.0)
    return 0.6 * similarity + 0.4 * norm_engagement


def _is_reply(content: str) -> bool:
    """Check if a tweet is a reply (starts with @mention)."""
    return content.strip().startswith("@")


def get_similar_tweets(query_text: str, source_ids: list[str], limit: int = 20, threshold: float = 0.3, content_type: str = "tweet") -> list[dict]:
    """Find similar tweets using pgvector cosine similarity with engagement weighting and diversity sampling.
    
    Args:
        query_text: Text to find similar tweets for
        source_ids: List of source IDs to search within
        limit: Max number of results to return
        threshold: Minimum similarity threshold
        content_type: 'tweet' or 'reply' - filters examples by type
    
    Returns:
        List of tweet dicts with similarity scores and engagement data
    """
    import random
    
    if not source_ids:
        return []
    
    # Get total count first for fallback
    or_filter = ",".join(f"source_id.eq.{sid}" for sid in source_ids)
    count_result = supabase.table("source_tweets").select("id", count="exact").or_(or_filter).execute()
    total_count = count_result.count or 0
    
    # If few tweets, return all (no need for similarity search)
    if total_count <= 50:
        result = supabase.table("source_tweets").select("id, content, likes, retweets, source_id").or_(or_filter).order("likes", desc=True).limit(50).execute()
        tweets = [{"content": t["content"], "likes": t.get("likes", 0), "retweets": t.get("retweets", 0), "similarity": 1.0} for t in (result.data or [])]
        # Filter by content type
        if content_type == "reply":
            tweets = [t for t in tweets if _is_reply(t["content"])] or tweets
        else:
            tweets = [t for t in tweets if not _is_reply(t["content"])] or tweets
        return tweets[:limit]
    
    # Embed the query
    try:
        query_embedding = embed_batch([query_text])[0]
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        result = supabase.table("source_tweets").select("id, content, likes, retweets, source_id").or_(or_filter).order("likes", desc=True).limit(limit).execute()
        return [{"content": t["content"], "likes": t.get("likes", 0), "retweets": t.get("retweets", 0), "similarity": 0.0} for t in (result.data or [])]
    
    # Fetch top 50 candidates for diversity sampling
    fetch_count = max(limit * 3, 50)
    
    # Call the pgvector similarity function
    try:
        result = supabase.rpc("match_source_tweets", {
            "query_embedding": query_embedding,
            "match_source_ids": source_ids,
            "match_threshold": threshold,
            "match_count": fetch_count
        }).execute()
        
        candidates = [{"content": t["content"], "likes": t.get("likes", 0), "retweets": t.get("retweets", 0), "similarity": t.get("similarity", 0)} for t in (result.data or [])]
    except Exception as e:
        logger.error(f"Similarity search failed: {e}")
        result = supabase.table("source_tweets").select("id, content, likes, retweets, source_id").or_(or_filter).order("likes", desc=True).limit(fetch_count).execute()
        candidates = [{"content": t["content"], "likes": t.get("likes", 0), "retweets": t.get("retweets", 0), "similarity": 0.0} for t in (result.data or [])]
    
    if not candidates:
        return []
    
    # (b) Tweet type filtering
    if content_type == "reply":
        filtered = [t for t in candidates if _is_reply(t["content"])]
    else:
        filtered = [t for t in candidates if not _is_reply(t["content"])]
    # Fallback to all if filter yields too few
    if len(filtered) < 5:
        filtered = candidates
    
    # (a) Engagement weighting - compute combined scores
    for t in filtered:
        t["combined_score"] = _compute_combined_score(t["similarity"], t["likes"], t["retweets"])
    
    # Sort by combined score
    filtered.sort(key=lambda t: t["combined_score"], reverse=True)
    
    # (b) Diversity sampling: from top candidates, randomly sample `limit`
    # Take top pool (2x limit) then randomly pick from it
    pool_size = min(len(filtered), limit * 2)
    pool = filtered[:pool_size]
    
    if len(pool) <= limit:
        selected = pool
    else:
        # Always include top 5 (best matches), randomly sample rest
        top_guaranteed = pool[:5]
        rest_pool = pool[5:]
        random_picks = random.sample(rest_pool, min(limit - 5, len(rest_pool)))
        selected = top_guaranteed + random_picks
    
    # Sort final selection by combined_score for prompt coherence
    selected.sort(key=lambda t: t["combined_score"], reverse=True)
    
    logger.info(f"RAG: {len(candidates)} candidates → {len(filtered)} after type filter → {len(selected)} selected (type={content_type})")
    
    return selected


if __name__ == "__main__":
    main()
