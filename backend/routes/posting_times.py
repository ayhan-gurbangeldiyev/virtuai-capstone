"""
Optimal Posting Times API.
Analyzes generation history + general Twitter best practices for TR audience.
Returns heatmap data (7 days x 24 hours).
"""
from fastapi import APIRouter, Depends, Header
from middleware.auth import require_auth
from services.access_control import accessible_owner_ids
from middleware.active_account import get_active_account
from typing import Optional
from collections import Counter, defaultdict
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/posting-times", tags=["posting-times"])


def get_supabase():
    from server import supabase
    return supabase


# Turkey Twitter best practices (engagement multiplier 0-1)
# Based on general TR social media research
TR_BASE_HEATMAP = {
    # (day_of_week, hour): score
    # Monday
    **{(0, h): 0.3 for h in range(0, 7)},
    **{(0, h): 0.7 for h in range(7, 9)},
    (0, 9): 0.9, (0, 10): 0.85, (0, 11): 0.8,
    (0, 12): 0.9, (0, 13): 0.85,
    **{(0, h): 0.6 for h in range(14, 17)},
    (0, 17): 0.75, (0, 18): 0.85, (0, 19): 0.9, (0, 20): 0.95,
    (0, 21): 0.9, (0, 22): 0.7, (0, 23): 0.5,
    # Tuesday
    **{(1, h): 0.3 for h in range(0, 7)},
    **{(1, h): 0.7 for h in range(7, 9)},
    (1, 9): 0.85, (1, 10): 0.9, (1, 11): 0.85,
    (1, 12): 0.9, (1, 13): 0.8,
    **{(1, h): 0.6 for h in range(14, 17)},
    (1, 17): 0.8, (1, 18): 0.9, (1, 19): 0.95, (1, 20): 1.0,
    (1, 21): 0.9, (1, 22): 0.7, (1, 23): 0.5,
    # Wednesday
    **{(2, h): 0.3 for h in range(0, 7)},
    **{(2, h): 0.7 for h in range(7, 9)},
    (2, 9): 0.9, (2, 10): 0.95, (2, 11): 0.85,
    (2, 12): 0.9, (2, 13): 0.8,
    **{(2, h): 0.65 for h in range(14, 17)},
    (2, 17): 0.8, (2, 18): 0.85, (2, 19): 0.9, (2, 20): 0.95,
    (2, 21): 0.85, (2, 22): 0.65, (2, 23): 0.45,
    # Thursday
    **{(3, h): 0.3 for h in range(0, 7)},
    **{(3, h): 0.7 for h in range(7, 9)},
    (3, 9): 0.85, (3, 10): 0.9, (3, 11): 0.8,
    (3, 12): 0.85, (3, 13): 0.8,
    **{(3, h): 0.6 for h in range(14, 17)},
    (3, 17): 0.75, (3, 18): 0.85, (3, 19): 0.9, (3, 20): 0.95,
    (3, 21): 0.9, (3, 22): 0.7, (3, 23): 0.5,
    # Friday
    **{(4, h): 0.3 for h in range(0, 7)},
    **{(4, h): 0.65 for h in range(7, 9)},
    (4, 9): 0.8, (4, 10): 0.85, (4, 11): 0.8,
    (4, 12): 0.85, (4, 13): 0.75,
    **{(4, h): 0.55 for h in range(14, 17)},
    (4, 17): 0.7, (4, 18): 0.8, (4, 19): 0.85, (4, 20): 0.9,
    (4, 21): 0.85, (4, 22): 0.75, (4, 23): 0.6,
    # Saturday
    **{(5, h): 0.35 for h in range(0, 8)},
    **{(5, h): 0.6 for h in range(8, 10)},
    (5, 10): 0.75, (5, 11): 0.85, (5, 12): 0.9, (5, 13): 0.85,
    (5, 14): 0.8, (5, 15): 0.75, (5, 16): 0.7,
    (5, 17): 0.75, (5, 18): 0.8, (5, 19): 0.85, (5, 20): 0.9,
    (5, 21): 0.95, (5, 22): 0.85, (5, 23): 0.7,
    # Sunday
    **{(6, h): 0.4 for h in range(0, 9)},
    (6, 9): 0.55, (6, 10): 0.7, (6, 11): 0.8, (6, 12): 0.85,
    (6, 13): 0.8, (6, 14): 0.75, (6, 15): 0.7,
    **{(6, h): 0.65 for h in range(16, 18)},
    (6, 18): 0.75, (6, 19): 0.85, (6, 20): 0.95, (6, 21): 1.0,
    (6, 22): 0.85, (6, 23): 0.6,
}

DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


@router.get("/heatmap")
async def get_posting_heatmap(user=Depends(require_auth), account_id: str = Depends(get_active_account)):
    """
    Return 7x24 heatmap data for optimal posting times.
    Combines TR base data with user's generation/favorite patterns.
    """
    try:
        sb = get_supabase()

        # Get user's favorited content timestamps (scoped to current user)
        favs = sb.table("favorites").select("created_at").in_("user_id", accessible_owner_ids(user.id)).eq("account_id", account_id).execute()
        fav_hours = defaultdict(int)
        for f in (favs.data or []):
            try:
                dt = datetime.fromisoformat(f["created_at"].replace("Z", "+00:00"))
                # Convert to Istanbul time (UTC+3)
                hour = (dt.hour + 3) % 24
                day = dt.weekday()
                fav_hours[(day, hour)] += 1
            except Exception:
                continue

        # Build heatmap
        heatmap = []
        best_slots = []

        for day in range(7):
            row = []
            for hour in range(24):
                base_score = TR_BASE_HEATMAP.get((day, hour), 0.5)

                # Boost if user has favorites at this time
                user_boost = min(fav_hours.get((day, hour), 0) * 0.05, 0.2)
                score = min(base_score + user_boost, 1.0)
                score = round(score, 2)

                row.append(score)

                if score >= 0.9:
                    best_slots.append({
                        "day": DAYS_TR[day],
                        "day_index": day,
                        "hour": hour,
                        "time": f"{hour:02d}:00",
                        "score": score,
                    })

            heatmap.append(row)

        # Sort best slots by score
        best_slots.sort(key=lambda x: x["score"], reverse=True)

        return {
            "heatmap": heatmap,
            "days": DAYS_TR,
            "best_slots": best_slots[:10],
            "timezone": "Europe/Istanbul (UTC+3)",
            "data_source": "TR Twitter best practices" + (
                " + kullanıcı verileri" if fav_hours else ""
            ),
        }

    except Exception as e:
        logger.error(f"Posting times error: {e}")
        return {
            "heatmap": [[0.5] * 24 for _ in range(7)],
            "days": DAYS_TR,
            "best_slots": [],
            "timezone": "Europe/Istanbul (UTC+3)",
            "data_source": "fallback",
        }


@router.get("/best-now")
async def get_best_time_now(user=Depends(require_auth), account_id: str = Depends(get_active_account)):
    """Quick check: is now a good time to post?"""
    now = datetime.utcnow()
    istanbul_hour = (now.hour + 3) % 24
    day = now.weekday()

    score = TR_BASE_HEATMAP.get((day, istanbul_hour), 0.5)

    if score >= 0.9:
        verdict = "🟢 Harika zaman! Şimdi paylaş."
    elif score >= 0.7:
        verdict = "🟡 İyi zaman. Paylaşabilirsin."
    elif score >= 0.5:
        verdict = "🟠 Orta. Daha iyi saatler var."
    else:
        verdict = "🔴 Düşük etkileşim saati. Bekle."

    # Next best slot
    best_upcoming = None
    for h_offset in range(1, 25):
        check_hour = (istanbul_hour + h_offset) % 24
        check_day = (day + ((istanbul_hour + h_offset) // 24)) % 7
        s = TR_BASE_HEATMAP.get((check_day, check_hour), 0.5)
        if s >= 0.9:
            best_upcoming = {
                "day": DAYS_TR[check_day],
                "hour": check_hour,
                "time": f"{check_hour:02d}:00",
                "score": s,
                "hours_away": h_offset,
            }
            break

    return {
        "current_score": score,
        "current_time": f"{istanbul_hour:02d}:00",
        "current_day": DAYS_TR[day],
        "verdict": verdict,
        "next_best": best_upcoming,
    }
