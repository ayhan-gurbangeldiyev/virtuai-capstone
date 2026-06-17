-- raw_signals.url'e UNIQUE constraint ekle (dedup icin gerekli)
-- PostgREST resolution=ignore-duplicates bu constraint'e dayanir
ALTER TABLE raw_signals ADD CONSTRAINT raw_signals_url_unique UNIQUE (url);

-- rss_feeds tablosuna error_count increment fonksiyonu
CREATE OR REPLACE FUNCTION increment_feed_error_count(feed_id UUID)
RETURNS void AS $$
BEGIN
  UPDATE rss_feeds
  SET error_count = error_count + 1,
      health_score = GREATEST(0, health_score - 10)
  WHERE id = feed_id;
END;
$$ LANGUAGE plpgsql;
