/**
 * EventTracker.jsx — Horizontal event cards showing phase progress.
 *
 * Props:
 *   checkpoints: array from GET /api/checkpoints
 *   [{ name, date, purpose, days_until, readiness_score }]
 *
 * Phase durations are hardcoded from training_plan.py:
 *   Marathon   May 12 → Jul 18  (67 days)
 *   Melaka     Jul 19 → Aug 30  (43 days)
 *   Bintan     Aug 30 → Oct 12  (44 days)
 *   HIM        Oct 13 → Nov 21  (40 days)
 */

import { tokens, scoreColor } from "../lib/design";

const EVENT_CONFIG = {
  marathon: {
    abbrev:     "MARATHON",
    color:      tokens.blue,
    phaseStart: new Date(2026, 4, 12),   // May 12
    phaseEnd:   new Date(2026, 6, 18),   // Jul 18
  },
  melaka: {
    abbrev:     "MELAKA TRI",
    color:      tokens.gold,
    phaseStart: new Date(2026, 6, 19),   // Jul 19
    phaseEnd:   new Date(2026, 7, 30),   // Aug 30
  },
  bintan: {
    abbrev:     "BINTAN TRI",
    color:      tokens.green,
    phaseStart: new Date(2026, 7, 30),   // Aug 30
    phaseEnd:   new Date(2026, 9, 12),   // Oct 12
  },
  him: {
    abbrev:     "HALF IRONMAN",
    color:      tokens.red,
    phaseStart: new Date(2026, 9, 13),   // Oct 13
    phaseEnd:   new Date(2026, 10, 21),  // Nov 21
  },
};

function resolveConfig(name) {
  const n = name.toLowerCase();
  if (n.includes("marathon"))                     return EVENT_CONFIG.marathon;
  if (n.includes("melaka"))                       return EVENT_CONFIG.melaka;
  if (n.includes("bintan"))                       return EVENT_CONFIG.bintan;
  if (n.includes("ironman") || n.includes("him")) return EVENT_CONFIG.him;
  return null;
}

const DAY_MS = 86_400_000;

export default function EventTracker({ checkpoints = [] }) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  return (
    <div style={{
      display: "flex",
      gap: "8px",
      overflowX: "auto",
      paddingBottom: "4px",
      marginBottom: "8px",
      WebkitOverflowScrolling: "touch",
      scrollbarWidth: "none",
      msOverflowStyle: "none",
    }}>
      {checkpoints.map((event) => {
        const cfg = resolveConfig(event.name);
        if (!cfg) return null;

        const { abbrev, color, phaseStart, phaseEnd } = cfg;

        const phaseDays = Math.max(1, (phaseEnd - phaseStart) / DAY_MS);
        const elapsed   = Math.max(0, Math.min((today - phaseStart) / DAY_MS, phaseDays));
        const phasePct  = elapsed / phaseDays;

        const daysColor =
          event.days_until <= 14 ? tokens.red  :
          event.days_until <= 30 ? tokens.gold :
          tokens.textPrimary;

        return (
          <div
            key={event.name}
            style={{
              width:        "140px",
              minWidth:     "140px",
              height:       "120px",
              flexShrink:   0,
              boxSizing:    "border-box",
              background:   tokens.bgHover,
              borderTop:    `3px solid ${color}`,
              borderRight:  `1px solid ${tokens.border}`,
              borderBottom: `1px solid ${tokens.border}`,
              borderLeft:   `1px solid ${tokens.border}`,
              borderRadius: tokens.radiusMd,
              padding:      "12px 12px 12px",
              display:      "flex",
              flexDirection:"column",
              justifyContent: "space-between",
            }}
          >
            {/* ── Top: days count + event name ── */}
            <div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "4px", marginBottom: "4px" }}>
                <span style={{
                  fontFamily: tokens.fontDisplay,
                  fontSize:   "28px",
                  fontWeight: 700,
                  color:      daysColor,
                  lineHeight: 1,
                }}>
                  {event.days_until}
                </span>
                <span style={{
                  fontSize:      "7px",
                  color:         tokens.textMuted,
                  fontFamily:    tokens.fontMono,
                  letterSpacing: "1px",
                }}>
                  DAYS
                </span>
              </div>

              <div style={{
                fontSize:      "8px",
                fontFamily:    tokens.fontMono,
                color,
                letterSpacing: "0.8px",
                fontWeight:    500,
              }}>
                {abbrev}
              </div>
            </div>

            {/* ── Bottom: phase bar + readiness + purpose ── */}
            <div>
              {/* Phase progress */}
              <div style={{
                fontSize:      "7px",
                color:         tokens.textMuted,
                fontFamily:    tokens.fontMono,
                letterSpacing: "0.5px",
                marginBottom:  "3px",
              }}>
                PHASE {Math.round(phasePct * 100)}%
              </div>
              <div style={{
                height:       "3px",
                background:   tokens.border,
                borderRadius: "2px",
                overflow:     "hidden",
                marginBottom: "7px",
              }}>
                <div style={{
                  height:       "100%",
                  width:        `${phasePct * 100}%`,
                  background:   color,
                  borderRadius: "2px",
                }} />
              </div>

              {/* Readiness */}
              <div style={{
                fontSize:      "7px",
                fontFamily:    tokens.fontMono,
                letterSpacing: "0.5px",
                color: event.readiness_score != null
                  ? scoreColor(event.readiness_score)
                  : tokens.textMuted,
                marginBottom: "4px",
              }}>
                {event.readiness_score != null
                  ? `READINESS ${event.readiness_score}%`
                  : "READINESS —"}
              </div>

              {/* Purpose — one line, clipped */}
              <div style={{
                fontSize:           "8px",
                color:              tokens.textMuted,
                fontFamily:         tokens.fontMono,
                lineHeight:         1.3,
                overflow:           "hidden",
                display:            "-webkit-box",
                WebkitLineClamp:    1,
                WebkitBoxOrient:    "vertical",
              }}>
                {event.purpose}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
