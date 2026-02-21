"""
garmin_calendar_manager.py — Manage and reschedule Garmin Connect calendar items.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from garmin_client import get_garmin_client

logger = logging.getLogger(__name__)


def reschedule_workout(workout_name: str, from_date: date, to_date: date) -> Optional[str]:
    """Reschedule a workout on the Garmin calendar.
    
    1. Finds the workout on 'from_date'.
    2. Deletes the scheduled instance.
    3. Re-schedules the same workout template on 'to_date'.
    
    Returns the confirmation string or None on failure.
    """
    client = get_garmin_client()
    if not client:
        logger.error("Failed to authenticate with Garmin.")
        return None

    # 1. Fetch calendar items for the month containing from_date
    month_index = from_date.month - 1
    path = f"/calendar-service/year/{from_date.year}/month/{month_index}"
    
    try:
        data = client.connectapi(path, method="GET")
        items = data.get("calendarItems", [])
    except Exception as exc:
        logger.error("Failed to fetch calendar items: %s", exc)
        return None

    # 2. Find the specific workout instance
    target_item = None
    from_str = from_date.isoformat()
    for item in items:
        if (
            item.get("itemType") == "workout"
            and item.get("date") == from_str
            and item.get("title") == workout_name
        ):
            target_item = item
            break

    if not target_item:
        logger.warning("No workout named '%s' found on %s", workout_name, from_str)
        return f"Workout '{workout_name}' not found on calendar for today."

    calendar_id = target_item.get("id")         # The instance ID on the calendar
    template_id = target_item.get("workoutId")  # The underlying workout definition ID

    if not calendar_id or not template_id:
        logger.error("Missing ID information for workout: %s", target_item)
        return "Could not extract workout IDs for rescheduling."

    # 3. Delete the existing instance
    # The endpoint for deleting a scheduled workout is DELETE /workout-service/schedule/{id}
    try:
        client.connectapi(f"/workout-service/schedule/{calendar_id}", method="DELETE")
        logger.info("✅ Deleted workout instance %s from %s", calendar_id, from_str)
    except Exception as exc:
        logger.error("Failed to delete workout instance: %s", exc)
        return "Failed to remove the old workout from your calendar."

    # 4. Schedule the new instance on to_date
    try:
        client.connectapi(
            f"/workout-service/schedule/{template_id}",
            method="POST",
            json={"date": to_date.isoformat()}
        )
        logger.info("✅ Rescheduled '%s' to %s", workout_name, to_date.isoformat())
        return f"Calendar updated: '{workout_name}' moved to {to_date.isoformat()}."
    except Exception as exc:
        logger.error("Failed to schedule new workout instance: %s", exc)
        return f"Removed old workout, but failed to schedule on {to_date.isoformat()}."
