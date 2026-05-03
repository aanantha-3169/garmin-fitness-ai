# FRONTEND_SPEC.md — React Dashboard Specification

> Reference for Claude Code when working on `frontend/` components.
> All components have been scaffolded. This spec describes what each
> does, what data it expects, and what Claude Code should do when modifying.

---

## Architecture

```
frontend/
├── src/
│   ├── App.jsx                    ← Entry point, renders Dashboard
│   ├── components/
│   │   ├── Dashboard.jsx          ← Main layout, data fetching, tab routing
│   │   ├── CountdownBar.jsx       ← Days until each checkpoint
│   │   ├── ProbabilityPanel.jsx   ← Goal probability score + breakdown
│   │   ├── TodayPanel.jsx         ← Today's readiness, session, nutrition
│   │   ├── SessionHistory.jsx     ← Last 7 days training log
│   │   ├── TrainingPlan.jsx       ← Next 14 days from training plan
│   │   └── PrinciplesPanel.jsx    ← Principles + baseline stats + sources
│   └── lib/
│       ├── api.js                 ← All API calls + mock data
│       └── design.js              ← Design tokens, shared styles, utilities
├── public/
│   └── manifest.json              ← PWA manifest
└── vite.config.js
```

---

## Design System

All styling uses inline styles referencing tokens from `lib/design.js`.
**Never add Tailwind, CSS files, or styled-components.** The inline style
approach is intentional — it keeps components self-contained for easy
copy-paste into any environment.

### Color tokens
```js
import { tokens } from "../lib/design";
tokens.bg          // #060606 — page background
tokens.bgCard      // #0C0C0C — card background
tokens.border      // #1E1E1E — card borders
tokens.gold        // #C4A35A — primary accent, headers
tokens.green       // #5CB85C — good/compliant
tokens.red         // #E05C5C — bad/violation
tokens.textPrimary // #D8D0C0 — main text
tokens.textMuted   // #444 — secondary text
```

### Typography
- `tokens.fontMono` — DM Mono (all body text, labels, data)
- `tokens.fontDisplay` — Sora (numbers, headings, scores)

### Score → color
```js
import { scoreColor } from "../lib/design";
scoreColor(75) // green
scoreColor(55) // gold
scoreColor(30) // red
```

### Discipline utilities
```js
import { disciplineColor, disciplineIcon } from "../lib/design";
disciplineColor("swim") // "#5B9BD5" (blue)
disciplineIcon("bike")  // "🚴"
```

---

## Component Contracts

### Dashboard.jsx
**Role:** Orchestrator. Fetches everything, passes to children as props.
**Tabs:** TODAY | STATS | PLAN | CORE
**Auto-refresh:** every 5 minutes
**Do not** add data fetching to child components — data always flows down from Dashboard.

### CountdownBar.jsx
**Props:** `checkpoints` (array from `/api/checkpoints`)
**Shows:** Days until each checkpoint, name, purpose, readiness score
**Color:** Score-based (green/gold/red via scoreColor)
**Position:** Sticky below TopBar, always visible

### ProbabilityPanel.jsx
**Props:** `data` (from `/api/probability`)
**Shows:** Big score number, 4 component bars with weights, 30-day trend sparkline
**Key detail:** Formula is always visible at the bottom — transparency is a design requirement
**Weight:** Zone 2 × 25% + Consistency × 25% + Life Load × 25% + Swim Freq × 25%

### TodayPanel.jsx
**Props:** `data` (from `/api/today`)
**Shows:**
- Garmin row: body battery, sleep, RHR, stress
- HRV card
- Life load sliders: workday load + water fear level
- Today's session card (with HR target badge)
- AI readiness decision + principle violations
- Nutrition bar + macros
**Critical:** principle_violations array must render as red flags — these override a positive recommendation

### SessionHistory.jsx
**Props:** `data` (from `/api/week` — 7-day array)
**Shows:** One row per day, reversed (newest first), with:
- Zone 2 compliance badge (green ✓Z2 / red ⚠Z2) on each session
- Brother session tag (gold)
- Water fear level tag (when logged)
- Workday load dot indicator
- Week summary: sessions count, Zone 2 %, avg fear level

### TrainingPlan.jsx
**Props:** `data` (from `/api/plan` — 14-day array)
**Shows:** Grouped by week, with phase badge, discipline color + icon, duration
**Today row:** Highlighted with green border
**Past rows:** 45% opacity
**Brother sessions:** Gold tag
**Empty state:** Tell user to run /schedule in Telegram

### PrinciplesPanel.jsx
**Props:** `stats` (from `/api/stats`, optional)
**Shows:**
1. Baseline fitness stats (VO2, FTP, swim pace, run pace, Zone 2 window)
2. The four principles (numbered, color-coded)
3. Checkpoint map with countdown
4. Methodology sources
5. Probability formula
**Note:** This is static content. Only stats block is dynamic.

---

## API Data Shapes

See `lib/api.js` getMockData() for the exact shape of every endpoint.
When FastAPI endpoints are built, they must return data matching these exact shapes.
The mock data is the contract — api.js mock = what FastAPI must return.

---

## Development Setup

```bash
cd frontend
npm install
npm run dev          # Runs on localhost:3000
                     # API proxied to localhost:8000 via vite.config.js
```

**To use mock data only (no backend needed):**
```bash
VITE_USE_MOCK=true npm run dev
```

**Environment variables:**
```
VITE_API_URL=https://your-api.vercel.app   # Production
VITE_USE_MOCK=true                          # Development without backend
```

---

## PWA Setup

The app is configured as a PWA via `public/manifest.json`.
To install on iPhone: open in Safari → Share → Add to Home Screen.

**Still needed (Phase 3 task):**
- `public/icon-192.png` and `public/icon-512.png` (generate from a simple design)
- `index.html` needs `<link rel="manifest" href="/manifest.json">`
- Service worker for offline support (optional, add last)

---

## Vercel Deployment

```bash
cd frontend
vercel --prod
```

Set env vars in Vercel dashboard:
- `VITE_API_URL` = FastAPI deployment URL
- `VITE_USE_MOCK` = false (production)

---

## What Claude Code Should Do

**When adding a new metric to a panel:**
1. Add it to the mock data in `lib/api.js` first
2. Add the corresponding field to the FastAPI endpoint in `api/main.py`
3. Add the db_manager.py fetch in `db_manager.py`
4. Update the component to display it

**When changing the probability formula:**
1. Update `sport_science.py` (backend calculation)
2. Update the formula display string in `ProbabilityPanel.jsx`
3. Update the formula display in `PrinciplesPanel.jsx`
4. Update `SPORT_SCIENCE.md`
Keep all four in sync.

**When adding a new tab:**
1. Add to TABS array in Dashboard.jsx
2. Create the component
3. Add a case in the tab render section of Dashboard.jsx
4. Add the API call to api.js if needed

**When the design feels off:**
The reference aesthetic is: dark terminal, gold accent, DM Mono + Sora pairing,
minimal chrome, data-first. Never add shadows, gradients, or rounded corners
larger than 4px. The grid breaks and density are intentional.
