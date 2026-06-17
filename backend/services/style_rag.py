"""Style RAG v2 - Smart few-shot example selection using pgvector"""
import logging
import re
import math
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


async def get_style_examples(
    topic: str,
    source_id: str,
    supabase_client,
    openai_client,
    limit: int = 15,
    strategy: str = "hybrid"  # similarity, viral, hybrid
) -> List[dict]:
    """
    Smart few-shot example selection for style-consistent content generation.
    
    Strategies:
        - similarity: Pure cosine similarity to topic
        - viral: Highest engagement tweets
        - hybrid: Weighted mix of similarity + engagement + algo_score
    """
    try:
        if strategy == "viral":
            return await _get_viral_examples(source_id, supabase_client, limit)
        
        # Get topic embedding
        topic_embedding = await _get_embedding(topic, openai_client)
        if not topic_embedding:
            logger.warning("Failed to get topic embedding, falling back to viral strategy")
            return await _get_viral_examples(source_id, supabase_client, limit)
        
        # Get candidates via cosine similarity
        candidates = await _match_by_similarity(
            source_id, topic_embedding, supabase_client, candidate_count=20
        )
        
        if not candidates:
            logger.warning(f"No embedding matches for source {source_id}, falling back to viral")
            return await _get_viral_examples(source_id, supabase_client, limit)
        
        if strategy == "similarity":
            return candidates[:limit]
        
        # Hybrid scoring
        scored = _apply_hybrid_scoring(candidates)
        
        # Diversity filter
        diverse = _apply_diversity_filter(scored, limit)
        
        return diverse
        
    except Exception as e:
        logger.error(f"get_style_examples failed: {e}")
        return []


async def generate_embeddings_for_source(
    source_id: str,
    supabase_client,
    openai_client,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Generate embeddings for all source_tweets that don't have them yet.
    Returns stats about the operation.
    """
    stats = {"total": 0, "processed": 0, "errors": 0, "skipped": 0}
    
    try:
        # Fetch tweets without embeddings
        result = supabase_client.table("source_tweets") \
            .select("id, content") \
            .eq("source_id", source_id) \
            .is_("embedding", "null") \
            .limit(5000) \
            .execute()
        
        tweets = result.data if result.data else []
        stats["total"] = len(tweets)
        
        if not tweets:
            logger.info(f"No tweets need embeddings for source {source_id}")
            return stats
        
        logger.info(f"Generating embeddings for {len(tweets)} tweets (source: {source_id})")
        
        # Process in batches
        for i in range(0, len(tweets), batch_size):
            batch = tweets[i:i + batch_size]
            texts = [_clean_for_embedding(t["content"]) for t in batch]
            
            try:
                response = await openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts
                )
                
                # Update each tweet with its embedding
                for j, embedding_data in enumerate(response.data):
                    tweet_id = batch[j]["id"]
                    embedding = embedding_data.embedding
                    
                    try:
                        supabase_client.table("source_tweets") \
                            .update({"embedding": embedding}) \
                            .eq("id", tweet_id) \
                            .execute()
                        stats["processed"] += 1
                    except Exception as e:
                        logger.error(f"Failed to update embedding for tweet {tweet_id}: {e}")
                        stats["errors"] += 1
                
                logger.info(f"Batch {i // batch_size + 1}: {len(batch)} embeddings generated")
                
            except Exception as e:
                logger.error(f"Batch embedding generation failed: {e}")
                stats["errors"] += len(batch)
        
        logger.info(f"Embedding generation complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"generate_embeddings_for_source failed: {e}")
        stats["errors"] = -1
        return stats


# ═══════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════

async def _get_embedding(text: str, openai_client) -> Optional[List[float]]:
    """Get embedding for a text using OpenAI text-embedding-3-small"""
    try:
        cleaned = _clean_for_embedding(text)
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=[cleaned]
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


def _clean_for_embedding(text: str) -> str:
    """Clean text for embedding generation"""
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate to ~8000 chars (model limit safety)
    return text[:8000] if text else "empty"


async def _match_by_similarity(
    source_id: str,
    embedding: List[float],
    supabase_client,
    candidate_count: int = 20
) -> List[dict]:
    """Call Supabase RPC match_source_tweets for cosine similarity search"""
    try:
        result = supabase_client.rpc("match_source_tweets", {
            "query_embedding": embedding,
            "source_id_param": source_id,
            "match_count": candidate_count
        }).execute()
        
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"match_source_tweets RPC failed: {e}")
        return []


async def _get_viral_examples(
    source_id: str,
    supabase_client,
    limit: int = 8
) -> List[dict]:
    """Fallback: get highest engagement tweets"""
    try:
        result = supabase_client.table("source_tweets") \
            .select("id, content, likes, retweets, replies, algo_score, similarity") \
            .eq("source_id", source_id) \
            .order("likes", desc=True) \
            .limit(limit) \
            .execute()
        
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Viral examples fetch failed: {e}")
        return []


def _apply_hybrid_scoring(candidates: List[dict]) -> List[dict]:
    """
    Calculate hybrid_score = similarity*0.4 + normalized_engagement*0.35 + algo_score/100*0.25
    """
    if not candidates:
        return []
    
    # Find max engagement for normalization
    max_engagement = max(
        (c.get("likes", 0) + c.get("retweets", 0) * 2 + c.get("replies", 0))
        for c in candidates
    ) or 1
    
    for c in candidates:
        similarity = c.get("similarity", 0) or 0
        engagement = c.get("likes", 0) + c.get("retweets", 0) * 2 + c.get("replies", 0)
        normalized_engagement = engagement / max_engagement
        algo_score = (c.get("algo_score", 0) or 0) / 100.0
        
        c["hybrid_score"] = (
            similarity * 0.4 +
            normalized_engagement * 0.35 +
            algo_score * 0.25
        )
    
    candidates.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)
    return candidates


def _apply_diversity_filter(candidates: List[dict], limit: int) -> List[dict]:
    """
    Ensure diversity in selected examples:
    - Mix of short and long tweets
    - Mix of questions and statements
    - Different opening styles
    """
    if len(candidates) <= limit:
        return candidates
    
    selected = []
    short_count = 0  # <100 chars
    long_count = 0   # >=100 chars
    question_count = 0
    statement_count = 0
    seen_openings = set()
    
    for c in candidates:
        if len(selected) >= limit:
            break
        
        content = c.get("content", "")
        is_short = len(content) < 100
        is_question = "?" in content
        
        # Get first 3 words as opening signature
        words = content.strip().split()[:3]
        opening = " ".join(words).lower() if words else ""
        
        # Diversity checks
        half = limit // 2
        
        # Don't over-represent one length category
        if is_short and short_count >= half + 1:
            continue
        if not is_short and long_count >= half + 1:
            continue
        
        # Don't over-represent questions vs statements
        if is_question and question_count >= half + 1:
            continue
        
        # Avoid duplicate openings
        if opening in seen_openings and len(selected) > 2:
            continue
        
        selected.append(c)
        if is_short:
            short_count += 1
        else:
            long_count += 1
        if is_question:
            question_count += 1
        else:
            statement_count += 1
        seen_openings.add(opening)
    
    # If diversity filter was too strict, fill remaining slots
    if len(selected) < limit:
        for c in candidates:
            if c not in selected:
                selected.append(c)
                if len(selected) >= limit:
                    break
    
    return selected
