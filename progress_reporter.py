"""
progress_reporter.py — Weekly progress aggregation and AI coaching summary.

Queries the last 7 days from Supabase daily_logs, aggregates key metrics,
then passes the summary to Gemini for a coach-persona analysis.

Usage:
    from progress_reporter import build_and_send_weekly_report
    await build_and_send_weekly_report(bot, chat_id)
"""

import logging
import os
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3-flash-preview"

# ── MarkdownV2 helpers ────────────────────────────────────────────────────────

def _esc(text) -> str:
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))

def _bold(text: str) -> str:
    return f"*{_esc(text)}*"


# ── Data aggregation ──────────────────────────────────────────────────────────

def _extract_briefing_metric(row: dict, *keys):
    """Safely drill into morning_briefing_json with a chain of keys."""
    node = row.get("morning_briefing_json") or {}
    for k in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(k)
    return node


def aggregate_weekly(rows: list) -> dict:
    """Aggregate raw daily_log rows into a weekly summary dict.

    Returns a dict suitable for both the Telegram message and the Gemini prompt.
    """
    if not rows:
        return {}

    total_target   = 0
    total_consumed = 0
    total_protein  = 0
    total_carbs    = 0
    total_fats     = 0

    battery_readings = []
    sleep_scores     = []
    stress_readings  = []

    days_with_data      = 0
    days_workout_moved  = 0
    days_adjustment_needed = 0

    for row in rows:
        days_with_data += 1

        target   = row.get("target_calories")   or 0
        consumed = row.get("consumed_calories")  or 0
        total_target   += target
        total_consumed += consumed
        total_protein  += row.get("consumed_protein_g") or 0
        total_carbs    += row.get("consumed_carbs_g")   or 0
        total_fats     += row.get("consumed_fats_g")    or 0

        if row.get("workout_moved"):
            days_workout_moved += 1

        bb = _extract_briefing_metric(row, "metrics", "body_battery", "body_battery_current")
        if bb is not None:
            battery_readings.append(bb)

        sleep = _extract_briefing_metric(row, "metrics", "sleep", "sleep_score")
        if sleep is not None:
            sleep_scores.append(sleep)

        stress = _extract_briefing_metric(row, "metrics", "stress", "stress_avg")
        if stress is not None:
            stress_readings.append(stress)

        if _extract_briefing_metric(row, "decision", "adjustment_needed"):
            days_adjustment_needed += 1

    n = days_with_data or 1
    calorie_balance = total_consumed - total_target  # negative = deficit

    return {
        "period_start": rows[0]["date"],
        "period_end":   rows[-1]["date"],
        "days_logged":  days_with_data,

        # Calories
        "total_target_cal":   total_target,
        "total_consumed_cal": total_consumed,
        "calorie_balance":    calorie_balance,
        "avg_daily_deficit":  round(calorie_balance / n),

        # Macros (daily averages)
        "avg_protein_g": round(total_protein / n),
        "avg_carbs_g":   round(total_carbs   / n),
        "avg_fats_g":    round(total_fats    / n),

        # Recovery
        "avg_body_battery": round(sum(battery_readings) / len(battery_readings)) if battery_readings else None,
        "avg_sleep_score":  round(sum(sleep_scores)     / len(sleep_scores))     if sleep_scores     else None,
        "avg_stress":       round(sum(stress_readings)  / len(stress_readings))  if stress_readings  else None,

        # Training
        "days_workout_moved":      days_workout_moved,
        "days_training_adjusted":  days_adjustment_needed,
        "days_on_plan":            days_with_data - days_workout_moved,
    }


# ── Gemini coach analysis ─────────────────────────────────────────────────────

_COACH_PROMPT = """\
You are a supportive but evidence-based performance coach reviewing a client's 7-day training and nutrition data.

Provide EXACTLY:
1. A one-sentence trajectory assessment (are they progressing, plateauing, or regressing?).
2. Three concise bullet points — one on nutrition, one on recovery, one on training adherence.
3. One specific, actionable focus for next week.

Keep the tone motivational but honest. Do not use filler phrases like "Great job!".
Total response must be under 120 words.
"""


def generate_coach_analysis(summary: dict) -> str:
    """Send the weekly summary to Gemini and return the coach's analysis."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — skipping coach analysis.")
        return ""

    client = genai.Client(api_key=api_key)

    balance_label = "deficit" if summary["calorie_balance"] < 0 else "surplus"
    balance_abs   = abs(summary["calorie_balance"])

    user_prompt = (
        f"Week: {summary['period_start']} to {summary['period_end']} "
        f"({summary['days_logged']} days logged)\n\n"
        f"NUTRITION\n"
        f"  Total calorie {balance_label}: {balance_abs} kcal "
        f"(avg {abs(summary['avg_daily_deficit'])} kcal/day)\n"
        f"  Avg daily macros — Protein: {summary['avg_protein_g']}g  "
        f"Carbs: {summary['avg_carbs_g']}g  Fats: {summary['avg_fats_g']}g\n\n"
        f"RECOVERY\n"
        f"  Avg body battery: {summary['avg_body_battery'] or 'N/A'}\n"
        f"  Avg sleep score:  {summary['avg_sleep_score']  or 'N/A'}\n"
        f"  Avg stress:       {summary['avg_stress']       or 'N/A'}\n\n"
        f"TRAINING\n"
        f"  Days on plan:       {summary['days_on_plan']}\n"
        f"  Workouts moved:     {summary['days_workout_moved']}\n"
        f"  Days AI adjusted:   {summary['days_training_adjusted']}\n"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=_COACH_PROMPT,
                temperature=0.4,
            ),
        )
        return response.text.strip()
    except Exception as exc:
        logger.error("Gemini coach analysis failed: %s", exc)
        return ""


# ── Telegram message formatter ────────────────────────────────────────────────

def format_weekly_message(summary: dict, coach_text: str) -> str:
    """Build the MarkdownV2 weekly report message."""
    balance      = summary["calorie_balance"]
    bal_sign     = "\\-" if balance < 0 else "\\+"
    balance_str  = f"{bal_sign}{_esc(f'{abs(balance):,}')} kcal"
    avg_deficit  = summary["avg_daily_deficit"]
    avg_sign     = "\\-" if avg_deficit < 0 else "\\+"
    avg_str      = f"{avg_sign}{_esc(str(abs(avg_deficit)))} kcal/day"

    bb    = _esc(str(summary["avg_body_battery"])) if summary["avg_body_battery"] is not None else "N/A"
    sleep = _esc(str(summary["avg_sleep_score"]))  if summary["avg_sleep_score"]  is not None else "N/A"
    stress = _esc(str(summary["avg_stress"]))      if summary["avg_stress"]       is not None else "N/A"

    lines = [
        f"📅 {_bold('Weekly Report')} \\({_esc(summary['period_start'])} → {_esc(summary['period_end'])}\\)",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🔥 {_bold('Nutrition')}",
        f"  Calorie balance: {_bold(balance_str)}",
        f"  Avg per day: {_esc(avg_str)}",
        f"  Avg protein: {_bold(_esc(str(summary['avg_protein_g'])) + 'g')}  "
        f"Carbs: {_esc(str(summary['avg_carbs_g']))}g  "
        f"Fats: {_esc(str(summary['avg_fats_g']))}g",
        "",
        f"🔋 {_bold('Recovery')}",
        f"  Body Battery: {_bold(bb)}  \\|  Sleep Score: {_bold(sleep)}",
        f"  Avg Stress: {_bold(stress)}",
        "",
        f"🏋️ {_bold('Training')}",
        f"  Days on plan: {_bold(_esc(str(summary['days_on_plan'])))} / {_esc(str(summary['days_logged']))}",
        f"  Workouts moved: {_esc(str(summary['days_workout_moved']))}  \\|  "
        f"AI\\-adjusted days: {_esc(str(summary['days_training_adjusted']))}",
    ]

    if coach_text:
        # Escape the Gemini output and insert it
        lines += [
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🤖 {_bold('Coach Analysis')}",
            _esc(coach_text),
        ]

    return "\n".join(lines)


# ── Public entry point ────────────────────────────────────────────────────────

async def build_and_send_weekly_report(bot, chat_id: str) -> bool:
    """Fetch, aggregate, analyse, and send the weekly report.

    Called by both the /weekly command and the Sunday scheduled job.
    Returns True on successful send.
    """
    from db_manager import get_weekly_logs

    rows = get_weekly_logs(days=7)
    if not rows:
        await bot.send_message(
            chat_id=chat_id,
            text="📭 No data logged this week yet\\. Start logging meals and workouts to see your report\\!",
            parse_mode="MarkdownV2",
        )
        return False

    summary    = aggregate_weekly(rows)
    coach_text = generate_coach_analysis(summary)
    message    = format_weekly_message(summary, coach_text)

    await bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="MarkdownV2",
    )
    logger.info("✅ Weekly report sent for %s → %s", summary["period_start"], summary["period_end"])
    return True
