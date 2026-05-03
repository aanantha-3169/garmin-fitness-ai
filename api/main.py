"""
api/main.py — FastAPI app deployed to Vercel. Reads from Supabase.

All endpoints are read-only. No authentication (single-user system,
no sensitive data beyond personal fitness metrics).

Endpoints:
  GET  /api/health         → Vercel health check
  GET  /api/today          → garmin vitals, nutrition, session plan, readiness
  GET  /api/probability    → overall score + components + 30-day trend
  GET  /api/week           → last 7 days: sessions, load, fear, calories
  GET  /api/plan           → next 14 days of planned sessions (flat array)
  GET  /api/stats          → baseline fitness stats (VO2, FTP, swim pace)
  GET  /api/checkpoints    → each event: days until + readiness score
"""

import os
import sys
from datetime import date, timedelta
from typing import Any

# Make the parent garmin-ai directory importable when running from api/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

import db_manager
import sport_science
from training_plan import (
    AQUAMAN, BINTAN, IRONMAN,
    FTP_W_KG,
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


# ── Constants ─────────────────────────────────────────────────────────────────

_VO2_MAX   = 54       # Garmin-reported VO2max (CLAUDE.md athlete profile)
_SWIM_PACE = "1:58"   # 100m pool average
_5K_PRED   = "22:20"
_HALF_PRED = "1:49:27"

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_ACTIVITY_TYPE_MAP = {
    "swimming":       "swim",
    "open_water":     "swim",
    "running":        "run",
    "trail_running":  "run",
    "cycling":        "bike",
    "road_cycling":   "bike",
    "indoor_cycling": "bike",
    "virtual_ride":   "bike",
    "multi_sport":    "brick",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _days_until(target: date) -> int:
    return (target - date.today()).days


def _safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts; returns *default* if any key is absent."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
        if d is None:
            return default
    return d


def _map_activity_type(raw: str) -> str:
    low = raw.lower().replace(" ", "_")
    for k, v in _ACTIVITY_TYPE_MAP.items():
        if k in low:
            return v
    return "other"


def _disciplines_match(completed_raw: str, planned_discipline: str) -> bool:
    """Return True if the completed Garmin activity type matches the planned discipline."""
    return _map_activity_type(completed_raw) == planned_discipline


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    """Vercel health check — returns 200 when the service is up."""
    return {"status": "ok", "timestamp": date.today().isoformat()}


@app.get("/api/today")
def today():
    """Return today's Garmin vitals, nutrition totals, session plan, and readiness."""
    today_str = date.today().isoformat()
    hr_max    = get_athlete_hr_max()
    z2_low, z2_high = sport_science.zone2_bounds(hr_max)

    log       = db_manager.get_daily_log(today_str)
    plan      = db_manager.get_todays_plan()
    fear      = db_manager.get_latest_fear_level()
    completed = db_manager.get_completed_workout(today_str)

    # Extract nested morning briefing sub-dicts
    briefing = _safe_get(log, "morning_briefing_json", default={})
    metrics  = _safe_get(briefing, "metrics", default={})
    decision = _safe_get(briefing, "decision", default={})

    garmin = {
        "body_battery":           _safe_get(metrics, "body_battery", "body_battery_current"),
        "hrv_status":             _safe_get(metrics, "hrv", "hrv_status"),
        "hrv_overnight_avg":      _safe_get(metrics, "hrv", "hrv_overnight_avg"),
        "sleep_score":            _safe_get(metrics, "sleep", "sleep_score"),
        "sleep_quality":          _safe_get(metrics, "sleep", "sleep_quality"),
        "resting_heart_rate_bpm": _safe_get(metrics, "resting_heart_rate", "resting_heart_rate_bpm"),
        "stress_avg":             _safe_get(metrics, "stress", "stress_avg"),
    }

    nutrition = {
        "consumed_calories":  _safe_get(log, "consumed_calories", default=0),
        "target_calories":    _safe_get(log, "target_calories",   default=0),
        "consumed_protein_g": _safe_get(log, "consumed_protein_g", default=0),
        "consumed_carbs_g":   _safe_get(log, "consumed_carbs_g",   default=0),
        "consumed_fats_g":    _safe_get(log, "consumed_fats_g",    default=0),
        "meal_count":         _safe_get(log, "meal_count",         default=0),
    }

    # Build completed-activity block from Garmin sync (None when not yet synced)
    completed_block = None
    if completed:
        dur_secs = completed.get("duration_secs") or 0
        completed_block = {
            "activity_type":  _map_activity_type(completed.get("activity_type") or ""),
            "activity_name":  completed.get("activity_name"),
            "duration_mins":  round(dur_secs / 60) if dur_secs else None,
            "avg_heart_rate": completed.get("avg_hr"),
        }

    # Determine completion and deviation against the plan
    is_completed = False
    deviation    = False
    if plan and completed:
        is_completed = _disciplines_match(completed.get("activity_type") or "", plan.get("discipline") or "")
        deviation    = not is_completed
    elif completed and not plan:
        is_completed = True
        deviation    = True  # trained on a rest day

    if plan:
        session = {
            "planned_name":   plan.get("session_name"),
            "discipline":     plan.get("discipline"),
            "duration_mins":  plan.get("duration_mins"),
            "hr_target_low":  plan.get("hr_target_low", z2_low),
            "hr_target_high": plan.get("hr_target_high", z2_high),
            "description":    plan.get("description", ""),
            "is_completed":   is_completed,
            "is_rest_day":    False,
            "deviation":      deviation,
            "completed":      completed_block,
        }
    else:
        session = {
            "planned_name":   "Rest Day",
            "discipline":     "rest",
            "duration_mins":  None,
            "hr_target_low":  None,
            "hr_target_high": None,
            "description":    "Recovery. Prioritise sleep and nutrition.",
            "is_completed":   is_completed,
            "is_rest_day":    True,
            "deviation":      deviation,
            "completed":      completed_block,
        }

    readiness = {
        "recommended_action":      decision.get("recommended_action", "Check back after morning briefing."),
        "adjustment_needed":       decision.get("adjustment_needed", False),
        "zone2_target_hr_low":     decision.get("zone2_target_hr_low", z2_low),
        "zone2_target_hr_high":    decision.get("zone2_target_hr_high", z2_high),
        "principle_violations":    decision.get("principle_violations", []),
        "philosophical_reflection": (
            decision.get("water_fear_note")
            or decision.get("philosophical_reflection", "")
        ),
    }

    # Today's workday load from principle_compliance (days=0 → today only)
    today_compliance = db_manager.get_compliance_trend(days=0)
    workday_load = today_compliance[0].get("life_load_score") if today_compliance else None

    return {
        "date":             today_str,
        "garmin":           garmin,
        "nutrition":        nutrition,
        "session":          session,
        "readiness":        readiness,
        "water_fear_level": fear,
        "workday_load":     workday_load,
    }


@app.get("/api/probability")
def probability():
    """Return the latest probability score, component breakdown, and 30-day trend."""
    snap  = db_manager.get_latest_probability()
    trend = db_manager.get_probability_trend(days=30)

    trend_30d = [
        {"date": r["date"], "score": r.get("overall_score")}
        for r in trend
    ]

    if snap is None:
        return {
            "overall_score": None,
            "components": {
                "zone2_compliance": {"score": None, "note": "No data yet"},
                "consistency":      {"score": None, "note": "No data yet"},
                "life_load_buffer": {"score": None, "note": "No data yet"},
                "swim_frequency":   {"score": None, "note": "No data yet"},
            },
            "trend_30d":    trend_30d,
            "last_updated": None,
        }

    return {
        "overall_score": snap.get("overall_score"),
        "components": {
            "zone2_compliance": {
                "score": snap.get("zone2_compliance_score"),
                "note":  snap.get("zone2_compliance_note", ""),
            },
            "consistency": {
                "score": snap.get("consistency_score"),
                "note":  snap.get("consistency_note", ""),
            },
            "life_load_buffer": {
                "score": snap.get("life_load_buffer_score"),
                "note":  snap.get("life_load_buffer_note", ""),
            },
            "swim_frequency": {
                "score": snap.get("swim_frequency_score"),
                "note":  snap.get("swim_frequency_note", ""),
            },
        },
        "trend_30d":    trend_30d,
        "last_updated": snap.get("created_at") or snap.get("date"),
    }


@app.get("/api/week")
def week():
    """Return last 7 days as a flat array: session telemetry, load, fear, calories."""
    today_dt  = date.today()
    start_dt  = today_dt - timedelta(days=6)
    today_str = today_dt.isoformat()
    start_str = start_dt.isoformat()

    hr_max = get_athlete_hr_max()
    z2_low, z2_high = sport_science.zone2_bounds(hr_max)

    logs       = {r["date"]: r for r in db_manager.get_weekly_logs(days=7)}
    compliance = {r["date"]: r for r in db_manager.get_compliance_trend(days=7)}

    fear: dict = {}
    for r in db_manager.get_fear_trend(days=7):
        fear.setdefault(r["date"], r)

    # Completed workout telemetry — direct query (no db_manager helper for range)
    workouts: dict = {}
    if db_manager.supabase:
        try:
            res = (
                db_manager.supabase.table("completed_workouts")
                .select("date, activity_type, activity_name, duration_secs, avg_hr")
                .gte("date", start_str)
                .lte("date", today_str)
                .execute()
            )
            workouts = {r["date"]: r for r in (res.data or [])}
        except Exception:
            pass

    result = []
    for i in range(7):
        d     = start_dt + timedelta(days=i)
        d_str = d.isoformat()

        log     = logs.get(d_str)
        comp    = compliance.get(d_str)
        fear_r  = fear.get(d_str)
        workout = workouts.get(d_str)

        session = None
        if workout:
            avg_hr        = workout.get("avg_hr")
            dur_secs      = workout.get("duration_secs") or 0
            duration_mins = round(dur_secs / 60) if dur_secs else None
            in_zone2      = (z2_low <= avg_hr <= z2_high) if isinstance(avg_hr, (int, float)) else None
            session = {
                "type":          _map_activity_type(workout.get("activity_type", "")),
                "name":          workout.get("activity_name", "Training Session"),
                "duration_mins": duration_mins,
                "avg_hr":        avg_hr,
                "zone2":         in_zone2,
            }

        result.append({
            "date":              d_str,
            "day":               _DAY_NAMES[d.weekday()],
            "session":           session,
            "workday_load":      comp.get("life_load_score") if comp else None,
            "water_fear_level":  fear_r.get("fear_level") if fear_r else None,
            "calories_consumed": log.get("consumed_calories") if log else None,
        })

    return result


@app.get("/api/plan")
def plan():
    """Return next 14 days of planned sessions as a flat array.

    Falls back to the live periodization engine when the DB table is empty.
    """
    today_str = date.today().isoformat()
    end_str   = (date.today() + timedelta(days=13)).isoformat()

    sessions = db_manager.get_planned_sessions(today_str, end_str)

    if not sessions:
        sessions = get_week_sessions(0) + get_week_sessions(1)
        sessions = [s for s in sessions if s["date"] >= today_str]

    result = []
    for s in sessions:
        d   = date.fromisoformat(s["date"])
        row = {
            "date":          s["date"],
            "day":           _DAY_NAMES[d.weekday()],
            "name":          s.get("session_name") or s.get("name", "Training Session"),
            "discipline":    s.get("discipline", "other"),
            "duration_mins": s.get("duration_mins"),
            "phase":         s.get("phase", get_current_phase()),
        }
        if s.get("is_brother_session") or s.get("brother_session"):
            row["brother_session"] = True
        result.append(row)

    return result


@app.get("/api/stats")
def stats():
    """Return baseline fitness stats derived from the athlete profile and SPORT_SCIENCE.md."""
    hr_max = get_athlete_hr_max()
    z2_low, z2_high = sport_science.zone2_bounds(hr_max)

    return {
        "vo2_max":            _VO2_MAX,
        "vo2_max_category":   "Excellent",
        "vo2_max_percentile": "Top 10%",
        "ftp_w_kg":           FTP_W_KG,
        "ftp_category":       "Untrained",
        "swim_pace_100m":     _SWIM_PACE,
        "run_5k_predicted":   _5K_PRED,
        "run_half_predicted": _HALF_PRED,
        "zone2_hr_low":       z2_low,
        "zone2_hr_high":      z2_high,
        "last_updated":       "2026-04-15",
    }


@app.get("/api/checkpoints")
def checkpoints():
    """Return each checkpoint event with days remaining and readiness score."""
    prob = db_manager.get_latest_probability()
    overall     = _safe_get(prob, "overall_score")           if prob else None
    swim_score  = _safe_get(prob, "swim_frequency_score")    if prob else None

    # Aquaman is swim-only: use swim_frequency component when available
    aquaman_readiness = swim_score if swim_score is not None else overall

    return [
        {
            "name":            "Aquaman Langkawi",
            "date":            AQUAMAN.isoformat(),
            "type":            "swim_2km",
            "purpose":         "Open water fear confrontation",
            "days_until":      _days_until(AQUAMAN),
            "readiness_score": aquaman_readiness,
            "critical_metric": "swim_frequency",
        },
        {
            "name":            "Bintan Triathlon",
            "date":            BINTAN.isoformat(),
            "type":            "triathlon",
            "purpose":         "Full triathlon dress rehearsal",
            "days_until":      _days_until(BINTAN),
            "readiness_score": overall,
            "critical_metric": "ftp",
        },
        {
            "name":            "Half Ironman",
            "date":            IRONMAN.isoformat(),
            "type":            "ironman_70.3",
            "purpose":         "The endpoint",
            "days_until":      _days_until(IRONMAN),
            "readiness_score": overall,
            "critical_metric": "all",
        },
    ]


# ── Vercel ASGI entry point ───────────────────────────────────────────────────
# Vercel's Python runtime looks for a top-level `handler` callable.
# Mangum wraps the FastAPI ASGI app so Vercel can invoke it as a serverless fn.
handler = Mangum(app, lifespan="off")
