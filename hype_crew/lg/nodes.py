"""Faz 1 — ana CrewAI Flow'un LangGraph node sarmalayıcıları (strangler/wrap-first).

MANTIK YENİDEN YAZILMAZ. Node'lar flow.py'daki kanıtlanmış metodları çağırır.

İKİ ÖNEMLİ TASARIM KARARI (runtime testiyle doğrulandı):
1) TEK cf/run: `make_nodes(cf)` run başına TEK, düzgün init'li AutonomousContentFlow()
   örneği alır (graph.py kurar). `__new__` ile init ATLAMAK CrewAI 1.14.4'te yetmez —
   `Flow.state` property'si `StateProxy(self._state, self._state_lock)` döndürür ve
   _state_lock + diğer internals yalnız gerçek __init__'te oluşur. Her node cf._state'i
   gelen LangGraph state'iyle değiştirir → tek init (15 init israfı yok), resume-güvenli
   (state checkpointer'dan gelir; cf taze süreçte yeniden kurulur).
2) Node dict döndürür: LangGraph 1.2.x pydantic-state'te node'lardan dict bekler
   (HypeFlowState instance reddedilir). `_updates(cf)` state'in TÜM alanlarını dict
   olarak verir; nested alt-objeler (trend/plan/...) model_dump YAPILMADAN olduğu gibi
   geçer (kayıpsız) → LangGraph aynı-tip alanlara merge eder. Graph sıralı (tek-yazıcı)
   olduğundan tam-alan döndürmek güvenli; reducer gerekmez.

NOT: flow.py metodları içindeki asyncio.run() adacıkları (write/visual/video/publish)
node'ları SYNC tutmayı zorunlu kılar → graph SYNC invoke edilir (graph.py).

Router'lar tam dal string'ini döndürür; add_conditional_edges map'leri string→node
çevirir (graph.py). İş-node'ları _updates(cf) döndürür.
"""
from __future__ import annotations

from flow import AutonomousContentFlow  # noqa: F401  (tip + reuse)


def _updates(cf) -> dict:
    """Güncel cf._state'in tüm alanlarını LangGraph merge'i için dict olarak ver.
    Nested pydantic alt-objeler olduğu gibi (kayıpsız) geçer."""
    s = cf._state
    return {k: getattr(s, k) for k in type(s).model_fields}


def make_nodes(cf: AutonomousContentFlow) -> dict:
    """Verilen TEK cf örneği üstüne bağlı node + router callable'larını üret.
    Her çağrı cf._state'i gelen state ile değiştirir, mevcut flow.py metodunu
    çalıştırır, iş-node'larında _updates(cf) döndürür / router'larda dal string'i."""

    def _set(state) -> None:
        # Flow.state, ._state üstünde @property → setattr doğrudan ._state'e yazar
        object.__setattr__(cf, "_state", state)

    # ── iş node'ları (10) ──
    def node_initialize(state):
        _set(state)
        cf.initialize()          # dönüş (account_id) yok sayılır; state'te var
        return _updates(cf)

    def node_run_crew(state):
        _set(state)
        cf.run_crew(cf._state.account_id)
        return _updates(cf)

    def node_write(state):
        _set(state)
        cf.write_via_typehype()
        return _updates(cf)

    def node_compliance(state):
        _set(state)
        cf.run_compliance()
        return _updates(cf)

    def node_visual(state):
        _set(state)
        cf.generate_visual()
        return _updates(cf)

    def node_video(state):
        _set(state)
        cf.generate_video()
        return _updates(cf)

    def node_publish(state):
        _set(state)
        cf.publish_to_drafts()
        return _updates(cf)

    def node_dry_run_complete(state):
        _set(state)
        cf.dry_run_complete()
        return _updates(cf)

    def node_skip_complete(state):
        _set(state)
        cf.skip_complete()
        return _updates(cf)

    def node_fail_complete(state):
        _set(state)
        cf.fail_complete()
        return _updates(cf)

    # ── router'lar (5) — flow.py route_after_* tam string'i döndürür ──
    def route_after_crew(state):
        _set(state)
        return cf.route_after_crew()

    def route_after_write(state):
        _set(state)
        return cf.route_after_write()

    def route_after_compliance(state):
        _set(state)
        return cf.route_after_compliance()

    def route_after_visual(state):
        _set(state)
        return cf.route_after_visual()

    def route_after_video(state):
        _set(state)
        return cf.route_after_video()

    return {
        "node_initialize": node_initialize,
        "node_run_crew": node_run_crew,
        "node_write": node_write,
        "node_compliance": node_compliance,
        "node_visual": node_visual,
        "node_video": node_video,
        "node_publish": node_publish,
        "node_dry_run_complete": node_dry_run_complete,
        "node_skip_complete": node_skip_complete,
        "node_fail_complete": node_fail_complete,
        "route_after_crew": route_after_crew,
        "route_after_write": route_after_write,
        "route_after_compliance": route_after_compliance,
        "route_after_visual": route_after_visual,
        "route_after_video": route_after_video,
    }
