"""
sport_science.py — Sport science calculations.

All formulas from docs/SPORT_SCIENCE.md. These functions are the transparent
calculation layer that the AI uses as ground truth.

No side effects. No I/O. No database calls. Pure functions only.

Sources:
  - HR zones:        Joe Friel / Garmin HRmax model
  - Running paces:   Jack Daniels' Running Formula (3rd ed.), VDOT tables
  - Swim CSS:        Swim Smooth CSS method (Paul Newsome)
  - TSS:             Coggan/Allen, Training Peaks methodology
  - Periodization:   80/20 Triathlon (Matt Fitzgerald) + Luuc Muis HIM model
  - Life load:       docs/SPORT_SCIENCE.md, TSS adjustment rules
"""

from __future__ import annotations

import math
from typing import Optional


# ── Heart-rate zone bounds ────────────────────────────────────────────────────

def zone2_bounds(hr_max: int) -> tuple[int, int]:
    """Return Zone 2 (aerobic) HR bounds in bpm for a given HRmax.

    Source: Joe Friel / Garmin zone model.
      Zone 2 = 60–76 % of HRmax
      Athlete reference: HRmax 191 → Zone 2: 115–145 bpm

    Args:
        hr_max: Athlete's maximum heart rate in bpm.

    Returns:
        (low, high) — inclusive Zone 2 bounds in bpm.
    """
    low  = math.ceil(hr_max * 0.60)
    high = math.floor(hr_max * 0.76)
    return low, high


def all_zone_bounds(hr_max: int) -> dict[int, tuple[int, int]]:
    """Return all 5 HR zones for a given HRmax.

    Source: Joe Friel / Garmin zone model.

    Returns:
        {zone_number: (low_bpm, high_bpm)}
        Zone 5 upper bound is set to hr_max.
    """
    return {
        1: (0,                      math.ceil(hr_max * 0.60) - 1),
        2: (math.ceil(hr_max * 0.60),  math.floor(hr_max * 0.76)),
        3: (math.ceil(hr_max * 0.76),  math.floor(hr_max * 0.84)),
        4: (math.ceil(hr_max * 0.84),  math.floor(hr_max * 0.92)),
        5: (math.ceil(hr_max * 0.92),  hr_max),
    }


def zone_for_hr(bpm: int, hr_max: int) -> int:
    """Return the zone number (1–5) for a given heart rate and HRmax."""
    zones = all_zone_bounds(hr_max)
    for zone, (low, high) in zones.items():
        if low <= bpm <= high:
            return zone
    return 5 if bpm > hr_max * 0.92 else 1


# ── Running — Jack Daniels VDOT ───────────────────────────────────────────────

def vdot_from_time(distance_m: int, time_secs: int) -> float:
    """Estimate VDOT from a race result using the Daniels/Gilbert formula.

    Source: Jack Daniels' Running Formula (3rd ed.)
    Formula: iterative approximation — percent VO2max at race velocity → VDOT.

    Uses the velocity-to-%VO2max regression:
      %VO2max = 0.8 + 0.1894393·e^(-0.012778·t) + 0.2989558·e^(-0.1932605·t)
    where t = duration in minutes.

    VO2 at race pace:
      VO2 = −4.60 + 0.182258·v + 0.000104·v²
    where v = race velocity in m/min.

    Returns:
        VDOT (float) — higher is fitter; typical age-grouper range 30–55.
    """
    if distance_m <= 0 or time_secs <= 0:
        raise ValueError("distance_m and time_secs must be positive.")

    t_min = time_secs / 60.0
    v_m_per_min = distance_m / t_min

    # Percent VO2max at race duration
    pct_vo2max = (
        0.8
        + 0.1894393 * math.exp(-0.012778 * t_min)
        + 0.2989558 * math.exp(-0.1932605 * t_min)
    )

    # VO2 (ml/kg/min) at race pace
    vo2 = -4.60 + 0.182258 * v_m_per_min + 0.000104 * v_m_per_min ** 2

    if pct_vo2max <= 0:
        raise ValueError("Calculated %VO2max is non-positive — race time likely invalid.")

    return round(vo2 / pct_vo2max, 1)


def easy_pace_from_vdot(vdot: float) -> tuple[int, int]:
    """Return easy/Zone-2 run pace range in seconds-per-km for a given VDOT.

    Source: Jack Daniels' Running Formula VDOT tables.
    Approximation: Easy pace = 59–65 % of vVO2max.

    The velocity at VO2max (vVO2max) in m/min is estimated from:
      VO2max ≈ VDOT  →  v_o2max = (VDOT + 4.60) / (0.182258 + 0.000104·v)
    Solved iteratively via the quadratic form:
      0.000104·v² + 0.182258·v − (VDOT + 4.60) = 0

    Easy pace band = velocities at 59 % and 65 % of vVO2max, converted to
    seconds per km (slower pace = lower velocity = more seconds → swap order
    so the tuple reads (fast_end_secs, slow_end_secs)).

    Returns:
        (min_secs_per_km, max_secs_per_km) — fast end first.
        Example for VDOT 44: roughly (379, 420) → ~6:19–7:00 /km
    """
    if vdot <= 0:
        raise ValueError("VDOT must be positive.")

    # Solve 0.000104·v² + 0.182258·v − (vdot + 4.60) = 0  for v (m/min)
    a = 0.000104
    b = 0.182258
    c = -(vdot + 4.60)
    discriminant = b ** 2 - 4 * a * c
    v_o2max = (-b + math.sqrt(discriminant)) / (2 * a)  # m/min at VO2max

    v_fast = v_o2max * 0.65   # 65 % of vVO2max → fast end of easy band
    v_slow = v_o2max * 0.59   # 59 % of vVO2max → slow end of easy band

    # Convert m/min → secs/km  (1 km = 1000 m, 1 min = 60 s)
    # secs_per_km = (1000 m/km) / (v m/min) × (60 s/min)
    secs_fast = round(1000.0 / v_fast * 60)
    secs_slow = round(1000.0 / v_slow * 60)

    return secs_fast, secs_slow


def format_pace(secs_per_km: int) -> str:
    """Format seconds-per-km as 'M:SS' string."""
    return f"{secs_per_km // 60}:{secs_per_km % 60:02d}"


# ── Swim — Critical Swim Speed (CSS) ─────────────────────────────────────────

def css_from_times(t400m_secs: int, t200m_secs: int) -> float:
    """Calculate Critical Swim Speed (CSS) in seconds per 100 m.

    Source: Swim Smooth CSS method (Paul Newsome).
    Formula: CSS = (400 − 200) / (t400 − t200) × 100
             in sec/100m

    CSS represents the fastest pace sustainable for ~30 min without fatigue
    accumulation — the swim equivalent of FTP.

    Args:
        t400m_secs: Time to swim 400 m in seconds (time trial effort).
        t200m_secs: Time to swim 200 m in seconds (time trial effort).

    Returns:
        CSS in seconds per 100 m.

    Raises:
        ValueError: If t400m_secs <= t200m_secs (physically impossible result).
    """
    if t400m_secs <= t200m_secs:
        raise ValueError(
            "t400m_secs must be greater than t200m_secs — "
            "check that you have not swapped the arguments."
        )
    delta_dist = 400 - 200           # metres
    delta_time = t400m_secs - t200m_secs  # seconds

    secs_per_100m = (delta_time / delta_dist) * 100
    return round(secs_per_100m, 1)


def swim_easy_bounds(css_secs_100m: float) -> tuple[float, float]:
    """Return Zone-2 swim pace bounds in seconds per 100 m.

    Source: Swim Smooth model.
    Easy / Zone-2 swim pace = CSS + 10 s/100m  to  CSS + 25 s/100m

    Returns:
        (fast_end, slow_end) in secs per 100m.
    """
    return round(css_secs_100m + 10, 1), round(css_secs_100m + 25, 1)


# ── Training Stress Score (TSS) ───────────────────────────────────────────────

def calculate_tss(duration_hrs: float, if_: float) -> float:
    """Calculate Training Stress Score (TSS) for a session.

    Source: Coggan/Allen, Training Peaks methodology.
    Formula: TSS = (duration_hrs × IF²) × 100

    This is the standard simplified form where IF = NP/FTP.
    For power-meter sessions this is precise; for HR- or pace-based
    sessions it is approximate (use if_ derived from zone or pace factor).

    Common IF reference values:
      Zone 1 recovery:  0.55
      Zone 2 aerobic:   0.65–0.75
      Zone 3 tempo:     0.80–0.85
      Zone 4 threshold: 0.95–1.05
      Zone 5 VO2:       1.05–1.20

    Args:
        duration_hrs: Session duration in hours.
        if_:          Intensity Factor (unitless, typically 0.5–1.2).

    Returns:
        TSS as a float. Typical session range: 30–150.
    """
    if duration_hrs < 0:
        raise ValueError("duration_hrs cannot be negative.")
    if if_ < 0:
        raise ValueError("Intensity Factor cannot be negative.")

    return round(duration_hrs * (if_ ** 2) * 100, 1)


def rtss_from_pace(duration_hrs: float, pace_secs_per_km: int, vdot: float) -> float:
    """Estimate running TSS (rTSS) from pace and duration.

    Source: Jack Daniels-derived pace factor.
    IF for running ≈ (threshold_velocity) / (race_velocity)
    Approximated as: IF ≈ 1.0 when running at threshold pace.

    Easy pace for VDOT 44 is ~379–420 s/km → IF ≈ 0.70–0.75.
    This function computes IF from the ratio of the runner's easy pace to
    their threshold pace (Daniels threshold ≈ 5:05/km for VDOT 44).

    Args:
        duration_hrs:     Session duration in hours.
        pace_secs_per_km: Actual run pace in secs/km.
        vdot:             Athlete VDOT.

    Returns:
        rTSS (float).
    """
    # Threshold pace from VDOT: approx threshold velocity = 92.5 % of vVO2max
    a = 0.000104
    b = 0.182258
    c = -(vdot + 4.60)
    discriminant = b ** 2 - 4 * a * c
    v_o2max = (-b + math.sqrt(discriminant)) / (2 * a)
    v_threshold = v_o2max * 0.925          # m/min
    t_threshold_secs_km = 1000 / v_threshold * 60  # secs/km

    # Intensity factor = threshold_pace / actual_pace (pace is inverse of velocity)
    if_ = t_threshold_secs_km / pace_secs_per_km
    return calculate_tss(duration_hrs, if_)


def stss_from_swim(distance_km: float, css_secs_100m: float, actual_pace_secs_100m: float) -> float:
    """Estimate swim TSS (sTSS) from distance and pace vs CSS.

    Source: Coggan/Allen swim TSS approximation.
    IF for swim = CSS_pace / actual_pace (both in secs/100m, lower = faster).

    Args:
        distance_km:            Total swim distance in km.
        css_secs_100m:          Athlete's CSS in secs per 100 m.
        actual_pace_secs_100m:  Average swim pace achieved in secs per 100 m.

    Returns:
        sTSS (float).
    """
    if actual_pace_secs_100m <= 0 or css_secs_100m <= 0:
        raise ValueError("Pace values must be positive.")

    # Duration from distance and pace
    secs_per_km = actual_pace_secs_100m * 10
    duration_hrs = distance_km * secs_per_km / 3600

    # IF: CSS pace vs actual pace (pace in secs → lower = faster → IF > 1 when faster than CSS)
    if_ = css_secs_100m / actual_pace_secs_100m
    return calculate_tss(duration_hrs, if_)


# ── Probability / completion-likelihood score ─────────────────────────────────

def calculate_probability(logs: list[dict]) -> dict:
    """Estimate race-completion probability score from recent training logs.

    Source: Custom model derived from SPORT_SCIENCE.md principles.

    Scoring model (0–100):
      - Compliance rate (sessions completed / scheduled, last 14d): 40 pts
      - Zone 2 ratio (Zone 2 sessions / total sessions):            25 pts
      - Weekly TSS trend (positive gradient = bonus):               20 pts
      - Fear trend (decreasing water fear = bonus):                 15 pts

    Each log dict must contain at a minimum:
      {
        "date":         str (ISO 8601),
        "scheduled":    bool,    # was a session planned?
        "completed":    bool,    # did the athlete do it?
        "in_zone2":     bool,    # was HR within Zone 2 for >70% of session?
        "tss":          float,   # session TSS (0 if rest/missed),
        "fear_level":   int | None,  # 1–10 water fear log (or None)
      }

    Args:
        logs: List of daily log dicts, most-recent last (ascending date).
              Expects up to 14 entries; silently uses the last 14.

    Returns:
        dict with keys:
          "score"         — overall 0–100 int
          "compliance"    — 0.0–1.0 fraction of scheduled sessions completed
          "zone2_ratio"   — 0.0–1.0 fraction of completed sessions in Zone 2
          "tss_trend"     — "up" | "flat" | "down"
          "fear_trend"    — "improving" | "stable" | "worsening" | "no_data"
          "breakdown"     — dict of component scores
    """
    recent = logs[-14:] if len(logs) > 14 else logs

    # ── Compliance (40 pts) ───────────────────────────────────────────────────
    scheduled = [l for l in recent if l.get("scheduled", False)]
    completed  = [l for l in scheduled if l.get("completed", False)]
    compliance = (len(completed) / len(scheduled)) if scheduled else 0.0
    compliance_score = round(compliance * 40)

    # ── Zone 2 ratio (25 pts) ─────────────────────────────────────────────────
    done_sessions = [l for l in recent if l.get("completed", False)]
    zone2_sessions = [l for l in done_sessions if l.get("in_zone2", False)]
    zone2_ratio = (len(zone2_sessions) / len(done_sessions)) if done_sessions else 0.0
    zone2_score = round(zone2_ratio * 25)

    # ── Weekly TSS trend (20 pts) ─────────────────────────────────────────────
    tss_values = [l.get("tss", 0.0) for l in recent if l.get("completed", False)]
    tss_trend = "flat"
    tss_score = 10  # neutral base

    if len(tss_values) >= 4:
        mid = len(tss_values) // 2
        avg_early = sum(tss_values[:mid]) / mid
        avg_late  = sum(tss_values[mid:]) / (len(tss_values) - mid)
        if avg_late > avg_early * 1.05:
            tss_trend = "up"
            tss_score = 20
        elif avg_late < avg_early * 0.90:
            tss_trend = "down"
            tss_score = 0
        else:
            tss_trend = "flat"
            tss_score = 10

    # ── Fear trend (15 pts) ───────────────────────────────────────────────────
    fear_logs = [l["fear_level"] for l in recent if l.get("fear_level") is not None]
    fear_trend = "no_data"
    fear_score = 7  # neutral when no data

    if len(fear_logs) >= 3:
        avg_early_fear = sum(fear_logs[: len(fear_logs) // 2]) / (len(fear_logs) // 2)
        avg_late_fear  = sum(fear_logs[len(fear_logs) // 2 :]) / math.ceil(len(fear_logs) / 2)

        if avg_late_fear < avg_early_fear - 0.5:
            fear_trend = "improving"
            fear_score = 15
        elif avg_late_fear > avg_early_fear + 0.5:
            fear_trend = "worsening"
            fear_score = 0
        else:
            fear_trend = "stable"
            fear_score = 7

    total_score = min(100, compliance_score + zone2_score + tss_score + fear_score)

    return {
        "score":        total_score,
        "compliance":   round(compliance, 3),
        "zone2_ratio":  round(zone2_ratio, 3),
        "tss_trend":    tss_trend,
        "fear_trend":   fear_trend,
        "breakdown": {
            "compliance_score": compliance_score,
            "zone2_score":      zone2_score,
            "tss_score":        tss_score,
            "fear_score":       fear_score,
        },
    }


# ── Life load adjustment ──────────────────────────────────────────────────────

def life_load_adjustment(avg_load: float) -> float:
    """Return a TSS target multiplier based on average recent workday load.

    Source: docs/SPORT_SCIENCE.md — TSS adjustment rules.

    Rules:
      avg_load <= 7.0  → no adjustment  (multiplier = 1.00)
      7.0 < avg_load <= 8.0 → reduce by 20 % (multiplier = 0.80)
      avg_load > 8.0   → reduce by 35 % (multiplier = 0.65)

    Note: workday_load = 10 triggers an automatic full-rest override at
    the training_advisor layer; this function only returns TSS multipliers.

    Args:
        avg_load: Average workday load score (1–10) over recent days.

    Returns:
        Multiplier (float) to apply to weekly TSS target.
    """
    if avg_load < 0 or avg_load > 10:
        raise ValueError("avg_load must be between 0 and 10.")

    if avg_load <= 7.0:
        return 1.00
    elif avg_load <= 8.0:
        return 0.80
    else:
        return 0.65


# ── Cycling power zones ───────────────────────────────────────────────────────

def ftp_watts(ftp_w_kg: float, weight_kg: float) -> float:
    """Return absolute FTP in watts from W/kg and body weight."""
    return round(ftp_w_kg * weight_kg, 1)


def bike_zone2_power_bounds(ftp_w: float) -> tuple[float, float]:
    """Return Coggan Zone 2 power bounds in watts.

    Source: Coggan/Allen power zone model.
    Zone 2 (Endurance) = 56–75 % of FTP.

    Returns:
        (low_watts, high_watts)
    """
    return round(ftp_w * 0.56, 1), round(ftp_w * 0.75, 1)


# ── Pace / distance helpers ───────────────────────────────────────────────────

def pace_100m_from_time(distance_m: float, duration_secs: float) -> Optional[str]:
    """Return swim pace per 100 m as 'M:SS' string.

    Args:
        distance_m:    Total distance swum in metres.
        duration_secs: Total duration in seconds.

    Returns:
        Pace string e.g. '2:05', or None if inputs are missing/invalid.
    """
    if not distance_m or not duration_secs or distance_m <= 0 or duration_secs <= 0:
        return None
    secs_per_100m = (duration_secs / distance_m) * 100
    mins = int(secs_per_100m // 60)
    secs = int(secs_per_100m % 60)
    return f"{mins}:{secs:02d}"


def run_pace_from_time(distance_m: float, duration_secs: float) -> Optional[str]:
    """Return run pace per km as 'M:SS' string."""
    if not distance_m or not duration_secs or distance_m <= 0 or duration_secs <= 0:
        return None
    secs_per_km = (duration_secs / distance_m) * 1000
    mins = int(secs_per_km // 60)
    secs = int(secs_per_km % 60)
    return f"{mins}:{secs:02d}"
