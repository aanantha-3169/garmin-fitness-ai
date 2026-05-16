# CLAUDE.md — Ironman Pipeline Project

> This file is the primary context source for Claude Code. Read it fully before
> making any changes. When in doubt about a decision, check PRINCIPLES.md first.

## What This Project Is

A personal athletic performance pipeline for a single athlete targeting a
Half Ironman in November 2026. The system is NOT a generic fitness app.
Every architectural decision must serve the four principles in `docs/PRINCIPLES.md`.

## Tech Stack (Non-Negotiable)

| Layer | Technology | Rationale |
|---|---|---|
| AI API | **Gemini** (google-genai) | Cost. Do not switch to Claude API. |
| Context injection | Structured files + Pydantic schemas | Replaces model memory |
| Bot | python-telegram-bot v21 | Already in production |
| Backend API | **FastAPI** (new — Vercel) | Serves dashboard data |
| Frontend | **React + Vite** (new — Vercel) | Dashboard UI |
| Database | **Supabase** (PostgreSQL) | Already in production |
| Garmin | garminconnect + garth | Already in production |
| Auth (Garmin) | OAuth token persistence via Supabase | Already working |
| Hosting (bot) | **Render** | Existing deployment |
| Hosting (frontend) | **Vercel** | New deployment |
| Mobile | **PWA** + Scriptable widget | No native app |

## Repository Structure

```
garmin-fitness-ai/          ← Existing Render bot service
├── CLAUDE.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PRINCIPLES.md
│   ├── SPORT_SCIENCE.md
│   ├── SCHEMA.md
│   └── BUILD_PLAN.md
│
├── EXISTING FILES (keep unless noted):
│   ├── garmin_client.py        ← Keep as-is. Auth works.
│   ├── garmin_metrics.py       ← Keep + add swim telemetry
│   ├── garmin_telemetry.py     ← Keep + add swim fields
│   ├── garmin_calendar_manager.py ← Keep as-is
│   ├── garmin_nutrition.py     ← Keep as-is
│   ├── db_manager.py           ← Keep + add new table functions
│   ├── meal_tracker_bot.py     ← Keep as-is (Gemini photo analysis stays)
│   ├── intent_router.py        ← Keep + add FEAR and TRAINING_LOG intents
│   ├── progress_reporter.py    ← Keep + add Zone 2 and probability metrics
│   ├── commute_optimizer.py    ← Keep as-is (Jakarta commute feature)
│   ├── main.py                 ← Extend with new commands
│   └── requirements.txt        ← Update with new deps
│
├── NEW FILES (build these):
│   ├── ironman_agent.py        ← Replaces training_advisor.py
│   ├── training_plan.py        ← Triathlon periodization engine
│   ├── sport_science.py        ← Zone 2, VDOT, CSS, TSS calculations
│   └── api/
│       └── main.py             ← FastAPI app (deployed to Vercel)
│
└── frontend/                   ← React + Vite (deployed to Vercel)
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   │   ├── Dashboard.jsx
    │   │   ├── ProbabilityPanel.jsx
    │   │   ├── CountdownBar.jsx
    │   │   ├── SessionHistory.jsx
    │   │   ├── TrainingPlan.jsx
    │   │   └── PrinciplesPanel.jsx
    │   └── lib/
    │       └── api.js          ← Calls FastAPI endpoints
    ├── public/
    │   ├── manifest.json       ← PWA manifest
    │   └── sw.js               ← Service worker
    └── vite.config.js
```

## Athlete Profile (Hardcoded Context)

```python
ATHLETE = {
    "name": "Athlete",
    "vo2_max": 54,           # Excellent, top 10% for age/gender
    "ftp_w_kg": 2.22,        # Untrained — critical gap
    "swim_pace_100m": "1:58", # Pool average
    "run_5k_predicted": "22:20",
    "run_half_predicted": "1:49:27",
    "water_fear": True,      # Actively working on it
    "timezone": "Asia/Jakarta",
    "work_window": "09:00-19:00",
    "training_window": "05:30-08:30",
    "side_project_hours": "weekend_afternoons",
}
```

## Checkpoint Events (Hardcoded)

```python
CHECKPOINTS = [
    {
        "name": "Score Marathon",
        "date": "2026-07-19",
        "type": "marathon",
        "purpose": "Running fitness benchmark",
        "critical_path": "run",
    },
    {
        "name": "Melaka Triathlon",
        "date": "2026-08-30",
        "type": "triathlon",
        "purpose": "First full triathlon experience before Bintan",
        "critical_path": "all",
    },
    {
        "name": "Bintan Triathlon",
        "date": "2026-10-12",
        "type": "triathlon",
        "purpose": "Full triathlon dress rehearsal",
        "critical_path": "all",
    },
    {
        "name": "Half Ironman",
        "date": "2026-11-21", 
        "type": "ironman_70.3",
        "purpose": "The endpoint — 1.9km swim / 90km bike / 21km run",
        "critical_path": "all",
    },
]
```

## AI API Usage Pattern

All Gemini calls follow this pattern. Never call Gemini without injecting
the principles context:

```python
from training_plan import get_athlete_context

def build_system_prompt(base_prompt: str) -> str:
    """Always inject principles + athlete context into system prompts."""
    principles = Path("docs/PRINCIPLES.md").read_text()
    sport_science = Path("docs/SPORT_SCIENCE.md").read_text()
    context = get_athlete_context()  # Current metrics snapshot
    
    return f"""
{base_prompt}

=== ATHLETE PRINCIPLES (NON-NEGOTIABLE) ===
{principles}

=== SPORT SCIENCE PARAMETERS ===
{sport_science}

=== CURRENT ATHLETE CONTEXT ===
{context}
"""
```

## Probability Score Formula (Transparent)

```python
def calculate_probability(logs: list[dict]) -> dict:
    """
    Score = (zone2_compliance × 0.25) +
            (consistency × 0.25) +
            (life_load_buffer × 0.25) +
            (swim_frequency × 0.25)
    
    All components are 0-100 scores calculated from the last 14 days.
    
    zone2_compliance  = sessions with avg_hr 115-145 / total sessions
    consistency       = actual sessions / target 7 sessions
    life_load_buffer  = ((10 - avg_workday_load) / 9) × 100
    swim_frequency    = swim sessions / target 4 sessions
    """
```

## Zone 2 Heart Rate Window

```
Zone 2 = 115-145 bpm (conservative window, recalibrate when max HR confirmed)
Based on: Max HR observed = 191 bpm (bike ride data)
Zone 2 = 60-76% HRmax = 115-145 bpm
```

## Key Constraints

1. **Never hardcode Garmin credentials.** All secrets via .env / Render env vars.
2. **All Garmin API calls use `_safe_call()` pattern** from garmin_metrics.py. Wrap everything.
3. **Supabase is source of truth.** SQLite is ephemeral fallback only (Render filesystem).
4. **The training schedule is not PT sessions and badminton.** It is triathlon periodization.
   See `training_plan.py` (to be built) and `docs/BUILD_PLAN.md` Phase 1 Task 3.
5. **Never remove the Pydantic schema pattern** from the AI response layer. It prevents hallucination.
6. **Fear level (1-10) is a first-class metric**, not a text note. It goes in `water_fear_logs` table.
7. **The dashboard is read-only.** Data entry happens via Telegram bot only.

## Current Known Issues to Fix

- `garmin_scheduler.py` — `_WEEKLY_SCHEDULE` has wrong sport types (PT/badminton not triathlon)
- `training_advisor.py` — uses Gemini but has NO principles context injected
- `progress_reporter.py` — weekly report has NO Zone 2 compliance metric
- `intent_router.py` — missing FEAR and TRAINING_LOG intents
- `garmin_telemetry.py` — no swim-specific field extraction
- `db_manager.py` — missing tables: water_fear_logs, ironman_training_plan, principle_compliance

## Environment Variables Required

```bash
# Existing (Render)
GARMIN_EMAIL=
GARMIN_PASSWORD=
GARMIN_TOKENSTORE=~/.garminconnect
GARMIN_OAUTH1_TOKEN=   # base64 fallback
GARMIN_OAUTH2_TOKEN=   # base64 fallback
SUPABASE_URL=
SUPABASE_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
GEMINI_API_KEY=

# New (Vercel)
SUPABASE_URL=          # Same as above
SUPABASE_KEY=          # Same as above
VITE_API_URL=          # FastAPI endpoint URL
```

## Testing Approach

- No unit test framework currently. Don't add one unless specifically asked.
- Test Telegram commands manually via the bot.
- Test FastAPI endpoints via `/docs` (Swagger UI built into FastAPI).
- Log everything. The existing logging pattern (logger.info/warning/error) is correct.
