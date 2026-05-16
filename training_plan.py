"""
training_plan.py — Triathlon periodization engine.

Generates the full 26-week training plan from today to the Half Ironman,
phase-aware and principle-compliant.

Key functions:
- generate_full_plan() → list of session dicts
- get_athlete_context() → current snapshot for AI prompts
- get_current_phase() → str
- get_week_sessions(week_offset=0) → list of sessions for that week
"""

from datetime import date, timedelta
from typing import Any, Optional

from garmin_scheduler import (
    SPORT_SWIMMING, SPORT_RUNNING, SPORT_CYCLING, SPORT_MULTISPORT,
    _SCHEDULE_BY_PHASE,
    get_phase,
)
from sport_science import zone2_bounds

# ── Checkpoint dates ─────────────────────────────────────────────────────────

SCORE_MARATHON = date(2026, 7, 19)
MELAKA         = date(2026, 8, 30)
BINTAN         = date(2026, 10, 12)
IRONMAN        = date(2026, 11, 21)

# ── Athlete baselines (SPORT_SCIENCE.md) ─────────────────────────────────────

# HR_MAX is no longer a plain constant — use get_athlete_hr_max() instead.
# The value below is the last confirmed fallback; keep it updated after
# field tests so the hardcoded path stays reasonable.
_HR_MAX_FALLBACK = 196   # observed during run, May 2026

VDOT          = 44     # derived from 5k predictor (22:20)
FTP_W_KG      = 2.22   # current untrained FTP
WEIGHT_KG     = 74.0
CSS_SECS_100M = 130    # ~2:10/100m (estimated; confirm via time trial)


def get_athlete_hr_max(client=None) -> int:
    """Return the athlete's current HRmax via the 3-tier fallback chain.

    Calls garmin_metrics.get_hr_max() which resolves:
      1. Garmin API (live, updates DB cache on new high)
      2. DB cache  (last known value from metric_logs)
      3. Hardcoded _HR_MAX_FALLBACK constant

    Args:
        client: Optional authenticated Garmin client. When None the API
                step is skipped and the DB/hardcoded fallback is used.

    Returns:
        HRmax as int.
    """
    try:
        from garmin_metrics import get_hr_max
        return get_hr_max(client)
    except Exception:
        # garmin_metrics or db_manager unavailable (e.g. unit tests)
        return _HR_MAX_FALLBACK


# ── Discipline mapping ───────────────────────────────────────────────────────

_SPORT_KEY_TO_DISCIPLINE: dict[str, str] = {
    "swimming":    "swim",
    "running":     "run",
    "cycling":     "bike",
    "multi_sport": "brick",
    "other":       "brick",
}


# ── Periodization helpers ────────────────────────────────────────────────────

def get_current_phase() -> str:
    """Return the current training phase string."""
    return get_phase(date.today())


def _week_number(target_date: date, plan_start: date) -> int:
    """Return 1-based week number of *target_date* relative to *plan_start*."""
    return ((target_date - plan_start).days // 7) + 1


def _periodization_multiplier(week_num: int) -> float:
    """Return volume multiplier for *week_num* using the 3+1 build/recovery cycle.

    Weeks 1-3 of each cycle progressively load; week 4 is recovery (65%).
    Source: SPORT_SCIENCE.md periodization model.
    """
    return [1.0, 1.1, 1.15, 0.65][(week_num - 1) % 4]


def _is_recovery_week(week_num: int) -> bool:
    return (week_num % 4) == 0


def _distance_target(discipline: str, duration_mins: int) -> Optional[float]:
    """Estimate Zone 2 distance target in km for the given discipline and duration."""
    if discipline == "run":
        # Zone 2 easy pace ≈ 6:40/km → km = duration / 6.67
        return round(duration_mins / 6.67, 1)
    if discipline == "swim":
        # Effective pool pace (including drills/rest) ≈ 40 min/km
        return round(duration_mins / 40, 1)
    return None  # bike and brick: HR-based, no distance target


# ── Session conversion ───────────────────────────────────────────────────────

def _to_plan_row(
    session: dict,
    target_date: date,
    week_num: int,
    phase: str,
    multiplier: float,
) -> dict[str, Any]:
    """Convert a garmin_scheduler session dict to an ironman_training_plan row."""
    sport_key  = session.get("sport_type", {}).get("sportTypeKey", "other")
    discipline = _SPORT_KEY_TO_DISCIPLINE.get(sport_key, "other")

    duration = max(20, round(session.get("duration_minutes", 45) * multiplier))
    hr_target = session.get("hr_target")
    hr_low, hr_high = hr_target if hr_target else zone2_bounds(get_athlete_hr_max())

    return {
        "week_number":        week_num,
        "phase":              phase,
        "date":               target_date.isoformat(),
        "day_of_week":        target_date.weekday(),
        "discipline":         discipline,
        "session_name":       session.get("name", "Training Session"),
        "duration_mins":      duration,
        "hr_target_low":      hr_low,
        "hr_target_high":     hr_high,
        "distance_target":    _distance_target(discipline, duration),
        "description":        session.get("description", ""),
        "notes":              "Recovery week — reduced volume." if _is_recovery_week(week_num) else None,
        "is_brother_session": session.get("brother_session", False),
        "garmin_scheduled":   False,
    }


# ── Public API ───────────────────────────────────────────────────────────────

def generate_full_plan(start_date: Optional[date] = None) -> list[dict]:
    """Generate the full periodized plan from *start_date* to the Half Ironman.

    Aligns to the Monday of the current week when *start_date* is omitted.
    Returns a list of row dicts suitable for db_manager.upsert_training_plan().
    Rest days produce no row.
    """
    if start_date is None:
        today = date.today()
        start_date = today - timedelta(days=today.weekday())

    rows: list[dict] = []
    current = start_date

    while current <= IRONMAN:
        phase   = get_phase(current)
        session = _SCHEDULE_BY_PHASE[phase].get(current.weekday())

        if session is not None:
            week_num   = _week_number(current, start_date)
            multiplier = _periodization_multiplier(week_num)
            rows.append(_to_plan_row(session, current, week_num, phase, multiplier))

        current += timedelta(days=1)

    return rows


def get_week_sessions(week_offset: int = 0) -> list[dict]:
    """Return sessions for the week at *week_offset* from the current week.

    week_offset=0 → current week, 1 → next week, -1 → last week.

    Reads from the database first. Falls back to generating live from the
    scheduler when the DB has no rows for that week (e.g. before plan is seeded).
    """
    from db_manager import get_week_plan as _db_week

    db_rows = _db_week(week_offset)
    if db_rows:
        return db_rows

    # DB not seeded yet — generate on the fly with periodization applied
    today      = date.today()
    plan_start = today - timedelta(days=today.weekday())   # this week's Monday
    week_start = plan_start + timedelta(weeks=week_offset)

    sessions: list[dict] = []
    for offset in range(7):
        d = week_start + timedelta(days=offset)
        if d > IRONMAN:
            break
        phase   = get_phase(d)
        session = _SCHEDULE_BY_PHASE[phase].get(d.weekday())
        if session is not None:
            week_num   = _week_number(d, plan_start)
            multiplier = _periodization_multiplier(week_num)
            sessions.append(_to_plan_row(session, d, week_num, phase, multiplier))

    return sessions


def get_athlete_context() -> dict[str, Any]:
    """Return the current athlete snapshot for use in AI prompts.

    Combines live signals from the database with hardcoded baselines from
    SPORT_SCIENCE.md so callers have a single consistent source of truth.
    """
    from db_manager import (
        get_latest_fear_level,
        get_latest_probability,
        get_todays_plan,
        get_compliance_trend,
    )

    today = date.today()
    phase = get_current_phase()
    hr_max = get_athlete_hr_max()
    zone2_low, zone2_high = zone2_bounds(hr_max)

    return {
        # Timeline
        "current_phase":        phase,
        "days_to_score_marathon": (SCORE_MARATHON - today).days,
        "days_to_melaka":         (MELAKA        - today).days,
        "days_to_bintan":         (BINTAN        - today).days,
        "days_to_ironman":        (IRONMAN       - today).days,
        # Today
        "todays_session":       get_todays_plan(),
        # Fitness baselines (SPORT_SCIENCE.md)
        "hr_max":               hr_max,
        "zone2_low":            zone2_low,
        "zone2_high":           zone2_high,
        "vdot":                 VDOT,
        "ftp_w_kg":             FTP_W_KG,
        "weight_kg":            WEIGHT_KG,
        "css_secs_per_100m":    CSS_SECS_100M,
        # Live signals
        "latest_fear_level":    get_latest_fear_level(),
        "latest_probability":   get_latest_probability(),
        "compliance_trend_14d": get_compliance_trend(days=14),
    }
