-- 013 — DB-side reject of tweet_feed writes for deactivated batches.
--
-- A1 audit (2026-06-07): tr_haber + spor + ai_tech rows kept landing
-- in tweet_feed at 06:25 UTC every cycle despite their trend_x_sources
-- rows being is_active=false. The Python fetcher's get_active_batches()
-- correctly filtered; the writes were coming from an upstream n8n
-- workflow that ignored is_active and consulted a legacy hardcoded
-- account list. Two writers, one source of truth — splitable surfaces.
--
-- This trigger collapses both paths into one DB-side guard. Any
-- INSERT or UPDATE OF batch_type that names a batch_type with zero
-- is_active=true rows in trend_x_sources is rejected with a
-- check_violation. The two free streams that don't live in
-- trend_x_sources (monitor / radar) are whitelisted.

CREATE OR REPLACE FUNCTION tweet_feed_reject_inactive_batch()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.batch_type IN ('monitor', 'radar') THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1 FROM trend_x_sources
        WHERE batch_type = NEW.batch_type
          AND is_active  = TRUE
    ) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION
        'tweet_feed insert/update rejected: batch_type=% has no active rows in trend_x_sources. '
        'If this is a legitimate new batch, add an is_active=true row to trend_x_sources first.',
        NEW.batch_type
        USING ERRCODE = 'check_violation';
END;
$$;

DROP TRIGGER IF EXISTS trg_tweet_feed_reject_inactive_batch ON tweet_feed;
CREATE TRIGGER trg_tweet_feed_reject_inactive_batch
    BEFORE INSERT OR UPDATE OF batch_type ON tweet_feed
    FOR EACH ROW
    EXECUTE FUNCTION tweet_feed_reject_inactive_batch();
