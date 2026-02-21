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
        # Fetch current calories
        res = supabase.table("daily_logs").select("consumed_calories").eq("date", date_str).single().execute()
        if not res.data:
            logger.warning(f"⚠️ No log found for {date_str} to add calories to.")
            return False
        
        current_cal = res.data.get("consumed_calories", 0)
        new_total = current_cal + calories
        
        # Update total
        supabase.table("daily_logs").update({"consumed_calories": new_total}).eq("date", date_str).execute()
        logger.info(f"🔥 Added {calories} kcal to {date_str}. New total: {new_total} kcal")
        return True
    except Exception as exc:
        logger.error(f"❌ Failed to add calories for {date_str}: {exc}")
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
