/**
 * Dashboard.jsx — Main layout orchestrator
 *
 * Fetches all data from the FastAPI backend and distributes to child components.
 * Handles loading states, error states, and auto-refresh every 5 minutes.
 *
 * Tab structure:
 *   TODAY    — TodayPanel (readiness, session, nutrition, metrics)
 *   STATS    — ProbabilityPanel + SessionHistory
 *   PLAN     — TrainingPlan (next 14 days)
 *   CORE     — PrinciplesPanel (principles + baseline stats)
 */

import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { tokens, loadFonts } from "../lib/design";
import CountdownBar from "./CountdownBar";
import ProbabilityPanel from "./ProbabilityPanel";
import TodayPanel from "./TodayPanel";
import SessionHistory from "./SessionHistory";
import TrainingPlan from "./TrainingPlan";
import PrinciplesPanel from "./PrinciplesPanel";

const TABS = ["TODAY", "STATS", "PLAN", "CORE"];
const REFRESH_MS = 5 * 60 * 1000; // 5 minutes

function TopBar({ probability, isLoading, lastUpdated }) {
  const color =
    probability >= 70 ? tokens.green : probability >= 50 ? tokens.gold : tokens.red;

  return (
    <div style={{
      background: tokens.bgCard,
      borderBottom: `1px solid ${tokens.border}`,
      padding: "12px 20px",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      position: "sticky",
      top: 0,
      zIndex: 10,
    }}>
      <div>
        <div style={{
          fontFamily: "'Sora', sans-serif",
          fontWeight: 700,
          fontSize: "12px",
          letterSpacing: "5px",
          color: tokens.gold,
        }}>
          IRONMAN PIPELINE
        </div>
        <div style={{ fontSize: "8px", letterSpacing: "2px", color: tokens.textMuted, marginTop: "2px", fontFamily: tokens.fontMono }}>
          HALF IRONMAN · NOV 2026 · ZONE 2 PROTOCOL
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: "2px", justifyContent: "flex-end" }}>
          <span style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: "42px",
            fontWeight: 700,
            lineHeight: 1,
            color: isLoading ? tokens.textMuted : color,
            transition: "color 0.4s ease",
          }}>
            {isLoading ? "—" : probability}
          </span>
          <span style={{ fontSize: "16px", color: tokens.textMuted }}>%</span>
        </div>
        <div style={{ fontSize: "7px", letterSpacing: "3px", color: tokens.textMuted, fontFamily: tokens.fontMono }}>
          GOAL PROBABILITY
        </div>
        {lastUpdated && (
          <div style={{ fontSize: "7px", color: "#2a2a2a", fontFamily: tokens.fontMono, marginTop: "2px" }}>
            {lastUpdated}
          </div>
        )}
      </div>
    </div>
  );
}

function TabBar({ active, onChange }) {
  return (
    <div style={{
      display: "flex",
      gap: "3px",
      padding: "10px 16px",
      background: tokens.bgCard,
      borderBottom: `1px solid ${tokens.border}`,
      position: "sticky",
      top: "64px",
      zIndex: 9,
    }}>
      {TABS.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          style={{
            flex: 1,
            background: active === tab ? tokens.gold : "transparent",
            border: `1px solid ${active === tab ? tokens.gold : tokens.border}`,
            color: active === tab ? "#060606" : tokens.textMuted,
            padding: "7px 4px",
            fontSize: "8px",
            letterSpacing: "2px",
            cursor: "pointer",
            borderRadius: "2px",
            fontFamily: tokens.fontMono,
            fontWeight: active === tab ? "700" : "400",
            transition: "all 0.15s ease",
          }}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}

function LoadingState() {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "60px 20px",
      gap: "16px",
    }}>
      <div style={{
        fontFamily: "'Sora', sans-serif",
        fontSize: "32px",
        fontWeight: 700,
        color: tokens.gold,
        animation: "pulse 1.5s ease-in-out infinite",
      }}>
        —
      </div>
      <div style={{ fontSize: "9px", letterSpacing: "3px", color: tokens.textMuted, fontFamily: tokens.fontMono }}>
        SYNCING GARMIN DATA
      </div>
      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
      `}</style>
    </div>
  );
}

function ErrorBanner({ message, onRetry }) {
  return (
    <div style={{
      margin: "12px 16px",
      padding: "10px 14px",
      background: "#1F0D0D",
      border: `1px solid #3a1a1a`,
      borderRadius: "4px",
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
          padding: "3px 8px",
          cursor: "pointer",
          borderRadius: "2px",
          fontFamily: tokens.fontMono,
          letterSpacing: "1px",
        }}
      >
        RETRY
      </button>
    </div>
  );
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("TODAY");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const [today, setToday] = useState(null);
  const [probability, setProbability] = useState(null);
  const [week, setWeek] = useState([]);
  const [plan, setPlan] = useState([]);
  const [stats, setStats] = useState(null);
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
      setWeek(weekData || []);
      setPlan(planData || []);
      setStats(statsData);
      setCheckpoints(checkpointsData || []);
      setLastUpdated(new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }));
    } catch (err) {
      setError("Could not reach API. Showing cached data.");
      console.error("Dashboard fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFonts();
    fetchAll();
    const interval = setInterval(fetchAll, REFRESH_MS);
    return () => clearInterval(interval);
  }, [fetchAll]);

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
      <TopBar
        probability={overallScore}
        isLoading={isLoading}
        lastUpdated={lastUpdated}
      />

      <CountdownBar checkpoints={checkpoints} />

      <TabBar active={activeTab} onChange={setActiveTab} />

      {error && <ErrorBanner message={error} onRetry={fetchAll} />}

      <div style={{ padding: "14px 16px", paddingBottom: "40px" }}>
        {isLoading ? (
          <LoadingState />
        ) : (
          <>
            {activeTab === "TODAY" && <TodayPanel data={today} />}

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

      {/* PWA-friendly bottom safe area */}
      <div style={{ height: "env(safe-area-inset-bottom, 0px)" }} />
    </div>
  );
}
