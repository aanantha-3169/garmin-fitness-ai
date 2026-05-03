# BUILD_PLAN.md — Phase-by-Phase Task List

> This is the active work queue for Claude Code.
> Complete phases in order. Do not start Phase 2 until Phase 1 is done.
> Mark tasks [x] as completed.

---

## Phase 1 — Replace the Brain (Priority: Critical)

These fixes make the system actually know what it's doing.

### Task 1.1 — Inject principles into training_advisor.py
**File:** `training_advisor.py`
**Change:** Add principles context injection to `_build_user_prompt()`

```python
# Before building the prompt, load principles:
principles = Path("docs/PRINCIPLES.md").read_text()
sport_science = Path("docs/SPORT_SCIENCE.md").read_text()

# Prepend to system prompt:
_SYSTEM_PROMPT = f"""
{principles}

{sport_science}

{existing_system_prompt}
"""
```

**Also update the TrainingDecision schema:**
```python
class TrainingDecision(BaseModel):
    adjustment_needed: bool
    recommended_action: str
    target_calories: int
    zone2_target_hr_low: int = 115      # NEW
    zone2_target_hr_high: int = 145     # NEW
    principle_violations: list[str] = [] # NEW — flag if recommendation breaks a principle
    water_fear_note: Optional[str] = None # NEW — if swim session, note fear context
    philosophical_reflection: Optional[str] = None
```

**Acceptance criteria:** Running analyze_readiness() with sleep_score=40 and
workday_load=9 must recommend rest, not reduced training. Check the principle_violations field.

---

### Task 1.2 — Add FEAR and TRAINING_LOG intents to intent_router.py
**File:** `intent_router.py`
**Change:** Add two new intents to the classifier

```
FEAR — water/race fear expression
  e.g. "felt okay in the pool today", "panicked at the wall",
       "water fear was 3/10 this morning", "still scared of open water"

TRAINING_LOG — athlete reporting a completed session
  e.g. "did 750m in 16 minutes", "45 min bike avg HR 138",
       "ran 8km at 6:30 pace"
```

Update `_SYSTEM_PROMPT` to include these intents with examples.
Update `_FALLBACK` to still return MEAL (safe default).

---

### Task 1.3 — Rewrite training schedule in garmin_scheduler.py
**File:** `garmin_scheduler.py`
**Change:** Replace `_WEEKLY_SCHEDULE` entirely

The new schedule is triathlon periodization, not PT sessions.
It must be phase-aware (based on weeks until each checkpoint).

```python
def get_phase(today: date) -> str:
    """Return current training phase based on checkpoint dates."""
    aquaman = date(2026, 7, 25)
    bintan = date(2026, 10, 12)
    ironman = date(2026, 11, 21)
    
    days_to_aquaman = (aquaman - today).days
    days_to_bintan = (bintan - today).days
    days_to_ironman = (ironman - today).days
    
    if days_to_ironman <= 14:
        return "taper_ironman"
    elif days_to_bintan <= 14:
        return "taper_bintan"
    elif days_to_aquaman <= 21:
        return "pre_aquaman"
    elif days_to_aquaman > 60:
        return "base"
    else:
        return "build"

# New weekly schedule (base phase example):
_BASE_SCHEDULE = {
    0: {"name": "Zone 2 Swim", "sport_type": SPORT_SWIMMING, 
        "description": "Pool swim. Zone 2 HR 115-145. Focus: catch-up drill + continuous laps.",
        "duration_minutes": 45, "hr_target": (115, 145)},
    1: {"name": "Zone 2 Run", "sport_type": SPORT_RUNNING,
        "description": "Easy aerobic run. 6:20-7:00/km. Do not exceed 145 bpm.",
        "duration_minutes": 45, "hr_target": (115, 145)},
    2: {"name": "Zone 2 Bike", "sport_type": SPORT_CYCLING,
        "description": "Outdoor or indoor bike. Strict Zone 2. 115-145 bpm.",
        "duration_minutes": 75, "hr_target": (115, 145)},
    3: {"name": "Zone 2 Swim", "sport_type": SPORT_SWIMMING,
        "description": "Pool swim. Technique focus. Continuous 400m blocks.",
        "duration_minutes": 45, "hr_target": (115, 145)},
    4: None,  # Rest / mobility
    5: {"name": "Zone 2 Bike (Brother Session)", "sport_type": SPORT_CYCLING,
        "description": "Outdoor ride with brother if available. Zone 2 always.",
        "duration_minutes": 90, "hr_target": (115, 145), "brother_session": True},
    6: {"name": "Long Zone 2 Brick", "sport_type": SPORT_OTHER,
        "description": "Bike 60-75 min then run 15-20 min. Both in Zone 2.",
        "duration_minutes": 90, "hr_target": (115, 145)},
}
```

Add SPORT_SWIMMING and SPORT_CYCLING constants.

---

### Task 1.4 — Add /fear command to Telegram bot
**Files:** `meal_tracker_bot.py`, `main.py`, `db_manager.py`

1. Add `log_water_fear()` to db_manager.py (see SCHEMA.md)
2. Add handler in meal_tracker_bot.py:

```python
async def _cmd_fear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /fear [1-10] — log today's water fear level."""
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
    
    # Contextual response based on level
    if level <= 3:
        note = "Building that calm baseline 🌊"
    elif level <= 6:
        note = "Normal. Keep showing up. The water gets quieter."
    else:
        note = "Noted. Rest is okay. Fear is information, not failure."
    
    await update.message.reply_text(
        f"💧 Fear level {level}/10 logged.\n{note}"
    )
```

3. Register `CommandHandler("fear", _cmd_fear)` in main.py

---

### Task 1.5 — Add /load command for workday stress
**Files:** `meal_tracker_bot.py`, `main.py`, `db_manager.py`

Similar to /fear but for workday load. Writes to `principle_compliance` table.

```python
async def _cmd_load(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /load [1-10] — log today's workday stress level."""
```

---

## Phase 2 — Data Layer Extension

### Task 2.1 — Add swim telemetry to garmin_telemetry.py

Add `_extract_swim_telemetry()` function:

```python
def _extract_swim_telemetry(activity: dict) -> dict:
    """Extract swim-specific fields from a Garmin swim activity."""
    base = _extract_telemetry(activity)
    
    # Swim-specific fields
    base.update({
        "swim_stroke_type": activity.get("strokeType", {}).get("strokeTypeKey"),
        "avg_strokes_per_length": activity.get("avgStrokes"),
        "pool_length_meters": activity.get("poolLength"),
        "num_lengths": activity.get("numActiveLengths"),
        "total_distance_meters": activity.get("distance"),
        "avg_pace_per_100m": _calculate_pace_100m(
            activity.get("distance"), activity.get("duration")
        ),
        "best_pace_per_100m": activity.get("minPace100m"),
    })
    return base

def _calculate_pace_100m(distance_m: float, duration_secs: float) -> Optional[str]:
    """Return pace per 100m as MM:SS string."""
    if not distance_m or not duration_secs:
        return None
    secs_per_100m = (duration_secs / distance_m) * 100
    mins = int(secs_per_100m // 60)
    secs = int(secs_per_100m % 60)
    return f"{mins}:{secs:02d}"
```

Update `sync_todays_workout()` to call `_extract_swim_telemetry()` when
`activity_type` contains "swimming".

### Task 2.2 — Add new db_manager.py functions
See SCHEMA.md for the full list. Add all functions for:
- `water_fear_logs`
- `ironman_training_plan`
- `principle_compliance`
- `probability_snapshots`
- `get_dashboard_data()` aggregate function

### Task 2.3 — Create training_plan.py
**New file.** The triathlon periodization engine.

```python
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
```

### Task 2.4 — Create sport_science.py
**New file.** Pure calculation functions, no side effects.

```python
"""
sport_science.py — Sport science calculations.

All formulas from SPORT_SCIENCE.md. These functions are the transparent
calculation layer that the AI uses as ground truth.
"""

def zone2_bounds(hr_max: int) -> tuple[int, int]: ...
def vdot_from_time(distance_m: int, time_secs: int) -> float: ...
def easy_pace_from_vdot(vdot: float) -> tuple[int, int]: ...  # returns (min_secs, max_secs) per km
def css_from_times(t400m_secs: int, t200m_secs: int) -> float: ...  # returns secs per 100m
def calculate_tss(duration_hrs: float, if_: float) -> float: ...
def calculate_probability(logs: list[dict]) -> dict: ...
def life_load_adjustment(avg_load: float) -> float: ...  # returns TSS multiplier
```

### Task 2.5 — Create Supabase tables
Run SQL in Supabase dashboard to create:
- `water_fear_logs`
- `ironman_training_plan`
- `principle_compliance`
- `probability_snapshots`

SQL is in SCHEMA.md.

---

## Phase 3 — FastAPI + Dashboard

### Task 3.1 — Create api/main.py
```python
"""FastAPI app deployed to Vercel. Reads from Supabase."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Ironman Pipeline API")

# All endpoints read-only. No auth (single-user, no sensitive data).
```

Implement all endpoints from SCHEMA.md.

### Task 3.2 — Create vercel.json for API
```json
{
  "builds": [{"src": "api/main.py", "use": "@vercel/python"}],
  "routes": [{"src": "/api/(.*)", "dest": "api/main.py"}]
}
```

### Task 3.3 — Build React dashboard
**Directory:** `frontend/`
**Based on:** The existing Claude artifact dashboard (dark terminal aesthetic)
**Data source:** FastAPI endpoints

Components needed:
- `Dashboard.jsx` — main layout
- `CountdownBar.jsx` — days until each checkpoint
- `ProbabilityPanel.jsx` — score + breakdown bars
- `TodayPanel.jsx` — today's readiness, session, calories
- `SessionHistory.jsx` — last 7 days log
- `TrainingPlan.jsx` — next 14 days from ironman_training_plan
- `PrinciplesPanel.jsx` — static principles display

### Task 3.4 — Add PWA support
- `frontend/public/manifest.json` — app name, icons, display: standalone
- `frontend/public/sw.js` — basic service worker for offline capability
- Add `<link rel="manifest">` to index.html

### Task 3.5 — Create Scriptable widget script
**File:** `scriptable/ironman_widget.js`
Small JavaScript for the Scriptable iOS app that calls `/api/today`
and renders a native-looking home screen widget showing:
- Probability score (big number)
- Today's session
- Body battery
- Days to Aquaman

---

## Phase 4 — Polish (After Phases 1-3 Complete)

- [ ] Add `/plan` command to Telegram (shows next 7 days)
- [ ] Add `/probability` command to Telegram (instant score)
- [ ] Add `/week` command (weekly compliance summary without waiting for Sunday)
- [ ] Tune Zone 2 bounds after proper HRmax field test
- [ ] Run CSS time trial to get accurate swim pace baseline
- [ ] Add brother session tagging to bike sessions
- [ ] Add Bintan race registration reminder (set for 3 months before Oct 12)
- [ ] Add weekly probability snapshot save job (runs Sunday with weekly report)

---

## Current Status

- [x] Phase 0: Full codebase review complete
- [x] Phase 0: CLAUDE.md and docs/ created
- [ ] Phase 1: In progress
- [ ] Phase 2: Not started
- [ ] Phase 3: Not started
- [ ] Phase 4: Not started
