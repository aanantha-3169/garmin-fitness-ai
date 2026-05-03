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


def save_completed_workout(date_str: str, data: Dict[str, Any]) -> bool:
    """Upsert a completed workout telemetry row for *date_str*."""
    if not supabase:
        return False
    try:
        payload = {"date": date_str, **data}
        existing = supabase.table("completed_workouts").select("date").eq("date", date_str).execute()
        if existing.data:
            supabase.table("completed_workouts").update(payload).eq("date", date_str).execute()
        else:
            supabase.table("completed_workouts").insert(payload).execute()
        logger.info("✅ Completed workout saved for %s", date_str)
        return True
    except Exception as exc:
        logger.error("❌ Failed to save completed workout for %s: %s", date_str, exc)
        return False


def get_completed_workout(date_str: str) -> Optional[Dict[str, Any]]:
    """Return the completed workout row for *date_str*, or None."""
    if not supabase:
        return None
    try:
        res = supabase.table("completed_workouts").select("*").eq("date", date_str).execute()
        return res.data[0] if res.data else None
    except Exception as exc:
        logger.error("❌ Failed to get completed workout for %s: %s", date_str, exc)
        return None


def log_subjective(date_str: str, context_text: str, sentiment_score: float) -> bool:
    """Append a subjective log entry (injury, fatigue note, mood) for *date_str*."""
    if not supabase:
        return False
    try:
        supabase.table("subjective_logs").insert({
            "date": date_str,
            "context_text": context_text,
            "sentiment_score": sentiment_score,
        }).execute()
        logger.info("✅ Subjective log saved for %s", date_str)
        return True
    except Exception as exc:
        logger.error("❌ Failed to save subjective log: %s", exc)
        return False


def get_recent_subjective_logs(days: int = 2) -> list:
    """Return subjective log entries from the last *days* days, oldest first."""
    if not supabase:
        return []
    try:
        from datetime import date, timedelta
        start = (date.today() - timedelta(days=days)).isoformat()
        res = (
            supabase.table("subjective_logs")
            .select("date, context_text, sentiment_score")
            .gte("date", start)
            .order("date", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.error("❌ Failed to fetch subjective logs: %s", exc)
        return []


def log_metric(date_str: str, metric_type: str, value: float) -> bool:
    """Log a user-reported metric (weight, soreness scale, etc.) for *date_str*."""
    if not supabase:
        return False
    try:
        supabase.table("metric_logs").insert({
            "date": date_str,
            "metric_type": metric_type,
            "value": value,
        }).execute()
        logger.info("✅ Metric log saved: %s = %s on %s", metric_type, value, date_str)
        return True
    except Exception as exc:
        logger.error("❌ Failed to save metric log: %s", exc)
        return False


# ── HR Max cache (hr_max metric in metric_logs) ──────────────────────────────

_HR_MAX_METRIC = "hr_max"


def save_cached_hr_max(hr_max: int) -> bool:
    """Persist the athlete's observed HRmax to metric_logs.

    Uses today's date as the row key. Old rows are preserved so the history
    of HRmax observations is queryable. The most recent row is used as the
    cached fallback by get_cached_hr_max().
    """
    from datetime import date
    return log_metric(date.today().isoformat(), _HR_MAX_METRIC, float(hr_max))


def get_cached_hr_max() -> Optional[int]:
    """Return the most recently saved HRmax from metric_logs, or None.

    Returns None when the DB is unavailable or no HRmax has ever been saved.
    Callers should fall back to their hardcoded constant in that case.
    """
    if not supabase:
        return None
    try:
        res = (
            supabase.table("metric_logs")
            .select("value")
            .eq("metric_type", _HR_MAX_METRIC)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return int(res.data[0]["value"])
        return None
    except Exception as exc:
        logger.error("❌ Failed to fetch cached HRmax: %s", exc)
        return None


def get_weekly_logs(days: int = 7) -> list:
    """Return the last *days* rows from daily_logs ordered oldest-first.

    Each row includes all columns so progress_reporter can extract both
    top-level fields and nested morning_briefing_json metrics.
    """
    if not supabase:
        return []

    try:
        from datetime import date, timedelta
        start = (date.today() - timedelta(days=days - 1)).isoformat()
        res = (
            supabase.table("daily_logs")
            .select("*")
            .gte("date", start)
            .order("date", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.error("❌ Failed to fetch weekly logs: %s", exc)
        return []


def log_water_fear(
    date_str: str,
    fear_level: int,
    context_note: str = "",
    session_type: str = "general",
) -> bool:
    """Insert a water fear log entry for *date_str*."""
    if not supabase:
        return False
    try:
        supabase.table("water_fear_logs").insert({
            "date": date_str,
            "fear_level": fear_level,
            "context_note": context_note or None,
            "session_type": session_type,
        }).execute()
        logger.info("✅ Water fear level %s logged for %s", fear_level, date_str)
        return True
    except Exception as exc:
        logger.error("❌ Failed to log water fear for %s: %s", date_str, exc)
        return False


def log_workday_load(date_str: str, load_level: int) -> bool:
    """Upsert today's workday stress score into principle_compliance."""
    if not supabase:
        return False
    try:
        supabase.table("principle_compliance").upsert(
            {"date": date_str, "life_load_score": load_level},
            on_conflict="date",
        ).execute()
        logger.info("✅ Workday load %s logged for %s", load_level, date_str)
        return True
    except Exception as exc:
        logger.error("❌ Failed to log workday load for %s: %s", date_str, exc)
        return False


# ── water_fear_logs ─────────────────────────────────────────────────────────

def get_fear_trend(days: int = 30) -> list:
    """Return fear log entries for the last *days* days, oldest first."""
    if not supabase:
        return []
    try:
        from datetime import date, timedelta
        start = (date.today() - timedelta(days=days)).isoformat()
        res = (
            supabase.table("water_fear_logs")
            .select("date, fear_level, context_note, session_type, created_at")
            .gte("date", start)
            .order("date", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.error("❌ Failed to fetch fear trend: %s", exc)
        return []


def get_latest_fear_level() -> Optional[int]:
    """Return the most recently logged fear level, or None."""
    if not supabase:
        return None
    try:
        res = (
            supabase.table("water_fear_logs")
            .select("fear_level")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0]["fear_level"] if res.data else None
    except Exception as exc:
        logger.error("❌ Failed to fetch latest fear level: %s", exc)
        return None


# ── ironman_training_plan ────────────────────────────────────────────────────

def get_planned_sessions(start_date: str, end_date: str) -> list:
    """Return training plan sessions between *start_date* and *end_date* inclusive."""
    if not supabase:
        return []
    try:
        res = (
            supabase.table("ironman_training_plan")
            .select("*")
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.error("❌ Failed to fetch planned sessions: %s", exc)
        return []


def get_todays_plan() -> Optional[Dict[str, Any]]:
    """Return today's training plan session, or None if rest day."""
    if not supabase:
        return None
    try:
        from datetime import date
        today = date.today().isoformat()
        res = (
            supabase.table("ironman_training_plan")
            .select("*")
            .eq("date", today)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as exc:
        logger.error("❌ Failed to fetch today's plan: %s", exc)
        return None


def get_week_plan(week_offset: int = 0) -> list:
    """Return all sessions for the week at *week_offset* from the current week.

    week_offset=0 is the current Mon–Sun, 1 is next week, -1 is last week.
    """
    if not supabase:
        return []
    try:
        from datetime import date, timedelta
        today = date.today()
        week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6)
        return get_planned_sessions(week_start.isoformat(), week_end.isoformat())
    except Exception as exc:
        logger.error("❌ Failed to fetch week plan: %s", exc)
        return []


def upsert_training_plan(sessions: list) -> bool:
    """Bulk-upsert a list of session dicts into ironman_training_plan.

    Sessions with an 'id' key are updated in place; new sessions are inserted.
    """
    if not supabase:
        return False
    try:
        supabase.table("ironman_training_plan").upsert(sessions).execute()
        logger.info("✅ Upserted %d training plan sessions.", len(sessions))
        return True
    except Exception as exc:
        logger.error("❌ Failed to upsert training plan: %s", exc)
        return False


def mark_garmin_scheduled(plan_id: int) -> bool:
    """Set garmin_scheduled=True for the given plan row id."""
    if not supabase:
        return False
    try:
        supabase.table("ironman_training_plan").update(
            {"garmin_scheduled": True}
        ).eq("id", plan_id).execute()
        logger.info("✅ Marked plan id=%s as Garmin scheduled.", plan_id)
        return True
    except Exception as exc:
        logger.error("❌ Failed to mark plan id=%s scheduled: %s", plan_id, exc)
        return False


# ── principle_compliance ─────────────────────────────────────────────────────

def log_compliance(date_str: str, data: Dict[str, Any]) -> bool:
    """Upsert a full compliance record for *date_str*.

    *data* may contain any subset of principle_compliance columns.
    """
    if not supabase:
        return False
    try:
        supabase.table("principle_compliance").upsert(
            {"date": date_str, **data},
            on_conflict="date",
        ).execute()
        logger.info("✅ Compliance record upserted for %s.", date_str)
        return True
    except Exception as exc:
        logger.error("❌ Failed to log compliance for %s: %s", date_str, exc)
        return False


def get_compliance_trend(days: int = 14) -> list:
    """Return compliance rows for the last *days* days, oldest first."""
    if not supabase:
        return []
    try:
        from datetime import date, timedelta
        start = (date.today() - timedelta(days=days)).isoformat()
        res = (
            supabase.table("principle_compliance")
            .select("*")
            .gte("date", start)
            .order("date", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.error("❌ Failed to fetch compliance trend: %s", exc)
        return []


# ── probability_snapshots ────────────────────────────────────────────────────

def save_probability_snapshot(date_str: str, scores: Dict[str, Any]) -> bool:
    """Insert a probability snapshot row for *date_str*.

    *scores* should contain overall_score and component keys matching the table.
    """
    if not supabase:
        return False
    try:
        supabase.table("probability_snapshots").insert(
            {"date": date_str, **scores}
        ).execute()
        logger.info("✅ Probability snapshot saved for %s.", date_str)
        return True
    except Exception as exc:
        logger.error("❌ Failed to save probability snapshot for %s: %s", date_str, exc)
        return False


def get_probability_trend(days: int = 90) -> list:
    """Return probability snapshots for the last *days* days, oldest first."""
    if not supabase:
        return []
    try:
        from datetime import date, timedelta
        start = (date.today() - timedelta(days=days)).isoformat()
        res = (
            supabase.table("probability_snapshots")
            .select("*")
            .gte("date", start)
            .order("date", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.error("❌ Failed to fetch probability trend: %s", exc)
        return []


def get_latest_probability() -> Optional[Dict[str, Any]]:
    """Return the most recent probability snapshot row, or None."""
    if not supabase:
        return None
    try:
        res = (
            supabase.table("probability_snapshots")
            .select("*")
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as exc:
        logger.error("❌ Failed to fetch latest probability: %s", exc)
        return None


# ── Dashboard aggregate ──────────────────────────────────────────────────────

def get_dashboard_data() -> Dict[str, Any]:
    """Return everything the dashboard needs in a single call.

    Keys returned:
      today_log        — daily_logs row for today
      today_plan       — ironman_training_plan row for today (or None)
      latest_prob      — most recent probability_snapshots row
      prob_trend       — last 30 days of probability snapshots
      compliance_trend — last 14 days of principle_compliance rows
      fear_trend       — last 30 days of water_fear_logs rows
      next_14_days     — ironman_training_plan rows for next 14 days
    """
    from datetime import date, timedelta
    today = date.today()
    return {
        "today_log":        get_daily_log(today.isoformat()),
        "today_plan":       get_todays_plan(),
        "latest_prob":      get_latest_probability(),
        "prob_trend":       get_probability_trend(days=30),
        "compliance_trend": get_compliance_trend(days=14),
        "fear_trend":       get_fear_trend(days=30),
        "next_14_days":     get_planned_sessions(
            today.isoformat(),
            (today + timedelta(days=13)).isoformat(),
        ),
    }


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
