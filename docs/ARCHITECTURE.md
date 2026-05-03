# ARCHITECTURE.md — System Design

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│  RENDER (existing)                                      │
│                                                         │
│  main.py                                                │
│  ├── Telegram Bot (python-telegram-bot)                 │
│  │   ├── meal_tracker_bot.py  (photo/text meals)        │
│  │   ├── telegram_notifier.py (briefing + status)       │
│  │   └── intent_router.py    (NLP classifier)           │
│  │                                                      │
│  ├── Scheduled Jobs                                     │
│  │   ├── 05:45 WIB — morning briefing                   │
│  │   ├── 20:00 WIB — workout sync                       │
│  │   └── Sunday 20:00 WIB — weekly report               │
│  │                                                      │
│  └── Garmin Layer                                       │
│      ├── garmin_client.py    (auth + token mgmt)        │
│      ├── garmin_metrics.py   (health data)              │
│      ├── garmin_telemetry.py (workout data)             │
│      ├── garmin_scheduler.py (calendar mgmt)            │
│      └── garmin_nutrition.py (nutrition sync)           │
│                                                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  SUPABASE (existing + extended)                         │
│                                                         │
│  Tables:                                                │
│  daily_logs           (existing)                        │
│  garmin_tokens        (existing)                        │
│  completed_workouts   (existing)                        │
│  subjective_logs      (existing)                        │
│  metric_logs          (existing)                        │
│  water_fear_logs      (NEW)                             │
│  ironman_training_plan (NEW)                            │
│  principle_compliance  (NEW)                            │
│  probability_snapshots (NEW)                            │
│                                                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  VERCEL (new)                                           │
│                                                         │
│  api/main.py (FastAPI)                                  │
│  ├── GET /api/today                                     │
│  ├── GET /api/probability                               │
│  ├── GET /api/week                                      │
│  ├── GET /api/plan                                      │
│  ├── GET /api/stats                                     │
│  ├── GET /api/checkpoints                               │
│  └── GET /health                                        │
│                                                         │
│  frontend/ (React + Vite)                               │
│  ├── Dashboard (desktop)                                │
│  └── PWA (mobile home screen)                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  MOBILE (iPhone)                                        │
│                                                         │
│  Option A: PWA pinned to home screen (full dashboard)   │
│  Option B: Scriptable widget (glance view)              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Data Flow — Morning Briefing (05:45 WIB)

```
1. main.py job fires
2. garmin_client.py → authenticate (Supabase tokens → local files → credentials)
3. garmin_metrics.py → fetch sleep, HRV, body battery, stress, RHR
4. training_plan.py → get_todays_plan() → retrieve today's planned session
5. garmin_scheduler.py → ensure session is on Garmin calendar
6. db_manager.py → get_completed_workout(yesterday) → yesterday's telemetry
7. db_manager.py → get_recent_subjective_logs(days=2) → athlete notes
8. ironman_agent.py → analyze_readiness(metrics, plan, telemetry, notes)
   └── Gemini API call with:
       - docs/PRINCIPLES.md (injected)
       - docs/SPORT_SCIENCE.md (injected)
       - training_plan.get_athlete_context() (current snapshot)
       - All Garmin metrics
       - Yesterday's execution
       - Athlete notes
9. db_manager.py → init_daily_log() → persist to Supabase
10. telegram_notifier.py → send_morning_briefing() → Telegram message + buttons
```

---

## Data Flow — Meal Photo (anytime)

```
1. User sends photo to Telegram bot
2. meal_tracker_bot._handle_photo() downloads image
3. Gemini vision → _analyze_food_photo() → macro estimates JSON
4. Bot sends estimate with ✅ Save / ✏️ Update / ❌ Cancel buttons
5. User confirms → _handle_meal_callback()
6. db_manager.add_macros() → Supabase daily_logs
7. garmin_nutrition.log_meal_to_garmin() → Garmin Connect
8. Bot replies with updated daily totals
```

---

## Data Flow — Dashboard (anytime)

```
1. User opens dashboard URL (browser or PWA)
2. React app loads, calls FastAPI /api/today
3. FastAPI reads Supabase:
   - daily_logs (calories, macros)
   - morning_briefing_json (metrics, decision)
   - water_fear_logs (latest fear level)
   - ironman_training_plan (today + next 7 days)
   - probability_snapshots (latest score)
4. FastAPI returns combined JSON
5. React renders dashboard components
6. Auto-refresh every 5 minutes (or manual pull-to-refresh on mobile)
```

---

## AI Layer Architecture

```
All AI calls use the same pattern:

Input → Context Injection → Gemini → Pydantic Validation → Output

Context injection sources (always included):
1. docs/PRINCIPLES.md — the four principles
2. docs/SPORT_SCIENCE.md — Zone 2 bounds, VDOT, CSS
3. get_athlete_context() — current metrics snapshot

Calls:
- ironman_agent.py → TrainingDecision (morning readiness)
- meal_tracker_bot.py → macro estimates (photo + text)
- progress_reporter.py → weekly coach analysis
- intent_router.py → MEAL/METRIC/SUBJECTIVE/QUERY/FEAR/TRAINING_LOG
- _handle_query() → general nutrition/training questions
```

---

## Module Dependency Map

```
main.py
├── garmin_client.py
├── garmin_metrics.py
├── garmin_telemetry.py
├── garmin_scheduler.py (→ training_plan.py NEW)
├── ironman_agent.py (NEW, replaces training_advisor.py)
│   ├── sport_science.py (NEW)
│   └── training_plan.py (NEW)
├── telegram_notifier.py
│   ├── garmin_client.py
│   ├── garmin_metrics.py
│   ├── garmin_scheduler.py
│   └── db_manager.py
├── meal_tracker_bot.py
│   ├── garmin_client.py
│   ├── garmin_nutrition.py
│   ├── intent_router.py
│   └── db_manager.py
├── progress_reporter.py
│   └── db_manager.py
└── db_manager.py (→ Supabase)

api/main.py (NEW, Vercel)
└── db_manager.py (→ Supabase, shared module)

frontend/ (NEW, Vercel)
└── api/main.py (HTTP calls)
```

---

## Key Design Decisions

**Why Gemini not Claude for AI calls?**
Cost. The system makes 3-5 AI calls per day minimum. At scale this matters.
Gemini Flash is significantly cheaper. The quality difference is negligible
when context is properly structured via files.

**Why FastAPI not Flask?**
Async support, automatic Swagger docs at /docs, Pydantic integration.
FastAPI on Vercel via serverless functions works well.

**Why Vercel for frontend not Render?**
Render is stateful-server hosting (good for long-running bots).
Vercel is serverless (good for APIs and static frontends). Right tool for each job.
Also: Vercel free tier is generous for a single-user app.

**Why PWA not native iOS widget?**
Native iOS widget = Swift + Xcode + Apple Developer account + App Store review.
This is 2-4 weeks of work outside the athlete's existing stack.
PWA + Scriptable covers 90% of the value in half a day of work.

**Why keep Supabase not move to another DB?**
Garmin token persistence is already working in Supabase. This is production infrastructure.
The new tables extend it, not replace it.

**Why keep the Telegram bot as the primary input interface?**
The dashboard is READ-ONLY by design. All data entry via Telegram keeps
friction low — the athlete is already there for the morning briefing.
Adding a second data entry surface (dashboard forms) creates split attention.
