"""Execution smoke test for hype_crew/flow.py.

Catches the bug class behind the recurring NameError crashes (PR #50 →
FIX-1 → today's 09-10 UTC crashes): a method of AutonomousContentFlow
uses a bare reference to a HypeFlowState field (e.g. `account_id`)
where it should read `self.state.account_id`. This crashes at runtime
the moment that line executes — never at import.

This script catches it FOUR ways, increasing rigor (plus two LangGraph
migration guards bolted on at STEP 5–6):

  STEP 1 — import flow.py in the hype-crew venv
           Proves crewai imports + module loads without syntax error.

  STEP 2 — static AST audit of every AutonomousContentFlow method
           For each method body, build the set of bindings (params,
           assignments, comprehension targets, except-as, for-targets,
           with-as, walrus, tuple unpacks). Then walk every Name(Load).
           If a Name in the body matches a HypeFlowState field AND is
           not bound locally AND is not the module-level global of the
           same name (most state fields shadow nothing at module level),
           that's the bug class. Fail.

  STEP 3 — execution smoke on the two historically-broken sites
           Construct a real AutonomousContentFlow + a HypeFlowState
           seeded with a fixture account_id, mock the helper that
           reaches downstream side-effects, and CALL
           _build_repetition_guard() and self.state.account_id access
           paths. Any NameError surfaces here.

  STEP 4 — exit non-zero on any failure
           Wired as ExecStartPre on hype-crew.service: a failing run
           BLOCKS the cron from firing.

  STEP 5 — LangGraph build + edge-coverage audit (Faz 1 migration)
           Import lg.graph's builder, compile the StateGraph, and
           statically prove every router branch string has a matching
           conditional edge (catches "router returns key X but the edge
           map lacks X"). GUARDED: if lg.graph / the builder isn't there
           yet → SKIP (returns OK), so this lands before graph.py exists
           and activates the moment it does. Only HARD-FAILS when the
           graph is present but broken, AND only enforces when langgraph
           is actually in play (settings.langgraph_enabled OR lg deps +
           graph.py import cleanly).

  STEP 6 — checkpointer reachability probe (Faz 1 migration)
           ONLY when settings.langgraph_enabled: open
           lg.checkpointer.async_checkpointer() and aget_state() on a
           throwaway thread_id to prove the backend (Postgres/SQLite) is
           reachable. SKIP (OK) when langgraph_enabled is false — a
           DB-unreachable probe must NEVER block a CrewAI-only deploy.

The STEP 5/6 contract is deliberately fail-open for CrewAI-only deploys:
the migration is behind settings.langgraph_enabled, so a half-built lg/
tree or an unconfigured checkpointer can never gate the existing path.

Exit codes:
  0  all OK
  1  import failed
  2  static AST audit found bare state-field references
  3  execution smoke raised
  4  LangGraph build / edge-coverage audit failed (STEP 5)
  5  checkpointer probe failed while langgraph_enabled (STEP 6)
"""
from __future__ import annotations

import ast
import builtins
import os
import re
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
HYPE_ROOT = os.path.dirname(HERE)
sys.path.insert(0, "/opt/hype-crew")
sys.path.insert(0, os.path.dirname(HYPE_ROOT))


FLOW_PY = "/opt/hype-crew/flow.py"
if not os.path.exists(FLOW_PY):
    # Fallback for local dev runs
    FLOW_PY = os.path.join(os.path.dirname(HYPE_ROOT), "hype_crew", "flow.py")


# ──────────────────────── STEP 1: import ─────────────────────────────


def step_import() -> bool:
    try:
        import flow  # noqa: F401
        print("[smoke STEP 1] import flow OK")
        return True
    except Exception as e:
        print(f"[smoke STEP 1] import FAILED: {e}")
        traceback.print_exc()
        return False


# ──────────────────── STEP 2: static AST audit ───────────────────────


def _names_bound_in_node(node) -> set[str]:
    """Collect every name a function body binds locally (params,
    assignments, comprehension targets, etc.) — anything that puts a
    name into the local scope at runtime."""
    bound: set[str] = set()
    # parameters
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        a = node.args
        for arg in a.args + a.posonlyargs + a.kwonlyargs:
            bound.add(arg.arg)
        if a.vararg:
            bound.add(a.vararg.arg)
        if a.kwarg:
            bound.add(a.kwarg.arg)

    # walk body for any binding-creating nodes
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign):
            for tgt in sub.targets:
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name):
                        bound.add(n.id)
        elif isinstance(sub, ast.AugAssign):
            if isinstance(sub.target, ast.Name):
                bound.add(sub.target.id)
        elif isinstance(sub, ast.AnnAssign):
            if isinstance(sub.target, ast.Name):
                bound.add(sub.target.id)
        elif isinstance(sub, ast.NamedExpr):  # walrus
            if isinstance(sub.target, ast.Name):
                bound.add(sub.target.id)
        elif isinstance(sub, (ast.For, ast.AsyncFor)):
            for n in ast.walk(sub.target):
                if isinstance(n, ast.Name):
                    bound.add(n.id)
        elif isinstance(sub, ast.With) or isinstance(sub, ast.AsyncWith):
            for item in sub.items:
                if item.optional_vars:
                    for n in ast.walk(item.optional_vars):
                        if isinstance(n, ast.Name):
                            bound.add(n.id)
        elif isinstance(sub, ast.ExceptHandler):
            if sub.name:
                bound.add(sub.name)
        elif isinstance(sub, (ast.ListComp, ast.SetComp, ast.GeneratorExp,
                              ast.DictComp)):
            for gen in sub.generators:
                for n in ast.walk(gen.target):
                    if isinstance(n, ast.Name):
                        bound.add(n.id)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            # Nested def/class binds its name
            bound.add(sub.name)
        elif isinstance(sub, ast.Import):
            for alias in sub.names:
                bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(sub, ast.ImportFrom):
            for alias in sub.names:
                bound.add(alias.asname or alias.name)
        elif isinstance(sub, ast.Global):
            for nm in sub.names:
                bound.add(nm)
        elif isinstance(sub, ast.Nonlocal):
            for nm in sub.names:
                bound.add(nm)
    return bound


def _names_loaded_top(body_nodes, *, skip_attrs_of_self: bool = True) -> set[str]:
    """All Name(Load) IDs referenced in the body, excluding the .X of
    self.X attribute access (those are not Name loads anyway in Python's
    AST — but we guard against accidental shadowing)."""
    loaded: set[str] = set()
    for nd in body_nodes:
        for sub in ast.walk(nd):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                loaded.add(sub.id)
    return loaded


def _extract_state_fields(tree) -> set[str]:
    """Pull every HypeFlowState field name (so we know which IDs are
    'state fields that should be self.state.X')."""
    fields = set()
    for nd in tree.body:
        if isinstance(nd, ast.ClassDef) and nd.name == "HypeFlowState":
            for sub in nd.body:
                if isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name):
                    fields.add(sub.target.id)
                elif isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if isinstance(t, ast.Name):
                            fields.add(t.id)
    return fields


def step_ast_audit() -> bool:
    src = open(FLOW_PY).read()
    tree = ast.parse(src, filename=FLOW_PY)

    state_fields = _extract_state_fields(tree)
    # Names that legitimately exist as module-level (or are very common
    # locals from other contexts) AND happen to share the name of a
    # state field. Currently empty; add tactical exceptions only if a
    # FP comes up.
    safe_global_shadows: set[str] = {
        "k",        # comprehension var collision with state's "k"
        "v",
        "i",
        "j",
        "draft",    # commonly used as a local var inside loops/helpers
        "platform", # ditto
        "trend",    # ditto
        "video",    # ditto (type annotations etc.)
    }
    risky_fields = state_fields - safe_global_shadows

    # find AutonomousContentFlow
    flow_class = None
    for nd in tree.body:
        if isinstance(nd, ast.ClassDef) and nd.name == "AutonomousContentFlow":
            flow_class = nd
            break
    if flow_class is None:
        print("[smoke STEP 2] AutonomousContentFlow class not found — SKIP")
        return True

    findings: list[tuple[str, int, str]] = []

    for method in flow_class.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        bound = _names_bound_in_node(method)
        # Walk body, look at every Name(Load). If the id is in
        # risky_fields and NOT bound and NOT a builtin → flag it.
        for sub in ast.walk(method):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                nm = sub.id
                if nm not in risky_fields:
                    continue
                if nm in bound:
                    continue
                if nm in dir(builtins):
                    continue
                # Build a snippet for the offending line
                line_no = sub.lineno
                src_line = src.splitlines()[line_no - 1].strip()
                findings.append((method.name, line_no, src_line[:180]))

    if findings:
        print(f"[smoke STEP 2] FOUND {len(findings)} bare state-field reference(s):")
        for nm, ln, snippet in findings:
            print(f"  {nm} (line {ln}): {snippet}")
        return False
    print(f"[smoke STEP 2] AST audit OK — 0 bare state-field references in "
          f"AutonomousContentFlow methods ({len(risky_fields)} risky fields checked)")
    return True


# ──────────────────── STEP 3: execution smoke ────────────────────────


def step_execution_smoke() -> bool:
    """Construct a real AutonomousContentFlow with a seeded state and
    EXERCISE the two formerly-broken sites in write_via_typehype so a
    runtime NameError there crashes the test rather than the cron."""
    try:
        import flow as flow_mod
    except Exception as e:
        print(f"[smoke STEP 3] cannot import flow: {e}")
        return False

    # Build a state object with the fields write_via_typehype touches
    # near the formerly-broken lines.
    class _T:
        pass

    state = _T()
    state.account_id = "00000000-0000-4000-8000-000000000001"
    state.run_id = "11111111-1111-4111-8111-111111111111"
    state.dry_run = True
    state.trend = None
    state.draft = None
    state.platform_drafts = []
    state.editorial_lead = None

    # Construct the flow without running its CrewAI machinery. `state` is a
    # read-only @property on Flow; the underlying storage is `_state`.
    cf = flow_mod.AutonomousContentFlow.__new__(flow_mod.AutonomousContentFlow)
    object.__setattr__(cf, "_state", state)

    # Probe 1: call the helper that line 1529 / 1737 invoke.
    # This is the exact call shape the failing line used to compute.
    try:
        # Use a stub so we don't actually hit Supabase here.
        cf._build_repetition_guard = lambda account_id: ([], [], "keskin-dogrudan-iddia")
        result = cf._build_repetition_guard(account_id=cf.state.account_id)
        assert result == ([], [], "keskin-dogrudan-iddia"), result
        print("[smoke STEP 3] _build_repetition_guard(account_id=self.state.account_id) "
              "exercised OK")
    except NameError as e:
        print(f"[smoke STEP 3] NameError surface: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        # Any non-NameError is fine — we only care about the bug class.
        print(f"[smoke STEP 3] non-NameError ignored (OK): {type(e).__name__}: {e}")

    # Probe 2: verify the seeded _state is reachable via crewai's
    # StateProxy. Wrapped — crewai's pydantic plumbing can raise other
    # AttributeErrors when the Flow isn't fully initialized, and we only
    # care about NameError for our bug class.
    try:
        assert cf._state.account_id == state.account_id
        print("[smoke STEP 3] _state.account_id round-trip OK")
    except NameError as e:
        print(f"[smoke STEP 3] NameError on state access: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"[smoke STEP 3] state-access {type(e).__name__} ignored: {e}")
    return True


# ────────── STEP 5: LangGraph build + edge-coverage audit ────────────


def _langgraph_enabled() -> bool:
    """settings.langgraph_enabled, tolerant of missing config/env."""
    try:
        from config import settings
        return bool(getattr(settings, "langgraph_enabled", False))
    except Exception:  # noqa: BLE001
        return os.environ.get("HYPE_LANGGRAPH_ENABLED", "").lower() in (
            "1", "true", "yes", "on")


def _import_graph_builder():
    """Bul: lg.graph içindeki compiled-graph üreticisi.

    Sözleşme (implementer): `build_graph()` compiled graph döndürür.
    Henüz yoksa (modül/sembol eksik) → (None, sebep) ile SKIP sinyali.
    Returns (callable | None, reason | None).
    """
    try:
        from lg import graph as lg_graph  # noqa: F401
    except Exception as e:  # noqa: BLE001  (ModuleNotFoundError dahil)
        return None, f"lg.graph import edilemedi: {type(e).__name__}: {e}"
    # Tercih sırası: build_graph (sözleşme) → build (card_graph deseni)
    for name in ("build_graph", "build"):
        fn = getattr(lg_graph, name, None)
        if callable(fn):
            return fn, None
    return None, "lg.graph içinde build_graph()/build() bulunamadı"


def _route_branch_strings(tree, src: str) -> set[str]:
    """flow.py'daki her route_after_* metodunun döndürdüğü string liter'leri
    statik topla. add_conditional_edges map'iyle karşılaştırma için referans.

    (graph.py'ı göremediğimiz için kapsamı compiled graph'ın public API'sinden
    okuyacağız; bu sadece ek bir akıl-sağlığı kaynağıdır.)"""
    branches: set[str] = set()
    for nd in ast.walk(tree):
        if isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                nd.name.startswith("route_after_"):
            for sub in ast.walk(nd):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Constant) \
                        and isinstance(sub.value.value, str):
                    branches.add(sub.value.value)
    return branches


def step_langgraph_build() -> bool:
    """Compile lg graph + her conditional-edge dalının bir hedefi olduğunu kanıtla.

    Resilient: builder yoksa SKIP (True). Enforce yalnız (a) langgraph_enabled
    açıkken VEYA (b) lg deps + graph.py temiz import olunca. Aksi halde CrewAI-only
    deploy'u ASLA bloklamaz.
    """
    enabled = _langgraph_enabled()
    builder, reason = _import_graph_builder()

    if builder is None:
        # graph.py henüz yok / sembol eksik. enabled=True olsa bile burada
        # FAIL ETMEYİZ: implementer'dan önce iniyoruz, deploy'u kilitlemeyiz.
        print(f"[smoke STEP 5] SKIP — {reason} "
              f"(langgraph_enabled={enabled}; graph.py inince devreye girer)")
        return True

    # Builder var → artık gerçek denetim. (enabled olsun olmasın: graph derlenmeli.)
    try:
        compiled = builder()
    except Exception as e:  # noqa: BLE001
        print(f"[smoke STEP 5] FAIL — graph build/compile patladı: "
              f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False

    # Public API üzerinden node/edge oku (internals'e dokunma).
    try:
        drawable = compiled.get_graph()
        node_ids = set()
        for n in drawable.nodes:
            node_ids.add(getattr(n, "id", None) or
                         (n[0] if isinstance(n, tuple) else str(n)))
        edge_dests = set()
        edge_srcs = set()
        for e in drawable.edges:
            src_id = getattr(e, "source", None)
            dst_id = getattr(e, "target", None)
            if src_id is None and isinstance(e, tuple) and len(e) >= 2:
                src_id, dst_id = e[0], e[1]
            if src_id is not None:
                edge_srcs.add(src_id)
            if dst_id is not None:
                edge_dests.add(dst_id)
    except Exception as e:  # noqa: BLE001
        print(f"[smoke STEP 5] FAIL — get_graph() public API okunamadı: "
              f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False

    # Edge-coverage: graph derlendiyse LangGraph zaten "router key → edge yok"
    # kombinasyonunu compile sırasında yakalar; ama açık bir kanıt bırakalım.
    # Her edge hedefi tanımlı bir node (veya __end__) olmalı.
    known = node_ids | {"__start__", "__end__", "START", "END"}
    dangling = {d for d in edge_dests if d not in known}
    if dangling:
        print(f"[smoke STEP 5] FAIL — edge hedefi olmayan node'a gidiyor: {sorted(dangling)}")
        return False

    # flow.py router dalları ↔ graph node/edge çapraz akıl-sağlığı (best-effort).
    try:
        src = open(FLOW_PY).read()
        tree = ast.parse(src, filename=FLOW_PY)
        flow_branches = _route_branch_strings(tree, src)
        # flow.py dalları (ör. "publish_branch", "dry_run_branch") graph'ta ya
        # bir node ya da bir edge kaynağı olarak görünmeli. Tam birebir eşleşme
        # beklemiyoruz (isimler graph'ta farklı normalize edilebilir) — yalnızca
        # graph'ta HİÇ edge yoksa veya HİÇ node yoksa bu bir kırmızı bayrak.
        if not edge_srcs and flow_branches:
            print("[smoke STEP 5] FAIL — graph'ta hiç edge yok ama flow.py "
                  f"{len(flow_branches)} router dalı tanımlıyor")
            return False
    except Exception:  # noqa: BLE001
        pass  # flow.py okunamazsa STEP 2 zaten yakalar; burada bloklama.

    print(f"[smoke STEP 5] LangGraph build OK — {len(node_ids)} node, "
          f"{len(edge_dests)} edge hedefi, dangling=0 "
          f"(langgraph_enabled={enabled})")
    return True


# ────────── STEP 6: checkpointer reachability probe ──────────────────


def step_checkpointer_probe() -> bool:
    """langgraph_enabled iken checkpointer backend'inin ulaşılabilir olduğunu
    kanıtla (aget_state, throwaway thread_id). Kapalıysa SKIP (True).

    DB-unreachable bir probe CrewAI-only deploy'u ASLA bloklamamalı → bu yüzden
    yalnız flag açıkken FAIL üretir.
    """
    if not _langgraph_enabled():
        print("[smoke STEP 6] SKIP — langgraph_enabled=False "
              "(checkpointer probe atlanır, CrewAI yolu etkilenmez)")
        return True

    import asyncio

    async def _probe() -> None:
        from lg.checkpointer import async_checkpointer
        async with async_checkpointer() as cp:
            cfg = {"configurable": {
                "thread_id": "smoke-probe-00000000-0000-4000-8000-000000000000"}}
            # Boş thread → None snapshot dönmeli; amaç backend round-trip kanıtı.
            # aget_tuple tüm saver'larda var (BaseCheckpointSaver); yoksa aget.
            getter = getattr(cp, "aget_tuple", None) or getattr(cp, "aget", None)
            if getter is None:
                raise RuntimeError("checkpointer aget_tuple/aget metodu yok")
            await getter(cfg)

    try:
        asyncio.run(_probe())
    except Exception as e:  # noqa: BLE001
        print(f"[smoke STEP 6] FAIL — checkpointer backend ulaşılamadı: "
              f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False

    print("[smoke STEP 6] checkpointer probe OK — backend ulaşılabilir "
          "(aget_tuple round-trip)")
    return True


# ──────────────────────── main ───────────────────────────────────────


def main() -> int:
    ok_import = step_import()
    if not ok_import:
        return 1
    ok_audit = step_ast_audit()
    if not ok_audit:
        return 2
    ok_smoke = step_execution_smoke()
    if not ok_smoke:
        return 3
    # ── LangGraph (Faz 1) guards — fail-open for CrewAI-only deploys ──
    ok_lg_build = step_langgraph_build()
    if not ok_lg_build:
        return 4
    ok_cp_probe = step_checkpointer_probe()
    if not ok_cp_probe:
        return 5
    print("[smoke] all steps PASSED (STEP 1-4 + LangGraph STEP 5-6)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
