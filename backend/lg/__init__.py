"""backend/lg — X-ingestion için LangGraph dayanıklılık kabuğu.

İçerik pipeline'ının `hype_crew/lg/` motorunun backend-aynası. Aynı Supabase
`langgraph` checkpoint şemasını paylaşır (motor/gözlem simetrisi) ama backend
kendi venv'inde kendi langgraph kopyasını çalıştırır (iki ayrı venv gerçeği).

Flag: TREND_INGEST_LANGGRAPH_ENABLED (default OFF). Kapalıyken bu paket hiç
import edilmez → mevcut trend_engine.refresh_all() yolu birebir korunur.
"""
