"""SÖZLÜK/SENCE? kart zamanlayıcı/sequencer — üret + render + draft + (Faz5) yayın.

Kurallar (Berkay 13 Haz 2026):
- Tip-ALTERNATİF: asla arka arkaya iki aynı tip (daily_drafts son kart tipinden devam).
- DEDUP: card_history (yakın zamanda kullanılan terim/soru tekrar etmez).
- Platform: instagram + twitter + linkedin (youtube/devto HARİÇ — CARD_PLATFORMS).
- Kurak gün: 4 kart (2 SÖZLÜK + 2 SENCE?, alternatif), İstanbul prime saatleri.
- Haber-sonrası: o habere bağlı 1 SÖZLÜK + 1 SENCE?, haberden sonraki slotlara.

Saatlere normalde crew karar verir (Faz 4 time_picker enjekte edilir); yoksa
deterministik fallback (İstanbul prime slotları).
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Optional

from loguru import logger

from callbacks.supabase_logger import finalize_run, init_run, log_stage
from .dictionary_card import generate_dictionary_card
from .question_card import generate_question_card
from .supabase_client import make_supabase
from .text_card_render import render_and_store_text_card

CARD_PLATFORMS = ("instagram", "twitter", "linkedin")   # youtube/devto YOK
_KINDS = ("dictionary", "question")
_IST = dt.timezone(dt.timedelta(hours=3))               # İstanbul UTC+3 (sabit)
_PRIME_HOURS = [11, 14, 17, 20]                          # fallback prime slotlar (İstanbul)


# --- çözümleme ---
def resolve_persona(account_id: str) -> Optional[dict]:
    try:
        r = (make_supabase().table("personas")
             .select("id, owner_user_id, default_target_platforms")
             .eq("primary_account_id", account_id).limit(1).execute())
        rows = r.data or []
        return rows[0] if rows else None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-sched] persona çözülemedi {account_id}: {e}")
        return None


def _integration_id(owner_user_id: str, platform: str) -> Optional[str]:
    """connected_accounts → postiz_integration_id (flow._resolve_account_for_platform deseni)."""
    try:
        r = (make_supabase().table("connected_accounts")
             .select("postiz_integration_id")
             .eq("user_id", owner_user_id)
             .or_(f"platform.eq.{platform},postiz_provider.eq.{platform}")
             .limit(1).execute())
        rows = r.data or []
        return (rows[0].get("postiz_integration_id") if rows else None) or None
    except Exception:  # noqa: BLE001
        return None


def cards_publish_enabled() -> bool:
    """Kartlar Postiz'e canlı yayınlansın mı? (KAPALI → pending_review draft)."""
    try:
        from config import settings
        return bool(getattr(settings, "cards_publish_enabled", False))
    except Exception:  # noqa: BLE001
        return False


def publish_card_to_postiz(card: dict, scheduled_at: dt.datetime, persona: dict) -> Optional[str]:
    """Kartı 3 platforma (ig/tw/li) Postiz'e zamanla. Görsel bir kez upload, tek
    schedule_posts çağrısı. youtube/devto YOK. Postiz group/post id döndürür."""
    from .postiz_client import PlatformPost, PostizClient
    owner = persona.get("owner_user_id")
    client = PostizClient()
    media = [client.upload_image_url(card["image_url"])]
    posts: list = []
    for plat in CARD_PLATFORMS:
        integ = _integration_id(owner, plat)
        if not integ:
            logger.warning(f"[card-sched] {plat} integration yok, atlandı")
            continue
        posts.append(PlatformPost(integration_id=integ, provider=plat,
                                  content=card["caption"], media=media))
    if not posts:
        return None
    resp = client.schedule_posts(posts, scheduled_at)

    def _first_id(obj):  # Postiz yanıtı dict/list/iç-içe olabilir — ilk id'yi bul
        if isinstance(obj, dict):
            for k in ("postId", "id", "post_id", "group"):
                if obj.get(k):
                    return str(obj[k])
            for vv in obj.values():
                r = _first_id(vv)
                if r:
                    return r
        elif isinstance(obj, list):
            for it in obj:
                r = _first_id(it)
                if r:
                    return r
        return None

    v = _first_id(resp)
    logger.info(f"[card-sched] PUBLISH kind={card['kind']} platforms={len(posts)} @ {scheduled_at.isoformat()} id={v}")
    return str(v) if v else "SCHEDULED"


# --- kurak tespiti ---
def has_recent_news(account_id: str, hours: int = 24) -> bool:
    """Son `hours` saatte bu account için hype_auto HABER draft'ı var mı?
    (Kart kaynağı 'hype_cards' hariç — sadece gerçek haber.)"""
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).isoformat()
    try:
        r = (make_supabase().table("daily_drafts").select("id")
             .eq("account_id", account_id).eq("source", "hype_auto")
             .gte("created_at", since).limit(1).execute())
        return bool(r.data)
    except Exception:  # noqa: BLE001
        return True   # şüphede → kurak DEĞİL say (fazladan kart basma)


# --- alternatiflik + dedup ---
def last_card_kind(account_id: str) -> Optional[str]:
    try:
        r = (make_supabase().table("daily_drafts").select("content_type, scheduled_at")
             .eq("account_id", account_id).in_("content_type", list(_KINDS))
             .order("scheduled_at", desc=True).limit(1).execute())
        rows = r.data or []
        return rows[0]["content_type"] if rows else None
    except Exception:  # noqa: BLE001
        return None


def alternation_order(n: int, last_kind: Optional[str]) -> list[str]:
    """n kart için tip dizisi — asla iki aynı arka arkaya, son tipi tekrarlama.

    NOT: Bu yalnızca BATCH-İÇİ alternasyon verir + tek bir `last_kind` seed'i.
    Birden çok batch (companion + drought) aynı global-max'tan seed alıp
    çakışınca "çift çift" (q,q,d,d) üretebilir. Cross-batch güvenli atama için
    `assign_kinds_chronological` kullan (schedulerlar onu çağırır). Bu fonksiyon
    geri-uyum/test için duruyor."""
    if last_kind == "dictionary":
        start = "question"
    else:                       # question veya None → dictionary'le başla
        start = "dictionary"
    other = "question" if start == "dictionary" else "dictionary"
    return [start if i % 2 == 0 else other for i in range(n)]


def _opposite_kind(k: Optional[str]) -> str:
    return "question" if k == "dictionary" else "dictionary"


def _existing_card_slots(account_id: str, *, since_iso: str) -> list[tuple[str, str]]:
    """Bu account için `since_iso`'dan itibaren PLANLANMIŞ kart slotları:
    [(scheduled_at_iso, kind), ...] — scheduled_at'e göre tekilleştirilmiş
    (her kart 3 platform satırı; aynı scheduled_at+content_type)."""
    try:
        r = (make_supabase().table("daily_drafts")
             .select("content_type, scheduled_at")
             .eq("account_id", account_id).in_("content_type", list(_KINDS))
             .gte("scheduled_at", since_iso)
             .order("scheduled_at", desc=False).limit(500).execute())
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-sched] mevcut slot okuma hata: {e}")
        return []
    seen: dict[str, str] = {}
    for row in (r.data or []):
        sa = row.get("scheduled_at")
        ct = row.get("content_type")
        if sa and ct and sa not in seen:
            seen[sa] = ct
    return sorted(seen.items())


def latest_scheduled_card_time(account_id: str) -> Optional[dt.datetime]:
    """Bu account için GELECEKTE planlanmış en geç kart slotu (UTC), yoksa None.
    Companion kartlarını kuyruğun SONUNA çapalamak için — araya girip 'çift çift'
    yaratmasın (2-tip ile mevcut kartların arasına ekleme çakışmayı zorlar)."""
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        r = (make_supabase().table("daily_drafts").select("scheduled_at")
             .eq("account_id", account_id).in_("content_type", list(_KINDS))
             .gte("scheduled_at", now_iso)
             .order("scheduled_at", desc=True).limit(1).execute())
        rows = r.data or []
        if not rows or not rows[0].get("scheduled_at"):
            return None
        t = dt.datetime.fromisoformat(rows[0]["scheduled_at"])
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-sched] latest slot okuma hata: {e}")
        return None


def assign_kinds_chronological(account_id: str, times: list[dt.datetime]) -> list[str]:
    """Yeni `times` slotlarına, MEVCUT planlanmış kartları da hesaba katarak
    kronolojik komşusuna göre tip ata — asla iki aynı tip arka arkaya.

    Tek global seed yerine birleşik zaman çizelgesinde yürür: her yeni slot,
    kendinden hemen ÖNCEKİ kartın (mevcut ya da bu batch'te atanmış) ZIDDI olur.
    Bu, companion + drought batch'leri araya girse bile "çift çift"i önler."""
    if not times:
        return []
    new_sorted = sorted(times)
    window_start = (new_sorted[0] - dt.timedelta(days=2)).isoformat()
    existing = _existing_card_slots(account_id, since_iso=window_start)

    # Birleşik olay listesi: (time, kind_or_None, is_new, orig_index)
    events: list[tuple[dt.datetime, Optional[str], bool, int]] = []
    for sa_iso, kind in existing:
        try:
            t = dt.datetime.fromisoformat(sa_iso)
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        events.append((t, kind, False, -1))
    for idx, t in enumerate(new_sorted):
        tt = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        events.append((tt, None, True, idx))
    # Aynı an: mevcut kart yeni slottan ÖNCE gelsin (komşuluk doğru kurulsun)
    events.sort(key=lambda e: (e[0], e[2]))

    out: list[Optional[str]] = [None] * len(new_sorted)
    prev_kind: Optional[str] = None
    for _t, kind, is_new, idx in events:
        if is_new:
            assigned = _opposite_kind(prev_kind) if prev_kind else "dictionary"
            out[idx] = assigned
            prev_kind = assigned
        else:
            prev_kind = kind
    return [k or "dictionary" for k in out]


def _recent_keys(account_id: str, kind: str, days: int = 45) -> list[str]:
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    try:
        r = (make_supabase().table("card_history").select("key_text")
             .eq("account_id", account_id).eq("card_kind", kind)
             .gte("created_at", since).limit(300).execute())
        return [x["key_text"] for x in (r.data or [])]
    except Exception:  # noqa: BLE001
        return []


def _record_history(account_id: str, kind: str, key: str, content: str, trend_id=None):
    try:
        make_supabase().table("card_history").insert({
            "account_id": account_id, "card_kind": kind,
            "key_text": (key or "").lower().strip()[:200],
            "content": content, "trend_id": trend_id,
        }).execute()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-sched] history insert: {e}")


# --- üretim + draft ---
async def produce_card(kind: str, account_id: str, *,
                       news_topic: Optional[str] = None,
                       news_source: Optional[str] = None) -> Optional[dict]:
    """Tek kart: içerik üret (gate'li) → render → Supabase. None = üretilemedi."""
    if kind == "dictionary":
        c = await generate_dictionary_card(news_topic=news_topic, news_source=news_source,
                                           avoid_terms=_recent_keys(account_id, "dictionary"))
        if not c:
            return None
        main, sub, key = c["term"], c["gloss"], c["term"]
        caption = f"{c['term']} — {c['gloss']}"
    else:
        c = await generate_question_card(news_topic=news_topic,
                                         avoid_questions=_recent_keys(account_id, "question"))
        if not c:
            return None
        main, sub, key = c["question"], None, c["question"]
        caption = f"{c['question']}\n\nSence? 👇"
    # İLK kart (bu account+kind hiç kullanılmadıysa) → seriyi tanıtan ÇOK KISA giriş
    if not _recent_keys(account_id, kind, days=36500):
        _intro = {
            "dictionary": "✨ Yeni seri — SÖZLÜK: yapay zekanın havalı terimlerini sade Türkçe ile açıklıyorum.",
            "question": "✨ Yeni seri — SENCE?: yapay zekayı birlikte düşünelim, sen de yorumda söyle.",
        }.get(kind)
        if _intro:
            caption = f"{_intro}\n\n{caption}"
    try:
        _r0 = time.perf_counter()
        r = await render_and_store_text_card(theme_key=kind, main_text=main, sub_text=sub)
        render_ms = int((time.perf_counter() - _r0) * 1000)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-sched] render hata kind={kind}: {e}")
        return None
    return {
        "kind": kind, "image_url": r["image_url"], "caption": caption, "key": key,
        # şeffaflık (crew flow stage'leri için)
        "main": main, "sub": sub,
        "gate_reason": c.get("gate_reason", ""), "model": c.get("model", ""),
        "tokens": int(c.get("tokens", 0)), "attempts": int(c.get("attempts", 1)),
        # gerçek alt-adım süreleri (ms) — "0 sn" sorununu çözer
        "gen_ms": int(c.get("gen_ms", 0)), "gate_ms": int(c.get("gate_ms", 0)),
        "render_ms": render_ms,
    }


def write_card_drafts(*, account_id: str, persona: dict, card: dict, scheduled_at_iso: str,
                      status: str = "pending_review", trend_id=None,
                      postiz_post_id: Optional[str] = None, hype_run_id=None) -> list[dict]:
    """daily_drafts'a platform başına satır + card_history kaydı (one image, 3 platform)."""
    owner = persona.get("owner_user_id") if persona else None
    rows = [{
        "user_id": owner, "account_id": account_id,
        "persona_id": persona.get("id") if persona else None,
        "platform": plat, "content": card["caption"], "status": status,
        "source": "hype_cards", "content_type": card["kind"],
        "image_url": card["image_url"], "scheduled_at": scheduled_at_iso,
        "trend_id": trend_id, "postiz_post_id": postiz_post_id, "hype_run_id": hype_run_id,
    } for plat in CARD_PLATFORMS]
    make_supabase().table("daily_drafts").insert(rows).execute()
    _record_history(account_id, card["kind"], card["key"], card["caption"], trend_id)
    logger.info(f"[card-sched] draft kind={card['kind']} x{len(rows)} @ {scheduled_at_iso} status={status}")
    return rows


# --- zaman seçimi ---
def fallback_times(n: int, now_utc: Optional[dt.datetime] = None) -> list[dt.datetime]:
    """n adet GELECEK İstanbul prime slotu (UTC). Bugün dolduysa yarına taşar."""
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    out: list[dt.datetime] = []
    day = now.astimezone(_IST).date()
    while len(out) < n:
        for h in _PRIME_HOURS:
            t = dt.datetime.combine(day, dt.time(h, 0), tzinfo=_IST).astimezone(dt.timezone.utc)
            if t > now + dt.timedelta(minutes=20):
                out.append(t)
                if len(out) == n:
                    break
        day = day + dt.timedelta(days=1)
    return out[:n]


async def llm_pick_times(n: int, now_utc: Optional[dt.datetime] = None) -> list[dt.datetime]:
    """Yayın saatlerine CREW (LLM editör) karar verir — İstanbul prime, aralıklı.
    Her hata/eksiklikte deterministik fallback_times ile tamamlanır."""
    from .card_gates import chat_json
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    now_ist = now.astimezone(_IST)
    sys = """Sen Cansu'nun sosyal medya editörüsün. Bugün belli sayıda GÖRSEL KART
İstanbul saatiyle yayınlanacak. En iyi yayın saatlerini seç:
- İstanbul prime pencereleri: öğle (12:00-13:30), akşamüstü (17:00-18:30), akşam (20:00-21:30).
- Saatler ARALIKLI olsun (aralarında en az ~2.5 saat).
- ŞU ANDAN ÖNCEKİ saati SEÇME.
Yalnızca JSON döndür: {"times_istanbul": ["HH:MM", ...]} (n adet)."""
    user = f"Şu an İstanbul saati: {now_ist.strftime('%H:%M')}. {n} adet yayın saati seç."
    try:
        v, _meta = await chat_json(sys, user, temperature=0.4, max_tokens=120)
        out: list[dt.datetime] = []
        for s in (v.get("times_istanbul") or []):
            hh, mm = (int(x) for x in str(s).split(":")[:2])
            t = dt.datetime.combine(now_ist.date(), dt.time(hh, mm), tzinfo=_IST).astimezone(dt.timezone.utc)
            if t <= now + dt.timedelta(minutes=20):
                t = t + dt.timedelta(days=1)
            out.append(t)
        out = sorted(set(out))
        if len(out) < n:                       # eksikse fallback ile tamamla
            for t in fallback_times(n, now):
                if t not in out:
                    out.append(t)
        return sorted(out)[:n]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-sched] llm saat seçimi fallback: {e}")
        return fallback_times(n, now)


# --- orkestrasyon (her batch = bir hype_run; her alt-adım = bir hype_stage → Crew Flow şeffaflığı) ---
def _safe_log(run_id, order, label, output, *, model="", tokens=0, status="success", duration_ms=None):
    """log_stage sarmalayıcı — NON-FATAL (kayıt patlasa kart akışı kırılmaz)."""
    if not run_id:
        return
    try:
        log_stage(run_id, agent_name=label, stage_order=order, output=output,
                  model_used=model, tokens_used=tokens, status=status, duration_ms=duration_ms)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-sched] stage log hata ({label}): {e}")


async def _run_card_batch(account_id, persona, *, source, kinds, times, trend_id=None,
                          news_topic=None, news_source=None) -> int:
    """Bir kart batch'ini ÇALIŞTIR + her adımı hype_runs/hype_stages'a yaz (şeffaf).
    Kayıt hataları kart üretimini/yayınını ASLA bloklamaz (hepsi non-fatal)."""
    publish = cards_publish_enabled()
    status = "auto_scheduled" if publish else "pending_review"
    publisher = publish_card_to_postiz if publish else None
    started = time.time()
    run_id = None
    try:
        run_id = init_run(account_id, trend_id=trend_id, triggered_by="cron", dry_run=not publish)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[card-sched] init_run hata (kayıtsız devam): {e}")

    order = 0
    _safe_log(run_id, order, "Saat Seçimi",
              {"node": "saat", "source": source, "times": [t.isoformat() for t in times],
               "picker": "llm" if source == "drought" else "haber+offset"})
    order += 1

    written, summaries = 0, []
    for i, (kind, when) in enumerate(zip(kinds, times)):
        card = await produce_card(kind, account_id, news_topic=news_topic, news_source=news_source)
        if not card:
            _safe_log(run_id, order, f"İçerik Üret #{i+1}",
                      {"node": "icerik", "card_index": i, "kind": kind, "error": "üretilemedi (gate/LLM)"},
                      status="failed")
            order += 1
            continue
        _safe_log(run_id, order, f"İçerik Üret #{i+1}",
                  {"node": "icerik", "card_index": i, "kind": kind, "main": card["main"],
                   "sub": card.get("sub"), "caption": card["caption"], "attempts": card["attempts"]},
                  model=card["model"], tokens=card["tokens"], duration_ms=card.get("gen_ms"))
        order += 1
        _safe_log(run_id, order, f"Kart Kapısı #{i+1}",
                  {"node": "card_gate", "card_index": i, "ok": True, "reason": card["gate_reason"]},
                  duration_ms=card.get("gate_ms"))
        order += 1
        _safe_log(run_id, order, f"Render #{i+1}",
                  {"node": "render", "card_index": i, "image_url": card["image_url"]},
                  duration_ms=card.get("render_ms"))
        order += 1

        postiz_id = None
        publish_ok = (publisher is None)   # yayıncı yoksa zaten pending_review yolu
        _p0 = time.perf_counter()
        if publisher is not None:
            _MAX = 3
            for _att in range(1, _MAX + 1):
                try:
                    postiz_id = publisher(card=card, scheduled_at=when, persona=persona)
                    publish_ok = True
                    break
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[card-sched] publish hata deneme {_att}/{_MAX} kind={kind}: {e}")
                    if _att < _MAX:
                        time.sleep(2 ** (_att - 1))   # 1s, 2s (transient 401/5xx/timeout)
                    else:
                        logger.error(f"[card-sched] publish FİNAL BAŞARISIZ kind={kind} @ {when.isoformat()}")
                        try:
                            from .alerter import send_alert
                            send_alert(
                                f"Kart yayını başarısız: {kind}",
                                severity="CRITICAL",
                                platform=",".join(CARD_PLATFORMS),
                                reason=f"{type(e).__name__}: {str(e)[:160]}",
                                action="Postiz bağlantısını kontrol et; kart pending_review'da bekliyor.",
                                extra={"account_id": account_id, "card_kind": kind},
                            )
                        except Exception as _ae:  # noqa: BLE001
                            logger.warning(f"[card-sched] alert gönderilemedi: {_ae}")
        publish_ms = int((time.perf_counter() - _p0) * 1000)
        # KRİTİK FIX: publish başarısızsa YALAN 'auto_scheduled' YAZMA → pending_review,
        # postiz_post_id YOK. Böylece sessiz kayıp olmaz; operatör onaya görür.
        eff_status = status if publish_ok else "pending_review"
        eff_postiz = postiz_id if publish_ok else None
        write_card_drafts(account_id=account_id, persona=persona, card=card,
                          scheduled_at_iso=when.isoformat(), status=eff_status,
                          trend_id=trend_id, postiz_post_id=eff_postiz, hype_run_id=run_id)
        _safe_log(run_id, order, f"Yayın #{i+1}",
                  {"node": "publish", "card_index": i, "platforms": list(CARD_PLATFORMS),
                   "scheduled_at": when.isoformat(), "status": eff_status,
                   "postiz_post_id": eff_postiz, "publish_ok": publish_ok},
                  status=("success" if publish_ok else "failed"),
                  duration_ms=publish_ms)
        order += 1
        summaries.append({"index": i, "kind": kind, "key": card["key"], "image_url": card["image_url"]})
        written += 1

    if run_id:
        try:
            finalize_run(run_id, status="completed", started_at_ts=started, trend_id=trend_id,
                         flow_state={"run_kind": "cards", "card_source": source,
                                     "card_count": written, "cards": summaries})
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[card-sched] finalize_run hata: {e}")
    return written


async def schedule_drought_cards(account_id: str, *, count: int = 4,
                                 status: Optional[str] = None, use_llm: bool = True) -> int:
    """Kurak gün: count kart (alternatif tip), CREW'in seçtiği İstanbul saatlerine."""
    persona = resolve_persona(account_id)
    if not persona:
        logger.warning(f"[card-sched] persona yok, kurak atlandı: {account_id}")
        return 0
    times = sorted(await llm_pick_times(count) if use_llm else fallback_times(count))
    kinds = assign_kinds_chronological(account_id, times)
    n = await _run_card_batch(account_id, persona, source="drought", kinds=kinds, times=times)
    logger.info(f"[card-sched] KURAK {n}/{count} kart acc={account_id}")
    return n


async def schedule_companion_cards(account_id: str, *, news_topic: str,
                                   news_source: Optional[str] = None, trend_id=None,
                                   base_time_utc: Optional[dt.datetime] = None,
                                   status: Optional[str] = None) -> int:
    """Haber-sonrası: o habere bağlı 1 SÖZLÜK + 1 SENCE?, haberden sonraki slotlara."""
    persona = resolve_persona(account_id)
    if not persona:
        return 0
    base = base_time_utc or dt.datetime.now(dt.timezone.utc)
    # Çift-çift önleme: companion'ı, halihazırda kuyrukta planlanmış son kartın
    # SONRASINA çapala (araya girip alternasyonu kıramasın). Kuyruk boşsa base.
    last = latest_scheduled_card_time(account_id)
    anchor = max(base, last) if last else base
    times = sorted([anchor + dt.timedelta(hours=3), anchor + dt.timedelta(hours=6)])
    kinds = assign_kinds_chronological(account_id, times)
    n = await _run_card_batch(account_id, persona, source="companion", kinds=kinds, times=times,
                              trend_id=trend_id, news_topic=news_topic, news_source=news_source)
    logger.info(f"[card-sched] COMPANION {n}/2 kart acc={account_id} trend={trend_id}")
    return n
