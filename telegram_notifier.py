"""
telegram_notifier.py — Interactive morning briefing and status bot.

Supports:
- /status: Real-time Garmin check (work-out completion, body battery).
- Inline Keyboards: interactive decisions on training (Move/Agree).
- Callback Queries: handle user button clicks.
- Morning Briefing: Formatted MarkdownV2 with commute & mindfulness.

Usage:
    # In your main bot runner:
    from telegram_notifier import setup_notifier_handlers
    setup_notifier_handlers(application)
"""

import logging
import os
import re
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from training_advisor import analyze_readiness, TrainingDecision
from commute_optimizer import get_commute_recommendation
from garmin_client import get_garmin_client
from garmin_metrics import get_health_metrics, check_todays_activity_status

logger = logging.getLogger(__name__)


# ── MarkdownV2 helpers ───────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))


def _bold(text: str) -> str:
    return f"*{_esc(text)}*"


# ── Message Formatting ───────────────────────────────────────────────────────

def format_briefing_text(
    decision: TrainingDecision,
    metrics: dict,
) -> str:
    """Build the MarkdownV2 morning briefing message string."""
    battery = metrics.get("body_battery", {}).get("body_battery_current", "–")
    hrv_status = metrics.get("hrv", {}).get("hrv_status", "–")
    hrv_avg = metrics.get("hrv", {}).get("hrv_overnight_avg", "–")
    sleep_score = metrics.get("sleep", {}).get("sleep_score", "–")
    sleep_quality = metrics.get("sleep", {}).get("sleep_quality", "–")
    rhr = metrics.get("resting_heart_rate", {}).get("resting_heart_rate_bpm", "–")
    stress = metrics.get("stress", {}).get("stress_avg", "–")

    status_emoji = "⚠️" if decision.adjustment_needed else "✅"

    lines = [
        f"☀️ {_bold('Health Briefing')}",
        "",
        f"🔋 {_bold('Body Battery:')} {_esc(str(battery))}  \\|  "
        f"💓 {_bold('HRV:')} {_esc(str(hrv_avg))} \\({_esc(str(hrv_status))}\\)",
        "",
        f"😴 {_bold('Sleep:')} {_esc(str(sleep_score))} \\({_esc(str(sleep_quality))}\\)  \\|  "
        f"❤️ {_bold('RHR:')} {_esc(str(rhr))} bpm",
        "",
        f"😤 {_bold('Stress Avg:')} {_esc(str(stress))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🎯 {_bold('Target Calories:')} {_esc(f'{decision.target_calories:,}')}",
        "",
        f"{status_emoji} {_bold('Workout Action:')} {_esc(decision.recommended_action)}",
    ]

    if decision.philosophical_reflection:
        lines += [
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🧘 {_bold('Mindfulness Moment')}",
            f"_{_esc(decision.philosophical_reflection)}_",
        ]

    try:
        commute_rec = get_commute_recommendation()
        lines += [
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🚗 {_bold('Commute')}",
            _esc(commute_rec),
        ]
    except Exception as exc:
        logger.warning("Could not get commute recommendation: %s", exc)

    return "\n".join(lines)


def get_decision_keyboard(adjustment_needed: bool, workout_name: str) -> InlineKeyboardMarkup:
    """Create the inline keyboard with the workout name embedded in callback data."""
    # Escape workout name to avoid issues in callback data string
    # (assuming name doesn't contain ':')
    if adjustment_needed:
        keyboard = [
            [
                InlineKeyboardButton("📅 Reschedule to Tomorrow", callback_data=f"move_tomorrow:{workout_name}"),
                InlineKeyboardButton("🔥 Force Proceed Anyway", callback_data=f"keep_today:{workout_name}"),
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("✅ Agree & Proceed", callback_data=f"keep_today:{workout_name}"),
                InlineKeyboardButton("📅 Move it anyway", callback_data=f"move_tomorrow:{workout_name}"),
            ]
        ]
    return InlineKeyboardMarkup(keyboard)


# ── Bot Handlers ─────────────────────────────────────────────────────────────

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetcher for real-time Garmin data and readiness analysis.
    
    Always pulls latest data from Garmin. If the workout is not yet done,
    it re-evaluates the plan if recovery metrics have significantly changed.
    """
    chat_id = str(update.effective_chat.id)
    allowed_id = os.getenv("TELEGRAM_CHAT_ID")
    if allowed_id and chat_id != allowed_id:
        return

    await update.message.reply_text("🔄 Syncing latest Garmin metrics...")

    # 1. Fetch live metrics from Garmin
    client = get_garmin_client()
    if not client:
        await update.message.reply_text("❌ Failed to authenticate with Garmin.")
        return

    today_str = date.today().isoformat()
    metrics = get_health_metrics(client)
    battery = metrics.get("body_battery", {}).get("body_battery_current", "–")
    
    # Workout type details
    weekday = date.today().weekday()
    expected_type = "strength_training"
    workout_name = "Training Session"
    if weekday == 2: workout_name = "Lift A: Push & Quads"
    elif weekday == 5: workout_name = "Lift B: Pull & Hinge"
    elif weekday == 6: 
        workout_name = "Zone 2 Long Run"
        expected_type = "running"

    is_completed = check_todays_activity_status(client, expected_type)
    
    # 2. Re-evaluate Plan (Dynamic decision making)
    from db_manager import get_daily_log, init_daily_log, update_morning_briefing
    from training_advisor import analyze_readiness
    
    cached_log = get_daily_log(today_str)
    decision = None
    notification_prefix = ""

    if cached_log and cached_log.get("morning_briefing_json"):
        briefing = cached_log["morning_briefing_json"]
        morning_metrics = briefing.get("metrics", {})
        morning_decision = briefing.get("decision", {})
        
        # Check for significant state change if training is still due
        if not is_completed and not cached_log.get("workout_moved"):
            morning_bb = morning_metrics.get("body_battery", {}).get("body_battery_current", 100)
            current_bb = metrics.get("body_battery", {}).get("body_battery_current", 0)
            
            # Re-analyze if body battery crashed (>15 pts drop or <25 absolute)
            if (morning_bb - current_bb > 15) or current_bb < 25:
                logger.info("⚠️ Significant recovery drop detected. Re-evaluating plan.")
                decision = analyze_readiness(metrics, workout_name)
                
                # Check for Pivot: If we were supposed to train but now shouldn't
                if not decision.adjustment_needed and morning_decision.get("adjustment_needed") == False:
                    # Recommendation stayed the same
                    pass 
                elif decision.adjustment_needed != morning_decision.get("adjustment_needed"):
                    notification_prefix = "🔄 {_bold('Plan Adapted:')} Recovery metrics have changed since this morning\\. Updating advice\\.\n\n"
                
                # Update Supabase with the new decision/metrics
                briefing["metrics"] = metrics
                briefing["decision"] = decision.model_dump()
                update_morning_briefing(today_str, briefing)
            else:
                # Use cached decision but updated metrics
                from training_advisor import TrainingDecision
                decision = TrainingDecision.model_validate(morning_decision)
                briefing["metrics"] = metrics
                update_morning_briefing(today_str, briefing)
        else:
            # Workout done or moved, just use existing decision for display
            from training_advisor import TrainingDecision
            decision = TrainingDecision.model_validate(morning_decision)
    else:
        # No morning data: Generate fresh
        decision = analyze_readiness(metrics, workout_name)
        briefing_data = {"metrics": metrics, "decision": decision.model_dump(), "workout_name": workout_name}
        init_daily_log(today_str, decision.target_calories, briefing_data)

    # 3. Final UI check
    if cached_log and cached_log.get("workout_moved"):
        await update.message.reply_text(
            f"📅 {_bold('Workout rescheduled')}\\. Your training for today was moved tomorrow\\. Current Body Battery: {_bold(str(battery))}\\.",
            parse_mode="MarkdownV2"
        )
        return

    if is_completed:
        await update.message.reply_text(
            f"✅ {_bold('Workout logged')}\\. Current Body Battery: {_bold(str(battery))}\\. Recover well\\!",
            parse_mode="MarkdownV2"
        )
        return

    # 4. Display
    text = notification_prefix + format_briefing_text(decision, metrics)
    reply_markup = get_decision_keyboard(decision.adjustment_needed, workout_name)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="MarkdownV2")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks for the training decisions."""
    query = update.callback_query
    await query.answer()

    data = query.data
    action = data.split(":")[0] if ":" in data else data
    workout_name = data.split(":")[1] if ":" in data else "Training Session"

    today_str = date.today().isoformat()
    from db_manager import update_workout_moved

    # 1. Remove buttons immediately to provide visual feedback of processing
    await query.edit_message_reply_markup(reply_markup=None)

    if action == "move_tomorrow":
        from garmin_calendar_manager import reschedule_workout
        from datetime import timedelta
        
        # Send a separate status message to avoid editing complexity
        status_msg = await query.message.reply_text(f"🔄 {_bold('Updating Calendar …')}", parse_mode="MarkdownV2")
        
        result_msg = reschedule_workout(workout_name, date.today(), date.today() + timedelta(days=1))
        
        if result_msg and "Calendar updated" in result_msg:
            update_text = f"✅ {_bold('Update:')} {result_msg}"
            update_workout_moved(today_str, True)
        else:
            update_text = f"⚠️ {_bold('Wait:')} {result_msg or 'Reschedule failed.'}"
            
        await status_msg.edit_text(text=update_text, parse_mode="MarkdownV2")

    elif action == "keep_today":
        update_text = f"✅ {_bold('Update:')} Proceeding with today\\'s plan for {_bold(workout_name)}\\."
        update_workout_moved(today_str, False)
        await query.message.reply_text(text=update_text, parse_mode="MarkdownV2")


def setup_notifier_handlers(application):
    """Register the status and callback handlers with the application."""
    application.add_handler(CommandHandler("status", handle_status))
    application.add_handler(CallbackQueryHandler(handle_callback))


# ── Programmatic Sending (for main.py / scheduler) ───────────────────────────

def send_morning_briefing(
    decision: TrainingDecision,
    garmin_metrics: dict,
) -> bool:
    """Format and send the morning briefing with buttons via raw requests.
    
    This is used by main.py for the scheduled 5:45 AM briefing.
    """
    import requests
    import json

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
        return False

    # Determine today's workout name
    today = date.today()
    weekday = today.weekday()
    workout_name = "Training Session"
    if weekday == 2:
        workout_name = "Lift A: Push & Quads"
    elif weekday == 5:
        workout_name = "Lift B: Pull & Hinge"
    elif weekday == 6:
        workout_name = "Zone 2 Long Run"

    text = format_briefing_text(decision, garmin_metrics)
    kb = get_decision_keyboard(decision.adjustment_needed, workout_name)
    
    # Convert InlineKeyboardMarkup to a serializable dict for requests
    reply_markup = {
        "inline_keyboard": [
            [{"text": b.text, "callback_data": b.callback_data} for b in row]
            for row in kb.inline_keyboard
        ]
    }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "reply_markup": json.dumps(reply_markup)
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("✅ Programmatic briefing sent with buttons.")
        return True
    except Exception as exc:
        logger.error("❌ Failed to send programmatic briefing: %s", exc)
        return False
