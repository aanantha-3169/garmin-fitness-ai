/**
 * TodayPanel.jsx — Today's readiness, planned session, nutrition, and Garmin metrics
 *
 * Props:
 *   data: object from GET /api/today
 *   {
 *     date,
 *     garmin: { body_battery, hrv_status, hrv_overnight_avg, sleep_score,
 *                sleep_quality, resting_heart_rate_bpm, stress_avg },
 *     nutrition: { consumed_calories, target_calories, consumed_protein_g,
 *                  consumed_carbs_g, consumed_fats_g, meal_count },
 *     session: { planned_name, discipline, duration_mins, hr_target_low,
 *                hr_target_high, description, is_completed, is_rest_day },
 *     readiness: { recommended_action, adjustment_needed, principle_violations,
 *                  philosophical_reflection },
 *     water_fear_level,
 *     workday_load,
 *   }
 */

import {
  tokens, scoreColor, calorieColor, disciplineColor,
  disciplineIcon, card, sectionLabel
} from "../lib/design";

function MetricTile({ label, value, unit = "", color }) {
  return (
    <div style={{
      background: tokens.bg,
      border: `1px solid ${tokens.border}`,
      borderRadius: tokens.radiusSm,
      padding: "10px 12px",
      flex: 1,
    }}>
      <div style={{ fontSize: "8px", letterSpacing: "2px", color: tokens.textMuted, fontFamily: tokens.fontMono, marginBottom: "4px" }}>
        {label}
      </div>
      <div style={{ fontFamily: "'Sora', sans-serif", fontSize: "22px", fontWeight: 700, color: color || tokens.textPrimary, lineHeight: 1 }}>
        {value ?? "—"}
        {unit && <span style={{ fontSize: "11px", color: tokens.textMuted, marginLeft: "2px" }}>{unit}</span>}
      </div>
    </div>
  );
}

function SliderBar({ value, max = 10, color, label }) {
  const pct = (value / max) * 100;
  return (
    <div style={{ marginBottom: "8px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", color: tokens.textMuted, fontFamily: tokens.fontMono, marginBottom: "3px" }}>
        <span>{label}</span>
        <span style={{ color }}>{value}/{max}</span>
      </div>
      <div style={{ height: "3px", background: tokens.border, borderRadius: "2px", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: "2px", transition: "width 0.6s ease" }} />
      </div>
    </div>
  );
}

export default function TodayPanel({ data }) {
  const garmin = data?.garmin || {};
  const nutrition = data?.nutrition || {};
  const session = data?.session || {};
  const readiness = data?.readiness || {};
  const fearLevel = data?.water_fear_level;
  const workdayLoad = data?.workday_load;

  const calPct = nutrition.consumed_calories && nutrition.target_calories
    ? (nutrition.consumed_calories / nutrition.target_calories) * 100 : 0;
  const calColor = calorieColor(nutrition.consumed_calories, nutrition.target_calories);

  const batteryColor = garmin.body_battery >= 60 ? tokens.green : garmin.body_battery >= 30 ? tokens.gold : tokens.red;
  const sleepColor = garmin.sleep_score >= 70 ? tokens.green : garmin.sleep_score >= 55 ? tokens.gold : tokens.red;
  const stressColor = garmin.stress_avg <= 30 ? tokens.green : garmin.stress_avg <= 50 ? tokens.gold : tokens.red;
  const loadColor = workdayLoad <= 4 ? tokens.green : workdayLoad <= 7 ? tokens.gold : tokens.red;
  const fearColor = fearLevel <= 3 ? tokens.green : fearLevel <= 6 ? tokens.gold : tokens.red;

  const s = {
    grid2: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "8px" },
    grid4: { display: "flex", gap: "6px", marginBottom: "8px", flexWrap: "wrap" },

    sessionCard: {
      background: session.is_completed ? "#0D1F0D" : session.is_rest_day ? tokens.bg : "#0A0F1A",
      border: `1px solid ${session.is_completed ? tokens.greenBorder : session.is_rest_day ? tokens.border : "#1a2a3a"}`,
      borderRadius: tokens.radiusMd,
      padding: "14px",
      marginBottom: "8px",
    },
    sessionHeader: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" },
    sessionName: {
      fontFamily: "'Sora', sans-serif",
      fontSize: "16px",
      fontWeight: 700,
      color: disciplineColor(session.discipline),
      letterSpacing: "1px",
    },
    sessionBadge: {
      fontSize: "9px",
      padding: "3px 8px",
      borderRadius: tokens.radiusSm,
      fontFamily: tokens.fontMono,
      background: session.is_completed ? "#0D1F0D" : "#111",
      color: session.is_completed ? tokens.green : tokens.textMuted,
      border: `1px solid ${session.is_completed ? tokens.greenBorder : tokens.border}`,
    },
    sessionMeta: { display: "flex", gap: "12px", fontSize: "10px", color: tokens.textSecondary, fontFamily: tokens.fontMono, marginBottom: "8px" },
    sessionDesc: { fontSize: "10px", color: tokens.textMuted, lineHeight: 1.7, fontFamily: tokens.fontMono },
    hrTarget: {
      display: "inline-block",
      marginTop: "8px",
      padding: "4px 10px",
      background: "#0A150A",
      border: `1px solid ${tokens.greenBorder}`,
      borderRadius: tokens.radiusSm,
      fontSize: "10px",
      color: tokens.green,
      fontFamily: tokens.fontMono,
    },

    readinessCard: {
      ...card,
      background: readiness.adjustment_needed ? "#1A0D00" : tokens.bgCard,
      borderColor: readiness.adjustment_needed ? "#3a2000" : tokens.border,
    },
    readinessIcon: { fontSize: "12px", marginRight: "6px" },
    readinessAction: { fontSize: "11px", color: tokens.textPrimary, fontFamily: tokens.fontMono, lineHeight: 1.6 },
    violationItem: { fontSize: "9px", color: tokens.red, paddingTop: "4px", fontFamily: tokens.fontMono },
    reflection: {
      fontSize: "11px",
      color: tokens.gold,
      fontStyle: "italic",
      padding: "10px 12px",
      background: "#0F0C00",
      borderRadius: tokens.radiusSm,
      marginTop: "8px",
      lineHeight: 1.8,
      fontFamily: tokens.fontMono,
    },

    calBar: {
      height: "4px",
      background: tokens.border,
      borderRadius: "2px",
      overflow: "hidden",
      margin: "6px 0",
    },
    calFill: {
      height: "100%",
      width: `${Math.min(calPct, 100)}%`,
      background: calColor,
      borderRadius: "2px",
      transition: "width 0.8s ease",
    },
    macros: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr 1fr",
      gap: "4px",
      marginTop: "6px",
    },
    macroItem: {
      fontSize: "9px",
      color: tokens.textMuted,
      fontFamily: tokens.fontMono,
      textAlign: "center",
    },
    macroVal: {
      fontFamily: "'Sora', sans-serif",
      fontSize: "15px",
      fontWeight: 600,
      color: tokens.textPrimary,
      display: "block",
    },
  };

  return (
    <div>
      {/* Garmin Metrics Row */}
      <div style={{ ...sectionLabel, marginBottom: "8px" }}>GARMIN · TODAY</div>
      <div style={s.grid4}>
        <MetricTile label="BODY BATTERY" value={garmin.body_battery} color={batteryColor} />
        <MetricTile label="SLEEP SCORE" value={garmin.sleep_score} color={sleepColor} />
        <MetricTile label="RHR" value={garmin.resting_heart_rate_bpm} unit="bpm" />
        <MetricTile label="AVG STRESS" value={garmin.stress_avg} color={stressColor} />
      </div>

      {/* HRV */}
      <div style={{ ...card, display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px" }}>
        <div>
          <div style={{ fontSize: "8px", letterSpacing: "2px", color: tokens.textMuted, fontFamily: tokens.fontMono }}>HRV STATUS</div>
          <div style={{ fontSize: "13px", color: tokens.textPrimary, fontFamily: "'Sora', sans-serif", fontWeight: 600, marginTop: "2px" }}>
            {garmin.hrv_status || "—"}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "8px", letterSpacing: "2px", color: tokens.textMuted, fontFamily: tokens.fontMono }}>OVERNIGHT AVG</div>
          <div style={{ fontFamily: "'Sora', sans-serif", fontSize: "22px", fontWeight: 700, color: tokens.textPrimary }}>
            {garmin.hrv_overnight_avg || "—"}
          </div>
        </div>
      </div>

      {/* Life load indicators */}
      <div style={{ ...card, padding: "12px 14px" }}>
        <div style={{ ...sectionLabel, marginBottom: "10px" }}>LIFE LOAD</div>
        {workdayLoad !== undefined && (
          <SliderBar value={workdayLoad} label="WORKDAY LOAD" color={loadColor} />
        )}
        {fearLevel !== undefined && (
          <SliderBar value={fearLevel} label="WATER FEAR LEVEL" color={fearColor} />
        )}
      </div>

      {/* Today's Session */}
      <div style={{ ...sectionLabel, marginBottom: "8px" }}>TODAY'S SESSION</div>
      <div style={s.sessionCard}>
        <div style={s.sessionHeader}>
          <div style={s.sessionName}>
            {disciplineIcon(session.discipline)} {session.planned_name || "Rest Day"}
          </div>
          <span style={s.sessionBadge}>
            {session.is_completed ? "✓ DONE" : session.is_rest_day ? "REST" : "PENDING"}
          </span>
        </div>
        {!session.is_rest_day && (
          <>
            <div style={s.sessionMeta}>
              {session.duration_mins && <span>{session.duration_mins} MIN</span>}
              {session.discipline && <span>{session.discipline.toUpperCase()}</span>}
            </div>
            {session.description && (
              <div style={s.sessionDesc}>{session.description}</div>
            )}
            {session.hr_target_low && (
              <div style={s.hrTarget}>
                HR TARGET: {session.hr_target_low}–{session.hr_target_high} bpm (Zone 2)
              </div>
            )}
          </>
        )}
      </div>

      {/* Readiness Decision */}
      {readiness.recommended_action && (
        <div style={s.readinessCard}>
          <div style={{ ...sectionLabel, marginBottom: "8px" }}>AI READINESS DECISION</div>
          <div style={s.readinessAction}>
            <span style={s.readinessIcon}>{readiness.adjustment_needed ? "⚠️" : "✅"}</span>
            {readiness.recommended_action}
          </div>
          {readiness.principle_violations?.map((v, i) => (
            <div key={i} style={s.violationItem}>⚑ {v}</div>
          ))}
          {readiness.philosophical_reflection && (
            <div style={s.reflection}>{readiness.philosophical_reflection}</div>
          )}
        </div>
      )}

      {/* Nutrition */}
      <div style={card}>
        <div style={{ ...sectionLabel, marginBottom: "10px" }}>NUTRITION · TODAY</div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", fontFamily: tokens.fontMono }}>
          <span style={{ color: tokens.textSecondary }}>{nutrition.meal_count || 0} meals</span>
          <span style={{ color: calColor }}>
            <strong>{(nutrition.consumed_calories || 0).toLocaleString()}</strong>
            <span style={{ color: tokens.textMuted }}> / {(nutrition.target_calories || 0).toLocaleString()} kcal</span>
          </span>
        </div>
        <div style={s.calBar}><div style={s.calFill} /></div>
        <div style={s.macros}>
          {[
            { label: "PROTEIN", val: nutrition.consumed_protein_g, unit: "g" },
            { label: "CARBS", val: nutrition.consumed_carbs_g, unit: "g" },
            { label: "FATS", val: nutrition.consumed_fats_g, unit: "g" },
          ].map(({ label, val, unit }) => (
            <div key={label} style={s.macroItem}>
              <span style={s.macroVal}>{val ?? "—"}<span style={{ fontSize: "9px" }}>{unit}</span></span>
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
