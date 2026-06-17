"""LangGraph durability/resume katmanı (Faz 0+).

CrewAI Flow'dan LangGraph'a kademeli (strangler) geçiş. Bu paket CrewAI yolunu
DEĞİŞTİRMEZ — yalnız `langgraph_enabled` flag açıkken devreye girer.

- checkpointer.py — PostgresSaver (prod, `langgraph` şeması) ↔ AsyncSqliteSaver
  (dev/spike, secret gerekmez) seçici factory.
- card_graph.py — Faz 0 spike: kart pipeline'ı (produce→publish) LangGraph + resume.
"""
