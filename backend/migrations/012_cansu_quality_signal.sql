-- 012 — capture a quality signal per draft, not just publish/reject.
--
-- Problem this addresses: the faithfulness gate proves Cansu doesn't
-- FABRICATE; nothing yet measures whether she writes GOOD editorial.
-- hype_feedback already records quality-class rejection categories
-- (sounds_like_ai / shallow_insight / off_voice / ton_steril_ai_kelime
-- / yapi_sorunu_ozet_yorum / tone_too_corporate), but they were being
-- discarded from the operator scoreboards.
--
-- Two minimal additions:
--   (a) hype_feedback.edit_distance_chars — Levenshtein-style distance
--       between Cansu's draft and the operator's final content. High
--       distance on an approve = Cansu wrote poorly enough that the
--       operator rewrote heavily.
--   (b) hype_feedback.operator_quality_verdict — text. Allowed values:
--         'publishable_as_is' | 'needed_minor_edit' | 'needed_major_edit'
--         | 'discarded_quality' | NULL (operator skipped)
--       Set by the approve / reject routes from server-derived context
--       (e.g. quality-class rejection_category maps to discarded_quality;
--       low edit_distance → publishable_as_is; high edit_distance →
--       needed_major_edit). Operator UI can override later via PATCH.
--
-- Plus a rolling 14-day view that the Home / Quality dashboards can read
-- without re-computing on every page load.

BEGIN;

ALTER TABLE hype_feedback
    ADD COLUMN IF NOT EXISTS edit_distance_chars INTEGER,
    ADD COLUMN IF NOT EXISTS operator_quality_verdict TEXT
        CHECK (operator_quality_verdict IS NULL
            OR operator_quality_verdict IN (
                'publishable_as_is',
                'needed_minor_edit',
                'needed_major_edit',
                'discarded_quality'
            ));

CREATE INDEX IF NOT EXISTS idx_hype_feedback_account_quality
    ON hype_feedback (account_id, created_at DESC, operator_quality_verdict);

-- Rolling 14-day quality-acceptance view, per account.
-- approve_on_quality_rate = approves with verdict='publishable_as_is' / total approves.
-- median_edit_distance = approximate median over approved rows that carry a distance.
CREATE OR REPLACE VIEW v_cansu_quality_acceptance AS
WITH base AS (
    SELECT
        account_id,
        action,
        rejection_category,
        operator_quality_verdict,
        edit_distance_chars,
        created_at
    FROM hype_feedback
    WHERE created_at > NOW() - INTERVAL '14 days'
),
agg AS (
    SELECT
        account_id,
        COUNT(*) FILTER (WHERE action = 'approved')                  AS approves_14d,
        COUNT(*) FILTER (WHERE action = 'approved'
                          AND operator_quality_verdict = 'publishable_as_is') AS pub_as_is_14d,
        COUNT(*) FILTER (WHERE action = 'approved'
                          AND operator_quality_verdict = 'needed_minor_edit') AS minor_edit_14d,
        COUNT(*) FILTER (WHERE action = 'approved'
                          AND operator_quality_verdict = 'needed_major_edit') AS major_edit_14d,
        COUNT(*) FILTER (WHERE action = 'rejected'
                          AND rejection_category IN (
                              'sounds_like_ai',
                              'shallow_insight',
                              'off_voice',
                              'ton_steril_ai_kelime',
                              'yapi_sorunu_ozet_yorum',
                              'tone_too_corporate',
                              'haber_yanlis_aktarim'
                          ))                                          AS quality_rejects_14d,
        COUNT(*) FILTER (WHERE action = 'rejected')                  AS total_rejects_14d,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY edit_distance_chars)
            FILTER (WHERE action = 'approved' AND edit_distance_chars IS NOT NULL)
                                                                      AS median_edit_distance_chars
    FROM base
    GROUP BY account_id
)
SELECT
    account_id,
    approves_14d,
    pub_as_is_14d,
    minor_edit_14d,
    major_edit_14d,
    quality_rejects_14d,
    total_rejects_14d,
    median_edit_distance_chars,
    CASE WHEN (approves_14d + total_rejects_14d) > 0
         THEN (pub_as_is_14d::float / (approves_14d + total_rejects_14d))
         ELSE NULL END AS approve_on_quality_rate
FROM agg;

COMMIT;
