/**
 * design.js — Shared design tokens and utility functions
 *
 * Single source of truth for the dashboard's visual language.
 * Import from here, never hardcode colors or fonts in components.
 */

export const tokens = {
  // Colors
  bg: "#060606",
  bgCard: "#0C0C0C",
  bgHover: "#111111",
  border: "#1E1E1E",
  borderLight: "#151515",

  gold: "#C4A35A",
  goldDim: "#8a7040",
  green: "#5CB85C",
  greenDim: "#0D1F0D",
  greenBorder: "#1a3a1a",
  red: "#E05C5C",
  redDim: "#1F0D0D",
  redBorder: "#3a1a1a",
  blue: "#5B9BD5",

  textPrimary: "#D8D0C0",
  textSecondary: "#888",
  textMuted: "#444",
  textDead: "#2a2a2a",

  // Typography
  fontMono: "'DM Mono', monospace",
  fontDisplay: "'Sora', sans-serif",

  // Sizing
  radiusSm: "2px",
  radiusMd: "4px",
};

// Score → color mapping
export function scoreColor(score) {
  if (score >= 70) return tokens.green;
  if (score >= 50) return tokens.gold;
  return tokens.red;
}

// Discipline → color
export function disciplineColor(discipline) {
  const map = {
    swim: "#5B9BD5",
    bike: "#C4A35A",
    run: "#5CB85C",
    brick: "#9B7FD4",
    rest: tokens.textMuted,
  };
  return map[discipline] || tokens.textMuted;
}

// Discipline → emoji
export function disciplineIcon(discipline) {
  const map = {
    swim: "🌊",
    bike: "🚴",
    run: "🏃",
    brick: "⚡",
    rest: "—",
  };
  return map[discipline] || "•";
}

// Seconds → MM:SS
export function formatPace(secs) {
  if (!secs) return "--";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// Calories progress color
export function calorieColor(consumed, target) {
  const pct = consumed / target;
  if (pct < 0.5) return tokens.blue;
  if (pct < 0.9) return tokens.green;
  if (pct <= 1.1) return tokens.gold;
  return tokens.red;
}

// Shared card style
export const card = {
  background: tokens.bgCard,
  border: `1px solid ${tokens.border}`,
  borderRadius: tokens.radiusMd,
  padding: "14px",
  marginBottom: "10px",
};

// Section label style
export const sectionLabel = {
  fontSize: "8px",
  letterSpacing: "3px",
  color: tokens.gold,
  marginBottom: "12px",
  paddingBottom: "8px",
  borderBottom: `1px solid ${tokens.border}`,
  fontFamily: tokens.fontMono,
  textTransform: "uppercase",
};

// Google Fonts loader — call once in App.jsx
export function loadFonts() {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href =
    "https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,400&family=Sora:wght@300;400;600;700&display=swap";
  if (!document.querySelector(`link[href="${link.href}"]`)) {
    document.head.appendChild(link);
  }
}
