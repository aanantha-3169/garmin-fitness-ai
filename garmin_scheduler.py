"""
garmin_scheduler.py — Schedule workouts on the Garmin Connect calendar.

Weekly training block (7-week program):
  • Monday    — PT Session (strength/functional with personal trainer)
  • Tuesday   — Easy Run 5–7 km  (distance set by morning readiness check)
  • Wednesday — PT Session
  • Thursday  — PT Session
  • Friday    — Rest Day (nothing scheduled)
  • Saturday  — Badminton
  • Sunday    — Zone 2 Long Run (90 min)

Usage:
    from garmin_client import get_garmin_client
    from garmin_scheduler import schedule_training_block

    client = get_garmin_client()
    schedule_training_block(client, weeks=7)
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from garminconnect import Garmin

logger = logging.getLogger(__name__)

# ── Sport type constants ─────────────────────────────────────────────────────
SPORT_STRENGTH  = {"sportTypeId": 5,  "sportTypeKey": "strength_training"}
SPORT_RUNNING   = {"sportTypeId": 1,  "sportTypeKey": "running"}
SPORT_BADMINTON = {"sportTypeId": 63, "sportTypeKey": "racket_sports"}


# ── Weekly schedule definition ───────────────────────────────────────────────
# weekday(): Mon=0 Tue=1 Wed=2 Thu=3 Fri=4 Sat=5 Sun=6

_WEEKLY_SCHEDULE = {
    0: {  # Monday
        "name": "PT Session",
        "sport_type": SPORT_STRENGTH,
        "description": "Personal trainer session — strength & functional movement",
        "duration_minutes": 60,
    },
    1: {  # Tuesday
        "name": "Easy Run 5–7 km",
        "sport_type": SPORT_RUNNING,
        "description": "Easy aerobic run. Target distance 5 km (low readiness) to 7 km (high readiness).",
        "duration_minutes": 45,
    },
    2: {  # Wednesday
        "name": "PT Session",
        "sport_type": SPORT_STRENGTH,
        "description": "Personal trainer session — strength & functional movement",
        "duration_minutes": 60,
    },
    3: {  # Thursday
        "name": "PT Session",
        "sport_type": SPORT_STRENGTH,
        "description": "Personal trainer session — strength & functional movement",
        "duration_minutes": 60,
    },
    # Friday (4) — rest, nothing scheduled
    5: {  # Saturday
        "name": "Badminton",
        "sport_type": SPORT_BADMINTON,
        "description": "Badminton match / recreational play",
        "duration_minutes": 90,
    },
    6: {  # Sunday
        "name": "Zone 2 Long Run",
        "sport_type": SPORT_RUNNING,
        "description": "Zone 2 steady-state aerobic run",
        "duration_minutes": 90,
    },
}


# ── Low-level helpers ────────────────────────────────────────────────────────

def _get_calendar_items(client: Garmin, target_date: date) -> List[Dict[str, Any]]:
    """Return all calendar items for the month containing *target_date*."""
    month_index = target_date.month - 1  # Garmin uses 0-indexed months
    path = f"/calendar-service/year/{target_date.year}/month/{month_index}"
    try:
        data = client.connectapi(path, method="GET")
        return data.get("calendarItems", [])
    except Exception as exc:
        logger.warning("Could not fetch calendar for %s: %s", target_date, exc)
        return []


def _workout_exists_on_date(
    calendar_items: List[Dict[str, Any]],
    name: str,
    target_date: date,
) -> bool:
    """Return True if a workout with *name* already exists on *target_date*."""
    target_str = target_date.isoformat()
    for item in calendar_items:
        if (
            item.get("itemType") == "workout"
            and item.get("date") == target_str
            and item.get("title") == name
        ):
            return True
    return False


def _create_workout(
    client: Garmin,
    name: str,
    sport_type: Dict[str, Any],
    description: str = "",
    duration_minutes: Optional[int] = None,
) -> Optional[int]:
    """Create a workout definition and return its workoutId."""
    payload: Dict[str, Any] = {
        "workoutName": name,
        "description": description,
        "sportType": sport_type,
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": sport_type,
                "workoutSteps": [
                    {
                        "type": "ExecutableStepDTO",
                        "stepOrder": 1,
                        "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
                        "endCondition": {
                            "conditionTypeId": 7,
                            "conditionTypeKey": "iterations",
                        },
                        "endConditionValue": 1,
                    }
                ],
            }
        ],
    }

    if duration_minutes:
        payload["estimatedDurationInSecs"] = duration_minutes * 60

    try:
        result = client.connectapi(
            "/workout-service/workout", method="POST", json=payload
        )
        workout_id = result.get("workoutId")
        logger.info("  ✅ Created workout '%s' (id=%s)", name, workout_id)
        return workout_id
    except Exception as exc:
        logger.error("  ❌ Failed to create workout '%s': %s", name, exc)
        return None


def _schedule_workout_on_date(client: Garmin, workout_id: int, target_date: date) -> bool:
    """Schedule an existing workout on a specific calendar date."""
    try:
        client.connectapi(
            f"/workout-service/schedule/{workout_id}",
            method="POST",
            json={"date": target_date.isoformat()},
        )
        logger.info("  📅 Scheduled on %s", target_date.isoformat())
        return True
    except Exception as exc:
        logger.error("  ❌ Failed to schedule on %s: %s", target_date, exc)
        return False


# ── Public API ───────────────────────────────────────────────────────────────

def get_planned_workout(target_date: date) -> Optional[Dict[str, Any]]:
    """Return the workout definition for *target_date*, or None for rest days."""
    return _WEEKLY_SCHEDULE.get(target_date.weekday())


def schedule_workout(
    client: Garmin,
    name: str,
    target_date: date,
    duration_minutes: Optional[int] = None,
    description: str = "",
    sport_type: Optional[Dict[str, Any]] = None,
) -> bool:
    """Create a workout and schedule it on *target_date*.

    Skips if a workout with the same name already exists on that date.
    Returns True if scheduled (or already exists), False on failure.
    """
    if sport_type is None:
        sport_type = SPORT_STRENGTH

    cal_items = _get_calendar_items(client, target_date)
    if _workout_exists_on_date(cal_items, name, target_date):
        logger.info("  ⏭️  '%s' already on %s — skipping.", name, target_date)
        return True

    workout_id = _create_workout(client, name, sport_type, description, duration_minutes)
    if workout_id is None:
        return False

    return _schedule_workout_on_date(client, workout_id, target_date)


def schedule_training_block(
    client: Garmin,
    weeks: int = 7,
    start_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Schedule the full training block on the Garmin calendar.

    Starts from the Monday of the current week (or *start_date* if provided)
    and populates *weeks* weeks of the recurring schedule.

    Returns a summary dict: {"scheduled": [...], "skipped": [...], "failed": [...]}.
    """
    if start_date is None:
        today = date.today()
        # Roll back to the Monday of the current week
        start_date = today - timedelta(days=today.weekday())

    summary: Dict[str, List[str]] = {"scheduled": [], "skipped": [], "failed": []}

    total_days = weeks * 7
    logger.info(
        "📆 Scheduling %d-week training block from %s …", weeks, start_date.isoformat()
    )

    # Cache calendar items per month to reduce API calls
    cached_months: Dict[str, List[Dict[str, Any]]] = {}

    for offset in range(total_days):
        d = start_date + timedelta(days=offset)
        planned = _WEEKLY_SCHEDULE.get(d.weekday())
        if planned is None:
            continue  # Friday — rest day

        month_key = d.strftime("%Y-%m")
        if month_key not in cached_months:
            cached_months[month_key] = _get_calendar_items(client, d)
        cal_items = cached_months[month_key]

        label = f"{planned['name']} on {d.isoformat()}"

        if _workout_exists_on_date(cal_items, planned["name"], d):
            logger.info("  ⏭️  %s — already exists, skipping.", label)
            summary["skipped"].append(label)
            continue

        logger.info("  → Scheduling %s …", label)
        workout_id = _create_workout(
            client,
            planned["name"],
            planned["sport_type"],
            planned["description"],
            planned["duration_minutes"],
        )
        if workout_id is None:
            summary["failed"].append(label)
            continue

        ok = _schedule_workout_on_date(client, workout_id, d)
        if ok:
            summary["scheduled"].append(label)
            # Refresh cached month items so duplicate check stays accurate
            cached_months[month_key] = _get_calendar_items(client, d)
        else:
            summary["failed"].append(label)

    logger.info(
        "✅ Done. Scheduled: %d | Skipped: %d | Failed: %d",
        len(summary["scheduled"]),
        len(summary["skipped"]),
        len(summary["failed"]),
    )
    return summary
