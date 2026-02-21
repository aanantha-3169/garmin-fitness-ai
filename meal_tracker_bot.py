#!/usr/bin/env python3
"""
meal_tracker_bot.py — Telegram bot that tracks meals via food photos.

Send a photo of your meal → Gemini vision estimates macros →
daily totals stored in SQLite → replies with remaining calories.

Run:
    python meal_tracker_bot.py

Requires in .env:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID     (optional — restricts the bot to one user)
    GEMINI_API_KEY
"""

import json
import logging
import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3-flash-preview"

DB_PATH = Path(__file__).parent / "meal_tracker.db"
TARGET_CALORIES_FILE = Path(__file__).parent / "target_calories.json"

ANALYSIS_PROMPT = (
    "You are a sports nutritionist. Estimate the total calories, protein, "
    "carbs, and fats in this meal. Return ONLY a valid JSON object with "
    'keys: "estimated_calories" (int), "protein_g" (int), "carbs_g" (int), '
    '"fats_g" (int), "meal_description" (string).'
    "\n\nIf the user provided context, use it to refine your estimates."
)


# ── MarkdownV2 helpers ───────────────────────────────────────────────────────

def _esc(text) -> str:
    """Escape special chars for Telegram MarkdownV2."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))


def _bold(text: str) -> str:
    return f"*{_esc(text)}*"


# ── SQLite Meal Log ──────────────────────────────────────────────────────────

def _init_db():
    """Create the meals table if it doesn't exist."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     TEXT    NOT NULL,
            log_date    TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            calories    INTEGER NOT NULL DEFAULT 0,
            protein_g   INTEGER NOT NULL DEFAULT 0,
            carbs_g     INTEGER NOT NULL DEFAULT 0,
            fats_g      INTEGER NOT NULL DEFAULT 0,
            description TEXT
        )
    """)
    conn.commit()
    conn.close()


def _log_meal(
    chat_id: str,
    calories: int,
    protein: int,
    carbs: int,
    fats: int,
    description: str,
):
    """Insert a meal entry for today."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """INSERT INTO meals
           (chat_id, log_date, timestamp, calories, protein_g, carbs_g, fats_g, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(chat_id),
            date.today().isoformat(),
            datetime.now().isoformat(),
            calories,
            protein,
            carbs,
            fats,
            description,
        ),
    )
    conn.commit()
    conn.close()


def _get_daily_totals(chat_id: str) -> dict:
    """Return today's aggregated macros for *chat_id*."""
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute(
        """SELECT COALESCE(SUM(calories), 0),
                  COALESCE(SUM(protein_g), 0),
                  COALESCE(SUM(carbs_g), 0),
                  COALESCE(SUM(fats_g), 0),
                  COUNT(*)
           FROM meals
           WHERE chat_id = ? AND log_date = ?""",
        (str(chat_id), date.today().isoformat()),
    ).fetchone()
    conn.close()
    return {
        "calories": row[0],
        "protein_g": row[1],
        "carbs_g": row[2],
        "fats_g": row[3],
        "meal_count": row[4],
    }


# ── Target Calories ──────────────────────────────────────────────────────────

# ── Target Calories & Supabase Logging ───────────────────────────────────────

def _get_daily_data(chat_id: str) -> dict:
    """Fetch daily totals and target from Supabase/local hybrid.
    
    Priority: Supabase > Local File (for target) > SQLite (for totals)
    """
    from db_manager import get_daily_log
    
    today_str = date.today().isoformat()
    supabase_log = get_daily_log(today_str)
    
    # Defaults
    target = 2500
    consumed = 0
    
    if supabase_log:
        target = supabase_log.get("target_calories", target)
        consumed = supabase_log.get("consumed_calories", 0)
    else:
        # Fallback to local logic if Supabase is offline or not yet initialized
        if TARGET_CALORIES_FILE.exists():
            try:
                data = json.loads(TARGET_CALORIES_FILE.read_text())
                if data.get("date") == today_str:
                    target = int(data.get("target_calories", target))
            except Exception: pass
        
        # Pull totals from SQLite
        local_totals = _get_daily_totals(chat_id)
        consumed = local_totals["calories"]

    return {
        "target": target,
        "consumed": consumed,
        "remaining": max(0, target - consumed)
    }


def save_target_calories(target: int):
    """(Deprecated) Legacy local save. main.py now uses db_manager.init_daily_log."""
    TARGET_CALORIES_FILE.write_text(
        json.dumps({"date": date.today().isoformat(), "target_calories": target})
    )


# ── Gemini Vision ────────────────────────────────────────────────────────────

def _analyze_food_photo(image_bytes: bytes, user_description: str = None) -> Optional[dict]:
    """Send a food photo (and optional text) to Gemini and return macro estimates."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    contents = [types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")]
    prompt = ANALYSIS_PROMPT
    if user_description:
        prompt += f"\n\nUser Notes: {user_description}"
    
    contents.append(prompt)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
    )

    raw = response.text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ── Telegram Handlers ────────────────────────────────────────────────────────

async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "👋 Send me a photo of your meal and I'll estimate the macros!\n\n"
        "I'll show you my estimate first, then you can save or correct it\\.\n\n"
        "Commands:\n"
        "/today — show today's totals\n"
        "/reset — clear today's log",
        parse_mode="MarkdownV2"
    )


async def _cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /today — show daily totals."""
    chat_id = str(update.effective_chat.id)
    
    # Get combined data from Supabase/local
    data = _get_daily_data(chat_id)
    totals = _get_daily_totals(chat_id)  # For pro/carb/fat details from local SQLite
    
    t_cal = "{:,}".format(data["consumed"])
    t_tar = "{:,}".format(data["target"])
    t_rem = "{:,}".format(data["remaining"])
    t_pro = str(totals["protein_g"])
    t_carb = str(totals["carbs_g"])
    t_fat = str(totals["fats_g"])
    t_meals = str(totals["meal_count"])

    msg = (
        f"📊 {_bold('Todays Totals')} "
        f"\\({_esc(t_meals)} meals\\)\n\n"
        f"🔥 Calories: {_bold(t_cal)} / {_esc(t_tar)}\n"
        f"🥩 Protein:  {_bold(t_pro)}g\n"
        f"🍚 Carbs:    {_bold(t_carb)}g\n"
        f"🧈 Fats:     {_bold(t_fat)}g\n\n"
        f"🎯 Remaining: {_bold(t_rem)} kcal"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def _cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset — clear today's meals."""
    chat_id = str(update.effective_chat.id)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "DELETE FROM meals WHERE chat_id = ? AND log_date = ?",
        (chat_id, date.today().isoformat()),
    )
    conn.commit()
    conn.close()
    
    # Note: This doesn't reset Supabase yet, as that's often used for "history"
    # But for a true daily reset we might want to clear it there too.
    # For now, just local SQLite.
    await update.message.reply_text("🗑️ Today's meal log has been cleared locally\\.", parse_mode="MarkdownV2")


async def _handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming food photos."""
    chat_id = str(update.effective_chat.id)

    # Optional: restrict to allowed chat
    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        logger.warning("Ignoring photo from unauthorized chat %s", chat_id)
        return

    await update.message.reply_text("🔍 Analyzing your meal…")

    # Download the highest-resolution photo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    # Store photo in user_data for potential re-analysis
    context.user_data["pending_photo"] = bytes(image_bytes)

    # Analyze with Gemini
    await _perform_meal_analysis(update, context)


async def _perform_meal_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, user_note: Optional[str] = None):
    """Core analysis logic shared between photo and text-correction steps."""
    image_bytes = context.user_data.get("pending_photo")
    if not image_bytes:
        await update.effective_message.reply_text("❌ Session lost. Please send a new photo.")
        return

    try:
        result = _analyze_food_photo(image_bytes, user_note)
    except Exception as exc:
        logger.error("Gemini analysis failed: %s", exc)
        await update.effective_message.reply_text("❌ Sorry, I couldn't analyze that photo\\. Try again\\?", parse_mode="MarkdownV2")
        return

    if not result:
        await update.effective_message.reply_text("❌ Couldn't parse the result\\. Try a clearer photo\\.", parse_mode="MarkdownV2")
        return

    # Store calculation in user_data
    context.user_data["pending_meal"] = result
    # Clear correction flag
    context.user_data["awaiting_correction"] = False

    cal = result.get("estimated_calories", 0)
    pro = result.get("protein_g", 0)
    carbs = result.get("carbs_g", 0)
    fats = result.get("fats_g", 0)
    desc = result.get("meal_description", "Unknown meal")

    # Format reply with buttons
    title = f"🍽️ {_bold('Analysis')}" if not user_note else f"🔄 {_bold('Revised Analysis')}"
    msg = (
        f"{title}\n\n"
        f"📝 {_bold(desc)}\n"
        f"🔥 Calories: {_bold(str(cal))}\n"
        f"🥩 Protein:  {_bold(str(pro))}g\n"
        f"🍚 Carbs:    {_bold(str(carbs))}g\n"
        f"🧈 Fats:     {_bold(str(fats))}g\n\n"
        "Does this look correct?"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Save", callback_data="meal_save"),
            InlineKeyboardButton("✏️ Update", callback_data="meal_update"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="meal_cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode="MarkdownV2")


async def _handle_meal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle interactions with meal confirmation buttons."""
    from db_manager import add_calories
    query = update.callback_query
    chat_id = str(update.effective_chat.id)
    await query.answer()

    if query.data == "meal_save":
        result = context.user_data.pop("pending_meal", None)
        context.user_data.pop("pending_photo", None)
        
        if not result:
            await query.edit_message_text("❌ No pending meal found.")
            return

        cal = result.get("estimated_calories", 0)
        pro = result.get("protein_g", 0)
        carbs = result.get("carbs_g", 0)
        fats = result.get("fats_g", 0)
        desc = result.get("meal_description", "Unknown meal")

        # Log to LOCAL SQLite
        _log_meal(chat_id, cal, pro, carbs, fats, desc)
        # Sync to SUPABASE
        add_calories(date.today().isoformat(), cal)

        # UI Response
        await query.edit_message_text(f"✅ {_bold(desc)} saved to your log\\!", parse_mode="MarkdownV2")
        
        # Show updated totals
        data = _get_daily_data(chat_id)
        t_rem = "{:,}".format(data["remaining"])
        await query.message.reply_text(f"🎯 {_bold('Remaining:')} {_bold(t_rem)} kcal", parse_mode="MarkdownV2")

    elif query.data == "meal_update":
        context.user_data["awaiting_correction"] = True
        await query.edit_message_text(
            f"✏️ {_bold('Correction Mode')}\n\n"
            "Please describe the meal in more detail (e.g., 'there's more rice than it looks like' or 'it's actually grilled chicken')\\.\n\n"
            "I'll use your description to re-analyze the original photo\\.",
            parse_mode="MarkdownV2"
        )

    elif query.data == "meal_cancel":
        context.user_data.pop("pending_meal", None)
        context.user_data.pop("pending_photo", None)
        context.user_data.pop("awaiting_correction", None)
        await query.edit_message_text("❌ Meal discarded.")


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages for meal corrections."""
    text = update.message.text
    if context.user_data.get("awaiting_correction"):
        await update.message.reply_text("🔄 Re-analyzing with your correction…")
        await _perform_meal_analysis(update, context, user_note=text)
    else:
        # Default behavior for non-correction text
        pass


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    """Start the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env")
        return
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set in .env")
        return

    _init_db()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Meal tracker handlers
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("today", _cmd_today))
    app.add_handler(CommandHandler("reset", _cmd_reset))
    app.add_handler(MessageHandler(filters.PHOTO, _handle_photo))

    # Notifier/Status handlers
    from telegram_notifier import setup_notifier_handlers
    setup_notifier_handlers(app)

    logger.info("🤖 Garmin Assistant Bot is running. Send a photo or use /status!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
