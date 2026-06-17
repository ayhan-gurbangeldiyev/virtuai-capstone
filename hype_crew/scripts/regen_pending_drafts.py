"""Regen ALL pending_review drafts with the new per-platform lugat system.

2026-06-10 (Berkay) — voice rework testi: bekleyen draftlar yeni directive
(build_cansu_directive) + platform lugatı (_lugat_for_platform) + tam kaynak
metin (raw_content + source_tweets union) ile yeniden yazılır, flow'daki
sanitize zincirinden geçirilir ve daily_drafts.content güncellenir.

- Video'lu draftlar (video_url dolu) ATLANIR: content değişirse
  video_content_sha mismatch → approve guard videoyu stale sayar.
- Status değişmez (pending_review kalır) — operatör UI'da inceler.

Usage:
  python -m scripts.regen_pending_drafts            # yaz + DB güncelle
  DRY_RUN=1 python -m scripts.regen_pending_drafts  # yaz, DB'ye dokunma
  ONLY_RUN_ID=<uuid> ...                            # tek run'la sınırla
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flow import (  # noqa: E402
    build_cansu_directive,
    _lugat_for_platform,
    _sanitize_em_dash,
    _strip_all_hashtags,
    _strip_emojis,
    _strip_persona_disclosure,
    _enforce_platform_length,
)
from tools.supabase_client import make_supabase  # noqa: E402
from tools.typehype_client import generate_tweet_via_typehype  # noqa: E402
from config import settings  # noqa: E402

DRY_RUN = bool(os.environ.get("DRY_RUN"))
ONLY_RUN_ID = os.environ.get("ONLY_RUN_ID") or None
# Virgülle ayrılmış draft id listesi — yalnız bunları yeniden yaz
ONLY_DRAFT_IDS = {
    s.strip() for s in (os.environ.get("ONLY_DRAFT_IDS") or "").split(",") if s.strip()
}

# flow.write_via_typehype ile aynı eşlemeler (oradaki class attrleri
# flow instance'ı gerektirdiğinden burada literal tutuluyor).
_CONTENT_TYPE = {
    "twitter": "tweet", "x": "tweet", "linkedin": "linkedin",
    "instagram": "instagram", "devto": "blog", "youtube": "youtube",
}
_UZUNLUK = {
    "twitter": "punch", "x": "punch", "linkedin": "spark",
    "instagram": "punch", "devto": "storm", "youtube": "spark",
}
_VOICE = {
    "twitter": "first_person_witty", "x": "first_person_witty",
    "instagram": "first_person_witty", "linkedin": "hybrid",
    "devto": "hybrid", "youtube": "hybrid",
}


def _full_source_for_trend(sb, trend_id: str) -> str:
    """Gate + yazar ile aynı kaynak birleşimi (tools.cansu_voice tek tanım)."""
    from tools.cansu_voice import assemble_source_text
    rows = (
        sb.table("trends")
        .select("raw_content, source_tweets, full_source_text")
        .eq("id", trend_id).limit(1).execute()
    ).data or []
    return assemble_source_text(rows[0]) if rows else ""


def _sanitize(content: str, platform: str) -> str:
    content = _sanitize_em_dash(content)
    content = _strip_all_hashtags(content)
    content = _strip_emojis(content)
    content = _strip_persona_disclosure(content)
    content = _enforce_platform_length(content, platform)
    return content


def main() -> None:
    sb = make_supabase()
    q = (
        sb.table("daily_drafts")
        .select("id, platform, account_id, trend_id, trend_topic, hype_run_id, content, video_url")
        .eq("status", "pending_review")
        .is_("deleted_at", "null")
    )
    if not ONLY_DRAFT_IDS:
        # Toplu modda video'lu draftlara dokunma. ONLY_DRAFT_IDS ile açıkça
        # hedeflenirse video'lular da yazılır; update sırasında
        # video_content_sha yeni metne göre damgalanır (approve guard'ın
        # canlı sha karşılaştırması stale saymasın — video korunur,
        # caption bağımsız: 2026-06-10 pin kaldırma kararıyla tutarlı).
        q = q.is_("video_url", "null")
    if ONLY_RUN_ID:
        q = q.eq("hype_run_id", ONLY_RUN_ID)
    drafts = q.order("created_at", desc=True).execute().data or []
    if ONLY_DRAFT_IDS:
        drafts = [d for d in drafts if d["id"] in ONLY_DRAFT_IDS]
    print(f"{len(drafts)} pending draft (video'lular hariç){' [DRY RUN]' if DRY_RUN else ''}\n")

    directive = build_cansu_directive()  # canned/recent dinamikleri runtime-only; regen'de boş
    src_cache: dict[str, str] = {}
    ok = fail = 0

    for d in drafts:
        plat = (d["platform"] or "").lower()
        topic = d.get("trend_topic") or ""
        trend_id = d.get("trend_id")

        raw = ""
        if trend_id:
            if trend_id not in src_cache:
                src_cache[trend_id] = _full_source_for_trend(sb, trend_id)
            raw = src_cache[trend_id]
        if raw:
            kaynak = (
                "## KAYNAK METİN (tüm iddialar buna bağlı olmalı — kaynak "
                "dışı bir entity / sayı / ürün / olay / sebep YAZMA)\n" + raw.strip()
            )
        else:
            kaynak = (
                "## KAYNAK METİN: (yok)\nKaynak bulunamadı — yalnızca trend "
                "konusu kullanılarak yazılacak, spekülatif uzantı YOK."
            )

        context = "\n".join([
            directive,
            _lugat_for_platform(plat),
            f"Trend konusu: {topic}",
            kaynak,
        ])

        try:
            resp = generate_tweet_via_typehype(
                account_id=d["account_id"],
                etki="konustursun",
                karakter="haberci",
                uzunluk=_UZUNLUK.get(plat, "punch"),  # type: ignore[arg-type]
                yapi="dogal",
                additional_context=context,
                is_ultra=False,
                content_type=_CONTENT_TYPE.get(plat, "tweet"),  # type: ignore[arg-type]
                voice_mode=_VOICE.get(plat),
                model_override=getattr(settings, "writer_model", None) or None,
                clean_source_input=True,
            )
            new_content = _sanitize((resp.get("content") or "").strip(), plat)
            if not new_content:
                raise RuntimeError("writer boş içerik döndü")
        except Exception as e:
            fail += 1
            print(f"✗ [{plat}] {topic[:50]} — {type(e).__name__}: {str(e)[:120]}\n")
            continue

        print(f"── [{plat}] {topic[:60]} (id={d['id'][:8]}, src={len(raw)}ch)")
        print(f"   ESKİ: {(d.get('content') or '')[:160].replace(chr(10), ' ¶ ')}")
        print(f"   YENİ: {new_content[:160].replace(chr(10), ' ¶ ')}\n")

        if not DRY_RUN:
            payload: dict = {"content": new_content}
            if d.get("video_url"):
                import hashlib
                payload["video_content_sha"] = hashlib.sha256(
                    new_content.encode("utf-8")
                ).hexdigest()
                payload["video_stale"] = False
            sb.table("daily_drafts").update(payload).eq("id", d["id"]).execute()
        ok += 1

    print(f"bitti: {ok} yenilendi, {fail} hata{' (DB değişmedi — dry run)' if DRY_RUN else ''}")


if __name__ == "__main__":
    main()
