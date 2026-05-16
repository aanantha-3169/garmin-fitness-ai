# SPORT_SCIENCE.md — Calculation Reference

> All training prescriptions must be derived from these formulas.
> These are the "known sources" that make the system transparent and
> defensible. Cite the source when generating training recommendations.

---

## Heart Rate Zones

**Source:** Joe Friel / Garmin zone model based on HRmax

```
Athlete max HR observed: 191 bpm (bike ride data, May 2026)
Note: May not be true HRmax — recalibrate when confirmed via field test

Zone 1 (Recovery):    < 114 bpm    (< 60% HRmax)
Zone 2 (Aerobic):     115-145 bpm  (60-76% HRmax)  ← PRIMARY TRAINING ZONE
Zone 3 (Tempo):       146-160 bpm  (76-84% HRmax)  ← Avoid unless prescribed
Zone 4 (Threshold):   161-175 bpm  (84-92% HRmax)  ← Never without recovery mandate
Zone 5 (VO2 Max):     > 175 bpm    (> 92% HRmax)   ← Banned without explicit reason

Target: 80-90% of sessions in Zone 2 (Principle 01)
```

---

## Running Paces — Jack Daniels VDOT

**Source:** Jack Daniels' Running Formula (3rd edition)

```
Athlete 5k predictor: 22:20 → VDOT ≈ 44
Athlete half marathon predictor: 1:49:27 → confirms VDOT ~44

VDOT 44 training paces:
  Easy (Zone 2 run):      6:20-7:00 /km
  Marathon pace:          5:45 /km
  Threshold:              5:05 /km
  Interval (VO2):         4:45 /km

For this athlete: all run prescriptions use EASY pace only (6:20-7:00/km)
unless a specific Phase 3+ interval session is explicitly prescribed.
```

---

## Swim Pacing — Critical Swim Speed (CSS)

**Source:** Swim Smooth CSS method (Paul Newsome)

```
Current pool data:
  Average pace: 1:58/100m
  Best pace (sprint): 1:10/100m (single length, not sustained)

CSS estimate (needs proper 400m + 200m time trial to confirm):
  CSS ≈ 2:05-2:10/100m (estimated from session data)

Training pace targets:
  Easy (Zone 2 swim):    2:15-2:30/100m — conversation pace
  CSS (threshold):       2:05/100m — hard but sustainable
  Sprint:                sub-1:45/100m — very short efforts only

For now: All swim sessions are easy pace (2:15-2:30/100m) until CSS
is properly measured via time trial.

Melaka/Bintan swim target: Complete race swim at 2:20-2:30/100m
Half Ironman swim target: Complete 1.9km at 2:15/100m (≈43 min total)
```

---

## Cycling Power — FTP & Training Zones

**Source:** Coggan/Allen power zone model

```
Athlete current FTP: 2.22 W/kg (Untrained category)
Athlete weight: 74kg

FTP progression targets:
  Now (May 2026):      2.22 W/kg
  Melaka (Aug 2026):   2.5 W/kg    (+13% over 3 months)
  Bintan (Oct 2026):   2.8 W/kg    (+26% over 5 months)
  Half Ironman (Nov):  3.0 W/kg    (+35% over 6 months)

Monthly FTP improvement rate needed: ~3-4% (achievable with consistent Z2 work)

Coggan zones (% of FTP):
  Zone 1 (Recovery):   < 55%
  Zone 2 (Endurance):  56-75%   ← PRIMARY BIKE ZONE
  Zone 3 (Tempo):      76-90%
  Zone 4 (Threshold):  91-105%
  Zone 5 (VO2):        106-120%

For this athlete: All bike sessions are Zone 2 power (56-75% FTP).
Since FTP is untrained, HR-based zone control is more reliable currently.
Use HR 115-145 bpm as primary constraint. Add power meter later.

Pacing target for sprint tri bike (20km): ~55 min at current fitness
Pacing target for Half Ironman bike (90km): ~3:00-3:15 at target FTP
```

---

## Training Stress Score (TSS)

**Source:** Coggan/Allen, Training Peaks methodology

```
TSS = (duration_hrs × NP × IF) / (FTP × 3600) × 100

Where:
  NP  = Normalized Power
  IF  = Intensity Factor (NP / FTP)
  FTP = Functional Threshold Power

Simplified swim/run TSS:
  rTSS (run): (duration_hrs × 100 × pace_factor)
  sTSS (swim): (distance_km × pace_factor)

Weekly TSS targets by phase:
  Base phase (now-Jul):      250-350 TSS/week
  Build phase (Jul-Sep):     350-450 TSS/week
  Race prep (Oct-Nov):       250-350 TSS/week (with taper)
  Taper week:                150-200 TSS/week

Life load adjustment:
  If avg workday_load > 7: reduce target TSS by 20%
  If avg workday_load > 8: reduce target TSS by 35%
  Body battery < 25 at session time: automatic rest recommendation
```

---

## Periodization Model

**Source:** 80/20 Triathlon (Matt Fitzgerald) + Luuc Muis Half Ironman model

```
Training structure: 3-week build / 1-week recovery

Week 1-3: Progressive load
  Week 1: Base TSS × 1.0
  Week 2: Base TSS × 1.1
  Week 3: Base TSS × 1.15

Week 4: Recovery
  TSS drops to 60-65% of week 3
  All sessions Zone 1-2 only
  Extra sleep priority

Long workout progression (Sunday brick/long run):
  May-Jun:  60-75 min bike + 15 min run
  Jul:      90 min bike + 20 min run
  Aug-Sep: 120 min bike + 30 min run
  Oct:     Race simulation (sprint tri distance)
  Nov:     Taper
```

---

## Swim Mechanics Reference (Athlete-Specific)

```
Known issue: Right arm presses down on breath (identified by coach)
Cause: Athlete tilts head to breathe rather than rotating body
Fix: Trust the bow wave trough — only half mouth needs to clear water

Known issue: Early right arm pull before left leg kick meets it
Cause: Using right arm as lever to lift for breath
Fix: Catch-up drill — right arm holds until left hand taps it

Breathing side: Left side breather (right arm extended when breathing)

Water fear status: Active — panic response present in open water
Current approach: Graduated exposure (pool → supervised open water → race)
Fear tracking: Log daily fear level 1-10 via /fear Telegram command
```

---

## Readiness Decision Matrix

**Source:** Combined from training_advisor.py logic + HRV principles

```
Adjust training if 2+ of these are true:
  - sleep_score < 60
  - hrv_status is LOW or UNBALANCED
  - body_battery_current < 30
  - stress_avg > 50
  - resting_heart_rate elevated > 10% above baseline

Override to full rest if ANY of these are true:
  - body_battery < 20
  - sleep_score < 45
  - workday_load = 10 (crisis day)
  - subjective note contains injury keywords (pain, hurt, injury, sharp)
```
