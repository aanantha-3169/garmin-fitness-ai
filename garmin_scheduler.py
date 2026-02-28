"""
garmin_scheduler.py — Schedule workouts on the Garmin Connect calendar.

Creates workout definitions via the Garmin Connect API and schedules
them on specific dates.  Before scheduling, the calendar is checked
to prevent duplicate entries.

Usage:
    from garmin_client import get_garmin_client
    from garmin_scheduler import schedule_week

    client = get_garmin_client()
    schedule_week(client)
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from garminconnect import Garmin

logger = logging.getLogger(__name__)

# ── Sport type constants ─────────────────────────────────────────────────────
SPORT_STRENGTH = {"sportTypeId": 5, "sportTypeKey": "strength_training"}
SPORT_RUNNING  = {"sportTypeId": 1, "sportTypeKey": "running"}


# ── Low-level helpers ────────────────────────────────────────────────────────

def _get_calendar_items(client: Garmin, target_date: date) -> List[Dict[str, Any]]:
    """Return all calendar items for the month containing *target_date*.

    The calendar-service uses 0-indexed months (Jan=0, Feb=1, …).
    """
    month_index = target_date.month - 1
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
    """Check whether a workout with *name* is already on *target_date*."""
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
                        "stepType": {
                            "stepTypeId": 3,
                            "stepTypeKey": "interval",
                        },
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


def _schedule_workout(client: Garmin, workout_id: int, target_date: date) -> bool:
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
    """Return the workout definition for a given date based on the fixed schedule.

    Schedule:
      • Wednesday — Lift A: Push & Quads
      • Saturday  — Lift B: Pull & Hinge
      • Sunday    — Zone 2 Long Run
    """
    weekday = target_date.weekday()  # Mon=0 … Sun=6

    if weekday == 2:  # Wednesday
        return {
            "name": "Lift A: Push & Quads",
            "sport_type": SPORT_STRENGTH,
            "description": "Location: FTL Ben Hill",
            "duration_minutes": None,
        }
    elif weekday == 5:  # Saturday
        return {
            "name": "Lift B: Pull & Hinge",
            "sport_type": SPORT_STRENGTH,
            "description": "",
            "duration_minutes": None,
        }
    elif weekday == 6:  # Sunday
        return {
            "name": "Zone 2 Long Run",
            "sport_type": SPORT_RUNNING,
            "description": "Zone 2 steady state",
            "duration_minutes": 90,
        }
    return None


def schedule_workout(
    client: Garmin,
    name: str,
    target_date: date,
    duration_minutes: Optional[int] = None,
    description: str = "",
    sport_type: Optional[Dict[str, Any]] = None,
) -> bool:
    """Create a workout and schedule it on *target_date*.

    Returns True if the workout was scheduled (or already existed),
    False on failure.

    Duplicate check: skips scheduling if a workout with the same
    *name* already appears on that date in the Garmin calendar.
    """
    if sport_type is None:
        sport_type = SPORT_STRENGTH

    # ── Duplicate check ──────────────────────────────────────────────
    cal_items = _get_calendar_items(client, target_date)
    if _workout_exists_on_date(cal_items, name, target_date):
        logger.info("  ⏭️  '%s' already exists on %s — skipping.", name, target_date)
        return True

    # ── Create + schedule ────────────────────────────────────────────
    workout_id = _create_workout(
        client, name, sport_type, description, duration_minutes
    )
    if workout_id is None:
        return False

    return _schedule_workout(client, workout_id, target_date)


def schedule_week(client: Garmin, start_date: Optional[date] = None):
    """Populate the upcoming week with the recurring training schedule.

    Schedule (relative to *start_date*, default = today):
      • Wednesday PM — Lift A: Push & Quads  (FTL Ben Hill)
      • Saturday  AM — Lift B: Pull & Hinge
      • Sunday    AM — Zone 2 Long Run (90 min)

    Skips any workout that is already on the calendar for that day.
    """
    if start_date is None:
        start_date = date.today()

    # Build the list of target dates for the upcoming 7 days
    schedule = []
    for offset in range(7):
        d = start_date + timedelta(days=offset)
        planned = get_planned_workout(d)
        if planned:
            planned["date"] = d
            schedule.append(planned)

    if not schedule:
        logger.info("No workouts to schedule in the next 7 days from %s.", start_date)
        return

    logger.info(
        "Scheduling %d workout(s) for the week of %s …",
        len(schedule),
        start_date.isoformat(),
    )

    for entry in schedule:
        logger.info("→ %s on %s", entry["name"], entry["date"])
        schedule_workout(
            client,
            name=entry["name"],
            target_date=entry["date"],
            duration_minutes=entry["duration_minutes"],
            description=entry["description"],
            sport_type=entry["sport_type"],
        )
