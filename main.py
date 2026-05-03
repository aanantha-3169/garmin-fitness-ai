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
    _cmd_fear,
    _cmd_load,
    _handle_photo,
    _handle_meal_callback,
    _handle_message,
)
from progress_reporter import build_and_send_weekly_report
from garmin_telemetry import sync_todays_workout, format_execution_context

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

async def run_morning_briefing(_context):
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

    # 4. Inject yesterday's execution telemetry into the readiness prompt
    import datetime as _dt
    yesterday_str = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
    from db_manager import get_completed_workout
    from db_manager import get_recent_subjective_logs
    yesterdays_telemetry = get_completed_workout(yesterday_str)
    execution_ctx = format_execution_context(yesterdays_telemetry) if yesterdays_telemetry else ""
    subjective_logs = get_recent_subjective_logs(days=2)
    subjective_notes = "\n".join(
        f"- {log['date']}: {log['context_text']}" for log in subjective_logs
    )

    # 5. Generate Decision
    decision = analyze_readiness(
        metrics,
        planned_workout,
        execution_context=execution_ctx,
        subjective_notes=subjective_notes,
    )
    
    # 6. Persist to Supabase
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

    # 7. Send to Telegram
    success = send_morning_briefing(decision, metrics)
    if success:
        logger.info("✅ Morning briefing delivered successfully.")
    else:
        logger.error("❌ Morning briefing delivery failed.")


# ── /sync_workout Command ─────────────────────────────────────────────────

async def _cmd_sync_workout(update, _context):
    """Manually sync today's Garmin workout telemetry to Supabase."""
    await update.message.reply_text("🔄 Syncing today's workout from Garmin…")
    client = get_garmin_client()
    if not client:
        await update.message.reply_text("❌ Could not connect to Garmin.")
        return

    telemetry = sync_todays_workout(client)
    if not telemetry:
        await update.message.reply_text("📭 No workout found for today yet\\. Try again after your session\\.", parse_mode="MarkdownV2")
        return

    duration_min = round((telemetry.get("duration_secs") or 0) / 60)
    name = telemetry.get("activity_name", "Unknown")
    avg_hr = telemetry.get("avg_hr", "N/A")
    aero_te = telemetry.get("aerobic_training_effect")
    te_str = f"{aero_te:.1f}" if aero_te is not None else "N/A"

    import re
    from datetime import date as _date
    def esc(t): return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(t))

    # Verify the row actually landed in Supabase
    from db_manager import get_completed_workout
    saved = get_completed_workout(_date.today().isoformat())
    if not saved:
        await update.message.reply_text(
            f"⚠️ *Garmin data fetched but DB save failed\\!*\n\n"
            f"Activity: {esc(name)}\n"
            f"Check Render logs for the Supabase error\\.\n"
            f"The `completed\\_workouts` table may not exist in Supabase\\.",
            parse_mode="MarkdownV2",
        )
        return

    await update.message.reply_text(
        f"✅ *Workout synced\\!*\n\n"
        f"🏃 {esc(name)}\n"
        f"⏱ Duration: {esc(duration_min)} min\n"
        f"💓 Avg HR: {esc(avg_hr)} bpm\n"
        f"📈 Aerobic TE: {esc(te_str)}",
        parse_mode="MarkdownV2",
    )


# ── /weekly Command ───────────────────────────────────────────────────────

async def _cmd_weekly(update, context):
    """Send the 7-day progress report on demand."""
    chat_id = str(update.effective_chat.id)
    await update.message.reply_text("📊 Building your weekly report…")
    await build_and_send_weekly_report(context.bot, chat_id)


# ── /schedule Command ──────────────────────────────────────────────────────

async def _cmd_schedule(update, _context):
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
    application.add_handler(CommandHandler("fear", _cmd_fear))
    application.add_handler(CommandHandler("load", _cmd_load))
    application.add_handler(MessageHandler(filters.PHOTO, _handle_photo))
    application.add_handler(CallbackQueryHandler(_handle_meal_callback, pattern="^meal_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    
    # Training / Status Handlers
    application.add_handler(CommandHandler("sync_workout", _cmd_sync_workout))
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

    # Sync workout telemetry every day at 8:00 PM Jakarta time
    async def _sync_workout_job(_context):
        client = get_garmin_client()
        if client:
            sync_todays_workout(client)

    job_queue.run_daily(
        _sync_workout_job,
        time=time(hour=20, minute=0, tzinfo=TIMEZONE),
        name="daily_workout_sync"
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
