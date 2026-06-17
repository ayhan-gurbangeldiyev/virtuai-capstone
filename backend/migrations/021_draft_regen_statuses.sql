-- 021 (2026-06-10) — daily_drafts_status_check'e regen_done + regen_failed eklendi.
-- Video regen worker'ı persist'te status='regen_done' yazıyor, watchdog
-- 'regen_failed' yazıyor — ikisi de constraint'te yoktu: worker'ın draft
-- UPDATE'i 23514 ile sessizce reddediliyor, yeni video storage'da kalıp
-- draft eski videoyu göstermeye devam ediyordu (Fable 5 regen vakası).
-- Prod'a 2026-06-10 11:1x UTC elle uygulandı; bu dosya kayıt içindir.
ALTER TABLE daily_drafts DROP CONSTRAINT daily_drafts_status_check;
ALTER TABLE daily_drafts ADD CONSTRAINT daily_drafts_status_check CHECK (status = ANY (ARRAY[
  'pending'::text,'pending_review'::text,'edited'::text,'published'::text,
  'dismissed'::text,'auto_approved'::text,'auto_rejected'::text,
  'auto_scheduled'::text,'approved'::text,'deleted'::text,
  'archived_quality_sweep'::text,'regen_done'::text,'regen_failed'::text]));
