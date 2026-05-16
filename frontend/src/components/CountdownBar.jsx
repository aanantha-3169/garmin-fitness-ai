/**
 * CountdownBar.jsx — Days until each checkpoint event
 *
 * Props:
 *   checkpoints: array from GET /api/checkpoints
 *   [
 *     { name, date, type, purpose, days_until, readiness_score }
 *   ]
 */

import { tokens, scoreColor } from "../lib/design";

export default function CountdownBar({ checkpoints = [] }) {
  const s = {
    bar: {
      display: "grid",
      gridTemplateColumns: `repeat(${checkpoints.length || 3}, 1fr)`,
      background: tokens.bgCard,
      borderBottom: `1px solid ${tokens.border}`,
    },
    cell: (i, total) => ({
      padding: "12px 18px",
      borderRight: i < total - 1 ? `1px solid ${tokens.border}` : "none",
      position: "relative",
    }),
    days: (score) => ({
      fontFamily: tokens.fontDisplay,
      fontSize: "clamp(22px, 4vw, 32px)",
      fontWeight: 700,
      color: scoreColor(score),
      lineHeight: 1,
    }),
    daysLabel: {
      fontSize: "8px",
      letterSpacing: "2px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      marginTop: "1px",
    },
    name: {
      fontFamily: tokens.fontDisplay,
      fontSize: "10px",
      fontWeight: 600,
      color: tokens.textPrimary,
      marginTop: "6px",
      marginBottom: "2px",
      letterSpacing: "0.5px",
    },
    purpose: {
      fontSize: "8px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      lineHeight: 1.5,
    },
    readinessBadge: (score) => ({
      display: "inline-block",
      marginTop: "6px",
      padding: "2px 6px",
      fontSize: "8px",
      letterSpacing: "1px",
      fontFamily: tokens.fontMono,
      borderRadius: tokens.radiusSm,
      background: score >= 70 ? "#0D1F0D" : score >= 50 ? "#1a1200" : "#1F0D0D",
      color: scoreColor(score),
      border: `1px solid ${scoreColor(score)}22`,
    }),
  };

  if (!checkpoints.length) {
    return (
      <div style={s.bar}>
        {[
          { name: "Score Marathon",   date: "2026-07-19", purpose: "Running fitness benchmark",         readiness_score: null },
          { name: "Melaka Triathlon", date: "2026-08-30", purpose: "First full triathlon experience",    readiness_score: null },
          { name: "Bintan Triathlon", date: "2026-10-12", purpose: "Full triathlon dress rehearsal",     readiness_score: null },
          { name: "Half Ironman",     date: "2026-11-21", purpose: "The endpoint",                       readiness_score: null },
        ].map((e, i) => {
          const days = Math.ceil((new Date(e.date) - new Date()) / 86400000);
          return (
            <div key={e.name} style={s.cell(i, 3)}>
              <div style={s.days(e.readiness_score)}>{days}</div>
              <div style={s.daysLabel}>DAYS</div>
              <div style={s.name}>{e.name.toUpperCase()}</div>
              <div style={s.purpose}>{e.purpose}</div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div style={s.bar}>
      {checkpoints.map((event, i) => (
        <div key={event.name} style={s.cell(i, checkpoints.length)}>
          <div style={s.days(event.readiness_score)}>{event.days_until}</div>
          <div style={s.daysLabel}>DAYS</div>
          <div style={s.name}>{event.name.toUpperCase()}</div>
          <div style={s.purpose}>{event.purpose}</div>
          {event.readiness_score != null ? (
            <div style={s.readinessBadge(event.readiness_score)}>
              READINESS {event.readiness_score}%
            </div>
          ) : (
            <div style={s.readinessBadge(0)}>
              READINESS —
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
