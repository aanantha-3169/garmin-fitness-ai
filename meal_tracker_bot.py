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

from garmin_client import get_garmin_client
from garmin_nutrition import log_meal_to_garmin
from intent_router import classify_intent

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
    """Fetch daily totals and target from Supabase (source of truth on Render).

    Falls back to SQLite + local file only when Supabase is unreachable.
    Always returns calories, macros, meal_count, target, and remaining.
    """
    from db_manager import get_daily_log

    today_str = date.today().isoformat()
    supabase_log = get_daily_log(today_str)

    if supabase_log:
        target   = supabase_log.get("target_calories",  2500)
        consumed = supabase_log.get("consumed_calories", 0)
        return {
            "target":     target,
            "consumed":   consumed,
            "remaining":  max(0, target - consumed),
            "protein_g":  supabase_log.get("consumed_protein_g", 0),
            "carbs_g":    supabase_log.get("consumed_carbs_g",   0),
            "fats_g":     supabase_log.get("consumed_fats_g",    0),
            "meal_count": supabase_log.get("meal_count",         0),
        }

    # Supabase unavailable — fall back to local SQLite + file
    target = 2500
    if TARGET_CALORIES_FILE.exists():
        try:
            data = json.loads(TARGET_CALORIES_FILE.read_text())
            if data.get("date") == today_str:
                target = int(data.get("target_calories", target))
        except Exception:
            pass

    local = _get_daily_totals(chat_id)
    return {
        "target":     target,
        "consumed":   local["calories"],
        "remaining":  max(0, target - local["calories"]),
        "protein_g":  local["protein_g"],
        "carbs_g":    local["carbs_g"],
        "fats_g":     local["fats_g"],
        "meal_count": local["meal_count"],
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

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


def _analyze_food_text(description: str) -> Optional[dict]:
    """Send a text meal description to Gemini and return macro estimates."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = (
        ANALYSIS_PROMPT
        + f"\n\nMeal description: {description}"
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    raw = response.text.strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ── Telegram Handlers ────────────────────────────────────────────────────────

async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "👋 Log your meals in two ways:\n\n"
        "📷 *Send a photo* — I'll analyse it with AI\n"
        "✍️ *Type what you ate* — e\\.g\\. _'2 eggs, toast and coffee with milk'_\n\n"
        "I'll show you my estimate first, then you can save or correct it\\.\n\n"
        "Commands:\n"
        "/today — show today's totals\n"
        "/reset — clear today's log",
        parse_mode="MarkdownV2"
    )


async def _cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /today — show daily totals."""
    chat_id = str(update.effective_chat.id)
    
    data = _get_daily_data(chat_id)
    t_cal   = "{:,}".format(data["consumed"])
    t_tar   = "{:,}".format(data["target"])
    t_rem   = "{:,}".format(data["remaining"])
    t_pro   = str(data["protein_g"])
    t_carb  = str(data["carbs_g"])
    t_fat   = str(data["fats_g"])
    t_meals = str(data["meal_count"])

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


async def _perform_meal_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, user_note: Optional[str] = None, text_description: Optional[str] = None):
    """Core analysis logic shared between photo, text-correction, and text-only steps."""
    image_bytes = context.user_data.get("pending_photo")

    try:
        if text_description:
            result = _analyze_food_text(text_description)
        elif image_bytes:
            result = _analyze_food_photo(image_bytes, user_note)
        else:
            await update.effective_message.reply_text("❌ Session lost. Please send a new photo or describe your meal.")
            return
    except Exception as exc:
        logger.error("Gemini analysis failed: %s", exc)
        await update.effective_message.reply_text("❌ Sorry, I couldn't analyze that\\. Try again\\?", parse_mode="MarkdownV2")
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
    from db_manager import add_macros
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

        date_str = date.today().isoformat()

        # Log to LOCAL SQLite (ephemeral on Render, used as in-memory fallback)
        _log_meal(chat_id, cal, pro, carbs, fats, desc)
        # Sync to SUPABASE (persistent — source of truth on deployed bot)
        add_macros(date_str, cal, pro, carbs, fats)
        # Sync to GARMIN
        garmin = get_garmin_client()
        if garmin:
            log_meal_to_garmin(garmin, cal, pro, carbs, fats, date_str)

        # UI Response
        await query.edit_message_text(f"✅ {_bold(desc)} saved to your log\\!", parse_mode="MarkdownV2")

        # Show updated totals
        data = _get_daily_data(chat_id)
        t_cal = "{:,}".format(data["consumed"])
        t_tar = "{:,}".format(data["target"])
        t_rem = "{:,}".format(data["remaining"])
        msg = (
            f"📊 {_bold('Todays totals')} \\({_esc(str(data['meal_count']))} meals\\)\n\n"
            f"🔥 Calories: {_bold(t_cal)} / {_esc(t_tar)}\n"
            f"🥩 Protein:  {_bold(str(data['protein_g']))}g\n"
            f"🍚 Carbs:    {_bold(str(data['carbs_g']))}g\n"
            f"🧈 Fats:     {_bold(str(data['fats_g']))}g\n\n"
            f"🎯 Remaining: {_bold(t_rem)} kcal"
        )
        await query.message.reply_text(msg, parse_mode="MarkdownV2")

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


async def _handle_subjective(update: Update, text: str) -> None:
    """Persist a qualitative athlete note and acknowledge it."""
    from db_manager import log_subjective
    date_str = date.today().isoformat()

    # Simple sentiment: negative keywords → lower score
    negative_words = {"tight", "sore", "pain", "ache", "tired", "exhausted",
                      "drained", "heavy", "stiff", "injury", "hurt", "fatigue"}
    score = -0.5 if any(w in text.lower() for w in negative_words) else 0.3
    log_subjective(date_str, text, score)

    await update.message.reply_text(
        f"📝 {_bold('Note logged')}\\!\n\n"
        f"_{_esc(text)}_\n\n"
        "I'll factor this into tomorrow's readiness check\\.",
        parse_mode="MarkdownV2",
    )


async def _handle_metric(update: Update, extracted_value: Optional[dict]) -> None:
    """Persist a self-reported numeric metric and acknowledge it."""
    from db_manager import log_metric
    date_str = date.today().isoformat()

    if extracted_value and extracted_value.get("type") and extracted_value.get("value") is not None:
        metric_type = str(extracted_value["type"])
        value = float(extracted_value["value"])
        log_metric(date_str, metric_type, value)
        await update.message.reply_text(
            f"📊 {_bold('Metric saved')}: {_esc(metric_type)} \\= {_esc(str(value))}",
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text(
            "📊 Got it\\! I couldn't extract a specific number — try something like "
            "_'I weigh 82\\.5 kg'_ or _'soreness 6/10'_\\.",
            parse_mode="MarkdownV2",
        )


async def _cmd_fear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /fear [1-10] — log today's water fear level."""
    from db_manager import log_water_fear
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "📊 Log your water fear level: /fear [1-10]\n"
            "1 = completely calm, 10 = full panic response"
        )
        return

    level = int(args[0])
    if not 1 <= level <= 10:
        await update.message.reply_text("⚠️ Level must be between 1 and 10.")
        return

    log_water_fear(date.today().isoformat(), level)

    if level <= 3:
        note = "Building that calm baseline 🌊"
    elif level <= 6:
        note = "Normal. Keep showing up. The water gets quieter."
    else:
        note = "Noted. Rest is okay. Fear is information, not failure."

    await update.message.reply_text(f"💧 Fear level {level}/10 logged.\n{note}")


async def _cmd_load(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /load [1-10] — log today's workday stress level."""
    from db_manager import log_workday_load
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "📊 Log your workday stress: /load [1-10]\n"
            "1 = completely free day, 10 = back-to-back meetings all day"
        )
        return

    level = int(args[0])
    if not 1 <= level <= 10:
        await update.message.reply_text("⚠️ Level must be between 1 and 10.")
        return

    log_workday_load(date.today().isoformat(), level)

    if level <= 3:
        note = "Light day. Full session is a go."
    elif level <= 6:
        note = "Manageable. Train as planned, monitor how you feel."
    elif level <= 8:
        note = "Heavy day. Consider a shorter session or Zone 2 only."
    else:
        note = "Brutal day. Rest is a legitimate training choice."

    await update.message.reply_text(f"💼 Load {level}/10 logged.\n{note}")


async def _handle_query(update: Update, text: str) -> None:
    """Answer a general question using Gemini with today's nutrition context."""
    chat_id = str(update.effective_chat.id)
    data = _get_daily_data(chat_id)

    context_str = (
        f"Today's nutrition: {data['consumed']} / {data['target']} kcal consumed. "
        f"Protein: {data['protein_g']}g, Carbs: {data['carbs_g']}g, Fats: {data['fats_g']}g. "
        f"Remaining: {data['remaining']} kcal."
    )

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"Context: {context_str}\n\nUser question: {text}",
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a concise fitness nutrition assistant. "
                    "Answer the user's question in 1-3 sentences using the provided context. "
                    "Be direct and practical."
                ),
                temperature=0.3,
            ),
        )
        await update.message.reply_text(response.text.strip())
    except Exception as exc:
        logger.error("Query handler failed: %s", exc)
        await update.message.reply_text("❌ Sorry, I couldn't answer that right now\\.", parse_mode="MarkdownV2")


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route incoming text to the correct handler via the intent classifier.

    If the user is mid-correction flow, skip routing and go straight to
    meal re-analysis to avoid disrupting that interaction state.
    """
    text = update.message.text.strip()

    # Mid-correction: bypass router — user is refining a meal estimate
    if context.user_data.get("awaiting_correction"):
        await update.message.reply_text("🔄 Re-analyzing with your correction…")
        await _perform_meal_analysis(update, context, user_note=text)
        return

    # Classify intent before dispatching
    intent_result = await classify_intent(text)
    intent = intent_result.get("intent", "MEAL")
    confidence = intent_result.get("confidence", 0.0)

    # Low-confidence classifications default to MEAL to avoid losing food logs
    if confidence < 0.6:
        intent = "MEAL"

    if intent == "SUBJECTIVE":
        await _handle_subjective(update, text)
    elif intent == "METRIC":
        await _handle_metric(update, intent_result.get("extracted_value"))
    elif intent == "QUERY":
        await _handle_query(update, text)
    elif intent == "FEAR":
        await update.message.reply_text(
            "💧 Noted. Use /fear [1-10] to log your fear level so I can track the trend.\n"
            "e.g. /fear 4"
        )
    else:
        # MEAL — existing flow
        context.user_data.pop("pending_photo", None)
        await update.message.reply_text("🔍 Estimating macros from your description…")
        await _perform_meal_analysis(update, context, text_description=text)


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
