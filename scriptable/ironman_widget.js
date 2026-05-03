// Ironman Pipeline — Scriptable home screen widget
//
// Setup:
//   1. Install the Scriptable app (iOS).
//   2. Paste this file into a new Scriptable script.
//   3. Set API_BASE to your deployed Vercel API URL.
//   4. Add a Scriptable widget to your home screen, choose this script.
//   5. Set widget size to "Medium" for best layout.

const API_BASE = "https://your-vercel-app.vercel.app"; // ← replace with real URL

// ── Palette (matches dashboard dark terminal aesthetic) ───────────────────────
const C = {
  bg:       new Color("#0a0a0a"),
  card:     new Color("#111111"),
  gold:     new Color("#C4A35A"),
  dim:      new Color("#888888"),
  white:    new Color("#F0F0F0"),
  red:      new Color("#E05C5C"),
  green:    new Color("#5CE07A"),
};

// ── Fetch data ────────────────────────────────────────────────────────────────

async function fetchToday() {
  const req = new Request(`${API_BASE}/api/today`);
  req.timeoutInterval = 8;
  try {
    return await req.loadJSON();
  } catch {
    return null;
  }
}

async function fetchProbability() {
  const req = new Request(`${API_BASE}/api/probability`);
  req.timeoutInterval = 8;
  try {
    const data = await req.loadJSON();
    return data?.latest?.overall_score ?? null;
  } catch {
    return null;
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function addText(container, text, font, color, lines = 1) {
  const el = container.addText(String(text));
  el.font = font;
  el.textColor = color;
  el.lineLimit = lines;
  return el;
}

function phaseLabel(phase) {
  const map = {
    base:          "BASE",
    build:         "BUILD",
    pre_aquaman:   "PRE-AQUAMAN",
    taper_bintan:  "TAPER",
    taper_ironman: "TAPER",
  };
  return map[phase] ?? (phase ?? "—").toUpperCase();
}

// ── Widget layout ─────────────────────────────────────────────────────────────

async function buildWidget(today, probScore) {
  const w = new ListWidget();
  w.backgroundColor = C.bg;
  w.setPadding(14, 16, 14, 16);

  if (!today) {
    addText(w, "⚡ Ironman Pipeline", Font.boldSystemFont(13), C.gold);
    w.addSpacer(6);
    addText(w, "Could not reach API.", Font.systemFont(12), C.dim);
    addText(w, API_BASE, Font.systemFont(10), C.dim);
    return w;
  }

  // ── Row 1: phase tag + days to Aquaman ───────────────────────────────────
  const header = w.addStack();
  header.layoutHorizontally();

  const phaseBox = header.addStack();
  phaseBox.backgroundColor = C.gold;
  phaseBox.cornerRadius = 4;
  phaseBox.setPadding(2, 6, 2, 6);
  addText(phaseBox, phaseLabel(today.phase), Font.boldSystemFont(9), C.bg);

  header.addSpacer();

  const daysToAquaman = today.days_to_aquaman ?? "—";
  addText(header, `🌊 ${daysToAquaman}d`, Font.boldSystemFont(11), C.dim);

  w.addSpacer(10);

  // ── Row 2: probability score (big) + body battery ────────────────────────
  const scoreRow = w.addStack();
  scoreRow.layoutHorizontally();
  scoreRow.centerAlignContent();

  const scoreStr = probScore !== null ? String(probScore) : "—";
  const scoreColor = probScore >= 70 ? C.green : probScore >= 45 ? C.gold : C.red;
  addText(scoreRow, scoreStr, Font.boldSystemFont(38), scoreColor);

  scoreRow.addSpacer(8);

  const batteryCol = scoreRow.addStack();
  batteryCol.layoutVertically();

  const todayLog = today.today_log;
  const battery = todayLog?.morning_briefing_json?.metrics?.body_battery_current ?? null;
  const batteryStr = battery !== null ? `⚡ ${battery}` : "⚡ —";
  addText(batteryCol, batteryStr, Font.boldSystemFont(13), C.white);
  addText(batteryCol, "battery", Font.systemFont(9), C.dim);
  batteryCol.addSpacer(4);
  addText(batteryCol, "%", Font.systemFont(10), C.dim);

  scoreRow.addSpacer();

  w.addSpacer(8);

  // ── Row 3: today's session ───────────────────────────────────────────────
  const plan = today.todays_plan;
  const sessionName = plan?.session_name ?? "Rest Day";
  const discipline  = plan?.discipline ?? null;
  const duration    = plan?.duration_mins ? `${plan.duration_mins} min` : "";

  const disciplineIcon = {
    swim:  "🏊",
    run:   "🏃",
    bike:  "🚴",
    brick: "🔁",
    rest:  "😴",
  }[discipline] ?? "🎯";

  const sessionRow = w.addStack();
  sessionRow.layoutHorizontally();
  sessionRow.centerAlignContent();

  addText(sessionRow, `${disciplineIcon} `, Font.systemFont(14), C.white);
  const nameEl = addText(sessionRow, sessionName, Font.mediumSystemFont(12), C.white, 1);

  if (duration) {
    sessionRow.addSpacer();
    addText(sessionRow, duration, Font.systemFont(11), C.dim);
  }

  w.addSpacer(4);

  // ── Row 4: zone 2 HR range ───────────────────────────────────────────────
  const z2 = today.zone2_bounds;
  if (z2) {
    addText(w, `Zone 2: ${z2.low}–${z2.high} bpm`, Font.systemFont(10), C.dim);
  }

  return w;
}

// ── Entry point ───────────────────────────────────────────────────────────────

const [today, probScore] = await Promise.all([fetchToday(), fetchProbability()]);
const widget = await buildWidget(today, probScore);

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  widget.presentMedium();
}

Script.complete();
