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

    # 7. Calculate and persist probability snapshot
    logger.info("📈 Calculating Ironman probability score...")
    from datetime import timedelta
    from db_manager import get_weekly_logs, get_compliance_trend, save_probability_snapshot
    from sport_science import calculate_ironman_probability
    from training_plan import get_athlete_hr_max
    from sport_science import zone2_bounds

    hr_max = get_athlete_hr_max()
    z2_low, z2_high = zone2_bounds(hr_max)

    # Fetch last 14 days of completed workouts directly from Supabase
    from db_manager import supabase as _sb
    workouts_14d = []
    if _sb:
        try:
            start_14d = (today - timedelta(days=13)).isoformat()
            res = (
                _sb.table("completed_workouts")
                .select("date, activity_type, avg_hr")
                .gte("date", start_14d)
                .order("date", desc=False)
                .execute()
            )
            workouts_14d = res.data or []
        except Exception as exc:
            logger.warning("⚠️  Could not fetch completed_workouts for probability: %s", exc)

    compliance_14d = get_compliance_trend(days=14)

    snapshot = calculate_ironman_probability(
        completed_workouts=workouts_14d,
        compliance_rows=compliance_14d,
        zone2_low=z2_low,
        zone2_high=z2_high,
    )

    save_probability_snapshot(date_str, snapshot)
    logger.info(
        f"✅ Probability snapshot saved: {snapshot['overall_score']}% "
        f"(Z2={snapshot['zone2_component']} | "
        f"Consistency={snapshot['consistency_component']} | "
        f"Load={snapshot['life_load_component']} | "
        f"Swim={snapshot['swim_frequency_component']})"
    )


if __name__ == "__main__":
    main()
