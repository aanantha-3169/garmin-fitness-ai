/**
 * TrainingPlan.jsx — Next 14 days from ironman_training_plan table
 *
 * Props:
 *   data: array from GET /api/plan
 *   [
 *     {
 *       date, day, name, discipline, duration_mins, phase,
 *       brother_session, hr_target_low, hr_target_high, description
 *     }
 *   ]
 */

import { tokens, disciplineColor, disciplineIcon, card, sectionLabel } from "../lib/design";

const PHASE_LABELS = {
  base:          "BASE",
  build:         "BUILD",
  pre_score:     "PRE-MARATHON",
  taper_melaka:  "TAPER",
  taper_bintan:  "TAPER",
  taper_ironman: "TAPER",
};

const PHASE_COLORS = {
  base:          tokens.textMuted,
  build:         tokens.gold,
  pre_score:     tokens.blue,
  taper_melaka:  tokens.green,
  taper_bintan:  tokens.green,
  taper_ironman: tokens.green,
};

function phaseColor(phase) {
  return PHASE_COLORS[phase] || tokens.textMuted;
}

export default function TrainingPlan({ data = [] }) {
  const today = new Date().toISOString().split("T")[0];

  // Group by week
  const weeks = [];
  let currentWeek = [];
  data.forEach((session, i) => {
    currentWeek.push(session);
    if (currentWeek.length === 7 || i === data.length - 1) {
      weeks.push(currentWeek);
      currentWeek = [];
    }
  });

  const s = {
    wrapper: card,
    header: sectionLabel,

    weekBlock: { marginBottom: "16px" },
    weekLabel: {
      fontSize: "8px",
      letterSpacing: "2px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      marginBottom: "6px",
    },

    sessionRow: (isToday, isPast) => ({
      display: "flex",
      alignItems: "center",
      gap: "10px",
      padding: "8px 10px",
      marginBottom: "3px",
      borderRadius: tokens.radiusSm,
      background: isToday ? "#0A150A" : "transparent",
      border: `1px solid ${isToday ? tokens.greenBorder : "transparent"}`,
      opacity: isPast ? 0.45 : 1,
      transition: "background 0.2s",
    }),

    dateCol: {
      width: "28px",
      flexShrink: 0,
      fontSize: "9px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      letterSpacing: "0.5px",
    },
    iconCol: { width: "16px", flexShrink: 0, fontSize: "14px", lineHeight: 1 },
    mainCol: { flex: 1 },
    sessionName: (discipline) => ({
      fontSize: "11px",
      color: discipline === "rest" ? tokens.textMuted : disciplineColor(discipline),
      fontFamily: tokens.fontMono,
      fontStyle: discipline === "rest" ? "italic" : "normal",
    }),
    sessionMeta: {
      display: "flex",
      gap: "8px",
      marginTop: "1px",
      flexWrap: "wrap",
    },
    metaTag: {
      fontSize: "8px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
    },
    brotherTag: {
      fontSize: "8px",
      padding: "0px 4px",
      borderRadius: "1px",
      fontFamily: tokens.fontMono,
      background: "#0F0C00",
      color: tokens.gold,
      border: `1px solid #2a1a00`,
    },
    todayBadge: {
      fontSize: "8px",
      padding: "1px 5px",
      borderRadius: "2px",
      background: "#0D1F0D",
      color: tokens.green,
      border: `1px solid ${tokens.greenBorder}`,
      fontFamily: tokens.fontMono,
      letterSpacing: "1px",
    },
    phaseTag: (phase) => ({
      fontSize: "8px",
      padding: "1px 5px",
      borderRadius: "2px",
      fontFamily: tokens.fontMono,
      color: phaseColor(phase),
      background: `${phaseColor(phase)}11`,
      border: `1px solid ${phaseColor(phase)}33`,
    }),

    legend: {
      display: "flex",
      gap: "12px",
      marginTop: "12px",
      paddingTop: "10px",
      borderTop: `1px solid ${tokens.border}`,
      flexWrap: "wrap",
    },
    legendItem: { display: "flex", alignItems: "center", gap: "5px", fontSize: "8px", color: tokens.textMuted, fontFamily: tokens.fontMono },
    legendDot: (color) => ({ width: "6px", height: "6px", borderRadius: "50%", background: color, flexShrink: 0 }),
  };

  if (!data.length) {
    return (
      <div style={s.wrapper}>
        <div style={s.header}>TRAINING PLAN — NEXT 14 DAYS</div>
        <div style={{ fontSize: "10px", color: tokens.textMuted, textAlign: "center", padding: "20px" }}>
          No plan data. Run /schedule in the Telegram bot to populate.
        </div>
      </div>
    );
  }

  return (
    <div style={s.wrapper}>
      <div style={s.header}>TRAINING PLAN — NEXT 14 DAYS</div>

      {weeks.map((week, wi) => {
        const weekStart = new Date(week[0].date).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
        const weekEnd = new Date(week[week.length - 1].date).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
        const phase = week[0]?.phase;

        return (
          <div key={wi} style={s.weekBlock}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={s.weekLabel}>WEEK {wi + 1} · {weekStart} – {weekEnd}</div>
              {phase && <div style={s.phaseTag(phase)}>{PHASE_LABELS[phase] || phase.toUpperCase()}</div>}
            </div>

            {week.map((session) => {
              const isToday = session.date === today;
              const isPast = session.date < today;

              return (
                <div key={session.date} style={s.sessionRow(isToday, isPast)}>
                  <div style={s.dateCol}>{session.day}</div>
                  <div style={s.iconCol}>{disciplineIcon(session.discipline)}</div>
                  <div style={s.mainCol}>
                    <div style={s.sessionName(session.discipline)}>{session.name}</div>
                    <div style={s.sessionMeta}>
                      {session.duration_mins && (
                        <span style={s.metaTag}>{session.duration_mins}min</span>
                      )}
                      {session.hr_target_low && (
                        <span style={s.metaTag}>{session.hr_target_low}–{session.hr_target_high}bpm</span>
                      )}
                      {session.brother_session && (
                        <span style={s.brotherTag}>👥 BROTHER</span>
                      )}
                    </div>
                  </div>
                  {isToday && <span style={s.todayBadge}>TODAY</span>}
                </div>
              );
            })}
          </div>
        );
      })}

      {/* Legend */}
      <div style={s.legend}>
        {["swim", "bike", "run", "brick"].map(d => (
          <div key={d} style={s.legendItem}>
            <div style={s.legendDot(disciplineColor(d))} />
            {disciplineIcon(d)} {d.toUpperCase()}
          </div>
        ))}
      </div>
    </div>
  );
}
