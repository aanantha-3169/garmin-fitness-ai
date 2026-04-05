"""
garmin_nutrition.py — Sync meal macros to Garmin Connect's nutrition log.

Garmin's nutrition API is not officially documented; this uses the same
/nutrition-service/ endpoints that Garmin Connect web uses internally.

Each call is additive: it fetches the existing daily totals, adds the new
meal's macros, then writes the updated totals back. This mirrors what
the meal tracker does in SQLite and Supabase.
"""

import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

_NUTRITION_BASE = "/nutrition-service/nutrition"


def _get_daily_nutrition(client, date_str: str) -> Optional[dict]:
    """Fetch the existing nutrition log for *date_str* (YYYY-MM-DD).

    Returns the raw Garmin response dict, or None if no log exists yet.
    """
    try:
        data = client.connectapi(f"{_NUTRITION_BASE}/{date_str}", method="GET")
        if data and data.get("calendarDate"):
            return data
        return None
    except Exception as exc:
        # A 404 means no log yet for today — that's normal
        msg = str(exc)
        if "404" in msg or "Not Found" in msg:
            return None
        logger.warning("Could not fetch nutrition log for %s: %s", date_str, exc)
        return None


def log_meal_to_garmin(
    client,
    calories: int,
    protein_g: int,
    carbs_g: int,
    fats_g: int,
    date_str: Optional[str] = None,
) -> bool:
    """Add a meal's macros to Garmin Connect's daily nutrition log.

    Fetches the current day's totals and adds the new values before
    writing back, so multiple meals accumulate correctly.

    Args:
        client:     Authenticated Garmin client from get_garmin_client().
        calories:   Meal calories (kcal).
        protein_g:  Protein in grams.
        carbs_g:    Carbohydrates in grams.
        fats_g:     Fat in grams.
        date_str:   ISO date string (default: today).

    Returns:
        True on success, False on failure.
    """
    if date_str is None:
        date_str = date.today().isoformat()

    # Fetch existing totals so we can add to them
    existing = _get_daily_nutrition(client, date_str)

    if existing:
        nutrition_id = existing.get("userDailyNutritionId")
        new_calories = (existing.get("totalKilocalories") or 0) + calories
        new_protein  = (existing.get("totalProteinInGrams") or 0) + protein_g
        new_carbs    = (existing.get("totalCarbsInGrams") or 0) + carbs_g
        new_fats     = (existing.get("totalFatInGrams") or 0) + fats_g
    else:
        nutrition_id = None
        new_calories = calories
        new_protein  = protein_g
        new_carbs    = carbs_g
        new_fats     = fats_g

    payload = {
        "userDailyNutritionId": nutrition_id,
        "calendarDate": date_str,
        "totalKilocalories": new_calories,
        "totalProteinInGrams": new_protein,
        "totalCarbsInGrams": new_carbs,
        "totalFatInGrams": new_fats,
    }

    try:
        if nutrition_id:
            # Record exists — update it
            client.connectapi(_NUTRITION_BASE, method="PUT", json=payload)
        else:
            # No record yet — create one
            client.connectapi(_NUTRITION_BASE, method="POST", json=payload)

        logger.info(
            "✅ Garmin nutrition updated for %s: +%d kcal | +%dg protein | +%dg carbs | +%dg fat",
            date_str, calories, protein_g, carbs_g, fats_g,
        )
        return True

    except Exception as exc:
        logger.error("Failed to sync nutrition to Garmin for %s: %s", date_str, exc)
        return False
