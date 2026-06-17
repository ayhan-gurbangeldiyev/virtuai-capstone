"""
Quota Manager — XQuik API quota-aware degradation.

GET /account ile kalan quota kontrol (ücretsiz, 10dk cache).
Kademeli degradasyon: normal → reduced → minimal → free-only.
"""
import logging
import os
from services.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)

# Degradasyon seviyeleri — MUTLAK kalan krediye göre (creditInfo.balance).
# 2026-06-14 (Berkay kota endişesi): eski kod /account'tan currentPeriodUsage +
# quotaRemaining okuyordu ama XQuik /account'ta o alanlar YOK (doc: krediler
# `creditInfo` objesinde: balance/lifetimeUsed/lifetimePurchased). Bu yüzden
# parse hep 0 default'una düşüp sistem hep "normal/%0" görüyordu → kota-koruması
# KÖR. Artık gerçek `balance` okunuyor + alan okunamazsa fail-loud (sessiz normal yok).
NORMAL = "normal"
REDUCED = "reduced"
MINIMAL = "minimal"
FREE_ONLY = "free_only"

# Mutlak kredi eşikleri (env ile ayarlanır; default ~335K bütçe + ~1K/gün burn'e göre
# runway mantığı: >50K≈50+gün NORMAL, >20K REDUCED, >5K MINIMAL, altı FREE_ONLY).
_BAL_NORMAL = int(os.environ.get("QUOTA_BALANCE_NORMAL", "50000"))
_BAL_REDUCED = int(os.environ.get("QUOTA_BALANCE_REDUCED", "20000"))
_BAL_MINIMAL = int(os.environ.get("QUOTA_BALANCE_MINIMAL", "5000"))

CACHE_KEY = "quota:status"
CACHE_TTL = 600  # 10 dakika


def _to_int(v) -> int:
    """XQuik Bigint-string ('123456') → int. Bozuksa -1 (okunamadı işareti)."""
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return -1


async def get_quota_status() -> dict:
    """
    XQuik quota durumunu kontrol et.
    Ücretsiz, 10dk cache'li.

    Returns:
        {
            "mode": "normal"|"reduced"|"minimal"|"free_only",
            "usage_percent": float,
            "remaining": int,
            "batch_limit_multiplier": float,
            "trends_enabled": bool,
            "analysis_enabled": bool,
        }
    """
    # Cache'ten bak
    cached = await cache_get(CACHE_KEY)
    if cached:
        return cached

    # XQuik'ten çek
    try:
        from services.xquik_client import xquik
        account = await xquik.get_account()
    except Exception as e:
        logger.error(f"[quota] /account çağrısı başarısız: {e} → REDUCED (fail-safe)")
        # Hata: cache'leme (geçici olabilir), her çağrı tekrar denesin.
        return _build_status(REDUCED, usage_pct=-1, remaining=-1)

    # Plan inaktifse paid akışı durdur.
    plan = str(account.get("plan") or "").strip().lower()
    if plan and plan != "active":
        logger.error(f"[quota] plan='{plan}' (active değil) → FREE_ONLY")
        status = _build_status(FREE_ONLY, usage_pct=100, remaining=0)
        await cache_set(CACHE_KEY, status, CACHE_TTL)
        return status

    # Krediler creditInfo objesinde (doc: balance/lifetimeUsed/lifetimePurchased).
    credit = account.get("creditInfo")
    if not isinstance(credit, dict) or "balance" not in credit:
        # FAIL-LOUD: alan okunamadı → sessizce "normal" DEME. Throttle + ERROR.
        # (Aktif hesapta creditInfo her zaman olmalı; yoksa şema değişmiş ya da
        # kredi bitmiş demektir — ikisi de görünür olmalı.)
        logger.error(
            "[quota] creditInfo/balance YOK — kota okunamıyor (şema değişti mi / "
            "kredi bitti mi?). REDUCED'a düşülüyor, cache'lenmiyor."
        )
        return _build_status(REDUCED, usage_pct=-1, remaining=-1)

    balance = _to_int(credit.get("balance"))
    if balance < 0:
        logger.error(f"[quota] balance parse edilemedi: {credit.get('balance')!r} → REDUCED")
        return _build_status(REDUCED, usage_pct=-1, remaining=-1)

    # Görüntü için kullanım yüzdesi (lifetime; gating DEĞİL — gating mutlak balance).
    used = _to_int(credit.get("lifetimeUsed"))
    purchased = _to_int(credit.get("lifetimePurchased"))
    usage_pct = round(used / purchased * 100, 1) if (used >= 0 and purchased and purchased > 0) else 0

    # Gating: MUTLAK kalan kredi eşikleri.
    if balance >= _BAL_NORMAL:
        mode = NORMAL
    elif balance >= _BAL_REDUCED:
        mode = REDUCED
    elif balance >= _BAL_MINIMAL:
        mode = MINIMAL
    else:
        mode = FREE_ONLY

    status = _build_status(mode, usage_pct, balance)
    await cache_set(CACHE_KEY, status, CACHE_TTL)

    if mode != NORMAL:
        logger.warning(f"[quota] degradasyon: {mode} (kalan ~{balance} kredi, kullanım %{usage_pct})")
    else:
        logger.info(f"[quota] normal (kalan ~{balance} kredi)")

    return status


def _build_status(mode: str, usage_pct: float, remaining: int) -> dict:
    """Mod'a göre davranış parametrelerini belirle."""
    configs = {
        NORMAL: {
            "batch_limit_multiplier": 1.0,
            "trends_enabled": True,
            "analysis_enabled": True,
        },
        REDUCED: {
            "batch_limit_multiplier": 0.5,
            "trends_enabled": True,
            "analysis_enabled": True,
        },
        MINIMAL: {
            "batch_limit_multiplier": 0.3,
            "trends_enabled": False,
            "analysis_enabled": False,
        },
        FREE_ONLY: {
            "batch_limit_multiplier": 0.0,
            "trends_enabled": False,
            "analysis_enabled": False,
        },
    }

    config = configs.get(mode, configs[NORMAL])
    return {
        "mode": mode,
        "usage_percent": usage_pct,
        "remaining": remaining,
        **config,
    }
