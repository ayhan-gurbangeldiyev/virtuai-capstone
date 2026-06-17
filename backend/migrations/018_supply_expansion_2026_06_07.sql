-- Supply expansion 2026-06-07.
-- Editor's-desk was early-exiting most hours because fresh AI signal was
-- thin (ai_core fetching only 7 official lab accounts; ai_news_en relying
-- on 11 commentators; ai_news_tr down to one handle). XQuik-verified 7
-- of Berkay's 10 candidates and added them; dropped 3 dead/noisy.
--
-- Per-account verdict (gate proof):
--   ai_news_en
--     @karpathy       — verified (verified=true, 13/15 AI, 0 in 7d) — KEEP
--                       (gold but infrequent; Anthropic join announcement
--                        landed in last batch)
--     @levelsio       — verified (12/15 AI, 15/15 recent, 890k followers) — ADD
--     @jeremyphoward  — verified (11/15 AI, 0 in 7d, 313k) — KEEP
--                       (low frequency but high-signal launches)
--     @hardmaru       — verified (Sakana AI CEO, 13/15 AI, 3 recent, 412k) — ADD
--     @nearcyan       — DROP (11/15 AI but 0 recent; abandoning Twitter)
--   ai_core
--     @sama           — verified (OpenAI CEO, 9/15 AI, 7 recent, 5M) — ADD
--     @perplexity_ai  — verified (11/15 AI, 7 recent, 492k) — ADD
--     @MistralAI      — verified (12/15 AI, 0 in 7d) — KEEP (launches matter)
--   ai_news_tr
--     @deeplearningtr — DROP (NO_TWEETS via XQuik — handle doesn't return)
--     @aiturkiye      — DROP (NO_TWEETS via XQuik — same)
--     also probed: deeplearningturkiye=NOT_FOUND · yapayzekatr=64 followers
--                  (abandoned) · ai_turkiye/AI_Turkiye/altayb/datasciencetr
--                  =0 tweets · yapayZekaCom=NOT_FOUND
--     Conclusion: the TR AI Twitter scene is genuinely thin. The current
--     @semihdev (which Berkay called dead) is actually alive — Teknasyon's
--     Tech Culture & AI Enablement Manager, 14.7k followers, posting
--     Turkish AI content. Kept as-is.
--
-- Trigger trg_tweet_feed_reject_inactive_batch already in place stays:
-- it rejects inserts for any batch_type whose trend_x_sources row is
-- inactive, so adding noise sources accidentally still requires a
-- deliberate is_active=true flip.

INSERT INTO public.trend_x_sources (batch_type, username, is_active, fetch_limit)
VALUES
  ('ai_news_en', 'karpathy',     true, 30),
  ('ai_news_en', 'levelsio',     true, 30),
  ('ai_news_en', 'jeremyphoward', true, 30),
  ('ai_news_en', 'hardmaru',     true, 30),
  ('ai_core',    'sama',         true, 50),
  ('ai_core',    'perplexity_ai', true, 50),
  ('ai_core',    'MistralAI',    true, 50)
ON CONFLICT DO NOTHING;
