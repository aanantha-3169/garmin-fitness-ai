/**
 * SessionHistory.jsx — Last 7 days of training with compliance indicators
 *
 * Props:
 *   data: array from GET /api/week
 *   [
 *     {
 *       date, day,
 *       session: { type, name, duration_mins, avg_hr, zone2, brother_session } | null,
 *       workday_load,
 *       water_fear_level,
 *       calories_consumed
 *     }
 *   ]
 */

import { tokens, scoreColor, disciplineColor, disciplineIcon, card, sectionLabel } from "../lib/design";

function HRBadge({ avgHR, zone2 }) {
  if (!avgHR) return null;
  return (
    <span style={{
      fontSize: "8px",
      padding: "1px 5px",
      borderRadius: "2px",
      fontFamily: tokens.fontMono,
      background: zone2 ? "#0D1F0D" : "#1F0D0D",
      color: zone2 ? tokens.green : tokens.red,
      border: `1px solid ${zone2 ? "#1a3a1a" : "#3a1a1a"}`,
      marginLeft: "4px",
    }}>
      {avgHR}bpm {zone2 ? "✓Z2" : "⚠Z2"}
    </span>
  );
}

function LoadDot({ value, max = 10 }) {
  if (!value) return null;
  const color = value <= 4 ? tokens.green : value <= 7 ? tokens.gold : tokens.red;
  return (
    <span style={{
      display: "inline-block",
      width: "6px",
      height: "6px",
      borderRadius: "50%",
      background: color,
      marginLeft: "4px",
      verticalAlign: "middle",
      title: `Load ${value}/10`,
    }} />
  );
}

export default function SessionHistory({ data = [] }) {
  const s = {
    wrapper: card,
    header: { ...sectionLabel },
    row: {
      padding: "10px 0",
      borderBottom: `1px solid ${tokens.border}`,
      display: "flex",
      alignItems: "flex-start",
      gap: "12px",
    },
    dayCol: {
      width: "28px",
      flexShrink: 0,
      fontSize: "9px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      letterSpacing: "1px",
      paddingTop: "2px",
    },
    mainCol: { flex: 1 },
    sessionLine: { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "4px", marginBottom: "3px" },
    sessionName: (type) => ({
      fontSize: "11px",
      color: disciplineColor(type),
      fontFamily: tokens.fontMono,
    }),
    duration: {
      fontSize: "9px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
    },
    restLabel: {
      fontSize: "10px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      fontStyle: "italic",
    },
    meta: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" },
    fearTag: (level) => ({
      fontSize: "8px",
      padding: "1px 5px",
      borderRadius: "2px",
      fontFamily: tokens.fontMono,
      background: "#111",
      color: level <= 3 ? tokens.green : level <= 6 ? tokens.gold : tokens.red,
      border: `1px solid ${tokens.border}`,
    }),
    brotherTag: {
      fontSize: "8px",
      padding: "1px 5px",
      borderRadius: "2px",
      fontFamily: tokens.fontMono,
      background: "#0F0C00",
      color: tokens.gold,
      border: `1px solid #3a2a00`,
    },
    calTag: {
      fontSize: "8px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
    },
    rightCol: { textAlign: "right", flexShrink: 0 },
    icon: (type) => ({ fontSize: "16px", lineHeight: 1 }),

    summary: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr 1fr",
      gap: "6px",
      marginTop: "12px",
      paddingTop: "10px",
      borderTop: `1px solid ${tokens.border}`,
    },
    summaryItem: {
      fontSize: "9px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      textAlign: "center",
    },
    summaryVal: {
      fontFamily: "'Sora', sans-serif",
      fontSize: "18px",
      fontWeight: 700,
      color: tokens.textPrimary,
      display: "block",
      marginBottom: "2px",
    },
  };

  const sessions = data.filter(d => d.session);
  const zone2Sessions = sessions.filter(d => d.session?.zone2);
  const z2Pct = sessions.length > 0 ? Math.round((zone2Sessions.length / sessions.length) * 100) : 0;

  return (
    <div style={s.wrapper}>
      <div style={s.header}>SESSION HISTORY — LAST 7 DAYS</div>

      {data.length === 0 && (
        <div style={{ fontSize: "10px", color: tokens.textMuted, textAlign: "center", padding: "20px" }}>
          No sessions logged yet
        </div>
      )}

      {[...data].reverse().map((entry) => (
        <div key={entry.date} style={s.row}>
          <div style={s.dayCol}>{entry.day}</div>

          <div style={s.mainCol}>
            {entry.session ? (
              <>
                <div style={s.sessionLine}>
                  <span style={s.icon(entry.session.type)}>
                    {disciplineIcon(entry.session.type)}
                  </span>
                  <span style={s.sessionName(entry.session.type)}>
                    {entry.session.name}
                  </span>
                  {entry.session.duration_mins && (
                    <span style={s.duration}>{entry.session.duration_mins}min</span>
                  )}
                  <HRBadge avgHR={entry.session.avg_hr} zone2={entry.session.zone2} />
                </div>
                <div style={s.meta}>
                  {entry.session.brother_session && (
                    <span style={s.brotherTag}>👥 BROTHER</span>
                  )}
                  {entry.water_fear_level && (
                    <span style={s.fearTag(entry.water_fear_level)}>
                      FEAR {entry.water_fear_level}/10
                    </span>
                  )}
                  {entry.workday_load && (
                    <span style={s.calTag}>
                      LOAD {entry.workday_load}/10
                      <LoadDot value={entry.workday_load} />
                    </span>
                  )}
                  {entry.calories_consumed && (
                    <span style={s.calTag}>{entry.calories_consumed.toLocaleString()} kcal</span>
                  )}
                </div>
              </>
            ) : (
              <div style={s.restLabel}>
                — rest
                {entry.workday_load && (
                  <span style={{ marginLeft: "8px", fontSize: "8px", color: tokens.textMuted }}>
                    load {entry.workday_load}/10
                    <LoadDot value={entry.workday_load} />
                  </span>
                )}
              </div>
            )}
          </div>

          <div style={{ ...s.rightCol, fontSize: "9px", color: tokens.textMuted, fontFamily: tokens.fontMono }}>
            {new Date(entry.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
          </div>
        </div>
      ))}

      {/* Week summary */}
      {data.length > 0 && (
        <div style={s.summary}>
          <div style={s.summaryItem}>
            <span style={{ ...s.summaryVal, color: scoreColor(sessions.length >= 5 ? 80 : sessions.length >= 3 ? 55 : 30) }}>
              {sessions.length}
            </span>
            SESSIONS
          </div>
          <div style={s.summaryItem}>
            <span style={{ ...s.summaryVal, color: scoreColor(z2Pct) }}>
              {z2Pct}%
            </span>
            ZONE 2
          </div>
          <div style={s.summaryItem}>
            <span style={{ ...s.summaryVal, color: tokens.textPrimary }}>
              {data.filter(d => d.water_fear_level).length > 0
                ? Math.round(data.filter(d => d.water_fear_level).reduce((s, d) => s + d.water_fear_level, 0) / data.filter(d => d.water_fear_level).length * 10) / 10
                : "—"
              }
            </span>
            AVG FEAR
          </div>
        </div>
      )}
    </div>
  );
}
