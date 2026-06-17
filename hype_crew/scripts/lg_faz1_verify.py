"""Faz 1 parite koşum-takımı — CrewAI Flow ↔ LangGraph aynı sonucu mu üretiyor?

CrewAI Flow → LangGraph (strangler) göçünün Faz 1 doğrulayıcısı. Amaç: verilen
bir hesap için LangGraph yolu, CrewAI yolu ile **AYNI gözlemlenebilir sonucu**
üretiyor mu? DRY_RUN zorunlu — hiçbir dış yayın / ücretli çağrı OLMAZ; bu bir
parite kontrolü, canlı koşu değil.

Tasarım (çalıştırma):
    python -m scripts.lg_faz1_verify <account_id>

Akış:
  1. CrewAI yolu (mevcut): AutonomousContentFlow().kickoff() — dry_run zorlanır.
     → hype_runs.flow_state JSON + sıralı hype_stages satırları okunur.
  2. LangGraph yolu: lg.graph.run_or_resume(account_id, triggered_by) — dry_run
     zorlanır.
     → aynı şekilde flow_state + hype_stages okunur.
  3. DIFF: flow_state şekli/anahtarları + final_status + stage dizisi
     (agent_name / stage_order / status). Sapmaları raporla.

Determinizm toleransı: timestamp, run_id, token sayısı, LLM kelime seçimi gibi
non-deterministik alanlar KARŞILAŞTIRILMAZ. Karşılaştırılan: flow_state'in
YAPISI (anahtar şekli) + kontrol-akış yolu (stage dizisi + final_status).

Kuraklık/aday-yok koşuları da GEÇERLİ parite vakalarıdır: iki yol da boş
dönüyorsa (no_candidates, drought, dry_run_no_draft) bu bir EŞLEŞME'dir.

Defansif: lg.graph henüz import edilemiyorsa "graph not built yet — verifier
ready" yazıp exit 0 — implementer bitirmeden bu dosya temiz iner.

DRY_RUN zorlaması (önemli uyarı):
  Flow.initialize dry_run'ı DB config'ten (hype_account_config.dry_run_mode)
  okur ve DB env'i EZER. Yani bir hesabın DB'de dry_run_mode=false ise tek
  başına env ile dry_run'ı garanti EDEMEYİZ. Bu yüzden:
    (a) süreç başında HYPE_DRY_RUN=true set edilir (env fallback'i kapatır),
    (b) DB config dry_run_mode=false ise verifier hesabı REDDEDER (canlı yayın
        riski) — parite kontrolü asla canlı çağrı yapmamalı.
"""
from __future__ import annotations

import os
import sys

# ── DRY_RUN'ı HER ŞEYDEN ÖNCE zorla (config import edilmeden) ──────────────
# Bu, settings.dry_run fallback'ini True'ya sabitler. DB-wins istisnası aşağıda
# _assert_account_dry_safe() ile ayrıca kapatılır.
os.environ["HYPE_DRY_RUN"] = "true"
os.environ.setdefault("HYPE_LANGGRAPH_ENABLED", "true")  # LG yolunu açık say

import json  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

# sys.path — smoke_test_flow.py ile aynı kök çözümleme deseni
_HERE = os.path.dirname(os.path.abspath(__file__))
_HYPE_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, "/opt/hype-crew")
sys.path.insert(0, _HYPE_ROOT)
sys.path.insert(0, os.path.dirname(_HYPE_ROOT))


# ──────────────────────── Supabase okuma yardımcıları ─────────────────────


def _read_run(run_id: str) -> dict:
    """hype_runs satırını oku (flow_state + final status dahil)."""
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    r = (
        sb.table("hype_runs")
        .select("id, status, dry_run, flow_state, error")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    rows = r.data if isinstance(r.data, list) else []
    return rows[0] if rows and isinstance(rows[0], dict) else {}


def _read_stages(run_id: str) -> list[dict]:
    """hype_stages satırlarını stage_order'a göre sıralı oku."""
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    r = (
        sb.table("hype_stages")
        .select("agent_name, stage_order, status")
        .eq("run_id", run_id)
        .order("stage_order")
        .execute()
    )
    rows = [s for s in (r.data if isinstance(r.data, list) else []) if isinstance(s, dict)]
    # stage_order None gelirse deterministik sıralama için sona at
    rows.sort(key=lambda s: (s.get("stage_order") is None, s.get("stage_order") or 0))
    return rows


# ──────────────────── gözlemlenebilir-sonuç normalizasyonu ────────────────


def _flow_state_shape(fs) -> dict:
    """flow_state'in YAPISINI çıkar (değerleri değil): anahtar seti + hangi
    bölümlerin dolu/boş olduğu. LLM metni / timestamp / id karşılaştırılmaz.

    Dönen şekil parite-karşılaştırılabilir: {key: "present"|"null"|<type>}.
    """
    if not isinstance(fs, dict):
        return {"_type": type(fs).__name__}
    shape: dict[str, str] = {}
    for k in sorted(fs.keys()):
        v = fs[k]
        if v is None:
            shape[k] = "null"
        elif isinstance(v, dict):
            shape[k] = "object"
        elif isinstance(v, list):
            shape[k] = f"list[{len(v)}]"
        elif isinstance(v, bool):
            shape[k] = "bool"
        elif isinstance(v, (int, float)):
            shape[k] = "number"
        elif isinstance(v, str):
            # metin içeriği non-deterministik → yalnız dolu/boş ayrımı
            shape[k] = "str:nonempty" if v.strip() else "str:empty"
        else:
            shape[k] = type(v).__name__
    return shape


def _stage_path(stages: list[dict]) -> list[tuple]:
    """Kontrol-akış yolu: (agent_name, stage_order, status) üçlüleri.
    Token/duration/output gibi non-deterministik alanlar dışarıda."""
    return [
        (s.get("agent_name"), s.get("stage_order"), s.get("status"))
        for s in stages
    ]


def _observable(run: dict, stages: list[dict]) -> dict:
    """Bir koşumun parite-karşılaştırılabilir gözlemlenebilir sonucu."""
    fs = run.get("flow_state")
    return {
        "final_status": run.get("status"),
        "flow_state_label": (fs or {}).get("label") if isinstance(fs, dict) else None,
        "flow_state_shape": _flow_state_shape(fs),
        "stage_path": _stage_path(stages),
        "dry_run": run.get("dry_run"),
    }


# ──────────────────────────── DIFF ───────────────────────────────────────


def _diff_observables(crew: dict, lg: dict) -> list[str]:
    """İki gözlemlenebilir sonucu karşılaştır; insan-okur sapma listesi döndür.
    Boş liste → PARİTE."""
    diffs: list[str] = []

    if crew["final_status"] != lg["final_status"]:
        diffs.append(
            f"final_status: crew={crew['final_status']!r} != lg={lg['final_status']!r}"
        )

    if crew["flow_state_label"] != lg["flow_state_label"]:
        diffs.append(
            f"flow_state.label: crew={crew['flow_state_label']!r} != "
            f"lg={lg['flow_state_label']!r}"
        )

    # flow_state şekil farkı (anahtar bazında)
    c_shape, l_shape = crew["flow_state_shape"], lg["flow_state_shape"]
    all_keys = sorted(set(c_shape) | set(l_shape))
    for k in all_keys:
        cv, lv = c_shape.get(k, "<MISSING>"), l_shape.get(k, "<MISSING>")
        if cv != lv:
            diffs.append(f"flow_state[{k!r}]: crew={cv} != lg={lv}")

    # kontrol-akış yolu (stage dizisi)
    if crew["stage_path"] != lg["stage_path"]:
        diffs.append("stage_path divergence:")
        diffs.append(f"    crew: {crew['stage_path']}")
        diffs.append(f"    lg  : {lg['stage_path']}")

    return diffs


# ──────────────────────── koşum yürütücüler ──────────────────────────────


def _assert_account_dry_safe(account_id: str) -> None:
    """DB-wins istisnasını kapat: hesabın dry_run_mode'u açıkça False ise
    parite kontrolü canlı yayın yapabilir → REDDET. (env zaten true'ya
    sabitlendi; bu yalnız DB override'ını yakalar.)"""
    try:
        from tools.supabase_client import make_supabase
        sb = make_supabase()
        r = (
            sb.table("hype_account_config")
            .select("dry_run_mode")
            .eq("account_id", account_id)
            .limit(1)
            .execute()
        )
        rows = r.data if isinstance(r.data, list) else []
        if rows and isinstance(rows[0], dict):
            mode = rows[0].get("dry_run_mode")
            if mode is False:
                raise SystemExit(
                    f"[verify] ABORT — hesap {account_id[:8]} DB'de "
                    f"dry_run_mode=False; parite kontrolü canlı yayın riski "
                    f"taşır. Önce dry_run_mode=True yapın."
                )
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001  — config okunamazsa env-true ile devam
        print(f"[verify] uyarı: dry_run_mode okunamadı ({e}); env=true ile devam")


def run_crewai(account_id: str) -> tuple[str, dict, list[dict]]:
    """Mevcut CrewAI yolu — dry_run zorlanmış. (run_id, run_row, stage_rows)."""
    from flow import AutonomousContentFlow

    flow = AutonomousContentFlow()
    flow.state.account_id = account_id
    flow.state.triggered_by = "manual"   # hype_runs.triggered_by CHECK: {cron,manual,webhook}
    # dry_run env'den (HYPE_DRY_RUN=true) gelir; DB-wins yukarıda guard'landı.
    flow.kickoff()
    run_id = flow.state.run_id
    if not run_id:
        raise RuntimeError("CrewAI kickoff sonrası run_id boş — telemetri yazılmamış")
    return run_id, _read_run(run_id), _read_stages(run_id)


def run_langgraph(account_id: str):
    """LangGraph yolu — dry_run zorlanmış. lg.graph yoksa None döndür (SKIP).

    Returns (run_id, run_row, stage_rows) | None.
    """
    try:
        from lg import graph as lg_graph
    except Exception as e:  # noqa: BLE001
        print(f"[verify] lg.graph import edilemedi ({type(e).__name__}: {e})")
        return None

    runner = getattr(lg_graph, "run_or_resume", None)
    if not callable(runner):
        print("[verify] lg.graph.run_or_resume bulunamadı")
        return None

    result = runner(account_id, triggered_by="manual")   # CHECK: {cron,manual,webhook}

    # run_or_resume'un dönüş şekli graph.py sözleşmesine bağlı; run_id'yi esnek çöz.
    run_id = _extract_run_id(result)
    if not run_id:
        raise RuntimeError(
            "LangGraph run_or_resume sonrası run_id çözülemedi "
            f"(dönüş tipi: {type(result).__name__})"
        )
    return run_id, _read_run(run_id), _read_stages(run_id)


def _extract_run_id(result) -> str:
    """run_or_resume dönüşünden run_id'yi esnek çıkar (dict / state / attr)."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        rid = result.get("run_id") or result.get("id")
        return rid if isinstance(rid, str) else ""
    rid = getattr(result, "run_id", None) or getattr(result, "id", None)
    return rid if isinstance(rid, str) else ""


# ──────────────────────────── main ───────────────────────────────────────


def main(argv: list[str]) -> int:
    if len(argv) < 2 or not argv[1].strip():
        print("kullanım: python -m scripts.lg_faz1_verify <account_id>")
        return 2
    account_id = argv[1].strip()

    print("=" * 70)
    print(f"[verify] Faz 1 parite kontrolü — account={account_id[:8]} (DRY_RUN zorlu)")
    print("=" * 70)

    # LangGraph yolu HİÇ inmemişse, kalkışta net mesaj + exit 0 (temiz iner).
    try:
        from lg import graph as _probe  # noqa: F401
        _lg_present = hasattr(_probe, "run_or_resume")
    except Exception:  # noqa: BLE001
        _lg_present = False
    if not _lg_present:
        print("[verify] graph not built yet — verifier ready (exit 0).")
        print("[verify] lg.graph.run_or_resume hazır olunca bu harness paritesi koşar.")
        return 0

    _assert_account_dry_safe(account_id)

    # 1) CrewAI yolu
    print("\n[verify] (1/2) CrewAI yolu koşuyor...")
    t0 = time.time()
    try:
        crew_rid, crew_run, crew_stages = run_crewai(account_id)
    except Exception as e:  # noqa: BLE001
        print(f"[verify] FAIL — CrewAI koşumu patladı: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1
    crew_obs = _observable(crew_run, crew_stages)
    print(f"[verify] CrewAI tamam ({time.time() - t0:.1f}s) run={crew_rid[:8]} "
          f"status={crew_obs['final_status']} stages={len(crew_stages)}")

    # 2) LangGraph yolu
    print("\n[verify] (2/2) LangGraph yolu koşuyor...")
    t1 = time.time()
    try:
        lg_out = run_langgraph(account_id)
    except Exception as e:  # noqa: BLE001
        print(f"[verify] FAIL — LangGraph koşumu patladı: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1
    if lg_out is None:
        print("[verify] graph not built yet — verifier ready (exit 0).")
        return 0
    lg_rid, lg_run, lg_stages = lg_out
    lg_obs = _observable(lg_run, lg_stages)
    print(f"[verify] LangGraph tamam ({time.time() - t1:.1f}s) run={lg_rid[:8]} "
          f"status={lg_obs['final_status']} stages={len(lg_stages)}")

    # 3) DIFF
    print("\n" + "-" * 70)
    print("[verify] gözlemlenebilir-sonuç DIFF (yapı + kontrol-akış + final status)")
    print("-" * 70)
    diffs = _diff_observables(crew_obs, lg_obs)

    if not diffs:
        print("\n[verify] ✅ PASS — CrewAI ↔ LangGraph parite (yapı/yol/status eşit).")
        if crew_obs["final_status"] in ("no_candidates", "skipped") or \
                (crew_obs["flow_state_label"] or "").startswith(("drought", "dry_run")):
            print("[verify] not: bu bir kuraklık/aday-yok koşusu — geçerli parite vakası.")
        return 0

    print(f"\n[verify] ❌ FAIL — {len(diffs)} sapma bulundu:")
    for d in diffs:
        print(f"  - {d}")
    # Tam gözlemlenebilirleri da bas (debug için)
    print("\n[verify] crew_observable:")
    print(json.dumps(crew_obs, indent=2, ensure_ascii=False, default=str))
    print("\n[verify] lg_observable:")
    print(json.dumps(lg_obs, indent=2, ensure_ascii=False, default=str))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
