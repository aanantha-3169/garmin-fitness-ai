"""
garmin_scheduler.py — Schedule workouts on the Garmin Connect calendar.

Phase-aware triathlon periodization schedule targeting:
  • Score Marathon   — 2026-07-19
  • Melaka Triathlon — 2026-08-30
  • Bintan Triathlon — 2026-10-12
  • Half Ironman     — 2026-11-21

Phases (derived from days-to-race):
  base          — >60 days to Score Marathon; Zone 2 aerobic base building
  build         — 21–60 days to Score Marathon; volume increase
  pre_score     — ≤21 days to Score Marathon; race-specific sharpening
  taper_melaka  — ≤14 days to Melaka; taper for sprint triathlon
  taper_bintan  — ≤14 days to Bintan; volume cut for 70.3
  taper_ironman — ≤14 days to Ironman; maximum taper

Usage:
    from garmin_client import get_garmin_client
    from garmin_scheduler import schedule_training_block

    client = get_garmin_client()
    schedule_training_block(client, weeks=4)
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from garminconnect import Garmin

logger = logging.getLogger(__name__)

# ── Sport type constants ─────────────────────────────────────────────────────
SPORT_RUNNING     = {"sportTypeId": 1,  "sportTypeKey": "running",           "displayOrder": 1}
SPORT_CYCLING     = {"sportTypeId": 2,  "sportTypeKey": "cycling",           "displayOrder": 2}
SPORT_SWIMMING    = {"sportTypeId": 4,  "sportTypeKey": "swimming",          "displayOrder": 3}
SPORT_MULTISPORT  = {"sportTypeId": 5,  "sportTypeKey": "multi_sport",       "displayOrder": 5}
SPORT_OTHER       = {"sportTypeId": 8,  "sportTypeKey": "other",             "displayOrder": 8}
SPORT_STRENGTH    = {"sportTypeId": 13, "sportTypeKey": "strength_training", "displayOrder": 13}


# ── Phase detection ──────────────────────────────────────────────────────────
# weekday(): Mon=0 Tue=1 Wed=2 Thu=3 Fri=4 Sat=5 Sun=6

def get_phase(today: date = None) -> str:
    """Return current training phase based on days to each checkpoint."""
    if today is None:
        today = date.today()
    score_marathon = date(2026, 7, 19)
    melaka         = date(2026, 8, 30)
    bintan         = date(2026, 10, 12)
    ironman        = date(2026, 11, 21)

    days_to_ironman        = (ironman        - today).days
    days_to_bintan         = (bintan         - today).days
    days_to_melaka         = (melaka         - today).days
    days_to_score_marathon = (score_marathon - today).days

    if days_to_ironman <= 14:
        return "taper_ironman"
    elif days_to_bintan <= 14:
        return "taper_bintan"
    elif days_to_melaka <= 14:
        return "taper_melaka"
    elif days_to_score_marathon <= 21:
        return "pre_score"
    elif days_to_score_marathon > 60:
        return "base"
    else:
        return "build"


# ── Phase schedules ──────────────────────────────────────────────────────────

_BASE_SCHEDULE = {
    0: {"name": "Zone 2 Swim", "sport_type": SPORT_SWIMMING,
        "description": "Pool swim. Zone 2 HR 115-145. Focus: catch-up drill + continuous laps.",
        "duration_minutes": 45, "hr_target": (115, 145)},
    1: {"name": "Zone 2 Run", "sport_type": SPORT_RUNNING,
        "description": "Easy aerobic run. 6:20-7:00/km. Do not exceed 145 bpm.",
        "duration_minutes": 45, "hr_target": (115, 145)},
    2: {"name": "Zone 2 Swim", "sport_type": SPORT_SWIMMING,
        "description": "Pool swim. Technique focus. Continuous 400m blocks.",
        "duration_minutes": 45, "hr_target": (115, 145)},
    3: {"name": "Long Run — Zone 2", "sport_type": SPORT_RUNNING,
        "description": "Weekly long run. 5:30am start. 6:20-7:00/km. HR 115-145. "
                       "Walk if HR exceeds 145. Distance set by LONG_RUN_PROGRESSION "
                       "in training_plan.py.",
        "duration_minutes": 75, "hr_target": (115, 145)},
    4: None,  # Rest / mobility
    5: {"name": "Zone 2 Bike (Brother Session)", "sport_type": SPORT_CYCLING,
        "description": "Outdoor ride with brother if available. Zone 2 always.",
        "duration_minutes": 90, "hr_target": (115, 145), "brother_session": True},
    6: {"name": "Long Zone 2 Brick", "sport_type": SPORT_MULTISPORT,
        "description": "Bike 60-75 min then run 15-20 min. Both in Zone 2.",
        "duration_minutes": 90, "hr_target": (115, 145)},
}

_BUILD_SCHEDULE = {
    0: {"name": "Zone 2 Swim", "sport_type": SPORT_SWIMMING,
        "description": "Pool swim. Zone 2 HR 115-145. Build to 1500m continuous.",
        "duration_minutes": 60, "hr_target": (115, 145)},
    1: {"name": "Zone 2 Run", "sport_type": SPORT_RUNNING,
        "description": "Easy aerobic run. 6:20-7:00/km. Do not exceed 145 bpm.",
        "duration_minutes": 60, "hr_target": (115, 145)},
    2: {"name": "Zone 2 Bike", "sport_type": SPORT_CYCLING,
        "description": "Outdoor or indoor bike. Strict Zone 2. 115-145 bpm.",
        "duration_minutes": 90, "hr_target": (115, 145)},
    3: {"name": "Long Run — Zone 2", "sport_type": SPORT_RUNNING,
        "description": "Peak long run week. 5:30am start. 6:20-7:00/km. HR 115-145. "
                       "Nutrition at km 15. Walk breaks permitted.",
        "duration_minutes": 90, "hr_target": (115, 145)},
    4: None,  # Rest / mobility
    5: {"name": "Zone 2 Bike (Brother Session)", "sport_type": SPORT_CYCLING,
        "description": "Outdoor ride with brother if available. Zone 2 always.",
        "duration_minutes": 120, "hr_target": (115, 145), "brother_session": True},
    6: {"name": "Long Zone 2 Brick", "sport_type": SPORT_MULTISPORT,
        "description": "Bike 75-90 min then run 20-25 min. Both in Zone 2.",
        "duration_minutes": 120, "hr_target": (115, 145)},
}

_PRE_SCORE_SCHEDULE = {
    0: {"name": "Swim Sharpener", "sport_type": SPORT_SWIMMING,
        "description": "Pool swim. Race-pace 100m efforts. Simulate sprint distance.",
        "duration_minutes": 45, "hr_target": (115, 155)},
    1: {"name": "Easy Run", "sport_type": SPORT_RUNNING,
        "description": "Short easy run. Keep HR under 140. Legs fresh.",
        "duration_minutes": 30, "hr_target": (115, 140)},
    2: {"name": "Race Brick", "sport_type": SPORT_MULTISPORT,
        "description": "Bike 45 min Zone 2, then run 15 min at race effort.",
        "duration_minutes": 60, "hr_target": (115, 150)},
    3: None,  # Rest / mobility
    4: None,  # Rest
    5: {"name": "Zone 2 Bike (Brother Session)", "sport_type": SPORT_CYCLING,
        "description": "Easy ride. Keep it casual. Save legs for race week.",
        "duration_minutes": 60, "hr_target": (115, 135), "brother_session": True},
    6: {"name": "Easy Swim + Strides", "sport_type": SPORT_SWIMMING,
        "description": "Relaxed pool swim. 4x50m strides at end. Stay calm.",
        "duration_minutes": 30, "hr_target": (115, 140)},
}

_TAPER_BINTAN_SCHEDULE = {
    0: {"name": "Easy Swim", "sport_type": SPORT_SWIMMING,
        "description": "30 min easy pool swim. Smooth, no effort. Muscle memory only.",
        "duration_minutes": 30, "hr_target": (110, 135)},
    1: {"name": "Easy Run", "sport_type": SPORT_RUNNING,
        "description": "20-30 min easy jog. Below 135 bpm. Just move.",
        "duration_minutes": 25, "hr_target": (110, 135)},
    2: {"name": "Easy Bike", "sport_type": SPORT_CYCLING,
        "description": "45 min easy spin. Zone 2 only. No pushing.",
        "duration_minutes": 45, "hr_target": (110, 135)},
    3: None,  # Rest
    4: None,  # Rest
    5: {"name": "Short Brick", "sport_type": SPORT_MULTISPORT,
        "description": "Bike 30 min + Run 10 min. Easy pace. Shake out legs.",
        "duration_minutes": 40, "hr_target": (110, 140)},
    6: None,  # Rest / Race visualization
}

_TAPER_IRONMAN_SCHEDULE = {
    0: {"name": "Easy Swim", "sport_type": SPORT_SWIMMING,
        "description": "20 min easy swim. Drills only. Do not raise HR.",
        "duration_minutes": 20, "hr_target": (110, 130)},
    1: {"name": "Easy Run", "sport_type": SPORT_RUNNING,
        "description": "20 min jog. Very easy. Below 130 bpm.",
        "duration_minutes": 20, "hr_target": (110, 130)},
    2: {"name": "Easy Bike", "sport_type": SPORT_CYCLING,
        "description": "30 min easy spin. Just keep the legs moving.",
        "duration_minutes": 30, "hr_target": (110, 130)},
    3: None,  # Rest
    4: None,  # Rest
    5: None,  # Rest / Race visualization
    6: None,  # Rest
}

_SCHEDULE_BY_PHASE: Dict[str, Dict] = {
    "base":          _BASE_SCHEDULE,
    "build":         _BUILD_SCHEDULE,
    "pre_score":     _PRE_SCORE_SCHEDULE,
    "taper_melaka":  _TAPER_BINTAN_SCHEDULE,
    "taper_bintan":  _TAPER_BINTAN_SCHEDULE,
    "taper_ironman": _TAPER_IRONMAN_SCHEDULE,
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
                            "displayable": False,
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
    """Return the phase-appropriate workout for *target_date*, or None for rest days."""
    phase = get_phase(target_date)
    return _SCHEDULE_BY_PHASE[phase].get(target_date.weekday())


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
        planned = get_planned_workout(d)
        if planned is None:
            continue  # rest day

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
