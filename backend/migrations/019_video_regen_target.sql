-- 019 (2026-06-10) — image_regen_jobs.rejection_target CHECK'ine 'video' eklendi.
-- Route POST /hype/drafts/{id}/regen-video baştan beri rejection_target='video'
-- yazıyordu ama constraint yalnız image|both tanıyordu → UI'daki "videoyu
-- düzelt" akışı insert'te 23514 ile patlıyordu (Fable 5 TTS diakritik
-- re-render'ı sırasında keşfedildi). Prod'a 2026-06-10 03:37 UTC'de elle
-- uygulandı; bu dosya kayıt içindir.

ALTER TABLE image_regen_jobs DROP CONSTRAINT image_regen_jobs_rejection_target_check;
ALTER TABLE image_regen_jobs ADD CONSTRAINT image_regen_jobs_rejection_target_check
  CHECK (rejection_target = ANY (ARRAY['image'::text, 'both'::text, 'video'::text]));
