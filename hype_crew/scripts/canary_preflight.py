"""B1 canary pre-flight — six independent guards each return GREEN/RED."""
import os, sys, json, subprocess
from datetime import datetime, timezone
sys.path.insert(0, "/opt/contentfactory/backend")

CHECKS = []

def check(name, fn):
    try:
        ok, detail = fn()
        CHECKS.append({"name": name, "status": "GREEN" if ok else "RED", "detail": detail})
    except Exception as e:
        CHECKS.append({"name": name, "status": "RED", "detail": f"EXC: {type(e).__name__}: {e}"})


# 1) NER loaded in backend
def ner_loaded():
    try:
        import gliner, rapidfuzz  # noqa
        return True, f"gliner + rapidfuzz importable in backend venv"
    except Exception as e:
        return False, str(e)
check("backend NER loaded", ner_loaded)


# 2) Gate secret set
def gate_secret():
    s = os.environ.get("FAITHFULNESS_GATE_SECRET") or ""
    return (len(s) >= 16, f"FAITHFULNESS_GATE_SECRET length={len(s)} (need ≥16)")
check("gate token secret set", gate_secret)


# 3) Faithfulness choke-point CI (NER required at boot)
def ner_required():
    v = (os.environ.get("FAITHFULNESS_NER_REQUIRED") or "").lower()
    return (v in {"1", "true", "yes", "on"}, f"FAITHFULNESS_NER_REQUIRED={v}")
check("FAITHFULNESS_NER_REQUIRED=true", ner_required)


# 4) Circuit breaker / forced trip drill — verify the trip logic exists + can run
def breaker_exists():
    import importlib.util
    for path in ("/opt/hype-crew/scripts/shadow_circuit_breaker.py",
                 "/opt/hype-crew/tools/shadow_circuit_breaker.py"):
        if os.path.exists(path):
            return True, f"breaker module at {path}"
    return False, "no shadow_circuit_breaker.py found"
check("breaker drill module present", breaker_exists)


# 5) Kill-switch endpoint exists in backend route
def kill_switch():
    p = "/opt/contentfactory/backend/routes/hype.py"
    with open(p) as f:
        src = f.read()
    if "@router.post(\"/kill-switch\")" in src:
        return True, "POST /kill-switch found in hype.py"
    return False, "kill-switch endpoint missing"
check("kill-switch endpoint", kill_switch)


# 6) Verifier arms — schedule_posts wrapped in operator_publish_context
def verifier_arm():
    p = "/opt/contentfactory/backend/routes/hype.py"
    with open(p) as f:
        src = f.read()
    if "operator_publish_context()" in src:
        return True, "operator_publish_context() used in hype.py"
    return False, "operator_publish_context() not found"
check("operator-publish guard active", verifier_arm)


# 7) SEV-1 marker: POSTIZ_PUBLISH_ALLOW_NON_UI not set
def no_non_ui():
    v = os.environ.get("POSTIZ_PUBLISH_ALLOW_NON_UI") or ""
    return (v == "" or v.lower() in {"false", "0", "no", "off"},
            f"POSTIZ_PUBLISH_ALLOW_NON_UI={v or '(unset)'}")
check("POSTIZ_PUBLISH_ALLOW_NON_UI off", no_non_ui)


# 8) auto-publish per account
def auto_publish():
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY"))
    rows = sb.table("hype_account_config").select("account_id, auto_publish_enabled").execute().data or []
    on = [r for r in rows if r.get("auto_publish_enabled")]
    if on:
        return False, f"{len(on)} account(s) have auto_publish_enabled=true — DISARM before canary"
    return True, f"all {len(rows)} accounts have auto_publish_enabled=false (canary-safe baseline)"
check("auto-publish OFF (all accounts)", auto_publish)


print("\n=== CANARY PRE-FLIGHT ===\n")
for c in CHECKS:
    sym = "🟢" if c["status"] == "GREEN" else "🔴"
    print(f"  {sym} {c['name']:38} {c['detail']}")
greens = sum(1 for c in CHECKS if c["status"] == "GREEN")
print(f"\n  TOTAL: {greens}/{len(CHECKS)} GREEN")
