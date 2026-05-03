"""
garmin_telemetry.py — Post-workout execution telemetry extraction.

Fetches actual workout performance data from Garmin Connect after a session
completes and persists it to Supabase for use in the next morning's
readiness briefing.

Triggered by:
  - /sync_workout command (on-demand)
  - Scheduled 8:00 PM daily job in main.py

Usage:
    from garmin_telemetry import sync_todays_workout
    result = sync_todays_workout(client)
"""

import logging
from datetime import date
from typing import Any, Dict, Optional

from garminconnect import Garmin

logger = logging.getLogger(__name__)


# ── Extraction helpers ────────────────────────────────────────────────────────

def _pick_best_activity(activities: list) -> Optional[Dict[str, Any]]:
    """Return the longest activity from today's list (most likely the main session).

    Filters out very short incidentals (< 10 minutes).
    """
    eligible = [a for a in activities if (a.get("duration") or 0) > 600]
    if not eligible:
        return None
    return max(eligible, key=lambda a: a.get("duration", 0))


def _extract_telemetry(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the performance fields we care about from a raw activity dict."""
    return {
        "activity_id":   activity.get("activityId"),
        "activity_name": activity.get("activityName"),
        "activity_type": activity.get("activityType", {}).get("typeKey"),
        "duration_secs": int(activity.get("duration") or 0),
        "distance_meters": activity.get("distance"),
        "avg_hr":   int(activity["averageHR"]) if activity.get("averageHR") is not None else None,
        "max_hr":   int(activity["maxHR"])     if activity.get("maxHR")     is not None else None,
        "aerobic_training_effect":    activity.get("aerobicTrainingEffect"),
        "anaerobic_training_effect":  activity.get("anaerobicTrainingEffect"),
        "vo2max_value": activity.get("vO2MaxValue"),
        "avg_power":    activity.get("avgPower"),
        "calories":     int(activity["calories"]) if activity.get("calories") is not None else None,
        "raw_json":     activity,
    }


def _calculate_pace_100m(distance_m: float, duration_secs: float) -> Optional[str]:
    """Return average pace per 100 m as MM:SS string, or None if inputs are missing."""
    if not distance_m or not duration_secs:
        return None
    secs_per_100m = (duration_secs / distance_m) * 100
    mins = int(secs_per_100m // 60)
    secs = int(secs_per_100m % 60)
    return f"{mins}:{secs:02d}"


def _extract_swim_telemetry(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Extract swim-specific fields on top of the base telemetry."""
    base = _extract_telemetry(activity)
    base.update({
        "swim_stroke_type":       activity.get("strokeType", {}).get("strokeTypeKey"),
        "avg_strokes_per_length": activity.get("avgStrokes"),
        "pool_length_meters":     activity.get("poolLength"),
        "num_lengths":            activity.get("numActiveLengths"),
        "total_distance_meters":  activity.get("distance"),
        "avg_pace_per_100m":      _calculate_pace_100m(
            activity.get("distance"), activity.get("duration")
        ),
        "best_pace_per_100m":     activity.get("minPace100m"),
    })
    return base


# ── Public API ────────────────────────────────────────────────────────────────

def sync_todays_workout(client: Garmin, target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """Fetch today's best activity from Garmin and persist it to Supabase.

    Args:
        client:      Authenticated Garmin client.
        target_date: Date to sync (defaults to today).

    Returns:
        The extracted telemetry dict on success, or None if no activity found.
    """
    if target_date is None:
        target_date = date.today()

    date_str = target_date.isoformat()
    logger.info("🔄 Syncing workout telemetry for %s …", date_str)

    try:
        activities = client.get_activities_by_date(date_str, date_str) or []
    except Exception as exc:
        logger.error("Failed to fetch activities for %s: %s", date_str, exc)
        return None

    if not activities:
        logger.info("No activities found for %s.", date_str)
        return None

    activity = _pick_best_activity(activities)
    if not activity:
        logger.info("All activities for %s were under 10 minutes — skipping.", date_str)
        return None

    activity_type = activity.get("activityType", {}).get("typeKey", "")
    if "swimming" in activity_type:
        telemetry = _extract_swim_telemetry(activity)
    else:
        telemetry = _extract_telemetry(activity)

    from db_manager import save_completed_workout
    save_completed_workout(date_str, telemetry)

    logger.info(
        "✅ Synced: %s | %.0fm | AvgHR %s | AerobicTE %.1f",
        telemetry["activity_name"],
        (telemetry["duration_secs"] or 0) / 60,
        telemetry["avg_hr"] or "N/A",
        telemetry["aerobic_training_effect"] or 0,
    )
    return telemetry


def format_execution_context(telemetry: Dict[str, Any]) -> str:
    """Format a telemetry dict into a compact string for the Gemini prompt.

    Example output:
        Yesterday's execution — Easy Run 5–7 km:
        Duration: 48 min | AvgHR: 142 bpm | MaxHR: 158 bpm
        Aerobic TE: 3.2 | Anaerobic TE: 0.8 | VO2Max: 47.3
    """
    if not telemetry:
        return ""

    duration_min = round((telemetry.get("duration_secs") or 0) / 60)
    parts = [
        f"Yesterday's execution — {telemetry.get('activity_name', 'Unknown')}:",
        f"Duration: {duration_min} min",
    ]

    if telemetry.get("avg_hr"):
        parts.append(f"AvgHR: {telemetry['avg_hr']} bpm")
    if telemetry.get("max_hr"):
        parts.append(f"MaxHR: {telemetry['max_hr']} bpm")
    if telemetry.get("aerobic_training_effect") is not None:
        parts.append(f"Aerobic TE: {telemetry['aerobic_training_effect']:.1f}")
    if telemetry.get("anaerobic_training_effect") is not None:
        parts.append(f"Anaerobic TE: {telemetry['anaerobic_training_effect']:.1f}")
    if telemetry.get("vo2max_value"):
        parts.append(f"VO2Max: {telemetry['vo2max_value']:.1f}")

    # First item is the label, rest join as a single line
    summary = parts[0] + "\n" + " | ".join(parts[1:])

    # Append swim-specific line when present
    swim_parts = []
    if telemetry.get("total_distance_meters"):
        swim_parts.append(f"Distance: {telemetry['total_distance_meters']:.0f} m")
    if telemetry.get("avg_pace_per_100m"):
        swim_parts.append(f"Avg pace: {telemetry['avg_pace_per_100m']}/100m")
    if telemetry.get("num_lengths"):
        swim_parts.append(f"Lengths: {telemetry['num_lengths']}")
    if telemetry.get("swim_stroke_type"):
        swim_parts.append(f"Stroke: {telemetry['swim_stroke_type']}")
    if swim_parts:
        summary += "\n" + " | ".join(swim_parts)

    return summary
