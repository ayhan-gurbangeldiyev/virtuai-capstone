"""LangGraph StateGraph wiring — 5 roles + supervisor + interrupt + commit.

Topology:
    START → supervisor → (route_to_role)
        ├─ ceo  → (route_after_role) → interrupt | supervisor
        ├─ cpo  → (route_after_role) → interrupt | supervisor
        ├─ cbpo → (route_after_role) → interrupt | supervisor
        ├─ cfo  → (route_after_role) → interrupt | supervisor
        └─ cro  → (route_after_role) → interrupt | supervisor
    interrupt → commit_decisions → END
    supervisor → commit_decisions (when no more attendees) → END
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import (
    commit_decisions_node,
    human_approval_interrupt,
    route_after_role,
    route_to_role,
    supervisor_node,
)
from .state import ExecState


def _load_role_nodes(*, skeleton: bool):
    if skeleton:
        from .roles.skeletons import cbpo_node, ceo_node, cfo_node, cpo_node, cro_node
    else:
        from .roles.llm_nodes import cbpo_node, ceo_node, cfo_node, cpo_node, cro_node
    return ceo_node, cpo_node, cbpo_node, cfo_node, cro_node


def build_graph(checkpointer, *, skeleton: bool = False):
    """Compile the executive graph with the given checkpointer.

    Pass `skeleton=True` to use no-op role stubs (no LLM calls). Default uses
    the LLM-backed nodes from `roles.llm_nodes` (Gemini 3 Flash via OpenRouter).
    """
    ceo_node, cpo_node, cbpo_node, cfo_node, cro_node = _load_role_nodes(skeleton=skeleton)
    g = StateGraph(ExecState)

    # Nodes
    g.add_node("supervisor", supervisor_node)
    g.add_node("ceo", ceo_node)
    g.add_node("cpo", cpo_node)
    g.add_node("cbpo", cbpo_node)
    g.add_node("cfo", cfo_node)
    g.add_node("cro", cro_node)
    g.add_node("human_approval", human_approval_interrupt)
    g.add_node("commit_decisions", commit_decisions_node)

    # Entry
    g.add_edge(START, "supervisor")

    # Supervisor → role | done
    g.add_conditional_edges(
        "supervisor",
        route_to_role,
        {
            "CEO": "ceo",
            "CPO": "cpo",
            "CBPO": "cbpo",
            "CFO": "cfo",
            "CRO": "cro",
            "done": "commit_decisions",
        },
    )

    # Each role → interrupt (threshold breach) | back to supervisor
    for role in ("ceo", "cpo", "cbpo", "cfo", "cro"):
        g.add_conditional_edges(
            role,
            route_after_role,
            {"interrupt": "human_approval", "back": "supervisor"},
        )

    # After interrupt resume, return to supervisor so remaining roles can still speak
    g.add_edge("human_approval", "supervisor")
    g.add_edge("commit_decisions", END)

    return g.compile(checkpointer=checkpointer)
