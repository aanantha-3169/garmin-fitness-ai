#!/usr/bin/env python3
"""
seed_today.py — Run the morning briefing pipeline once, right now.

Authenticates with Garmin, fetches today's metrics, generates a readiness
decision, and persists everything to Supabase so the dashboard has real data.

Usage:
    source venv/bin/activate
    python seed_today.py
"""

import datetime
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    # 1. Authenticate with Garmin
    logger.info("🔑 Authenticating with Garmin...")
    from garmin_client import get_garmin_client
    client = get_garmin_client()
    if not client:
        logger.error("❌ Could not authenticate with Garmin. Check GARMIN_EMAIL / GARMIN_PASSWORD in .env")
        return

    # 2. Fetch today's health metrics
    logger.info("📊 Fetching health metrics from Garmin...")
    from garmin_metrics import get_health_metrics
    metrics = get_health_metrics(client)
    logger.info(f"   Body battery: {metrics.get('body_battery', {}).get('body_battery_current', 'N/A')}")
    logger.info(f"   Sleep score:  {metrics.get('sleep', {}).get('sleep_score', 'N/A')}")
    logger.info(f"   HRV status:   {metrics.get('hrv', {}).get('hrv_status', 'N/A')}")

    # 3. Determine today's planned workout
    logger.info("📅 Looking up today's planned workout...")
    from garmin_scheduler import get_planned_workout
    today = datetime.date.today()
    planned = get_planned_workout(today)
    planned_workout = planned["name"] if planned else "Rest Day / Active Recovery"
    workout_name   = planned_workout
    logger.info(f"   Planned: {planned_workout}")

    # 4. Get yesterday's execution context
    yesterday_str = (today - datetime.timedelta(days=1)).isoformat()
    from db_manager import get_completed_workout, get_recent_subjective_logs
    yesterdays_telemetry = get_completed_workout(yesterday_str)
    from garmin_telemetry import format_execution_context
    execution_ctx = format_execution_context(yesterdays_telemetry) if yesterdays_telemetry else ""
    subjective_logs = get_recent_subjective_logs(days=2)
    subjective_notes = "\n".join(
        f"- {log['date']}: {log['context_text']}" for log in subjective_logs
    )

    # 5. Generate readiness decision via Gemini
    logger.info("🤖 Generating readiness decision...")
    from training_advisor import analyze_readiness
    decision = analyze_readiness(
        metrics,
        planned_workout,
        execution_context=execution_ctx,
        subjective_notes=subjective_notes,
    )
    logger.info(f"   Recommended action: {decision.recommended_action}")

    # 6. Persist to Supabase
    logger.info("💾 Writing to Supabase...")
    from db_manager import init_daily_log
    date_str = metrics.get("date_today") or today.isoformat()
    briefing_data = {
        "metrics":      metrics,
        "decision":     decision.model_dump(),
        "workout_name": workout_name,
    }
    init_daily_log(date_str, decision.target_calories, briefing_data)
    logger.info(f"✅ Daily log for {date_str} saved. Refresh the dashboard!")


if __name__ == "__main__":
    main()
