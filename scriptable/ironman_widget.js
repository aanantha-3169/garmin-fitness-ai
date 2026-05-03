// Ironman Pipeline — Scriptable home screen widget
//
// Setup:
//   1. Install the Scriptable app (iOS).
//   2. Paste this file into a new Scriptable script.
//   3. Set API_BASE to your deployed Vercel API URL (no trailing slash).
//   4. Add a Scriptable widget to your home screen, choose this script.
//   5. Set widget size to "Medium" for best layout.

const API_BASE = "https://garmin-fitness-ai.vercel.app"; // no trailing slash

// ── Palette ───────────────────────────────────────────────────────────────────
const C = {
  bg:    new Color("#0a0a0a"),
  gold:  new Color("#C4A35A"),
  dim:   new Color("#666666"),
  muted: new Color("#444444"),
  white: new Color("#F0F0F0"),
  red:   new Color("#E05C5C"),
  green: new Color("#5CB85C"),
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

// ── Widget ────────────────────────────────────────────────────────────────────

async function buildWidget(today, checkpoints, week) {
  const w = new ListWidget();
  w.backgroundColor = C.bg;
  w.setPadding(12, 14, 12, 14);

  if (!today) {
    addText(w, "IRONMAN PIPELINE", Font.boldSystemFont(11), C.gold);
    w.addSpacer(6);
    addText(w, "Could not reach API.", Font.systemFont(11), C.dim);
    addText(w, API_BASE, Font.systemFont(9), C.dim);
    return w;
  }

  const session   = today.session ?? {};
  const completed = session.completed ?? null;

  // ── Row 1: next event + countdown ────────────────────────────────────────
  const header = w.addStack();
  header.layoutHorizontally();
  header.centerAlignContent();

  const nextEvent = checkpoints?.[0];
  const eventName = nextEvent ? nextEvent.name.toUpperCase() : "AQUAMAN LANGKAWI";
  const daysUntil = nextEvent ? `${nextEvent.days_until}d` : "—";

  addText(header, eventName, Font.boldSystemFont(8), C.gold);
  header.addSpacer();
  addText(header, `🌊 ${daysUntil}`, Font.boldSystemFont(10), C.dim);

  w.addSpacer(7);

  // ── Row 2: today's workout (hero) ─────────────────────────────────────────
  const sessionName = session.planned_name ?? "Rest Day";
  const discipline  = session.discipline   ?? "rest";
  const duration    = session.duration_mins ? `${session.duration_mins}min` : null;
  const isRest      = session.is_rest_day ?? false;

  const sessionRow = w.addStack();
  sessionRow.layoutHorizontally();
  sessionRow.centerAlignContent();

  addText(
    sessionRow,
    `${disciplineIcon(discipline)}  ${sessionName}`,
    Font.boldSystemFont(15),
    isRest ? C.dim : C.white,
    1
  );
  sessionRow.addSpacer();
  if (duration) addText(sessionRow, duration, Font.systemFont(11), C.dim);

  // Session description (truncated to 1 line)
  const desc = session.description;
  if (!isRest && desc) {
    w.addSpacer(3);
    addText(w, desc, Font.systemFont(10), C.dim, 1);
  }

  // Zone 2 HR target
  if (!isRest && session.hr_target_low) {
    w.addSpacer(2);
    addText(w, `HR ${session.hr_target_low}–${session.hr_target_high} bpm  ·  Zone 2`, Font.systemFont(10), C.dim);
  }

  w.addSpacer(7);

  // ── Row 3: execution — actual Garmin activity ─────────────────────────────
  const execRow = w.addStack();
  execRow.layoutHorizontally();
  execRow.centerAlignContent();

  if (completed) {
    const actName = completed.activity_name
      ?? (completed.activity_type ? completed.activity_type.toUpperCase() : "ACTIVITY");
    const actDur  = completed.duration_mins  ? `${completed.duration_mins}min` : null;
    const actHR   = completed.avg_heart_rate ? `${completed.avg_heart_rate}bpm` : null;
    const color   = session.deviation ? C.gold : C.green;
    const prefix  = session.deviation ? "⚡" : "✓";

    addText(execRow, `${prefix}  ${disciplineIcon(completed.activity_type)}  ${actName}`, Font.systemFont(11), color, 1);
    execRow.addSpacer();

    const execMeta = [actDur, actHR].filter(Boolean).join("  ·  ");
    if (execMeta) addText(execRow, execMeta, Font.systemFont(10), C.dim);
  } else {
    addText(execRow, "No activity synced yet", Font.systemFont(10), C.dim);
    execRow.addSpacer();
    addText(execRow, "/sync_workout", Font.systemFont(9), C.muted);
  }

  w.addSpacer();

  // ── Row 4: week progress dots ─────────────────────────────────────────────
  if (week && week.length > 0) {
    const weekRow = w.addStack();
    weekRow.layoutHorizontally();
    weekRow.centerAlignContent();

    const completed7 = week.filter(d => d.session !== null).length;
    const dots = week.map(d => d.session !== null ? "●" : "○").join(" ");

    addText(weekRow, dots, Font.systemFont(11), C.gold);
    weekRow.addSpacer();
    addText(weekRow, `${completed7}/7 this week`, Font.systemFont(10), C.dim);
  }

  return w;
}

// ── Entry point ───────────────────────────────────────────────────────────────

const [today, checkpoints, week] = await Promise.all([
  fetchJson("/api/today"),
  fetchJson("/api/checkpoints"),
  fetchJson("/api/week"),
]);

const widget = await buildWidget(today, checkpoints, week);

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  widget.presentMedium();
}

Script.complete();
