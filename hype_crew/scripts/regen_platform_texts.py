"""Targeted per-platform text regen for ONE existing run's drafts.

Regenerates distinct copy for twitter / linkedin / instagram (the LI==IG bug
on pre-fix drafts) via the TypeHype writer, grounded on the trend's real source,
then updates the daily_drafts rows. Each platform gets its own voice + length.

Usage: ACCOUNT_ID=.. RUN_ID=.. PLATFORMS=twitter,linkedin,instagram python -m scripts.regen_platform_texts
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.supabase_client import make_supabase  # noqa: E402
from tools.typehype_client import generate_tweet_via_typehype  # noqa: E402
from config import settings  # noqa: E402

ACCOUNT_ID = os.environ["ACCOUNT_ID"]
RUN_ID = os.environ["RUN_ID"]
PLATFORMS = (os.environ.get("PLATFORMS") or "twitter,linkedin,instagram").split(",")

_CONTENT_TYPE = {"twitter": "tweet", "x": "tweet", "linkedin": "linkedin", "instagram": "instagram"}
_UZUNLUK = {"twitter": "punch", "x": "punch", "linkedin": "spark", "instagram": "punch"}
_VOICE = {"twitter": "first_person_witty", "x": "first_person_witty",
          "instagram": "first_person_witty", "linkedin": "hybrid"}


def _resolve_account(sb, owner_user_id: str, platform: str):
    r = (sb.table("connected_accounts")
         .select("id, platform, postiz_provider, username")
         .eq("user_id", owner_user_id)
         .or_(f"platform.eq.{platform},postiz_provider.eq.{platform}")
         .limit(1).execute()).data or []
    return r[0] if r else None


def main() -> None:
    sb = make_supabase()
    persona = (sb.table("personas").select("id, owner_user_id")
               .eq("primary_account_id", ACCOUNT_ID).limit(1).execute()).data[0]
    owner = persona["owner_user_id"]

    # trend context from the run's drafts (trend_id, topic) + raw source
    drafts = (sb.table("daily_drafts").select("trend_id,trend_topic,insight")
              .eq("hype_run_id", RUN_ID).limit(1).execute()).data
    if not drafts:
        raise SystemExit(f"no drafts for run {RUN_ID}")
    trend_id = drafts[0]["trend_id"]; topic = drafts[0].get("trend_topic") or ""
    raw = ""
    if trend_id:
        tr = (sb.table("trends").select("raw_content").eq("id", trend_id).limit(1).execute()).data
        raw = (tr[0].get("raw_content") if tr else "") or ""

    context = (
        f"Trend konusu: {topic}\n\n"
        "## KAYNAK METİN (tüm iddialar SADECE buna bağlı olmalı; kaynak dışı "
        f"entity / sayı / iddia YAZMA):\n{raw}\n\n"
        "Nötr-olgusal Cansu sesiyle yaz. Soru ya da CTA ile BİTİRME. Kaynakta "
        "olmayan bilgi uydurma. Her platform KENDİ tonu ve uzunluğunda olsun."
    )
    print(f"trend: {topic}\nsource: {raw[:140]}\n")

    for plat in PLATFORMS:
        plat = plat.strip().lower()
        acc = _resolve_account(sb, owner, plat)
        if not acc:
            print(f"[{plat}] no connected account — skip"); continue
        try:
            resp = generate_tweet_via_typehype(
                account_id=acc["id"],
                etki="konustursun", karakter="haberci",
                uzunluk=_UZUNLUK.get(plat, "punch"),
                yapi="dogal", additional_context=context, is_ultra=False,
                content_type=_CONTENT_TYPE.get(plat, "tweet"),
                voice_mode=_VOICE.get(plat),
                model_override=getattr(settings, "writer_model", None) or None,
                clean_source_input=True,
            )
        except Exception as e:
            print(f"[{plat}] generate failed: {type(e).__name__}: {str(e)[:120]}"); continue
        content = (resp.get("content") or "").strip()
        if not content:
            print(f"[{plat}] empty content — skip"); continue
        upd = (sb.table("daily_drafts").update({"content": content})
               .eq("hype_run_id", RUN_ID).eq("platform", plat).execute()).data or []
        print(f"[{plat}] voice={_VOICE.get(plat)} len={len(content)} updated={len(upd)}")
        print("   " + content[:160].replace("\n", " ") + "\n")


if __name__ == "__main__":
    main()
