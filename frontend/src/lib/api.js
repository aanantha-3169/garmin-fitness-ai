/**
 * api.js — Ironman Pipeline API client
 *
 * All calls target the FastAPI backend (api/main.py on Vercel).
 * VITE_API_URL is set in .env.local for dev, Vercel env vars for prod.
 *
 * Mock data is returned when VITE_USE_MOCK=true or when the API is unreachable.
 * This allows frontend development without the backend running.
 */

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

async function fetchApi(endpoint) {
  if (USE_MOCK) {
    return getMockData(endpoint);
  }
  try {
    const res = await fetch(`${BASE_URL}${endpoint}`);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  } catch (err) {
    console.warn(`API call failed for ${endpoint}, falling back to mock data:`, err);
    return getMockData(endpoint);
  }
}

export const api = {
  getToday: () => fetchApi("/api/today"),
  getProbability: () => fetchApi("/api/probability"),
  getWeek: () => fetchApi("/api/week"),
  getPlan: () => fetchApi("/api/plan"),
  getStats: () => fetchApi("/api/stats"),
  getCheckpoints: () => fetchApi("/api/checkpoints"),
};

// ── Mock Data ────────────────────────────────────────────────────────────────
// Matches the exact shape the FastAPI endpoints return.
// Update these shapes when updating api/main.py endpoints.

function getMockData(endpoint) {
  const mocks = {
    "/api/today": {
      date: new Date().toISOString().split("T")[0],
      garmin: {
        body_battery: 72,
        hrv_status: "Balanced",
        hrv_overnight_avg: 48,
        sleep_score: 74,
        sleep_quality: "Good",
        resting_heart_rate_bpm: 52,
        stress_avg: 28,
      },
      nutrition: {
        consumed_calories: 1840,
        target_calories: 2600,
        consumed_protein_g: 142,
        consumed_carbs_g: 198,
        consumed_fats_g: 61,
        meal_count: 3,
      },
      session: {
        planned_name: "Zone 2 Swim",
        discipline: "swim",
        duration_mins: 45,
        hr_target_low: 115,
        hr_target_high: 145,
        description: "Pool swim. Focus: catch-up drill + continuous 200m blocks.",
        is_completed: false,
        is_rest_day: false,
      },
      readiness: {
        recommended_action: "Proceed with planned session",
        adjustment_needed: false,
        zone2_target_hr_low: 115,
        zone2_target_hr_high: 145,
        principle_violations: [],
        philosophical_reflection:
          "The water doesn't get quieter. You get steadier.",
      },
      water_fear_level: 5,
      workday_load: 6,
    },

    "/api/probability": {
      overall_score: 61,
      components: {
        zone2_compliance: { score: 55, note: "4/7 sessions in Zone 2" },
        consistency: { score: 71, note: "5/7 target sessions" },
        life_load_buffer: { score: 68, note: "Avg load 4.8/10" },
        swim_frequency: { score: 50, note: "2/4 target swims" },
      },
      trend_30d: [
        { date: "2026-04-03", score: 48 },
        { date: "2026-04-10", score: 52 },
        { date: "2026-04-17", score: 55 },
        { date: "2026-04-24", score: 58 },
        { date: "2026-05-01", score: 61 },
      ],
      last_updated: new Date().toISOString(),
    },

    "/api/week": [
      {
        date: "2026-04-27",
        day: "Mon",
        session: { type: "swim", name: "Zone 2 Swim", duration_mins: 45, avg_hr: 132, zone2: true },
        workday_load: 7,
        water_fear_level: 6,
        calories_consumed: 2420,
      },
      {
        date: "2026-04-28",
        day: "Tue",
        session: { type: "run", name: "Zone 2 Run", duration_mins: 42, avg_hr: 138, zone2: true },
        workday_load: 8,
        water_fear_level: null,
        calories_consumed: 2180,
      },
      {
        date: "2026-04-29",
        day: "Wed",
        session: null,
        workday_load: 9,
        water_fear_level: null,
        calories_consumed: 1950,
      },
      {
        date: "2026-04-30",
        day: "Thu",
        session: { type: "bike", name: "Zone 2 Bike", duration_mins: 90, avg_hr: 141, zone2: true },
        workday_load: 6,
        water_fear_level: null,
        calories_consumed: 2650,
      },
      {
        date: "2026-05-01",
        day: "Fri",
        session: null,
        workday_load: 5,
        water_fear_level: null,
        calories_consumed: 2100,
      },
      {
        date: "2026-05-02",
        day: "Sat",
        session: { type: "bike", name: "Zone 2 Bike (Brother)", duration_mins: 90, avg_hr: 155, zone2: false, brother_session: true },
        workday_load: 3,
        water_fear_level: null,
        calories_consumed: 2800,
      },
      {
        date: "2026-05-03",
        day: "Sun",
        session: { type: "swim", name: "Zone 2 Swim", duration_mins: 40, avg_hr: 129, zone2: true },
        workday_load: 2,
        water_fear_level: 5,
        calories_consumed: 1840,
      },
    ],

    "/api/plan": [
      { date: "2026-05-04", day: "Mon", name: "Zone 2 Swim", discipline: "swim", duration_mins: 45, phase: "base" },
      { date: "2026-05-05", day: "Tue", name: "Zone 2 Run", discipline: "run", duration_mins: 45, phase: "base" },
      { date: "2026-05-06", day: "Wed", name: "Zone 2 Bike", discipline: "bike", duration_mins: 75, phase: "base" },
      { date: "2026-05-07", day: "Thu", name: "Zone 2 Swim", discipline: "swim", duration_mins: 45, phase: "base" },
      { date: "2026-05-08", day: "Fri", name: "Rest", discipline: "rest", duration_mins: null, phase: "base" },
      { date: "2026-05-09", day: "Sat", name: "Zone 2 Bike (Brother)", discipline: "bike", duration_mins: 90, phase: "base", brother_session: true },
      { date: "2026-05-10", day: "Sun", name: "Long Zone 2 Brick", discipline: "brick", duration_mins: 90, phase: "base" },
      { date: "2026-05-11", day: "Mon", name: "Zone 2 Swim", discipline: "swim", duration_mins: 45, phase: "base" },
      { date: "2026-05-12", day: "Tue", name: "Zone 2 Run", discipline: "run", duration_mins: 45, phase: "base" },
      { date: "2026-05-13", day: "Wed", name: "Zone 2 Bike", discipline: "bike", duration_mins: 75, phase: "base" },
      { date: "2026-05-14", day: "Thu", name: "Zone 2 Swim", discipline: "swim", duration_mins: 45, phase: "base" },
      { date: "2026-05-15", day: "Fri", name: "Rest", discipline: "rest", duration_mins: null, phase: "base" },
      { date: "2026-05-16", day: "Sat", name: "Zone 2 Bike (Brother)", discipline: "bike", duration_mins: 90, phase: "base", brother_session: true },
      { date: "2026-05-17", day: "Sun", name: "Long Zone 2 Brick", discipline: "brick", duration_mins: 90, phase: "base" },
    ],

    "/api/stats": {
      vo2_max: 54,
      vo2_max_category: "Excellent",
      vo2_max_percentile: "Top 10%",
      ftp_w_kg: 2.22,
      ftp_category: "Untrained",
      swim_pace_100m: "1:58",
      run_5k_predicted: "22:20",
      run_half_predicted: "1:49:27",
      zone2_hr_low: 115,
      zone2_hr_high: 145,
      last_updated: "2026-04-15",
    },

    "/api/checkpoints": [
      {
        name: "Aquaman Langkawi",
        date: "2026-07-25",
        type: "swim_2km",
        purpose: "Open water fear confrontation",
        days_until: Math.ceil((new Date("2026-07-25") - new Date()) / 86400000),
        readiness_score: 45,
        critical_metric: "swim_frequency",
      },
      {
        name: "Bintan Triathlon",
        date: "2026-10-12",
        type: "triathlon",
        purpose: "Full triathlon dress rehearsal",
        days_until: Math.ceil((new Date("2026-10-12") - new Date()) / 86400000),
        readiness_score: 52,
        critical_metric: "ftp",
      },
      {
        name: "Half Ironman",
        date: "2026-11-21",
        type: "ironman_70.3",
        purpose: "The endpoint",
        days_until: Math.ceil((new Date("2026-11-21") - new Date()) / 86400000),
        readiness_score: 61,
        critical_metric: "all",
      },
    ],
  };

  return Promise.resolve(mocks[endpoint] || null);
}
