/**
 * ProbabilityPanel.jsx — Goal probability score + component breakdown
 *
 * Props:
 *   data: object from GET /api/probability
 *   {
 *     overall_score: number,
 *     components: {
 *       zone2_compliance: { score, note },
 *       consistency: { score, note },
 *       life_load_buffer: { score, note },
 *       swim_frequency: { score, note },
 *     },
 *     trend_30d: [{ date, score }]
 *   }
 */

import { tokens, scoreColor, card, sectionLabel } from "../lib/design";

const COMPONENTS = [
  { key: "zone2_compliance", label: "Zone 2 Compliance", weight: 25 },
  { key: "consistency", label: "Training Consistency", weight: 25 },
  { key: "life_load_buffer", label: "Life Load Buffer", weight: 25 },
  { key: "swim_frequency", label: "Swim Frequency", weight: 25 },
];

export default function ProbabilityPanel({ data }) {
  const score = data?.overall_score ?? 50;
  const components = data?.components ?? {};
  const trend = data?.trend_30d ?? [];
  const color = scoreColor(score);

  const s = {
    wrapper: { ...card, padding: "0" },

    header: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "flex-start",
      padding: "14px 16px 12px",
      borderBottom: `1px solid ${tokens.border}`,
    },
    headerLeft: {},
    label: { ...sectionLabel, marginBottom: "4px", paddingBottom: 0, borderBottom: "none" },
    subLabel: {
      fontSize: "9px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      letterSpacing: "1px",
    },
    scoreBlock: { textAlign: "right" },
    scoreNum: {
      fontFamily: tokens.fontDisplay,
      fontSize: "52px",
      fontWeight: 700,
      lineHeight: 1,
      color,
      transition: "color 0.4s ease",
    },
    scorePct: { fontSize: "20px", color: tokens.textMuted },
    scoreLabel: {
      fontSize: "8px",
      letterSpacing: "3px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      marginTop: "2px",
    },

    bars: { padding: "14px 16px" },
    barRow: { marginBottom: "12px" },
    barTop: {
      display: "flex",
      justifyContent: "space-between",
      fontSize: "9px",
      color: tokens.textSecondary,
      marginBottom: "4px",
      fontFamily: tokens.fontMono,
    },
    barScore: (s) => ({ color: scoreColor(s) }),
    barTrack: {
      height: "3px",
      background: tokens.border,
      borderRadius: "2px",
      overflow: "hidden",
    },
    barFill: (s) => ({
      height: "100%",
      width: `${s}%`,
      background: scoreColor(s),
      borderRadius: "2px",
      transition: "width 0.8s ease",
    }),
    barNote: {
      fontSize: "8px",
      color: tokens.textMuted,
      marginTop: "2px",
      fontFamily: tokens.fontMono,
    },

    trend: {
      padding: "0 16px 14px",
      borderTop: `1px solid ${tokens.border}`,
      paddingTop: "12px",
    },
    trendLabel: {
      fontSize: "8px",
      letterSpacing: "2px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      marginBottom: "8px",
    },
    trendChart: {
      display: "flex",
      alignItems: "flex-end",
      gap: "3px",
      height: "36px",
    },
    trendBar: (s, isLast) => ({
      flex: 1,
      height: `${Math.max(4, (s / 100) * 36)}px`,
      background: isLast ? scoreColor(s) : `${scoreColor(s)}55`,
      borderRadius: "1px",
      transition: "height 0.6s ease",
    }),
    formula: {
      fontSize: "8px",
      color: tokens.textDead,
      fontFamily: tokens.fontMono,
      marginTop: "10px",
      lineHeight: 1.8,
      borderTop: `1px solid ${tokens.border}`,
      paddingTop: "8px",
    },
  };

  return (
    <div style={s.wrapper}>
      {/* Header */}
      <div style={s.header}>
        <div style={s.headerLeft}>
          <div style={s.label}>GOAL PROBABILITY</div>
          <div style={s.subLabel}>HALF IRONMAN · NOV 2026</div>
        </div>
        <div style={s.scoreBlock}>
          <span style={s.scoreNum}>{score}</span>
          <span style={s.scorePct}>%</span>
          <div style={s.scoreLabel}>COMPLETION LIKELIHOOD</div>
        </div>
      </div>

      {/* Component bars */}
      <div style={s.bars}>
        <div style={{ ...sectionLabel, marginBottom: "12px" }}>
          BREAKDOWN — TRANSPARENT FORMULA
        </div>
        {COMPONENTS.map(({ key, label, weight }) => {
          const comp = components[key] || { score: 50, note: "No data" };
          return (
            <div key={key} style={s.barRow}>
              <div style={s.barTop}>
                <span>{label}</span>
                <span style={s.barScore(comp.score)}>
                  {comp.score}/100 × {weight}%
                </span>
              </div>
              <div style={s.barTrack}>
                <div style={s.barFill(comp.score)} />
              </div>
              <div style={s.barNote}>{comp.note}</div>
            </div>
          );
        })}
      </div>

      {/* 30-day trend */}
      {trend.length > 0 && (
        <div style={s.trend}>
          <div style={s.trendLabel}>30-DAY TREND</div>
          <div style={s.trendChart}>
            {trend.map((point, i) => (
              <div
                key={point.date}
                style={s.trendBar(point.score, i === trend.length - 1)}
                title={`${point.date}: ${point.score}%`}
              />
            ))}
          </div>
          <div style={s.formula}>
            FORMULA: (Zone2% + Consistency% + LifeLoad% + SwimFreq%) ÷ 4<br />
            Calculated from last 14 days of logged data · Zone 2 = 115-145 bpm
          </div>
        </div>
      )}
    </div>
  );
}
