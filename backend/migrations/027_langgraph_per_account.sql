-- 027 — Per-account LangGraph anahtarı (env-genel flag yerine DB-wins override).
-- Additive + nullable: NULL → env HYPE_LANGGRAPH_ENABLED fallback (config.effective_langgraph_enabled).
-- Mevcut davranış DEĞİŞMEZ (env ON + tüm değerler NULL → herkes ON, bugünküyle ayni).
-- Per-account override yalnız açık değer yazılınca devreye girer (örn. diğer 2 hesap
-- unfreeze edilmeden önce onları FALSE'a sabitlemek için).
ALTER TABLE hype_account_config
    ADD COLUMN IF NOT EXISTS langgraph_enabled boolean;

COMMENT ON COLUMN hype_account_config.langgraph_enabled IS
    'Per-account LangGraph override; NULL → env HYPE_LANGGRAPH_ENABLED fallback (config.effective_langgraph_enabled). runner branch + flow write-ahead AYNI değeri okur.';
