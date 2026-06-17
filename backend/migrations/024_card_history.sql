-- 022_card_history.sql — SÖZLÜK/SENCE? kart tekrar-önleme (dedup) defteri.
-- 13 Haz 2026 (Berkay): yardımcı kartların içeriği LLM üretir; aynı terim/soru
-- yakın zamanda tekrar edilmesin diye kullanılan içerik buraya kaydedilir.
-- card_kind ∈ {'dictionary','question'}. key_text = normalize edilmiş terim/soru.

CREATE TABLE IF NOT EXISTS card_history (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id  uuid,
    card_kind   text NOT NULL,
    key_text    text NOT NULL,            -- dedup anahtarı (lower/trim terim ya da soru)
    content     text,                     -- tam içerik (terim+açıklama ya da soru)
    trend_id    uuid,                     -- habere bağlıysa
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_card_history_lookup
    ON card_history (account_id, card_kind, created_at DESC);
