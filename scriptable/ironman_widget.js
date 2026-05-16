// Ironman Pipeline — Scriptable home screen widget
//
// Setup:
//   1. Install the Scriptable app (iOS).
//   2. Paste this file into a new Scriptable script.
//   3. Set API_BASE to your deployed Vercel API URL (no trailing slash).
//   4. Add a Scriptable widget to your home screen.
//   5. Medium size = compact view. Large size = full dashboard.

const API_BASE = "https://garmin-fitness-ai.vercel.app"; // no trailing slash

// ── Palette ───────────────────────────────────────────────────────────────────
const C = {
  bg:    new Color("#0a0a0a"),
  card:  new Color("#111111"),
  gold:  new Color("#C4A35A"),
  green: new Color("#5CB85C"),
  red:   new Color("#E05C5C"),
  blue:  new Color("#4A9EE0"),
  white: new Color("#F0F0F0"),
  dim:   new Color("#666666"),
  muted: new Color("#333333"),
};

// ── Fetch ─────────────────────────────────────────────────────────────────────
async function fetchJson(path) {
  const req = new Request(`${API_BASE}${path}`);
  req.timeoutInterval = 8;
  try { return await req.loadJSON(); } catch { return null; }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function addText(container, text, font, color, lines = 1) {
  const el = container.addText(String(text));
  el.font = font;
  el.textColor = color;
  el.lineLimit = lines;
  return el;
}

function disciplineIcon(d) {
  return { swim: "🏊", run: "🏃", bike: "🚴", brick: "🔁", rest: "😴" }[d] ?? "🎯";
}

function tierColor(tier) {
  if (tier === "RED")   return C.red;
  if (tier === "AMBER") return C.gold;
  return C.green;
}

function tierWord(tier) {
  if (tier === "RED")   return "REST TODAY";
  if (tier === "AMBER") return "SHORTENED";
  return "READY";
}

function batteryColor(v) {
  if (v == null) return C.dim;
  return v >= 60 ? C.green : v >= 30 ? C.gold : C.red;
}

function stressColor(v) {
  if (v == null) return C.dim;
  return v <= 25 ? C.green : v <= 50 ? C.gold : C.red;
}

function hrvColor(status) {
  return {
    Positive:   C.green,
    Balanced:   C.blue,
    Unbalanced: C.gold,
    Low:        C.red,
    Poor:       C.red,
  }[status] ?? C.dim;
}

function eventAbbrev(name) {
  const n = (name ?? "").toLowerCase();
  if (n.includes("ironman") || n.includes("him")) return "HIM";
  if (n.includes("bintan"))  return "BINTAN";
  if (n.includes("melaka"))  return "MELAKA";
  if (n.includes("marathon")) return "MARATHON";
  return name.slice(0, 6).toUpperCase();
}

function eventColor(name) {
  const n = (name ?? "").toLowerCase();
  if (n.includes("ironman") || n.includes("him")) return C.red;
  if (n.includes("bintan"))  return C.green;
  if (n.includes("melaka"))  return C.gold;
  return C.blue;
}

// ── Error widget ──────────────────────────────────────────────────────────────
function buildError(reason) {
  const w = new ListWidget();
  w.backgroundColor = C.bg;
  w.setPadding(14, 14, 14, 14);
  addText(w, "IRONMAN PIPELINE", Font.boldSystemFont(11), C.gold);
  w.addSpacer(8);
  addText(w, reason, Font.systemFont(11), C.dim, 3);
  addText(w, API_BASE, Font.systemFont(9), C.muted, 1);
  return w;
}

// ── Shared sections ───────────────────────────────────────────────────────────

function addHeader(w, probScore) {
  const row = w.addStack();
  row.layoutHorizontally();
  row.centerAlignContent();
  addText(row, "IRONMAN PIPELINE", Font.boldSystemFont(8), C.gold);
  row.addSpacer();
  if (probScore != null) {
    addText(row, `${probScore}%`, Font.boldSystemFont(11), C.white);
    addText(row, " PROB", Font.systemFont(7), C.dim);
  } else {
    addText(row, "— PROB", Font.systemFont(7), C.dim);
  }
}

function addStatus(w, tier, score) {
  const row = w.addStack();
  row.layoutHorizontally();
  row.centerAlignContent();
  addText(row, tierWord(tier), Font.boldSystemFont(19), tierColor(tier));
  row.addSpacer();
  if (score != null) {
    addText(row, `${score}`, Font.boldSystemFont(16), tierColor(tier));
    addText(row, " RDY", Font.systemFont(7), C.dim);
  }
}

function addSessionRow(w, session) {
  const discipline  = session.discipline   ?? "rest";
  const sessionName = session.planned_name ?? "Rest Day";
  const duration    = session.duration_mins ? `${session.duration_mins}min` : null;
  const isRest      = session.is_rest_day  ?? false;
  const isDone      = session.is_completed ?? false;

  const row = w.addStack();
  row.layoutHorizontally();
  row.centerAlignContent();
  addText(
    row,
    `${isDone ? "✓ " : ""}${disciplineIcon(discipline)} ${sessionName}`,
    Font.semiboldSystemFont(12),
    isDone ? C.green : isRest ? C.dim : C.white,
    1,
  );
  row.addSpacer();
  if (duration) addText(row, duration, Font.systemFont(11), C.dim);
}

function addHRRow(w, session) {
  if (!session.is_rest_day && session.hr_target_low) {
    addText(w, `HR ${session.hr_target_low}–${session.hr_target_high} bpm · Zone 2`, Font.systemFont(9), C.dim);
  }
}

function addVitalsRow(w, garmin) {
  const row = w.addStack();
  row.layoutHorizontally();
  row.centerAlignContent();

  const { body_battery: bat, sleep_score: sleep,
          resting_heart_rate_bpm: rhr, stress_avg: stress, hrv_status: hrv } = garmin;

  if (bat   != null) addText(row, `🔋${bat}`,  Font.boldSystemFont(11), batteryColor(bat));
  if (sleep != null) { row.addSpacer(6); addText(row, `💤${sleep}`, Font.boldSystemFont(11), C.blue); }
  if (rhr   != null) { row.addSpacer(6); addText(row, `❤️${rhr}`,   Font.boldSystemFont(11), C.white); }
  if (stress!= null) { row.addSpacer(6); addText(row, `⚡${stress}`, Font.boldSystemFont(11), stressColor(stress)); }
  if (hrv)           {
    row.addSpacer();
    addText(row, `HRV ${hrv.slice(0,3).toUpperCase()}`, Font.systemFont(9), hrvColor(hrv));
  }
}

function addEventsRow(w, checkpoints, max) {
  if (!checkpoints || checkpoints.length === 0) return;
  const row = w.addStack();
  row.layoutHorizontally();
  row.centerAlignContent();

  checkpoints.slice(0, max).forEach((cp, i) => {
    if (i > 0) { row.addSpacer(6); addText(row, "·", Font.systemFont(9), C.muted); row.addSpacer(6); }
    const inner = row.addStack();
    inner.layoutHorizontally();
    inner.centerAlignContent();
    addText(inner, `${cp.days_until}d `, Font.boldSystemFont(10), C.white);
    addText(inner, eventAbbrev(cp.name), Font.systemFont(8), eventColor(cp.name));
  });
}

function addWeekRow(w, week) {
  if (!week || week.length === 0) return;
  const row = w.addStack();
  row.layoutHorizontally();
  row.centerAlignContent();
  const count = week.filter(d => d.session !== null).length;
  const dots  = week.map(d => d.session !== null ? "●" : "○").join(" ");
  addText(row, dots, Font.systemFont(11), C.gold);
  row.addSpacer();
  addText(row, `${count}/7 sessions`, Font.systemFont(9), C.dim);
}

// ── Completed activity row (for large widget) ─────────────────────────────────
function addCompletedRow(w, session) {
  const c = session.completed;
  if (!c) return;
  const row = w.addStack();
  row.layoutHorizontally();
  row.centerAlignContent();
  const name  = c.activity_name ?? c.activity_type?.toUpperCase() ?? "ACTIVITY";
  const dur   = c.duration_mins  ? `${c.duration_mins}min`  : null;
  const hr    = c.avg_heart_rate ? `${c.avg_heart_rate}bpm` : null;
  const color = session.deviation ? C.gold : C.green;
  addText(row, `${session.deviation ? "⚡" : "✓"} ${name}`, Font.systemFont(9), color, 1);
  row.addSpacer();
  const meta = [dur, hr].filter(Boolean).join(" · ");
  if (meta) addText(row, meta, Font.systemFont(9), C.dim);
}

// ── Medium widget ─────────────────────────────────────────────────────────────
async function buildMedium(today, checkpoints, week, prob) {
  const w = new ListWidget();
  w.backgroundColor = C.bg;
  w.setPadding(12, 14, 10, 14);

  const session   = today.session   ?? {};
  const garmin    = today.garmin    ?? {};
  const readiness = today.readiness ?? {};
  const tier      = readiness.tier  ?? "GREEN";
  const score     = readiness.score ?? null;
  const probScore = prob?.overall_score ?? null;

  addHeader(w, probScore);
  w.addSpacer(4);

  addStatus(w, tier, score);
  w.addSpacer(2);

  addSessionRow(w, session);
  addHRRow(w, session);
  w.addSpacer(5);

  addVitalsRow(w, garmin);
  w.addSpacer(4);

  addEventsRow(w, checkpoints, 4);
  w.addSpacer(4);

  addWeekRow(w, week);

  return w;
}

// ── Large widget ──────────────────────────────────────────────────────────────
async function buildLarge(today, checkpoints, week, prob) {
  const w = new ListWidget();
  w.backgroundColor = C.bg;
  w.setPadding(14, 14, 14, 14);

  const session   = today.session   ?? {};
  const garmin    = today.garmin    ?? {};
  const readiness = today.readiness ?? {};
  const tier      = readiness.tier  ?? "GREEN";
  const score     = readiness.score ?? null;
  const probScore = prob?.overall_score ?? null;
  const fearLevel = today.water_fear_level;
  const workload  = today.workday_load;

  // Header
  addHeader(w, probScore);
  w.addSpacer(6);

  // Status (bigger on large)
  const statusRow = w.addStack();
  statusRow.layoutHorizontally();
  statusRow.centerAlignContent();
  addText(statusRow, tierWord(tier), Font.boldSystemFont(22), tierColor(tier));
  statusRow.addSpacer();
  if (score != null) {
    addText(statusRow, `${score}`, Font.boldSystemFont(20), tierColor(tier));
    addText(statusRow, " RDY", Font.systemFont(8), C.dim);
  }
  w.addSpacer(4);

  // Readiness note
  if (readiness.intensity_note) {
    addText(w, readiness.intensity_note, Font.systemFont(10), C.dim, 2);
    w.addSpacer(5);
  }

  // Session
  addSessionRow(w, session);
  addHRRow(w, session);
  w.addSpacer(2);

  // Session description
  if (!session.is_rest_day && session.description) {
    addText(w, session.description, Font.systemFont(9), C.dim, 1);
  }

  // Completed activity
  addCompletedRow(w, session);
  w.addSpacer(8);

  // Vitals
  const vitalsLabel = w.addStack();
  vitalsLabel.layoutHorizontally();
  addText(vitalsLabel, "GARMIN VITALS", Font.systemFont(7), C.muted);
  w.addSpacer(3);
  addVitalsRow(w, garmin);

  // Life load + fear on same row
  if (workload != null || fearLevel != null) {
    w.addSpacer(3);
    const lifeRow = w.addStack();
    lifeRow.layoutHorizontally();
    lifeRow.centerAlignContent();
    if (workload != null) {
      const wlColor = workload >= 8 ? C.red : workload >= 6 ? C.gold : C.green;
      addText(lifeRow, `LOAD ${workload}/10`, Font.systemFont(9), wlColor);
    }
    if (fearLevel != null) {
      if (workload != null) { lifeRow.addSpacer(10); addText(lifeRow, "·", Font.systemFont(9), C.muted); lifeRow.addSpacer(10); }
      const fearColor = fearLevel >= 7 ? C.red : fearLevel >= 4 ? C.gold : C.green;
      addText(lifeRow, `🌊 FEAR ${fearLevel}/10`, Font.systemFont(9), fearColor);
    }
  }

  w.addSpacer(8);

  // Events — all 4
  const eventsLabel = w.addStack();
  eventsLabel.layoutHorizontally();
  addText(eventsLabel, "EVENTS", Font.systemFont(7), C.muted);
  w.addSpacer(3);

  if (checkpoints && checkpoints.length > 0) {
    // Show 2 per row
    for (let i = 0; i < Math.min(checkpoints.length, 4); i += 2) {
      const evtRow = w.addStack();
      evtRow.layoutHorizontally();
      evtRow.centerAlignContent();

      const renderEvent = (cp) => {
        const inner = evtRow.addStack();
        inner.layoutHorizontally();
        inner.centerAlignContent();
        addText(inner, `${cp.days_until}d `, Font.boldSystemFont(12), C.white);
        addText(inner, eventAbbrev(cp.name), Font.systemFont(9), eventColor(cp.name));
        if (cp.readiness_score != null) {
          addText(inner, `  ${cp.readiness_score}%`, Font.systemFont(9), tierColor(cp.readiness_score >= 70 ? "GREEN" : cp.readiness_score >= 40 ? "AMBER" : "RED"));
        }
      };

      renderEvent(checkpoints[i]);
      if (checkpoints[i + 1]) {
        evtRow.addSpacer();
        renderEvent(checkpoints[i + 1]);
      }
      w.addSpacer(3);
    }
  }

  w.addSpacer(6);

  // Week
  const weekLabel = w.addStack();
  weekLabel.layoutHorizontally();
  addText(weekLabel, "THIS WEEK", Font.systemFont(7), C.muted);
  w.addSpacer(3);
  addWeekRow(w, week);

  return w;
}

// ── Entry point ───────────────────────────────────────────────────────────────
const [today, checkpoints, week, prob] = await Promise.all([
  fetchJson("/api/today"),
  fetchJson("/api/checkpoints"),
  fetchJson("/api/week"),
  fetchJson("/api/probability"),
]);

if (!today) {
  const w = buildError("Could not reach API. Check internet or Vercel deployment.");
  Script.setWidget(w);
  Script.complete();
}

let widget;
if (config.widgetFamily === "large") {
  widget = await buildLarge(today, checkpoints, week, prob);
} else {
  widget = await buildMedium(today, checkpoints, week, prob);
}

// Preview in app: show both sizes
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  const preview = config.widgetFamily ?? "medium";
  if (preview === "large") {
    await widget.presentLarge();
  } else {
    await widget.presentMedium();
  }
}

Script.complete();
