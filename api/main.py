"""
api/main.py — FastAPI app deployed to Vercel. Reads from Supabase.

All endpoints are read-only. No authentication (single-user system,
no sensitive data beyond personal fitness metrics).

Endpoints:
  GET  /health             → Vercel health check
  GET  /api/today          → today's metrics, readiness, calories, plan
  GET  /api/probability    → current score + breakdown + 30-day trend
  GET  /api/week           → last 7 days: sessions, compliance, fear
  GET  /api/plan           → next 14 days from ironman_training_plan
  GET  /api/stats          → baseline fitness stats (VO2, FTP, swim pace)
  GET  /api/checkpoints    → days until each event + readiness per event
"""

import os
import sys
from datetime import date, timedelta

# Make the parent garmin-ai directory importable when running from api/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db_manager
import sport_science
from training_plan import (
    AQUAMAN, BINTAN, IRONMAN,
    VDOT, FTP_W_KG, WEIGHT_KG, CSS_SECS_100M,
    get_current_phase,
    get_week_sessions,
    get_athlete_hr_max,
)

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="Ironman Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # locked down once the Vercel frontend URL is known
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _days_until(target: date) -> int:
    return (target - date.today()).days


def _checkpoint_entry(name: str, event_date: date, type_: str, purpose: str) -> dict:
    return {
        "name":       name,
        "date":       event_date.isoformat(),
        "type":       type_,
        "purpose":    purpose,
        "days_until": _days_until(event_date),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Vercel health check — returns 200 when the service is up."""
    return {"status": "ok", "timestamp": date.today().isoformat()}


@app.get("/api/today")
def today():
    """Return today's training context: log, plan, phase, Zone 2 bounds."""
    today_str = date.today().isoformat()
    hr_max = get_athlete_hr_max()
    z2_low, z2_high = sport_science.zone2_bounds(hr_max)

    return {
        "date":          today_str,
        "phase":         get_current_phase(),
        "days_to_aquaman": _days_until(AQUAMAN),
        "days_to_bintan":  _days_until(BINTAN),
        "days_to_ironman": _days_until(IRONMAN),
        "today_log":     db_manager.get_daily_log(today_str),
        "todays_plan":   db_manager.get_todays_plan(),
        "zone2_bounds":  {"low": z2_low, "high": z2_high},
    }


@app.get("/api/probability")
def probability():
    """Return the latest probability score and the last 30 days of snapshots."""
    return {
        "latest": db_manager.get_latest_probability(),
        "trend":  db_manager.get_probability_trend(days=30),
    }


@app.get("/api/week")
def week():
    """Return last 7 days of training logs, compliance records, and fear logs."""
    return {
        "daily_logs":  db_manager.get_weekly_logs(days=7),
        "compliance":  db_manager.get_compliance_trend(days=7),
        "fear":        db_manager.get_fear_trend(days=7),
    }


@app.get("/api/plan")
def plan():
    """Return the next 14 days of sessions from ironman_training_plan.

    Falls back to the live periodization engine when the DB table is empty.
    """
    today_str = date.today().isoformat()
    end_str   = (date.today() + timedelta(days=13)).isoformat()

    sessions = db_manager.get_planned_sessions(today_str, end_str)

    if not sessions:
        # DB not seeded yet — generate from current + next week
        sessions = get_week_sessions(0) + get_week_sessions(1)
        sessions = [s for s in sessions if s["date"] >= today_str]

    return {"sessions": sessions}


@app.get("/api/stats")
def stats():
    """Return baseline fitness stats derived from SPORT_SCIENCE.md."""
    hr_max = get_athlete_hr_max()
    z2_low, z2_high = sport_science.zone2_bounds(hr_max)

    ftp_w = sport_science.ftp_watts(FTP_W_KG, WEIGHT_KG)
    bike_z2_low, bike_z2_high = sport_science.bike_zone2_power_bounds(ftp_w)

    easy_fast_secs, easy_slow_secs = sport_science.easy_pace_from_vdot(VDOT)
    css_fast, css_slow = sport_science.swim_easy_bounds(CSS_SECS_100M)

    return {
        "vdot":        VDOT,
        "ftp_w_kg":    FTP_W_KG,
        "ftp_watts":   ftp_w,
        "weight_kg":   WEIGHT_KG,
        "hr_max":      hr_max,
        "zone2_hr": {
            "low":  z2_low,
            "high": z2_high,
        },
        "bike_zone2_power": {
            "low_watts":  bike_z2_low,
            "high_watts": bike_z2_high,
        },
        "easy_run_pace": {
            "fast": sport_science.format_pace(easy_fast_secs),
            "slow": sport_science.format_pace(easy_slow_secs),
        },
        "swim_easy_pace": {
            "fast_secs_per_100m": css_fast,
            "slow_secs_per_100m": css_slow,
        },
        "css_secs_per_100m": CSS_SECS_100M,
    }


@app.get("/api/checkpoints")
def checkpoints():
    """Return days until each checkpoint event and the current training phase."""
    return {
        "current_phase": get_current_phase(),
        "checkpoints": [
            _checkpoint_entry(
                "Aquaman Langkawi", AQUAMAN, "swim_2km",
                "Fear confrontation — first ocean swim. Finish. Nothing else.",
            ),
            _checkpoint_entry(
                "Bintan Triathlon", BINTAN, "triathlon",
                "Full triathlon dress rehearsal. Complete all three disciplines.",
            ),
            _checkpoint_entry(
                "Half Ironman Malaysia", IRONMAN, "ironman_70.3",
                "The endpoint. 1.9km swim / 90km bike / 21km run. Cross the line.",
            ),
        ],
    }
