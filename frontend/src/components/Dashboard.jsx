/**
 * Dashboard.jsx — Phone-first single-scroll layout.
 *
 * TODAY tab: Status Hero → Weekly Tracker → Event Strip →
 *            Garmin Row → HRV Card → AI Readiness Note
 * STATS / PLAN / CORE: existing child components unchanged.
 *
 * Navigation is bottom-bar only. Top bar is minimal (52px).
 * Training window countdown updates every 60 s independently.
 * Data refresh every 5 minutes.
 */

import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { tokens, disciplineIcon, loadFonts } from "../lib/design";
import ProbabilityPanel from "./ProbabilityPanel";
import SessionHistory from "./SessionHistory";
import TrainingPlan from "./TrainingPlan";
import PrinciplesPanel from "./PrinciplesPanel";
import EventTracker from "./EventTracker";

const REFRESH_MS  = 5 * 60 * 1000;
const CUTOFF_HOUR = 20;  // 8 pm

// ── Training window ──────────────────────────────────────────────────────────

function getWindowStatus(now) {
  const cutoff = new Date(now);
  cutoff.setHours(CUTOFF_HOUR, 0, 0, 0);
  const diffMs  = cutoff - now;
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMs <= 0)    return { text: "Training window closed · Rest well", color: tokens.textMuted };
  if (diffMin < 30)   return { text: "Window closing", color: tokens.red };
  if (diffMin < 60)   return { text: `${diffMin} min left — decide now`, color: tokens.gold };
  const h = Math.floor(diffMin / 60);
  const m = diffMin % 60;
  return { text: `${h}hr${m ? ` ${m}min` : ""} left today`, color: tokens.textSecondary };
}

// ── Readiness tier ───────────────────────────────────────────────────────────

function getReadinessTier(todayData) {
  const r = todayData?.readiness;
  if (!r) return "GREEN";
  if (r.principle_violations?.length > 0) return "RED";
  if (r.adjustment_needed) return "AMBER";
  return "GREEN";
}

function tierLabel(tier) {
  if (tier === "RED")   return { word: "REST TODAY", color: tokens.red };
  if (tier === "AMBER") return { word: "SHORTENED",  color: tokens.gold };
  return                       { word: "READY",       color: tokens.green };
}

// ── Top Bar ──────────────────────────────────────────────────────────────────

function TopBar({ probability, isLoading }) {
  const col = probability >= 70 ? tokens.green : probability >= 50 ? tokens.gold : tokens.red;
  return (
    <div style={{
      background: tokens.bgCard,
      borderBottom: `1px solid ${tokens.border}`,
      height: "52px",
      padding: "0 16px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      position: "sticky",
      top: 0,
      zIndex: 20,
    }}>
      <div style={{
        fontFamily: tokens.fontDisplay,
        fontWeight: 700,
        fontSize: "13px",
        letterSpacing: "4px",
        color: tokens.gold,
      }}>
        IRONMAN
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: "3px" }}>
        <span style={{
          fontFamily: tokens.fontDisplay,
          fontSize: "26px",
          fontWeight: 700,
          lineHeight: 1,
          color: isLoading ? tokens.textMuted : col,
        }}>
          {isLoading ? "—" : probability}
        </span>
        <span style={{ fontSize: "11px", color: tokens.textMuted, fontFamily: tokens.fontMono }}>%</span>
        <span style={{
          fontSize: "8px",
          color: tokens.textMuted,
          fontFamily: tokens.fontMono,
          marginLeft: "2px",
          letterSpacing: "1px",
        }}>
          PROB
        </span>
      </div>
    </div>
  );
}

// ── Status Hero Card ─────────────────────────────────────────────────────────

function StatusHeroCard({ todayData, windowStatus }) {
  const tier      = getReadinessTier(todayData);
  const { word, color } = tierLabel(tier);
  const session   = todayData?.session;
  const readiness = todayData?.readiness;

  return (
    <div style={{
      background: tokens.bgCard,
      border: `1px solid ${tokens.border}`,
      borderLeft: `4px solid ${color}`,
      borderRadius: tokens.radiusMd,
      padding: "20px 16px 14px",
      marginBottom: "8px",
    }}>
      <style>{`@keyframes redPulse { 0%,100% { opacity:1 } 50% { opacity:0.7 } }`}</style>

      {/* Status word */}
      <div style={{
        fontFamily: tokens.fontDisplay,
        fontSize: "36px",
        fontWeight: 700,
        color,
        lineHeight: 1,
        marginBottom: "12px",
        animation: tier === "RED" ? "redPulse 1.5s ease-in-out infinite" : "none",
      }}>
        {word}
      </div>

      {/* Session summary or rest note */}
      {tier === "RED" ? (
        <div style={{
          fontSize: "11px",
          color: tokens.textSecondary,
          fontFamily: tokens.fontMono,
          lineHeight: 1.7,
          marginBottom: "12px",
        }}>
          {readiness?.intensity_note || readiness?.recommended_action || "Full rest today."}
        </div>
      ) : session && !session.is_rest_day ? (
        <div style={{ marginBottom: "12px" }}>
          <div style={{
            fontSize: "16px",
            fontWeight: 600,
            color: tokens.textPrimary,
            fontFamily: tokens.fontDisplay,
            marginBottom: "8px",
          }}>
            {session.planned_name}
            {session.duration_mins != null && (
              <span style={{ color: tokens.textMuted }}> · {session.duration_mins} min</span>
            )}
          </div>
          {session.hr_target_low && (
            <div style={{
              display: "inline-block",
              padding: "3px 8px",
              background: tokens.greenDim,
              border: `1px solid ${tokens.greenBorder}`,
              borderRadius: tokens.radiusSm,
              fontSize: "9px",
              color: tokens.green,
              fontFamily: tokens.fontMono,
              letterSpacing: "0.5px",
            }}>
              HR {session.hr_target_low}–{session.hr_target_high} bpm · Zone 2
            </div>
          )}
        </div>
      ) : (
        <div style={{
          fontSize: "11px",
          color: tokens.textMuted,
          fontFamily: tokens.fontMono,
          marginBottom: "12px",
        }}>
          Planned rest day.
        </div>
      )}

      <div style={{ borderTop: `1px solid ${tokens.border}`, marginBottom: "10px" }} />

      {/* Training window countdown */}
      <div style={{
        fontSize: "10px",
        color: windowStatus.color,
        fontFamily: tokens.fontMono,
        letterSpacing: "0.3px",
        transition: "color 0.3s ease",
      }}>
        ⏱ {windowStatus.text}
      </div>

      {/* Water fear level */}
      {todayData?.water_fear_level != null && (
        <div style={{
          fontSize: "10px",
          color: tokens.textMuted,
          fontFamily: tokens.fontMono,
          marginTop: "6px",
        }}>
          🌊 Fear level {todayData.water_fear_level}/10 today
        </div>
      )}
    </div>
  );
}

// ── Weekly Tracker ───────────────────────────────────────────────────────────

function localDateStr(d = new Date()) {
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join("-");
}

function WeeklyTracker({ week }) {
  const todayStr = localDateStr();

  return (
    <div style={{
      background: tokens.bgCard,
      border: `1px solid ${tokens.border}`,
      borderRadius: tokens.radiusMd,
      padding: "12px 12px 10px",
      marginBottom: "8px",
    }}>
      <div style={{
        fontSize: "8px",
        letterSpacing: "3px",
        color: tokens.gold,
        fontFamily: tokens.fontMono,
        marginBottom: "12px",
      }}>
        THIS WEEK
      </div>

      <div style={{ display: "flex", justifyContent: "space-between" }}>
        {week.map((entry) => {
          const isToday  = entry.date === todayStr;
          const isPast   = entry.date < todayStr;
          const s        = entry.session;

          let dotBg     = "transparent";
          let dotBorder = `1px solid ${tokens.border}`;

          if (!isPast && !isToday) {
            // future — empty ring
          } else if (s) {
            dotBg     = s.zone2 ? tokens.green : tokens.gold;
            dotBorder = "none";
          } else {
            // past or today with no session — missed / rest
            dotBg     = tokens.textDead;
            dotBorder = "none";
          }

          return (
            <div key={entry.date} style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "4px",
            }}>
              {/* Dot with optional today-ring */}
              <div style={{
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                background: dotBg,
                border: dotBorder,
                flexShrink: 0,
                outline: isToday ? `2px solid ${tokens.textPrimary}` : "none",
                outlineOffset: "3px",
              }} />

              <div style={{
                fontSize: "8px",
                color: isToday ? tokens.textPrimary : tokens.textMuted,
                fontFamily: tokens.fontMono,
                letterSpacing: "0.3px",
              }}>
                {entry.day.slice(0, 3).toUpperCase()}
              </div>

              <div style={{ fontSize: "10px", lineHeight: 1, minHeight: "12px" }}>
                {s ? disciplineIcon(s.type) : ""}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


// ── Garmin Metrics Row ───────────────────────────────────────────────────────

function metricValueColor(type, value) {
  if (value == null) return tokens.textMuted;
  if (type === "battery") return value >= 60 ? tokens.green : value >= 30 ? tokens.gold : tokens.red;
  if (type === "sleep")   return value >= 70 ? tokens.green : value >= 55 ? tokens.gold : tokens.red;
  if (type === "stress")  return value <= 30 ? tokens.green : value <= 50 ? tokens.gold : tokens.red;
  return tokens.textPrimary;
}

function GarminRow({ garmin }) {
  if (!garmin) return null;

  const tiles = [
    { label: "BATTERY", value: garmin.body_battery,          type: "battery" },
    { label: "SLEEP",   value: garmin.sleep_score,           type: "sleep" },
    { label: "RHR",     value: garmin.resting_heart_rate_bpm, type: "rhr" },
    { label: "STRESS",  value: garmin.stress_avg,            type: "stress" },
  ];

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(4, 1fr)",
      gap: "6px",
      marginBottom: "8px",
    }}>
      {tiles.map(({ label, value, type }) => (
        <div key={label} style={{
          background: tokens.bgCard,
          border: `1px solid ${tokens.border}`,
          borderRadius: tokens.radiusMd,
          padding: "10px 6px",
          textAlign: "center",
        }}>
          <div style={{
            fontFamily: tokens.fontDisplay,
            fontSize: "22px",
            fontWeight: 700,
            color: metricValueColor(type, value),
            lineHeight: 1,
            marginBottom: "4px",
          }}>
            {value ?? "—"}
          </div>
          <div style={{
            fontSize: "7px",
            letterSpacing: "1px",
            color: tokens.textMuted,
            fontFamily: tokens.fontMono,
          }}>
            {label}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── HRV Card ─────────────────────────────────────────────────────────────────

const HRV_STATUS_COLORS = {
  Positive:   tokens.green,
  Balanced:   tokens.green,
  Unbalanced: tokens.gold,
  Low:        tokens.red,
  Poor:       tokens.red,
};

function HRVCard({ garmin }) {
  if (!garmin) return null;
  const statusColor = HRV_STATUS_COLORS[garmin.hrv_status] || tokens.textMuted;

  return (
    <div style={{
      background: tokens.bgCard,
      border: `1px solid ${tokens.border}`,
      borderRadius: tokens.radiusMd,
      padding: "10px 14px",
      marginBottom: "8px",
      display: "flex",
      alignItems: "center",
      gap: "6px",
    }}>
      <span style={{ fontSize: "9px", color: tokens.textMuted,    fontFamily: tokens.fontMono, letterSpacing: "1px" }}>HRV</span>
      <span style={{ fontSize: "9px", color: tokens.textMuted,    fontFamily: tokens.fontMono }}>·</span>
      <span style={{ fontSize: "9px", color: statusColor,         fontFamily: tokens.fontMono, fontWeight: 500 }}>{garmin.hrv_status ?? "—"}</span>
      <span style={{ fontSize: "9px", color: tokens.textMuted,    fontFamily: tokens.fontMono }}>·</span>
      <span style={{ fontSize: "9px", color: tokens.textSecondary, fontFamily: tokens.fontMono }}>{garmin.hrv_overnight_avg ?? "—"} avg</span>
    </div>
  );
}

// ── AI Readiness Note ────────────────────────────────────────────────────────

function ReadinessNote({ readiness }) {
  const [expanded, setExpanded] = useState(false);
  if (!readiness?.philosophical_reflection) return null;

  const full    = readiness.philosophical_reflection;
  const preview = full.length > 80 ? full.slice(0, 80) + "…" : full;

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        background: tokens.bgCard,
        border: `1px solid ${tokens.border}`,
        borderLeft: `3px solid ${tokens.gold}`,
        borderRadius: tokens.radiusMd,
        padding: "14px 14px",
        minHeight: "44px",
        marginBottom: "8px",
        cursor: "pointer",
      }}
    >
      <div style={{
        fontSize: "10px",
        color: tokens.textSecondary,
        fontFamily: tokens.fontMono,
        lineHeight: 1.7,
        fontStyle: "italic",
      }}>
        {expanded ? full : preview}
      </div>
      <div style={{
        fontSize: "8px",
        color: tokens.goldDim,
        fontFamily: tokens.fontMono,
        marginTop: "6px",
        letterSpacing: "1px",
      }}>
        {expanded ? "COLLAPSE ↑" : "TAP TO READ ↓"}
      </div>
    </div>
  );
}

// ── Bottom Navigation ────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { id: "TODAY", label: "TODAY",  icon: "◎" },
  { id: "STATS", label: "STATS",  icon: "▲" },
  { id: "PLAN",  label: "PLAN",   icon: "≡" },
  { id: "CORE",  label: "CORE",   icon: "◈" },
];

function BottomNav({ active, onChange }) {
  return (
    <div style={{
      position: "fixed",
      bottom: 0,
      left: "50%",
      transform: "translateX(-50%)",
      width: "100%",
      maxWidth: "480px",
      background: tokens.bgCard,
      borderTop: `1px solid ${tokens.border}`,
      display: "flex",
      paddingBottom: "env(safe-area-inset-bottom, 0px)",
      zIndex: 30,
    }}>
      {NAV_ITEMS.map(({ id, label, icon }) => {
        const isActive = active === id;
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              borderTop: isActive ? `2px solid ${tokens.gold}` : "2px solid transparent",
              color: isActive ? tokens.gold : tokens.textMuted,
              height: "56px",
              fontSize: "7px",
              letterSpacing: "1.5px",
              cursor: "pointer",
              fontFamily: tokens.fontMono,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: "3px",
              padding: "6px 0 4px",
              transition: "color 0.15s ease, border-color 0.15s ease",
            }}
          >
            <span style={{ fontSize: "13px", lineHeight: 1 }}>{icon}</span>
            <span>{label}</span>
          </button>
        );
      })}
    </div>
  );
}

// ── Loading / Error ──────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "60px 20px",
      gap: "12px",
    }}>
      <div style={{
        fontFamily: tokens.fontDisplay,
        fontSize: "32px",
        fontWeight: 700,
        color: tokens.gold,
      }}>—</div>
      <div style={{
        fontSize: "9px",
        letterSpacing: "3px",
        color: tokens.textMuted,
        fontFamily: tokens.fontMono,
      }}>
        SYNCING
      </div>
    </div>
  );
}

function ErrorBanner({ message, onRetry }) {
  return (
    <div style={{
      marginBottom: "10px",
      padding: "10px 14px",
      background: tokens.redDim,
      border: `1px solid ${tokens.redBorder}`,
      borderRadius: tokens.radiusMd,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
    }}>
      <span style={{ fontSize: "10px", color: tokens.red, fontFamily: tokens.fontMono }}>
        ⚑ {message}
      </span>
      <button
        onClick={onRetry}
        style={{
          background: "transparent",
          border: `1px solid ${tokens.red}`,
          color: tokens.red,
          fontSize: "8px",
          padding: "10px 14px",
          minHeight: "44px",
          cursor: "pointer",
          borderRadius: tokens.radiusSm,
          fontFamily: tokens.fontMono,
          letterSpacing: "1px",
        }}
      >
        RETRY
      </button>
    </div>
  );
}

// ── Main Dashboard ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const [activeTab,     setActiveTab]     = useState("TODAY");
  const [isLoading,     setIsLoading]     = useState(true);
  const [error,         setError]         = useState(null);
  const [windowStatus,  setWindowStatus]  = useState(() => getWindowStatus(new Date()));

  const [today,       setToday]       = useState(null);
  const [probability, setProbability] = useState(null);
  const [week,        setWeek]        = useState([]);
  const [plan,        setPlan]        = useState([]);
  const [stats,       setStats]       = useState(null);
  const [checkpoints, setCheckpoints] = useState([]);

  const fetchAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [todayData, probData, weekData, planData, statsData, checkpointsData] = await Promise.all([
        api.getToday(),
        api.getProbability(),
        api.getWeek(),
        api.getPlan(),
        api.getStats(),
        api.getCheckpoints(),
      ]);
      setToday(todayData);
      setProbability(probData);
      setWeek(weekData        || []);
      setPlan(planData        || []);
      setStats(statsData);
      setCheckpoints(checkpointsData || []);
    } catch (err) {
      setError("Could not reach API. Showing cached data.");
      console.error("Dashboard fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Data refresh every 5 minutes
  useEffect(() => {
    loadFonts();
    fetchAll();
    const dataTimer = setInterval(fetchAll, REFRESH_MS);
    return () => clearInterval(dataTimer);
  }, [fetchAll]);

  // Window countdown — independent 60 s tick
  useEffect(() => {
    const clockTimer = setInterval(() => setWindowStatus(getWindowStatus(new Date())), 60_000);
    return () => clearInterval(clockTimer);
  }, []);

  const overallScore = probability?.overall_score ?? 50;

  return (
    <div style={{
      fontFamily: tokens.fontMono,
      background: tokens.bg,
      color: tokens.textPrimary,
      minHeight: "100vh",
      maxWidth: "480px",
      margin: "0 auto",
    }}>
      <TopBar probability={overallScore} isLoading={isLoading} />

      {/* Scrollable body — padding-bottom keeps content above fixed nav */}
      <div style={{ padding: "10px 14px", paddingBottom: "80px" }}>
        {error && <ErrorBanner message={error} onRetry={fetchAll} />}

        {isLoading ? (
          <LoadingState />
        ) : (
          <>
            {activeTab === "TODAY" && (
              <>
                <StatusHeroCard todayData={today} windowStatus={windowStatus} />
                <WeeklyTracker week={week} />
                <EventTracker checkpoints={checkpoints} />
                <GarminRow garmin={today?.garmin} />
                <HRVCard garmin={today?.garmin} />
                <ReadinessNote readiness={today?.readiness} />
              </>
            )}

            {activeTab === "STATS" && (
              <>
                <ProbabilityPanel data={probability} />
                <div style={{ height: "10px" }} />
                <SessionHistory data={week} />
              </>
            )}

            {activeTab === "PLAN" && <TrainingPlan data={plan} />}

            {activeTab === "CORE" && <PrinciplesPanel stats={stats} />}
          </>
        )}
      </div>

      <BottomNav active={activeTab} onChange={setActiveTab} />
    </div>
  );
}
