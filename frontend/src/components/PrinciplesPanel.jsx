/**
 * PrinciplesPanel.jsx — Static display of the four training principles
 * and athlete baseline stats.
 *
 * Props:
 *   stats: object from GET /api/stats (optional)
 *   {
 *     vo2_max, vo2_max_category, vo2_max_percentile,
 *     ftp_w_kg, ftp_category,
 *     swim_pace_100m, run_5k_predicted, run_half_predicted,
 *     zone2_hr_low, zone2_hr_high, last_updated
 *   }
 */

import { tokens, scoreColor, card, sectionLabel } from "../lib/design";

const PRINCIPLES = [
  {
    num: "01",
    title: "Zone 2 Sanctuary",
    desc: "80-90% of training is strictly Zone 2 (115-145 bpm). The pool, bike, and road are moving meditation — not battlefields. Training must give structural energy, not extract it.",
    color: tokens.blue,
    icon: "🌊",
  },
  {
    num: "02",
    title: "Life Load First",
    desc: "This athlete navigates maximum life weight. Code wins. Family wins. Training is third. If a session leaves him too depleted to write code or sit with family, the prescription has failed.",
    color: tokens.gold,
    icon: "⚖️",
  },
  {
    num: "03",
    title: "No Ego Racing",
    desc: "Checkpoints exist to confront fear, explore on the bike, and build discipline — not to perform for anyone. There is no target finish time. There is no competition.",
    color: tokens.green,
    icon: "🎯",
  },
  {
    num: "04",
    title: "Bloodline Anchor",
    desc: "Align cycling with brother's schedule whenever possible. This race is a vehicle to rebuild a two-year gap through shared physical momentum. The relationship is a primary purpose.",
    color: "#9B7FD4",
    icon: "👥",
  },
];

const CHECKPOINTS = [
  { name: "Aquaman Langkawi", date: "2026-07-25", what: "2km ocean swim", why: "Fear confrontation" },
  { name: "Bintan Triathlon", date: "2026-10-12", what: "Sprint triathlon", why: "Dress rehearsal" },
  { name: "Half Ironman", date: "2026-11-21", what: "1.9km / 90km / 21km", why: "The endpoint" },
];

const SOURCES = [
  "80/20 Triathlon — Matt Fitzgerald (Zone 2 polarization)",
  "Jack Daniels VDOT — Run pacing from VO2 Max",
  "Coggan/Allen — TSS and FTP power zones",
  "Luuc Muis — Half Ironman readiness model",
  "Swim Smooth — CSS method (Critical Swim Speed)",
];

export default function PrinciplesPanel({ stats }) {
  const s = {
    principleCard: {
      display: "flex",
      gap: "14px",
      padding: "14px 0",
      borderBottom: `1px solid ${tokens.border}`,
      alignItems: "flex-start",
    },
    principleNum: (color) => ({
      fontFamily: "'Sora', sans-serif",
      fontSize: "24px",
      fontWeight: 700,
      color,
      lineHeight: 1,
      flexShrink: 0,
      width: "36px",
    }),
    principleIcon: { fontSize: "18px", flexShrink: 0, paddingTop: "2px" },
    principleTitle: {
      fontFamily: "'Sora', sans-serif",
      fontSize: "12px",
      fontWeight: 600,
      color: tokens.textPrimary,
      marginBottom: "5px",
      letterSpacing: "0.5px",
    },
    principleDesc: {
      fontSize: "10px",
      color: tokens.textMuted,
      lineHeight: 1.8,
      fontFamily: tokens.fontMono,
    },

    statGrid: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: "6px",
      marginBottom: "0",
    },
    statItem: {
      background: tokens.bg,
      border: `1px solid ${tokens.border}`,
      borderRadius: tokens.radiusSm,
      padding: "10px 12px",
    },
    statLabel: {
      fontSize: "8px",
      letterSpacing: "2px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      marginBottom: "4px",
    },
    statValue: (color) => ({
      fontFamily: "'Sora', sans-serif",
      fontSize: "20px",
      fontWeight: 700,
      color: color || tokens.textPrimary,
      lineHeight: 1,
    }),
    statSub: {
      fontSize: "8px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      marginTop: "2px",
    },

    checkRow: {
      display: "flex",
      gap: "12px",
      padding: "10px 0",
      borderBottom: `1px solid ${tokens.border}`,
      alignItems: "center",
    },
    checkDate: {
      width: "60px",
      flexShrink: 0,
      fontSize: "9px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
    },
    checkName: {
      fontSize: "11px",
      color: tokens.textPrimary,
      fontFamily: tokens.fontMono,
    },
    checkMeta: {
      fontSize: "8px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      marginTop: "1px",
    },
    checkWhy: {
      marginLeft: "auto",
      fontSize: "8px",
      padding: "2px 6px",
      borderRadius: "2px",
      background: "#0F0C00",
      color: tokens.gold,
      border: `1px solid #2a1a00`,
      fontFamily: tokens.fontMono,
      flexShrink: 0,
    },

    sourceItem: {
      fontSize: "9px",
      color: tokens.textMuted,
      padding: "5px 0",
      borderBottom: `1px solid ${tokens.border}`,
      fontFamily: tokens.fontMono,
      letterSpacing: "0.3px",
    },
    formulaBox: {
      fontSize: "8px",
      color: "#2a2a2a",
      marginTop: "10px",
      lineHeight: 2,
      fontFamily: tokens.fontMono,
    },
  };

  return (
    <div>
      {/* Baseline Stats */}
      {stats && (
        <div style={card}>
          <div style={{ ...sectionLabel }}>BASELINE FITNESS</div>
          <div style={s.statGrid}>
            <div style={s.statItem}>
              <div style={s.statLabel}>VO2 MAX</div>
              <div style={s.statValue(tokens.green)}>{stats.vo2_max}</div>
              <div style={s.statSub}>{stats.vo2_max_category} · {stats.vo2_max_percentile}</div>
            </div>
            <div style={s.statItem}>
              <div style={s.statLabel}>FTP (W/KG)</div>
              <div style={s.statValue(tokens.red)}>{stats.ftp_w_kg}</div>
              <div style={s.statSub}>{stats.ftp_category} — critical gap</div>
            </div>
            <div style={s.statItem}>
              <div style={s.statLabel}>SWIM PACE</div>
              <div style={s.statValue()}>{stats.swim_pace_100m}</div>
              <div style={s.statSub}>/100m pool avg</div>
            </div>
            <div style={s.statItem}>
              <div style={s.statLabel}>RUN 5K PREDICTED</div>
              <div style={s.statValue()}>{stats.run_5k_predicted}</div>
              <div style={s.statSub}>VDOT ~44</div>
            </div>
          </div>
          <div style={{ ...s.statItem, marginTop: "6px" }}>
            <div style={s.statLabel}>ZONE 2 WINDOW</div>
            <div style={{ fontFamily: "'Sora', sans-serif", fontSize: "18px", fontWeight: 700, color: tokens.blue }}>
              {stats.zone2_hr_low}–{stats.zone2_hr_high} <span style={{ fontSize: "11px", color: tokens.textMuted }}>bpm</span>
            </div>
            <div style={s.statSub}>60-76% HRmax · Primary training zone</div>
          </div>
        </div>
      )}

      {/* The Four Principles */}
      <div style={card}>
        <div style={sectionLabel}>THE FOUR PRINCIPLES</div>
        {PRINCIPLES.map((p) => (
          <div key={p.num} style={s.principleCard}>
            <div style={s.principleNum(p.color)}>{p.num}</div>
            <div style={s.principleIcon}>{p.icon}</div>
            <div>
              <div style={s.principleTitle}>{p.title}</div>
              <div style={s.principleDesc}>{p.desc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Checkpoint Map */}
      <div style={card}>
        <div style={sectionLabel}>CHECKPOINT MAP</div>
        {CHECKPOINTS.map((c) => {
          const days = Math.ceil((new Date(c.date) - new Date()) / 86400000);
          return (
            <div key={c.name} style={s.checkRow}>
              <div style={s.checkDate}>
                <div style={{ fontFamily: "'Sora', sans-serif", fontSize: "20px", fontWeight: 700, color: tokens.gold, lineHeight: 1 }}>{days}</div>
                <div style={{ fontSize: "7px", color: tokens.textMuted, letterSpacing: "1px" }}>DAYS</div>
              </div>
              <div>
                <div style={s.checkName}>{c.name}</div>
                <div style={s.checkMeta}>{c.what}</div>
              </div>
              <div style={s.checkWhy}>{c.why}</div>
            </div>
          );
        })}
      </div>

      {/* Methodology */}
      <div style={card}>
        <div style={sectionLabel}>METHODOLOGY SOURCES</div>
        {SOURCES.map((src) => (
          <div key={src} style={s.sourceItem}>· {src}</div>
        ))}
        <div style={s.formulaBox}>
          PROBABILITY = (Zone2% × 0.25) + (Consistency% × 0.25) + (LifeLoad% × 0.25) + (SwimFreq% × 0.25)<br />
          Window: last 14 days · Zone 2 = 115-145 bpm · Targets: 7 sessions, 4 swims per 2 weeks
        </div>
      </div>
    </div>
  );
}
