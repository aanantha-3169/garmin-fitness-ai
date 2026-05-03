"""
garmin_metrics.py — Fetch daily health metrics from Garmin Connect.

Produces a clean JSON-serializable dict with:
  - Sleep Score
  - Resting Heart Rate
  - HRV (overnight avg + status)
  - Body Battery (current level)
  - Calories (total, active, resting)
  - All-Day Stress Score

Each metric is individually wrapped with error handling so that
a single missing/unsynced metric never blocks the rest.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from garminconnect import Garmin

logger = logging.getLogger(__name__)


def _safe_call(label: str, fn, *args, **kwargs) -> Optional[Any]:
    """Call *fn* and return its result, or None on any error."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning("⚠️  Could not fetch %s: %s", label, exc)
        return None


# ── Individual metric extractors ─────────────────────────────────────────────

def _extract_sleep_score(client: Garmin, cdate: str) -> Dict[str, Any]:
    """Sleep score + breakdown from last night."""
    data = _safe_call("sleep", client.get_sleep_data, cdate)
    if not data:
        return {"sleep_score": None, "sleep_quality": None, "note": "Sleep data not available"}

    dto = data.get("dailySleepDTO", {})
    scores = dto.get("sleepScores", {})
    overall = scores.get("overall", {})

    deep_pct = scores.get("deepPercentage", {}).get("value")
    rem_pct = scores.get("remPercentage", {}).get("value")
    light_pct = scores.get("lightPercentage", {}).get("value")

    sleep_secs = dto.get("sleepTimeSeconds")
    sleep_hours = round(sleep_secs / 3600, 1) if sleep_secs else None

    return {
        "sleep_score": overall.get("value"),
        "sleep_quality": overall.get("qualifierKey"),
        "sleep_duration_hours": sleep_hours,
        "deep_sleep_pct": deep_pct,
        "rem_sleep_pct": rem_pct,
        "light_sleep_pct": light_pct,
    }


def _extract_resting_heart_rate(client: Garmin, cdate: str) -> Dict[str, Any]:
    """Resting heart rate for the given day."""
    data = _safe_call("resting heart rate", client.get_rhr_day, cdate)
    if not data:
        return {"resting_heart_rate_bpm": None, "note": "RHR data not available"}

    metrics_map = (
        data.get("allMetrics", {})
            .get("metricsMap", {})
            .get("WELLNESS_RESTING_HEART_RATE", [])
    )
    rhr = int(metrics_map[0]["value"]) if metrics_map else None
    return {"resting_heart_rate_bpm": rhr}


def _extract_hrv(client: Garmin, cdate: str) -> Dict[str, Any]:
    """Overnight HRV average and status."""
    data = _safe_call("HRV", client.get_hrv_data, cdate)
    if not data:
        return {"hrv_overnight_avg": None, "hrv_status": None, "note": "HRV data not available"}

    summary = data.get("hrvSummary", {})
    baseline = summary.get("baseline", {})

    return {
        "hrv_overnight_avg": summary.get("lastNightAvg"),
        "hrv_weekly_avg": summary.get("weeklyAvg"),
        "hrv_status": summary.get("status"),
        "hrv_baseline_balanced_range": (
            f"{baseline.get('balancedLow')}-{baseline.get('balancedUpper')}"
            if baseline.get("balancedLow") is not None else None
        ),
    }


def _extract_body_battery(client: Garmin, cdate: str) -> Dict[str, Any]:
    """Most recent body battery reading."""
    data = _safe_call("body battery", client.get_body_battery, cdate)
    if not data:
        return {"body_battery_current": None, "note": "Body battery data not available"}

    entry = data[0] if data else {}
    values = entry.get("bodyBatteryValuesArray", [])

    # Walk backwards to find the latest non‑null reading
    current = None
    for pair in reversed(values):
        if len(pair) >= 2 and pair[1] is not None:
            current = pair[1]
            break

    return {
        "body_battery_current": current,
        "body_battery_charged": entry.get("charged"),
        "body_battery_drained": entry.get("drained"),
    }


def _extract_calories(client: Garmin, cdate: str) -> Dict[str, Any]:
    """Total, active, and resting calories."""
    data = _safe_call("calories", client.get_user_summary, cdate)
    if not data:
        return {"calories_total": None, "note": "Calorie data not available"}

    total = data.get("totalKilocalories")
    active = data.get("activeKilocalories")
    resting = data.get("bmrKilocalories")

    return {
        "calories_total": int(total) if total is not None else None,
        "calories_active": int(active) if active is not None else None,
        "calories_resting": int(resting) if resting is not None else None,
    }


def _extract_stress(client: Garmin, cdate: str) -> Dict[str, Any]:
    """All-day average and max stress levels."""
    data = _safe_call("stress", client.get_all_day_stress, cdate)
    if not data:
        return {"stress_avg": None, "note": "Stress data not available"}

    return {
        "stress_avg": data.get("avgStressLevel"),
        "stress_max": data.get("maxStressLevel"),
    }


def _extract_activities(client: Garmin, cdate: str) -> list:
    """Fetch raw activities for the given day."""
    return _safe_call("activities", client.get_activities_by_date, cdate, cdate) or []


# ── HRmax ─────────────────────────────────────────────────────────────────────

# Last-resort fallback if Garmin is unreachable AND the DB cache is empty.
# Update this when a new confirmed max is observed during a field test.
HR_MAX_FALLBACK = 196  # observed during run, May 2026


def get_hr_max(client: Optional[Garmin] = None) -> int:
    """Return the athlete's current observed HRmax.

    Resolution order (first success wins):
      1. Garmin API  — client.get_stats() -> maxHeartRate
      2. DB cache    — most recent 'hr_max' row in metric_logs
      3. Hardcoded   — HR_MAX_FALLBACK constant (update after confirmed field test)

    When the Garmin API returns a value higher than the cached value it is
    immediately persisted to the DB so future fallbacks are up to date.

    Args:
        client: Authenticated Garmin client. Pass None to skip API fetch
                and use the DB/hardcoded fallback directly.

    Returns:
        HRmax as an int (always >= 1).
    """
    from db_manager import get_cached_hr_max, save_cached_hr_max

    garmin_value: Optional[int] = None

    # 1. Try Garmin API
    if client is not None:
        stats = _safe_call("user stats", client.get_stats, date.today().isoformat())
        if stats:
            raw = stats.get("maxHeartRate") or stats.get("userMaxHeartRate")
            if raw and int(raw) > 0:
                garmin_value = int(raw)
                logger.info("❤️  Garmin HRmax from API: %d bpm", garmin_value)

    # 2. Try DB cache
    cached_value = get_cached_hr_max()

    # Persist to DB if API returned a new high
    if garmin_value is not None:
        if cached_value is None or garmin_value > cached_value:
            save_cached_hr_max(garmin_value)
            logger.info("💾  HRmax updated in DB cache: %d bpm", garmin_value)
        return garmin_value

    if cached_value is not None:
        logger.info("❤️  HRmax from DB cache: %d bpm", cached_value)
        return cached_value

    # 3. Hardcoded fallback
    logger.warning(
        "⚠️  Could not fetch HRmax from Garmin or DB. Using fallback: %d bpm",
        HR_MAX_FALLBACK,
    )
    return HR_MAX_FALLBACK


# ── Public API ───────────────────────────────────────────────────────────────


def get_health_metrics(client: Garmin) -> Dict[str, Any]:
    """Retrieve a comprehensive set of health metrics.

    Uses *yesterday* for sleep / HRV (overnight data) and
    *today* for body battery, calories, and stress (current / in-progress).

    Returns a JSON-serializable dict.
    """
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()

    metrics = {
        "date_yesterday": yesterday,
        "date_today": today,
        "sleep": _extract_sleep_score(client, yesterday),
        "resting_heart_rate": _extract_resting_heart_rate(client, yesterday),
        "hrv": _extract_hrv(client, yesterday),
        "body_battery": _extract_body_battery(client, today),
        "calories": _extract_calories(client, today),
        "stress": _extract_stress(client, today),
    }

    return metrics


def check_todays_activity_status(client: Garmin, expected_workout_type: str) -> bool:
    """Check if today's training obligation is fulfilled.

    Fulfilled if:
    1. A matching activity is found in Garmin (>15m).
    2. OR the workout was marked as 'moved' in Supabase.
    """
    today_str = date.today().isoformat()
    
    # 1. Check Supabase for 'moved' status
    try:
        from db_manager import get_daily_log
        log = get_daily_log(today_str)
        if log and log.get("workout_moved"):
            logger.info("📅 Workout for today was moved tomorrow (found in Supabase).")
            return True
    except Exception as exc:
        logger.warning("Could not check Supabase for workout_moved: %s", exc)

    # 2. Check Garmin Activities
    activities = _extract_activities(client, today_str)

    for activity in activities:
        atype = activity.get("activityType", {}).get("typeKey")
        duration = activity.get("duration", 0)

        if atype == expected_workout_type and duration > 900:
            logger.info(
                "✅ Found completed '%s' activity: %s (%.1fm)",
                expected_workout_type, activity.get("activityName"), duration / 60
            )
            return True

    logger.info("❌ No completed '%s' (>15m) found for today.", expected_workout_type)
    return False
