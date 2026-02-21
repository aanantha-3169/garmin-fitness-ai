#!/usr/bin/env python3
"""
main.py — Unified Garmin AI Bot & Morning Briefing Service.

Combines the Telegram bot (Meal Tracking, /status command) with
a scheduled daily job for the morning briefing.

Run:
    python main.py
"""

import logging
import os
import sys
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# Import our custom modules
from garmin_client import get_garmin_client
from garmin_metrics import get_health_metrics
from training_advisor import analyze_readiness
from telegram_notifier import (
    handle_status,
    handle_callback,
    send_morning_briefing,
)
from meal_tracker_bot import (
    _init_db,
    _cmd_start,
    _cmd_today,
    _cmd_reset,
    _handle_photo,
)

# ── Configuration ───────────────────────────────────────────────────────────

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TIMEZONE = ZoneInfo("Asia/Jakarta")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Scheduled Jobs ──────────────────────────────────────────────────────────

async def run_morning_briefing(context):
    """Job function to run the morning briefing pipeline."""
    logger.info("🌅 Starting scheduled morning briefing session...")
    
    # 1. Authenticate with Garmin
    client = get_garmin_client()
    if not client:
        logger.error("❌ Briefing failed: Could not authenticate with Garmin.")
        return

    # 2. Fetch Metrics
    metrics = get_health_metrics(client)
    
    # 3. Determine today's workout
    # (Simple logic: can be refined to check a calendar or schedule)
    import datetime
    weekday = datetime.date.today().weekday()
    planned_workout = "Rest Day / Active Recovery"
    workout_name = "General Training"
    
    if weekday == 0:
        planned_workout = "Lift A: Push & Quads (Heavy)"
        workout_name = "Lift A"
    elif weekday == 2:
        planned_workout = "Lift B: Pull & Hinge (Hypertrophy)"
        workout_name = "Lift B"
    elif weekday == 4:
        planned_workout = "Zone 2 Long Run (60 min)"
        workout_name = "Long Run"

    # 4. Generate Decision
    decision = analyze_readiness(metrics, planned_workout)
    
    # 5. Persist to Supabase
    from db_manager import init_daily_log
    date_str = metrics.get("date_today")
    if date_str:
        briefing_data = {
            "metrics": metrics,
            "decision": decision.model_dump(),
            "workout_name": workout_name
        }
        init_daily_log(date_str, decision.target_calories, briefing_data)
        logger.info(f"💾 Daily log for {date_str} persisted to Supabase.")

    # 6. Send to Telegram
    success = await send_morning_briefing(decision, metrics)
    if success:
        logger.info("✅ Morning briefing delivered successfully.")
    else:
        logger.error("❌ Morning briefing delivery failed.")


# ── Initialization ─────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment. Exiting.")
        sys.exit(1)

    # Initialize SQLite database for local meal tracking
    _init_db()

    # Build the application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # --- Register Handlers ---
    
    # Common Commands
    application.add_handler(CommandHandler("start", _cmd_start))
    
    # Meal Tracker Handlers
    application.add_handler(CommandHandler("today", _cmd_today))
    application.add_handler(CommandHandler("reset", _cmd_reset))
    application.add_handler(MessageHandler(filters.PHOTO, _handle_photo))
    
    # Training / Status Handlers
    application.add_handler(CommandHandler("status", handle_status))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # --- Schedule Jobs ---
    
    job_queue = application.job_queue
    # Run daily at 5:45 AM Jakarta time
    job_queue.run_daily(
        run_morning_briefing,
        time=time(hour=5, minute=45, tzinfo=TIMEZONE),
        name="daily_morning_briefing"
    )
    
    logger.info("🤖 Garmin Assistant is online and scheduled. (5:45 AM Jakarta)")
    
    # Start the bot
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
