-- 014 — editorial_lead_judgments.lead_outcome (C4 reframe).
--
-- Stores the outcome of each editor's-desk judgment so the
-- "Seçimler" page doesn't recompute "accept vs refuse" on every
-- request. Enum:
--   covered              — a draft was written for the lead trend
--   covered_published    — and that draft has a release_url
--   refused_dedup        — lead was a re-coverage; skipped
--   refused_gate         — gate blocked the draft (HARD_BLOCK / ERROR)
--   refused_other        — Lever A or downstream skipped without coverage
--   pending              — judgment exists but downstream not yet complete
-- The backfill assigns initial values from observable state today.

ALTER TABLE editorial_lead_judgments
    ADD COLUMN IF NOT EXISTS lead_outcome TEXT
        CHECK (lead_outcome IS NULL OR lead_outcome IN (
            'covered',
            'covered_published',
            'refused_dedup',
            'refused_gate',
            'refused_other',
            'pending'
        ));

CREATE INDEX IF NOT EXISTS idx_elj_account_outcome
    ON editorial_lead_judgments (account_id, judgment_date DESC, lead_outcome);

WITH base AS (
    SELECT
        j.id AS judgment_id,
        j.lead_trend_id,
        j.account_id,
        j.dry_run,
        (
            SELECT EXISTS (
                SELECT 1 FROM daily_drafts d
                WHERE d.trend_id = j.lead_trend_id
                  AND d.account_id = j.account_id
            )
        ) AS has_draft,
        (
            SELECT EXISTS (
                SELECT 1 FROM daily_drafts d
                WHERE d.trend_id = j.lead_trend_id
                  AND d.account_id = j.account_id
                  AND d.release_url IS NOT NULL
            )
        ) AS has_published
    FROM editorial_lead_judgments j
    WHERE j.lead_outcome IS NULL
)
UPDATE editorial_lead_judgments AS j
SET lead_outcome = CASE
    WHEN b.dry_run THEN 'pending'
    WHEN b.has_published THEN 'covered_published'
    WHEN b.has_draft     THEN 'covered'
    ELSE 'refused_other'
END
FROM base b
WHERE j.id = b.judgment_id;
