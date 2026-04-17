import os
import logging
from typing import Any, Dict, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Supabase Configuration ──────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("SUPABASE_URL or SUPABASE_KEY not found in environment.")
    supabase: Optional[Client] = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Database Operations ─────────────────────────────────────────────────────

def init_daily_log(date_str: str, target_cal: int, briefing_json: Dict[str, Any]) -> bool:
    """Initialize a new daily log row if it doesn't already exist.
    
    Sets consumed_calories to 0 and workout_moved to False by default.
    """
    if not supabase:
        return False

    try:
        # Check if the row already exists
        existing = supabase.table("daily_logs").select("*").eq("date", date_str).execute()
        
        if not existing.data:
            # Insert new row
            data = {
                "date": date_str,
                "target_calories": target_cal,
                "consumed_calories": 0,
                "consumed_protein_g": 0,
                "consumed_carbs_g": 0,
                "consumed_fats_g": 0,
                "meal_count": 0,
                "morning_briefing_json": briefing_json,
                "workout_moved": False
            }
            supabase.table("daily_logs").insert(data).execute()
            logger.info(f"✅ Initialized daily log for {date_str}")
        else:
            # Update the row with new target/briefing if it was re-run
            data = {
                "target_calories": target_cal,
                "morning_briefing_json": briefing_json
            }
            supabase.table("daily_logs").update(data).eq("date", date_str).execute()
            logger.info(f"🔄 Updated daily log for {date_str}")
        
        return True
    except Exception as exc:
        logger.error(f"❌ Failed to init daily log for {date_str}: {exc}")
        return False


def add_calories(date_str: str, calories: int) -> bool:
    """Increment consumed_calories for the given date."""
    if not supabase:
        return False

    try:
        res = supabase.table("daily_logs").select("consumed_calories").eq("date", date_str).single().execute()
        if not res.data:
            logger.warning(f"⚠️ No log found for {date_str} to add calories to.")
            return False

        current_cal = res.data.get("consumed_calories", 0)
        new_total = current_cal + calories

        supabase.table("daily_logs").update({"consumed_calories": new_total}).eq("date", date_str).execute()
        logger.info(f"🔥 Added {calories} kcal to {date_str}. New total: {new_total} kcal")
        return True
    except Exception as exc:
        logger.error(f"❌ Failed to add calories for {date_str}: {exc}")
        return False


def add_macros(date_str: str, calories: int, protein_g: int, carbs_g: int, fats_g: int) -> bool:
    """Increment all macro totals (calories + protein + carbs + fats) for the given date."""
    if not supabase:
        return False

    try:
        res = supabase.table("daily_logs").select(
            "consumed_calories, consumed_protein_g, consumed_carbs_g, consumed_fats_g, meal_count"
        ).eq("date", date_str).single().execute()

        if not res.data:
            logger.warning(f"⚠️ No log found for {date_str} to add macros to.")
            return False

        row = res.data
        updated = {
            "consumed_calories":  (row.get("consumed_calories")  or 0) + calories,
            "consumed_protein_g": (row.get("consumed_protein_g") or 0) + protein_g,
            "consumed_carbs_g":   (row.get("consumed_carbs_g")   or 0) + carbs_g,
            "consumed_fats_g":    (row.get("consumed_fats_g")    or 0) + fats_g,
            "meal_count":         (row.get("meal_count")         or 0) + 1,
        }

        supabase.table("daily_logs").update(updated).eq("date", date_str).execute()
        logger.info(
            f"✅ Macros added for {date_str}: +{calories} kcal | +{protein_g}g protein | +{carbs_g}g carbs | +{fats_g}g fat"
        )
        return True
    except Exception as exc:
        logger.error(f"❌ Failed to add macros for {date_str}: {exc}")
        return False


def get_daily_log(date_str: str) -> Optional[Dict[str, Any]]:
    """Retrieve the full row for the requested date."""
    if not supabase:
        return None

    try:
        res = supabase.table("daily_logs").select("*").eq("date", date_str).execute()
        return res.data[0] if res.data else None
    except Exception as exc:
        logger.error(f"❌ Failed to get daily log for {date_str}: {exc}")
        return None


def update_workout_moved(date_str: str, moved: bool) -> bool:
    """Update the workout_moved status for the given date."""
    if not supabase:
        return False

    try:
        supabase.table("daily_logs").update({"workout_moved": moved}).eq("date", date_str).execute()
        logger.info(f"✅ Workout moved status set to {moved} for {date_str}")
        return True
    except Exception as exc:
        logger.error(f"❌ Failed to update workout_moved for {date_str}: {exc}")
        return False


def update_morning_briefing(date_str: str, briefing_json: Dict[str, Any]) -> bool:
    """Update the morning_briefing_json payload for the given date."""
    if not supabase:
        return False

    try:
        supabase.table("daily_logs").update({"morning_briefing_json": briefing_json}).eq("date", date_str).execute()
        logger.info(f"✅ Morning briefing updated for {date_str}")
        return True
    except Exception as exc:
        logger.error(f"❌ Failed to update morning briefing for {date_str}: {exc}")
        return False


# ── Garmin Token Persistence ────────────────────────────────────────────────

_GARMIN_TOKEN_KEY = "garmin_tokens"


def save_garmin_tokens(oauth1_json: str, oauth2_json: str) -> bool:
    """Persist Garmin OAuth token file contents to Supabase.

    Stores both token files as JSON strings under a single row keyed by
    _GARMIN_TOKEN_KEY so they survive Render's ephemeral filesystem.
    """
    if not supabase:
        return False

    try:
        data = {
            "key": _GARMIN_TOKEN_KEY,
            "oauth1_token": oauth1_json,
            "oauth2_token": oauth2_json,
        }
        existing = supabase.table("garmin_tokens").select("key").eq("key", _GARMIN_TOKEN_KEY).execute()
        if existing.data:
            supabase.table("garmin_tokens").update(data).eq("key", _GARMIN_TOKEN_KEY).execute()
        else:
            supabase.table("garmin_tokens").insert(data).execute()
        logger.info("✅ Garmin tokens persisted to Supabase.")
        return True
    except Exception as exc:
        logger.error("❌ Failed to save Garmin tokens to Supabase: %s", exc)
        return False


def load_garmin_tokens() -> Optional[Dict[str, str]]:
    """Load Garmin OAuth token file contents from Supabase.

    Returns a dict with 'oauth1_token' and 'oauth2_token' strings,
    or None if no tokens are stored yet.
    """
    if not supabase:
        return None

    try:
        res = supabase.table("garmin_tokens").select("oauth1_token, oauth2_token").eq("key", _GARMIN_TOKEN_KEY).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as exc:
        logger.error("❌ Failed to load Garmin tokens from Supabase: %s", exc)
        return None
