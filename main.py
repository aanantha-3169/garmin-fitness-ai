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
from garmin_scheduler import get_planned_workout, schedule_workout, schedule_training_block
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
    _handle_meal_callback,
    _handle_message,
)
from progress_reporter import build_and_send_weekly_report

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
    
    # 3. Determine today's workout using unified schedule
    import datetime
    today = datetime.date.today()
    planned = get_planned_workout(today)
    
    planned_workout = "Rest Day / Active Recovery"
    workout_name = "General Training"
    
    if planned:
        planned_workout = planned["name"]
        workout_name = planned_workout
        # Ensure it's on the Garmin calendar
        logger.info(f"📅 Ensuring '{workout_name}' is scheduled on Garmin...")
        schedule_workout(
            client, 
            name=planned["name"], 
            target_date=today, 
            duration_minutes=planned["duration_minutes"],
            description=planned["description"],
            sport_type=planned["sport_type"]
        )

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
    success = send_morning_briefing(decision, metrics)
    if success:
        logger.info("✅ Morning briefing delivered successfully.")
    else:
        logger.error("❌ Morning briefing delivery failed.")


# ── /weekly Command ───────────────────────────────────────────────────────

async def _cmd_weekly(update, context):
    """Send the 7-day progress report on demand."""
    chat_id = str(update.effective_chat.id)
    await update.message.reply_text("📊 Building your weekly report…")
    await build_and_send_weekly_report(context.bot, chat_id)


# ── /schedule Command ──────────────────────────────────────────────────────

async def _cmd_schedule(update, context):
    """Schedule the 7-week training block on the Garmin calendar."""
    await update.message.reply_text("📆 Scheduling your 7-week training block on Garmin… this may take a minute.")

    client = get_garmin_client()
    if not client:
        await update.message.reply_text("❌ Could not connect to Garmin. Try again later.")
        return

    summary = schedule_training_block(client, weeks=7)

    lines = ["✅ *Training block scheduled!*\n"]
    if summary["scheduled"]:
        lines.append(f"📅 *Scheduled:* {len(summary['scheduled'])} workouts")
    if summary["skipped"]:
        lines.append(f"⏭️ *Already existed:* {len(summary['skipped'])} workouts")
    if summary["failed"]:
        lines.append(f"❌ *Failed:* {len(summary['failed'])} workouts")
        for f in summary["failed"]:
            lines.append(f"  • {f}")

    lines.append("\n*Weekly pattern:*")
    lines.append("Mon/Wed/Thu — PT Session")
    lines.append("Tue — Easy Run 5–7 km")
    lines.append("Fri — Rest")
    lines.append("Sat — Badminton")
    lines.append("Sun — Zone 2 Long Run")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


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
    application.add_handler(CallbackQueryHandler(_handle_meal_callback, pattern="^meal_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    
    # Training / Status Handlers
    application.add_handler(CommandHandler("weekly", _cmd_weekly))
    application.add_handler(CommandHandler("schedule", _cmd_schedule))
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

    # Send weekly report every Sunday at 8:00 PM Jakarta time
    async def _weekly_job(context):
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if chat_id:
            await build_and_send_weekly_report(context.bot, chat_id)

    job_queue.run_daily(
        _weekly_job,
        time=time(hour=20, minute=0, tzinfo=TIMEZONE),
        days=(6,),  # Sunday only
        name="weekly_progress_report"
    )
    
    logger.info("🤖 Garmin Assistant is online and scheduled. (5:45 AM Jakarta)")
    
    # Start the bot
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
