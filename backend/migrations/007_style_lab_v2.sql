-- Style Lab v2: Hibrit Stil Klonlama + Algoritma Entegrasyonu
-- Sprint 0: DB Migration

-- ============================================================
-- source_tweets: Yeni kolonlar
-- ============================================================
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS tweet_type TEXT DEFAULT 'original';
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS engagement_score FLOAT;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS algo_score FLOAT;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS word_count INT;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS has_link BOOLEAN DEFAULT FALSE;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS language TEXT;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS views BIGINT;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS bookmarks INT DEFAULT 0;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS quotes INT DEFAULT 0;

-- Index for embedding similarity search (if not exists)
-- Note: embedding column already exists as vector(1536)
CREATE INDEX IF NOT EXISTS idx_source_tweets_embedding 
  ON source_tweets USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_source_tweets_source_engagement 
  ON source_tweets (source_id, engagement_score DESC);

CREATE INDEX IF NOT EXISTS idx_source_tweets_source_algo 
  ON source_tweets (source_id, algo_score DESC);

-- ============================================================
-- style_profiles: Yeni kolonlar
-- ============================================================
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS viral_patterns JSONB DEFAULT '{}';
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS constraints JSONB DEFAULT '{}';
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS algo_insights JSONB DEFAULT '{}';
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS tweet_count INT DEFAULT 0;
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS avg_engagement FLOAT;
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS profile_version INT DEFAULT 1;
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ============================================================
-- pgvector: Similarity search function
-- ============================================================
CREATE OR REPLACE FUNCTION match_source_tweets(
    query_embedding vector(1536),
    source_id_param UUID,
    match_count INT DEFAULT 20
) RETURNS TABLE (
    id UUID,
    content TEXT,
    likes INT,
    retweets INT,
    replies INT,
    engagement_score FLOAT,
    algo_score FLOAT,
    tweet_type TEXT,
    word_count INT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        st.id, st.content, st.likes, st.retweets, st.replies,
        st.engagement_score, st.algo_score, st.tweet_type, st.word_count,
        1 - (st.embedding <=> query_embedding) AS similarity
    FROM source_tweets st
    WHERE st.source_id = source_id_param
        AND st.embedding IS NOT NULL
    ORDER BY st.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Multi-source variant (for profiles with multiple sources)
CREATE OR REPLACE FUNCTION match_source_tweets_multi(
    query_embedding vector(1536),
    source_ids UUID[],
    match_count INT DEFAULT 20
) RETURNS TABLE (
    id UUID,
    content TEXT,
    likes INT,
    retweets INT,
    replies INT,
    engagement_score FLOAT,
    algo_score FLOAT,
    tweet_type TEXT,
    word_count INT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        st.id, st.content, st.likes, st.retweets, st.replies,
        st.engagement_score, st.algo_score, st.tweet_type, st.word_count,
        1 - (st.embedding <=> query_embedding) AS similarity
    FROM source_tweets st
    WHERE st.source_id = ANY(source_ids)
        AND st.embedding IS NOT NULL
    ORDER BY st.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
