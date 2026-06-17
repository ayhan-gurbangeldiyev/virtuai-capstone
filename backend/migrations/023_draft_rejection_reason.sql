-- 023_draft_rejection_reason.sql
-- 2026-06-12 (Berkay): compliance/gate reddi DB'ye görünür olsun — "bu haber
-- niye postlanmadı" her zaman izlenebilsin. flow.py skip_complete artık
-- auto_rejected draft yazınca compliance.rejection_reason'ı buraya yazar.
ALTER TABLE daily_drafts ADD COLUMN IF NOT EXISTS rejection_reason text;
