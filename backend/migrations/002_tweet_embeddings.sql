-- Migration 002: Tweet Embeddings for RAG-based Style Cloning
-- Run in Supabase Dashboard → SQL Editor

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add embedding column to source_tweets
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- 3. Create HNSW index for cosine similarity search
CREATE INDEX IF NOT EXISTS idx_source_tweets_embedding 
ON source_tweets USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 4. Create a function for similarity search
CREATE OR REPLACE FUNCTION match_source_tweets(
  query_embedding vector(1536),
  match_source_ids uuid[],
  match_threshold float DEFAULT 0.3,
  match_count int DEFAULT 30
)
RETURNS TABLE (
  id uuid,
  source_id uuid,
  content text,
  likes int,
  retweets int,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    st.id,
    st.source_id,
    st.content,
    st.likes,
    st.retweets,
    1 - (st.embedding <=> query_embedding) AS similarity
  FROM source_tweets st
  WHERE st.source_id = ANY(match_source_ids)
    AND st.embedding IS NOT NULL
    AND 1 - (st.embedding <=> query_embedding) > match_threshold
  ORDER BY st.embedding <=> query_embedding
  LIMIT match_count;
$$;
