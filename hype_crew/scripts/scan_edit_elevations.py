"""Phase 43.D — Edit Elevation scanner.

Runs after `check_autonomy_gates.py` each day (chained via systemd
ExecStartPost on hype-autonomy-gates.service). For every active persona:

  1. Pulls the persona's editor_diffs rows from `hype_memory` from the
     last 30 days.
  2. Joins each editor_diff to its parent draft so we can read the
     draft's content_type (the "cluster" we promote a default INTO).
  3. Canonicalises the user's edit shape into a deterministic signature
     so "Cansu kahvede MacBook'la" written twice gets recognised as the
     same pattern. Empty / trivially-different patterns are dropped.
  4. Groups by (persona, content_type, signature). When a group hits
     ≥3 distinct drafts, an `edit_elevation_candidates` row is
     upserted (pending). Sample count + last_seen updated on re-scan.
  5. Berkay reviews via the UI / API — the rating endpoints
     (POST /elevations/{id}/{accept,reject}) handle the rest.

The script is read-mostly on hype_memory + daily_drafts plus a small
number of upserts on edit_elevation_candidates, so it's cheap to run
even hourly during early calibration.

CLI:
    python -m scripts.scan_edit_elevations
    python -m scripts.scan_edit_elevations --dry-run
    python -m scripts.scan_edit_elevations --persona <id>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from tools.supabase_client import make_supabase
except Exception:  # pragma: no cover — package-import fallback
    from hype_crew.tools.supabase_client import make_supabase  # type: ignore

logger = logging.getLogger("edit-elevations")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)


LOOKBACK_DAYS = 30
PROMOTION_THRESHOLD = 3       # ≥3 identical edits on same content_type → candidate
MIN_SIGNATURE_LENGTH = 8      # below this we treat as "no real shape"


def _canonicalize_edit_pattern(edit_fields: Optional[dict]) -> Optional[dict]:
    """Reduce `edit_fields` to a stable, comparable shape.

    Strings are normalised (lowercased, stripped, collapsed whitespace,
    truncated at 200 chars). Empty/whitespace-only values get dropped.
    None means "nothing comparable" and the caller skips it.
    """
    if not isinstance(edit_fields, dict):
        return None
    out: dict = {}
    for k, v in edit_fields.items():
        if v is None:
            continue
        if isinstance(v, str):
            normed = " ".join(v.strip().lower().split())
            if not normed:
                continue
            out[str(k)] = normed[:200]
        elif isinstance(v, (int, float, bool)):
            out[str(k)] = v
        elif isinstance(v, (list, tuple)):
            cleaned = []
            for item in v:
                if isinstance(item, str):
                    item_n = " ".join(item.strip().lower().split())[:200]
                    if item_n:
                        cleaned.append(item_n)
                elif item is not None:
                    cleaned.append(item)
            if cleaned:
                out[str(k)] = sorted(cleaned, key=lambda x: json.dumps(x, sort_keys=True))
        elif isinstance(v, dict):
            sub = _canonicalize_edit_pattern(v)
            if sub:
                out[str(k)] = sub
    return out or None


def _signature_for(pattern: dict) -> str:
    canonical_json = json.dumps(pattern, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _scan_persona(sb, persona: dict, *, dry_run: bool) -> dict:
    """Find candidate edit patterns for a single persona."""
    persona_id = persona["id"]
    slug = persona.get("slug") or persona_id
    primary_account_id = persona.get("primary_account_id")
    if not primary_account_id:
        logger.info(f"[{slug}] skip — no primary_account_id")
        return {"persona_id": persona_id, "skipped": "no_primary_account"}

    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    ).isoformat()

    edits_q = (
        sb.table("hype_memory")
        .select("id, content, metadata, created_at")
        .eq("account_id", primary_account_id)
        .eq("memory_type", "editor_diffs")
        .gte("created_at", cutoff_iso)
        .order("created_at", desc=False)
        .execute()
    )
    edit_rows = edits_q.data or []
    if not edit_rows:
        return {"persona_id": persona_id, "edits": 0, "groups": 0}

    # Pull the matching drafts so we can read their content_type. We
    # walk metadata for trend_id / draft_id hints.
    related_draft_ids = set()
    for r in edit_rows:
        md = r.get("metadata") or {}
        if not isinstance(md, dict):
            continue
        if md.get("draft_id"):
            related_draft_ids.add(md["draft_id"])

    draft_ct: dict[str, str] = {}
    if related_draft_ids:
        draft_ids = list(related_draft_ids)
        for i in range(0, len(draft_ids), 200):
            chunk = draft_ids[i:i + 200]
            try:
                d_rows = (
                    sb.table("daily_drafts")
                    .select("id, content_type")
                    .in_("id", chunk)
                    .execute()
                )
                for d in (d_rows.data or []):
                    if d.get("id") and d.get("content_type"):
                        draft_ct[d["id"]] = d["content_type"]
            except Exception as e:
                logger.warning(f"[{slug}] draft content_type fetch failed: {e}")

    # Group by (content_type, signature). Each group tracks its
    # sample drafts so we can show Berkay concrete evidence.
    groups: dict[tuple[Optional[str], str], dict] = {}
    for r in edit_rows:
        md = r.get("metadata") or {}
        if not isinstance(md, dict):
            continue
        edit_fields = md.get("edit_fields")
        canonical = _canonicalize_edit_pattern(edit_fields)
        if not canonical:
            continue
        signature = _signature_for(canonical)
        if len(signature) < MIN_SIGNATURE_LENGTH:
            continue
        draft_id = md.get("draft_id")
        content_type = draft_ct.get(draft_id) if draft_id else None
        key = (content_type, signature)
        g = groups.setdefault(key, {
            "pattern": canonical,
            "drafts": set(),
            "first_seen": r.get("created_at"),
            "last_seen": r.get("created_at"),
        })
        if draft_id:
            g["drafts"].add(draft_id)
        last_iso = g["last_seen"] or ""
        if r.get("created_at") and r["created_at"] > last_iso:
            g["last_seen"] = r["created_at"]

    candidates_upserted = 0
    for (content_type, signature), g in groups.items():
        n = len(g["drafts"])
        if n < PROMOTION_THRESHOLD:
            continue
        sample_drafts = list(g["drafts"])[:8]
        row = {
            "persona_id": persona_id,
            "account_id": primary_account_id,
            "content_type": content_type,
            "edit_signature": signature,
            "edit_pattern": g["pattern"],
            "sample_count": n,
            "example_draft_ids": sample_drafts,
            "last_seen": g["last_seen"],
        }
        logger.info(
            f"[{slug}] candidate: ct={content_type} n={n} "
            f"sig={signature[:10]}… pattern={list(g['pattern'].keys())}"
        )
        if dry_run:
            continue
        # Upsert on the UNIQUE(persona_id, content_type, edit_signature)
        # constraint — sample_count + last_seen refresh on every scan.
        try:
            sb.table("edit_elevation_candidates").upsert(
                row,
                on_conflict="persona_id,content_type,edit_signature",
            ).execute()
            candidates_upserted += 1
        except Exception as e:
            logger.warning(f"[{slug}] upsert failed: {e}")

    return {
        "persona_id": persona_id,
        "slug": slug,
        "edits_scanned": len(edit_rows),
        "groups_total": len(groups),
        "candidates_upserted": candidates_upserted,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--persona", help="single persona id (default: all active)")
    args = parser.parse_args()

    sb = make_supabase()
    q = (
        sb.table("personas")
        .select("id, slug, primary_account_id, is_active")
        .eq("is_active", True)
    )
    if args.persona:
        q = q.eq("id", args.persona)
    personas = q.execute().data or []
    if not personas:
        logger.info("no active personas")
        return 0

    total_candidates = 0
    for p in personas:
        try:
            res = _scan_persona(sb, p, dry_run=args.dry_run)
            total_candidates += res.get("candidates_upserted", 0)
        except Exception as e:
            logger.exception(f"persona {p.get('slug')} scan failed: {e}")
    logger.info(
        f"edit-elevations scan complete: personas={len(personas)} "
        f"new_or_refreshed_candidates={total_candidates} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
