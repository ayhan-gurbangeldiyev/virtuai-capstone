"""Editor's Desk — daily editorial-lead selection.

Takes the day's gate-passed AI candidates and runs ONE LLM pass that:
  (a) ranks them by editorial importance,
  (b) names the lead and strongest passed-over,
  (c) produces a grounded importance reason citing checkable attributes
      (recorded fields or verbatim raw_content quotes) — never vibes.

Hard integrity rule: every importance claim must trace to either a recorded
field (content_type, semantic_triggers, score) or a verbatim quote from the
candidate's raw_content. If a claim can't be grounded by that test, the
prompt instructs the LLM to drop it — never assert ungrounded.

Persistence is by `persist_judgment(sb, ...)` into `editorial_lead_judgments`.
Set `dry_run=True` for prototype / backfill runs that must not collide with
the live one-per-day unique index.

Phase 1 build — NOT wired into the planner yet. The planner will call
`select_lead()` per-day in a future phase to actually drive Cansu's flagship
pick. Until then the table is auditable history only.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

MODEL = "anthropic/claude-sonnet-4.6"
TEMPERATURE = 0.2  # lower than composer — judgment, not prose
MAX_TOKENS = 8000


SYSTEM_PROMPT_TR = """Sen bir yapay zeka editörüsün. Görevin: günün AI haberlerini GERÇEK editöryel önem sıralamasına koymak ve LIDER ile en güçlü ELENMIŞ haberi belirlemek.

GERÇEK ÖNEM — üç boyut (içerik türü / skor değil; bunlar yalnızca ipuçları):

1. BREADTH (kapsam / kitle genişliği):
   Ne kadar çok insanı, ne kadar geniş bir grubu etkiliyor?
   - Yüz milyonlarca tüketiciyi etkileyen kitle ürünü (ChatGPT, Instagram, iPhone) → çok geniş
   - Belirli bir sektörü (life sciences enterprise, security teams) → dar
   - Tek bir analist tahmini, basın bülteni → en dar

2. MAGNITUDE (büyüklük):
   Incremental update mu, major release mı, first-of-its-kind milestone mu?
   - "İlk kez", "tarihinde ilk", "purpose-built", "new series" → milestone
   - Major launch (yeni model, yeni ürün hattı) → major
   - Feature ekleme, fiyat güncelleme, küçük iyileştirme → incremental

3. TIMELINESS (güncellik):
   Bugün gerçekten yeni bir haber mi, yoksa tekrarlayan / geçmişin yeniden anlatımı mı?
   - Bugün/dün yayınlanmış bir duyuru → güncel
   - Önceki günlerin uzantısı, tahmin, rivayet → güncel değil

Bu üç boyutu BİRLİKTE değerlendir. Tek başına content_type veya score'a göre sıralama yapma. content_type bir ipucu; gerçek soru: bu haber kimi etkiliyor, ne kadar büyük, bugün mü?

ÖRNEK TEST: kitle tüketici ürününün küçük bir güncellemesi (yüz milyonlarca kullanıcı) ile niche enterprise alanının tam yeni bir lansmanı (binlerce alan uzmanı) çakıştığında: breadth × magnitude × timeliness birlikte değerlendirilmeli; otomatik olarak "lansman > güncelleme" denemez.

İDDIA TOPRAKLAMA — ÜÇ TİP KABUL EDILİR:

a. `recorded_field`: kayıtlı alan (content_type, score, semantic_triggers, source_name, published_at)
b. `raw_content_quote`: haberin raw_content'inden VERBATIM alıntı
c. `entity_common_knowledge`: adlandırılmış bir varlık (ChatGPT, OpenAI, Anthropic, NVIDIA, iPhone vb.) hakkında bağımsız operatörün TEK BİR WEB ARAMASIYLA doğrulayabileceği yaygın bilinen olgular.
   - GEÇERLİ örnek: "ChatGPT kitle tüketici ürünüdür ve yüz milyonlarca kullanıcısı vardır" (genel bilgi, kolayca doğrulanabilir)
   - GEÇERLİ örnek: "GPT-Rosalind hayat bilimleri kurumsal pazarına yönelik niche bir modeldir" (lansman tanımında açıkça belirtiliyor, sektör kapsamı bilinir)
   - GEÇERSİZ örnek: "ChatGPT'nin tam olarak 800 milyon kullanıcısı var" (uydurma sayı)
   - GEÇERSİZ örnek: "Bu sektörü değiştirecek" (his, vibe)
   - GEÇERSİZ örnek: "Geçen ay X şirketi Y yaptı" (kaynakta olmayan tarih veya olay)

YASAK: uydurma sayılar, kaynakta olmayan tarihler, his temelli iddialar ("game-changing", "revolutionary"), öznel önem yargıları.

Topraklayamadığın her iddiayı DÜŞÜR ve `dropped_claims` listesine ekle.

ABSOLUT ÖNEM SKORU (pool-invariant):

Her aday için `absolute_importance` alanı doldur (0-100). Bu skor aday havuzundan bağımsız olmalı: aynı haber, başka bir günün havuzunda da aynı skoru almalı. Sıralama bu skora göre yapılır; eşit skorlarda timeliness belirleyicidir.

JSON ÇIKTI FORMATI (parse edilebilir, başka metin yok):
{
  "ranking": [
    {"label":"A","rank":1,"trend_id":"...","absolute_importance":85,
     "breadth_note":"...","magnitude_note":"...","timeliness_note":"..."},
    ...
  ],
  "lead_label": "A" veya null,
  "passed_over_label": "B" veya null,
  "reason_clauses": [
    {
      "clause": "Türkçe cümle parçası",
      "grounding": {
        "candidate_label": "A",
        "type": "recorded_field" veya "raw_content_quote" veya "entity_common_knowledge",
        "evidence": "kayıtlı alan = değer, ya da raw_content alıntısı, ya da yaygın bilinen olgu"
      }
    }
  ],
  "operator_sentence": "Cansu bugün '...' hakkında yazdı; '...'ı öne çıkarmadı çünkü ...",
  "dropped_claims": ["Topraklayamadığım için düşürdüğüm iddia"]
}

OPERATÖR CÜMLESİ FORMATI:

- Aday sayısı 0 ise: tüm alanlar null. operator_sentence = null.
- Aday sayısı 1 ise: "Cansu bugün '[lead_topic]' hakkında yazdı." (gerekirse "çünkü" parçası)
- Aday sayısı ≥2: "Cansu bugün '[lead_topic]' hakkında yazdı; '[passed_over_topic]'ı öne çıkarmadı çünkü [grounded reason]."
- lead_topic / passed_over_topic: KELIMESI KELIMESINE aday topic'leri
- grounded reason: 1-2 ayırt edici boyut (breadth / magnitude / timeliness); her biri için reason_clauses içinde per-claim grounding

LIDER SEÇİM TESTİ — bir lideri belirledikten sonra kendine sor: "Bir şüpheci editör 'neden bu, diğeri değil?' diye sorsa, breadth/magnitude/timeliness gerçeği üzerinden savunabilir miyim?" Eğer cevap "yalnızca model_launch ladder'da daha üst" ise, yeterince savunulabilir değil — yeniden değerlendir.

NOT: Cansu'nun fiilen ne yazdığını BİLMİYORSUN. Adaylar arasında bağımsız editör olarak sıralama yap.
"""


def _get_client():
    try:
        from openai import OpenAI
    except ImportError:
        return None
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None
    return OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")


# ── Fix A — topic/cluster-level re-lead dedup ──────────────────────────
# Re-lead memory is signature-based, not trend_id-based, so the same story
# under a different trend_id (different scrape, different source URL, same
# product) is still excluded. cluster_id used as a defensive fast-path
# when present (currently NULL on most trends rows — the primary signal
# is normalized-token Jaccard on the topic title).

import re as _re
import unicodedata as _ud

_TR_STOPWORDS = {
    # Only true stopwords (conjunctions, postpositions, copulas). Verbs
    # like "tanıttı / tanıtıldı / duyuruldu / sundu" carry semantic
    # content (action of the announcement) and must NOT be stripped, or
    # dedup fails for the same product announced and re-announced under
    # different inflections (Computex preview vs. unveiling).
    "ile","icin","ise","ama","veya","ya","yada","ki","de","da",
    "bir","bu","onu","ona","ben","sen","biz","siz",
    "olarak","gibi","hakkinda","kadar","sonra","once","arasinda",
    "yeni","bazi","tum","cok","daha",
    # Suffix particles that appear after apostrophe splits (Nvidia'nın
    # → "nvidia nin"). These inflate signatures and break ratio-based
    # dedup. Keep this list to genuine grammatical particles, not nouns.
    "nin","nun","den","dan","ten","tan","sin","sun","tin","tun",
}
_EN_STOPWORDS = {"the","and","for","with","new","its","into","from","that","this","than","just"}


_STEM_LEN = 5  # prefix length for Turkish-suffix-tolerant matching

# Pre-fold Turkish-specific characters to ASCII equivalents BEFORE NFKD.
# NFKD + ascii-ignore would drop these silently (ı, ş, ğ have no
# decomposition), turning "tanıttı" into "tantt" instead of "tanitti" —
# which breaks stem matching across inflections of the same word.
_TR_FOLD = str.maketrans({
    "ı": "i", "İ": "i", "i": "i",
    "ş": "s", "Ş": "s",
    "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u",
    "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c",
})


def _topic_signature(title: Optional[str]) -> set[str]:
    """Normalized token-stem set for topic-level dedup.

    Steps: Turkish-fold (ı→i, ş→s, etc.) → NFKD strip remaining diacritics
    → lower → drop punctuation → tokenize → drop stopwords → drop tokens
    <3 chars → stem to first 5 chars. The prefix-stem makes the signature
    tolerant of Turkish noun suffixes (e.g. "Nvidia'nın" → "nvidi"
    matches "NVIDIA" → "nvidi"; "tanıtıldı" → "tanit" matches "tanıttı"
    → "tanit") so the same product/event under different inflections
    still dedupes.
    """
    if not title:
        return set()
    folded = title.translate(_TR_FOLD)
    s = _ud.normalize("NFKD", folded).encode("ascii", "ignore").decode("ascii").lower()
    s = _re.sub(r"[^a-z0-9\s]", " ", s)
    tokens = [t for t in s.split() if len(t) >= 3]
    meaningful = [t for t in tokens if t not in _TR_STOPWORDS and t not in _EN_STOPWORDS]
    return {t[:_STEM_LEN] for t in meaningful}


def _topics_similar(
    sig_a: set[str], sig_b: set[str],
    min_overlap: int = 2, ratio_threshold: float = 0.5,
) -> bool:
    """Topic similarity: requires BOTH absolute overlap count AND ratio.

    Two stories are similar iff they share at least `min_overlap` stems
    AND that overlap is at least `ratio_threshold` of the smaller set.
    The absolute-count floor prevents 2-token signatures with a single
    shared common-word stem (e.g., {nvidi, pric} vs {nvidi, serv}) from
    triggering a false dedup at 0.5 ratio. The ratio floor still catches
    legitimate same-story matches.
    """
    if not sig_a or not sig_b:
        return False
    overlap = len(sig_a & sig_b)
    smaller = min(len(sig_a), len(sig_b))
    if smaller == 0:
        return False
    return overlap >= min_overlap and (overlap / smaller) >= ratio_threshold


# ── Fix B — deterministic pre-rank + top-K cap ─────────────────────────
# Bounds the LLM's output tokens so 30+ candidate days don't fail parse.
# Pre-rank approximates breadth+magnitude+timeliness from recorded
# fields; the LLM still does the real judgment on the shortlist.

def _pre_rank_score(c: dict) -> float:
    sem = {(s or "").lower() for s in (c.get("semantic_triggers") or [])}
    ct = (c.get("content_type") or "").lower()
    score = float(c.get("score") or 0)
    magnitude = 0.0
    if "milestone" in sem: magnitude += 10
    if "launch" in sem: magnitude += 6
    if "breaking" in sem: magnitude += 4
    if "feature" in sem: magnitude += 2
    ct_tier = {
        "model_launch": 8, "product_launch": 6, "feature_major": 5,
        "research": 4, "partnership": 3, "security": 3, "opinion": 1,
    }.get(ct, 2)
    # recency boost — gently prefer trends published in last 36h
    recency = 0.0
    pub = c.get("published_at")
    if pub:
        try:
            from datetime import datetime as _dt, timezone as _tz
            dt = _dt.fromisoformat(str(pub).replace("Z", "+00:00"))
            age_h = (_dt.now(_tz.utc) - dt).total_seconds() / 3600
            if age_h <= 36:
                recency = 3
            elif age_h <= 72:
                recency = 1
        except Exception:
            pass
    return score * 0.5 + magnitude * 2 + ct_tier + recency


def _cap_pool(candidates: list[dict], top_k: int) -> list[dict]:
    if top_k <= 0 or len(candidates) <= top_k:
        return list(candidates)
    return sorted(candidates, key=_pre_rank_score, reverse=True)[:top_k]


def _label_for(i: int) -> str:
    """A, B, C, ..., Z, AA, AB, ..."""
    if i < 26:
        return chr(ord("A") + i)
    return chr(ord("A") + (i // 26) - 1) + chr(ord("A") + (i % 26))


def _normalize_candidates(raw_candidates: list[dict]) -> list[dict]:
    """Project the inputs into the minimal grounded view the LLM needs.

    Each candidate must already contain: trend_id, topic, content_type,
    category, semantic_triggers, score (from hype_stages.output) plus
    source_url, source_name, raw_content (from trends row).
    """
    norm: list[dict] = []
    for i, c in enumerate(raw_candidates):
        norm.append({
            "label": _label_for(i),
            "trend_id": c.get("trend_id"),
            "cluster_id": c.get("cluster_id"),
            "topic": (c.get("topic") or "").strip(),
            "content_type": c.get("content_type"),
            "category": c.get("category"),
            "semantic_triggers": c.get("semantic_triggers") or [],
            "score": c.get("score"),
            "source_url": c.get("source_url") or c.get("url"),
            "source_name": c.get("source_name"),
            "published_at": c.get("published_at"),
            "raw_content": (c.get("raw_content") or "").strip(),
        })
    return norm


def select_lead(
    candidates: list[dict],
    recent_lead_trend_ids: Optional[list[str]] = None,
    excluded_topics: Optional[list[str]] = None,
    excluded_cluster_ids: Optional[list[str]] = None,
    top_k: int = 10,
) -> Optional[dict]:
    """Run ONE LLM pass to rank + name lead/passed-over with grounded reason.

    Three-stage exclusion (re-lead memory):
      1. trend_id match (exact)
      2. cluster_id match (when present on the candidate)
      3. topic signature similarity (≥0.5) — catches the same story
         under a different trend_id

    Then deterministic pre-rank caps the pool to top_k candidates by a
    composite breadth/magnitude/timeliness heuristic so the LLM response
    doesn't blow the token budget. The LLM still does the real importance
    judgment on the shortlist.

    Returns parsed judgment dict (with `_candidates`, `_model`,
    `_excluded_trend_ids`, `_excluded_topics`, `_capped_to_top_k`
    attached) or None on LLM unavailable / parse failure / empty filtered
    pool. Pure function w.r.t. DB.
    """
    if not candidates:
        return None
    excluded_tid_set = set(recent_lead_trend_ids or [])
    excluded_cluster_set = {c for c in (excluded_cluster_ids or []) if c}
    excluded_signatures = [_topic_signature(t) for t in (excluded_topics or []) if t]

    def _is_excluded(cand: dict) -> bool:
        tid = cand.get("trend_id")
        if tid and tid in excluded_tid_set:
            return True
        cid = cand.get("cluster_id")
        if cid and cid in excluded_cluster_set:
            return True
        sig = _topic_signature(cand.get("topic"))
        for ex_sig in excluded_signatures:
            if _topics_similar(sig, ex_sig):
                return True
        return False

    filtered = [c for c in candidates if not _is_excluded(c)]
    if not filtered:
        logger.info("editors_desk: all candidates excluded by re-lead memory (topic/cluster/trend_id)")
        return None

    capped = _cap_pool(filtered, top_k=top_k)

    client = _get_client()
    if client is None:
        logger.warning("editors_desk: no OPENROUTER_API_KEY; skipping")
        return None
    norm = _normalize_candidates(capped)
    payload = {"candidates": norm}
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TR},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])
            text = text.strip()
        parsed = json.loads(text)
    except Exception:
        logger.exception("editors_desk: LLM call or parse failed")
        return None
    parsed["_candidates"] = norm
    parsed["_model"] = MODEL
    parsed["_excluded_trend_ids"] = sorted(excluded_tid_set)
    parsed["_excluded_topics"] = sorted(excluded_topics or [])
    parsed["_excluded_cluster_ids"] = sorted(excluded_cluster_set)
    parsed["_capped_to_top_k"] = top_k if len(filtered) > top_k else None
    parsed["_pool_size_after_dedup"] = len(filtered)
    return parsed


def _label_to_candidate(label: Optional[str], candidates: list[dict]) -> Optional[dict]:
    if not label:
        return None
    return next((c for c in candidates if c["label"] == label), None)


def persist_judgment(
    sb,
    *,
    account_id: str,
    judgment_date: str,        # ISO date YYYY-MM-DD
    judgment: dict,
    dry_run: bool = False,
    notes: Optional[str] = None,
) -> Optional[str]:
    """Insert the judgment into editorial_lead_judgments. Returns new row id.

    dry_run=True: prototype / backfill rows. Unique index on
    (account_id, judgment_date) WHERE dry_run=false lets dry_run rows
    coexist with one live row per day.
    """
    if not judgment:
        return None
    cands = judgment.get("_candidates") or []
    lead = _label_to_candidate(judgment.get("lead_label"), cands)
    passed = _label_to_candidate(judgment.get("passed_over_label"), cands)
    row = {
        "account_id": account_id,
        "judgment_date": judgment_date,
        "lead_trend_id": (lead or {}).get("trend_id"),
        "passed_over_trend_id": (passed or {}).get("trend_id"),
        "lead_topic": (lead or {}).get("topic"),
        "passed_over_topic": (passed or {}).get("topic"),
        "lead_source_url": (lead or {}).get("source_url"),
        "passed_over_source_url": (passed or {}).get("source_url"),
        "candidate_count": len(cands),
        "ranking": judgment.get("ranking") or [],
        "reason_clauses": judgment.get("reason_clauses") or [],
        "operator_sentence": judgment.get("operator_sentence"),
        "dropped_claims": judgment.get("dropped_claims") or [],
        "model": judgment.get("_model") or MODEL,
        "dry_run": dry_run,
        "notes": notes,
    }
    try:
        res = sb.table("editorial_lead_judgments").insert(row).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        # Günlük-singleton (account_id, judgment_date) WHERE dry_run=false:
        # otonom sistem günde çok kez lead seçer → ikinci+ INSERT 23505 verir.
        # Bu bir hata DEĞİL — günün en güncel lead'ini UPDATE ile kaydet (upsert).
        # Trend-bazlı tekrar engeli zaten recently_covered (hype_runs) tarafında;
        # bu sadece editöryal kaydı tazeler + 23505 log gürültüsünü bitirir.
        _es = str(e)
        if not dry_run and ("23505" in _es or "duplicate key" in _es.lower()):
            try:
                _payload = {
                    k: v for k, v in row.items()
                    if k not in ("account_id", "judgment_date")
                }
                upd = (
                    sb.table("editorial_lead_judgments")
                    .update(_payload)
                    .eq("account_id", account_id)
                    .eq("judgment_date", judgment_date)
                    .eq("dry_run", False)
                    .execute()
                )
                return upd.data[0]["id"] if upd.data else None
            except Exception:
                logger.exception("editors_desk: judgment upsert-update failed")
                return None
        logger.exception("editors_desk: persist failed")
        return None
