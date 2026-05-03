/**
 * TodayPanel.jsx — Today's readiness, planned session, nutrition, and Garmin metrics
 */

import {
  tokens, scoreColor, calorieColor, disciplineColor,
  disciplineIcon, card, sectionLabel
} from "../lib/design";

// ── Compact single-row Garmin vitals strip ────────────────────────────────────

function GarminStrip({ garmin }) {
  const batteryColor = garmin.body_battery >= 60 ? tokens.green
    : garmin.body_battery >= 30 ? tokens.gold : tokens.red;
  const sleepColor = garmin.sleep_score >= 70 ? tokens.green
    : garmin.sleep_score >= 55 ? tokens.gold : tokens.red;
  const stressColor = garmin.stress_avg <= 30 ? tokens.green
    : garmin.stress_avg <= 50 ? tokens.gold : tokens.red;

  const items = [
    { icon: "⚡", value: garmin.body_battery, color: batteryColor, label: "battery" },
    { icon: "😴", value: garmin.sleep_score,  color: sleepColor,   label: "sleep" },
    { icon: "♥",  value: garmin.resting_heart_rate_bpm, color: tokens.textPrimary, label: "rhr", unit: "bpm" },
    { icon: "~",  value: garmin.stress_avg,  color: stressColor,  label: "stress" },
  ];

  return (
    <div style={{
      ...card,
      padding: "10px 14px",
    }}>
      {/* Vitals row */}
      <div style={{ display: "flex", gap: "0", justifyContent: "space-between", marginBottom: "10px" }}>
        {items.map(({ icon, value, color, label, unit }) => (
          <div key={label} style={{ textAlign: "center", flex: 1 }}>
            <div style={{
              fontFamily: tokens.fontDisplay,
              fontSize: "24px",
              fontWeight: 700,
              color,
              lineHeight: 1,
            }}>
              {value ?? "—"}
            </div>
            <div style={{
              fontSize: "8px",
              color: tokens.textMuted,
              fontFamily: tokens.fontMono,
              letterSpacing: "1px",
              marginTop: "3px",
            }}>
              {icon} {label.toUpperCase()}{unit ? ` · ${unit}` : ""}
            </div>
          </div>
        ))}
      </div>

      {/* HRV row */}
      {garmin.hrv_status && (
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingTop: "8px",
          borderTop: `1px solid ${tokens.border}`,
        }}>
          <div>
            <div style={{ fontSize: "8px", letterSpacing: "1px", color: tokens.textMuted, fontFamily: tokens.fontMono }}>HRV</div>
            <div style={{ fontSize: "13px", fontWeight: 600, color: tokens.textPrimary, fontFamily: tokens.fontDisplay }}>
              {garmin.hrv_status}
            </div>
          </div>
          {garmin.hrv_overnight_avg && (
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "8px", letterSpacing: "1px", color: tokens.textMuted, fontFamily: tokens.fontMono }}>OVERNIGHT AVG</div>
              <div style={{ fontSize: "22px", fontWeight: 700, color: tokens.textPrimary, fontFamily: tokens.fontDisplay }}>
                {garmin.hrv_overnight_avg}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Session hero card ─────────────────────────────────────────────────────────

function SessionCard({ session }) {
  const isRest      = session.is_rest_day;
  const isCompleted = session.is_completed;
  const deviation   = session.deviation;
  const color       = disciplineColor(session.discipline);

  const badgeText = isCompleted
    ? (deviation ? "⚡ DIFF ACTIVITY" : "✓ DONE")
    : isRest ? "REST" : "PENDING";

  const badgeColor = isCompleted
    ? (deviation ? tokens.gold : tokens.green)
    : tokens.textMuted;

  const borderColor = isCompleted
    ? (deviation ? tokens.gold + "44" : tokens.greenBorder)
    : isRest ? tokens.border : "#1a2a3a";

  const bgColor = isCompleted
    ? (deviation ? "#1a1200" : tokens.greenDim)
    : isRest ? tokens.bg : "#08101a";

  return (
    <div style={{
      background: bgColor,
      border: `1px solid ${borderColor}`,
      borderRadius: tokens.radiusMd,
      padding: "16px",
      marginBottom: "10px",
    }}>
      {/* Header: name + badge */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "10px" }}>
        <div style={{
          fontFamily: tokens.fontDisplay,
          fontSize: "22px",
          fontWeight: 700,
          color: isRest ? tokens.textMuted : color,
          lineHeight: 1.1,
          flex: 1,
          paddingRight: "8px",
        }}>
          {disciplineIcon(session.discipline)} {session.planned_name || "Rest Day"}
        </div>
        <span style={{
          fontSize: "9px",
          padding: "3px 8px",
          borderRadius: tokens.radiusSm,
          fontFamily: tokens.fontMono,
          letterSpacing: "1px",
          whiteSpace: "nowrap",
          background: "transparent",
          color: badgeColor,
          border: `1px solid ${badgeColor}44`,
        }}>
          {badgeText}
        </span>
      </div>

      {/* Plan meta: duration + discipline */}
      {!isRest && (
        <div style={{
          display: "flex",
          gap: "12px",
          fontSize: "11px",
          color: tokens.textSecondary,
          fontFamily: tokens.fontMono,
          marginBottom: session.description ? "8px" : "0",
        }}>
          {session.duration_mins && <span>{session.duration_mins} MIN</span>}
          {session.discipline && <span>{session.discipline.toUpperCase()}</span>}
        </div>
      )}

      {/* Description */}
      {!isRest && session.description && (
        <div style={{
          fontSize: "11px",
          color: tokens.textMuted,
          lineHeight: 1.7,
          fontFamily: tokens.fontMono,
          marginBottom: "10px",
        }}>
          {session.description}
        </div>
      )}

      {/* HR target */}
      {!isRest && session.hr_target_low && (
        <div style={{
          display: "inline-block",
          padding: "5px 12px",
          background: "#08120a",
          border: `1px solid ${tokens.greenBorder}`,
          borderRadius: tokens.radiusSm,
          fontSize: "11px",
          color: tokens.green,
          fontFamily: tokens.fontMono,
          letterSpacing: "0.5px",
        }}>
          HR {session.hr_target_low}–{session.hr_target_high} bpm · Zone 2
        </div>
      )}

      {/* Completed activity strip */}
      {session.completed && (
        <div style={{
          marginTop: "12px",
          paddingTop: "12px",
          borderTop: `1px solid ${tokens.border}`,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}>
          <span style={{
            fontSize: "12px",
            fontFamily: tokens.fontMono,
            color: deviation ? tokens.gold : tokens.green,
          }}>
            {disciplineIcon(session.completed.activity_type)}{" "}
            {session.completed.activity_name || session.completed.activity_type?.toUpperCase()}
          </span>
          <span style={{ fontSize: "11px", fontFamily: tokens.fontMono, color: tokens.textSecondary }}>
            {[
              session.completed.duration_mins  ? `${session.completed.duration_mins}min`  : null,
              session.completed.avg_heart_rate ? `${session.completed.avg_heart_rate}bpm` : null,
            ].filter(Boolean).join(" · ")}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Life load (only renders when data exists) ─────────────────────────────────

function LifeLoadCard({ workdayLoad, fearLevel }) {
  const hasLoad = workdayLoad != null;
  const hasFear = fearLevel != null;
  if (!hasLoad && !hasFear) return null;

  const loadColor = workdayLoad <= 4 ? tokens.green : workdayLoad <= 7 ? tokens.gold : tokens.red;
  const fearColor = fearLevel  <= 3 ? tokens.green : fearLevel  <= 6 ? tokens.gold : tokens.red;

  function Bar({ value, max = 10, color, label }) {
    const pct = (value / max) * 100;
    return (
      <div style={{ marginBottom: hasFear && hasLoad ? "10px" : "0" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
          <span style={{ fontSize: "9px", color: tokens.textMuted, fontFamily: tokens.fontMono, letterSpacing: "1px" }}>{label}</span>
          <span style={{ fontSize: "14px", fontWeight: 700, color, fontFamily: tokens.fontDisplay }}>{value}<span style={{ fontSize: "9px", color: tokens.textMuted }}>/10</span></span>
        </div>
        <div style={{ height: "3px", background: tokens.border, borderRadius: "2px", overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: "2px", transition: "width 0.6s ease" }} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ ...card, padding: "12px 14px" }}>
      <div style={{ ...sectionLabel, marginBottom: "10px" }}>LIFE LOAD</div>
      {hasLoad && <Bar value={workdayLoad} color={loadColor} label="WORKDAY LOAD" />}
      {hasFear && <Bar value={fearLevel}   color={fearColor} label="WATER FEAR" />}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function TodayPanel({ data }) {
  const garmin    = data?.garmin    || {};
  const nutrition = data?.nutrition || {};
  const session   = data?.session   || {};
  const readiness = data?.readiness || {};

  const calPct  = nutrition.consumed_calories && nutrition.target_calories
    ? (nutrition.consumed_calories / nutrition.target_calories) * 100 : 0;
  const calColor = calorieColor(nutrition.consumed_calories, nutrition.target_calories);

  return (
    <div>
      {/* 1. Session — hero */}
      <div style={{ ...sectionLabel, marginBottom: "8px" }}>TODAY'S SESSION</div>
      <SessionCard session={session} />

      {/* 2. Garmin vitals — compact */}
      <div style={{ ...sectionLabel, marginBottom: "8px" }}>GARMIN · TODAY</div>
      <GarminStrip garmin={garmin} />

      {/* 3. AI readiness */}
      {readiness.recommended_action && (
        <>
          <div style={{ ...sectionLabel, marginBottom: "8px" }}>AI READINESS</div>
          <div style={{
            ...card,
            background: readiness.adjustment_needed ? "#1A0D00" : tokens.bgCard,
            borderColor: readiness.adjustment_needed ? "#3a2000" : tokens.border,
          }}>
            <div style={{ fontSize: "12px", color: tokens.textPrimary, fontFamily: tokens.fontMono, lineHeight: 1.7 }}>
              <span style={{ marginRight: "6px" }}>{readiness.adjustment_needed ? "⚠️" : "✅"}</span>
              {readiness.recommended_action}
            </div>
            {readiness.principle_violations?.map((v, i) => (
              <div key={i} style={{ fontSize: "9px", color: tokens.red, paddingTop: "4px", fontFamily: tokens.fontMono }}>⚑ {v}</div>
            ))}
            {readiness.philosophical_reflection && (
              <div style={{
                fontSize: "11px",
                color: tokens.gold,
                fontStyle: "italic",
                padding: "10px 12px",
                background: "#0F0C00",
                borderRadius: tokens.radiusSm,
                marginTop: "8px",
                lineHeight: 1.8,
                fontFamily: tokens.fontMono,
              }}>
                {readiness.philosophical_reflection}
              </div>
            )}
          </div>
        </>
      )}

      {/* 4. Life load — hidden when no data */}
      <LifeLoadCard workdayLoad={data?.workday_load} fearLevel={data?.water_fear_level} />

      {/* 5. Nutrition */}
      <div style={{ ...sectionLabel, marginBottom: "8px" }}>NUTRITION · TODAY</div>
      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "6px" }}>
          <span style={{ fontSize: "9px", color: tokens.textMuted, fontFamily: tokens.fontMono }}>
            {nutrition.meal_count || 0} MEALS
          </span>
          <span style={{ fontFamily: tokens.fontDisplay, fontSize: "20px", fontWeight: 700, color: calColor }}>
            {(nutrition.consumed_calories || 0).toLocaleString()}
            <span style={{ fontSize: "11px", color: tokens.textMuted, fontWeight: 400 }}>
              {" "}/ {(nutrition.target_calories || 0).toLocaleString()} kcal
            </span>
          </span>
        </div>
        <div style={{ height: "3px", background: tokens.border, borderRadius: "2px", overflow: "hidden", marginBottom: "10px" }}>
          <div style={{ height: "100%", width: `${Math.min(calPct, 100)}%`, background: calColor, borderRadius: "2px", transition: "width 0.8s ease" }} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "4px" }}>
          {[
            { label: "PROTEIN", val: nutrition.consumed_protein_g, unit: "g" },
            { label: "CARBS",   val: nutrition.consumed_carbs_g,   unit: "g" },
            { label: "FATS",    val: nutrition.consumed_fats_g,    unit: "g" },
          ].map(({ label, val, unit }) => (
            <div key={label} style={{ textAlign: "center" }}>
              <div style={{ fontFamily: tokens.fontDisplay, fontSize: "18px", fontWeight: 600, color: tokens.textPrimary }}>
                {val ?? "—"}<span style={{ fontSize: "9px", color: tokens.textMuted }}>{unit}</span>
              </div>
              <div style={{ fontSize: "8px", color: tokens.textMuted, fontFamily: tokens.fontMono, letterSpacing: "1px" }}>{label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
