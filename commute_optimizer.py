"""
commute_optimizer.py — Weather-based commute recommendation for Jakarta.

Uses the Open-Meteo API (free, no API key required) to check the
morning forecast and recommends the best transport option.

Decision logic:
  A. Rain ≥ 30% between 7–9 AM → Take the train shuttle + umbrella
  B. Clear + peak hours (7:30–9:00 AM) → Bike
  C. Clear + non-peak hours → Car

Usage:
    from commute_optimizer import get_commute_recommendation
    rec = get_commute_recommendation()
    print(rec)
"""

import logging
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger(__name__)

# ── Jakarta coordinates ──────────────────────────────────────────────────────
JAKARTA_LAT = -6.2088
JAKARTA_LON = 106.8456
JAKARTA_TZ = timezone(timedelta(hours=7))  # WIB (UTC+7)

# Open-Meteo forecast API (free, no key needed)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def _fetch_morning_forecast() -> dict:
    """Fetch the hourly forecast for Jakarta and extract 7–9 AM data.

    Returns a dict with:
        rain_probability: max precipitation probability (0-100) for 7-9 AM
        weather_codes: list of WMO weather codes for those hours
        temperature: avg temp for the window
        is_rainy: True if rain_probability >= 30
    """
    params = {
        "latitude": JAKARTA_LAT,
        "longitude": JAKARTA_LON,
        "hourly": "precipitation_probability,weather_code,temperature_2m",
        "timezone": "Asia/Jakarta",
        "forecast_days": 1,
    }

    resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    precip_probs = hourly.get("precipitation_probability", [])
    weather_codes = hourly.get("weather_code", [])
    temps = hourly.get("temperature_2m", [])

    # Filter for 07:00–09:00 (indices 7, 8 in a 0-indexed 24h array)
    morning_indices = []
    for i, t in enumerate(times):
        # times are like "2026-02-21T07:00"
        hour = int(t.split("T")[1].split(":")[0])
        if 7 <= hour <= 8:  # 07:00 and 08:00 cover the 7–9 AM window
            morning_indices.append(i)

    if not morning_indices:
        logger.warning("No morning forecast data found, assuming clear")
        return {
            "rain_probability": 0,
            "weather_codes": [],
            "temperature": 28.0,
            "is_rainy": False,
        }

    max_precip = max(precip_probs[i] for i in morning_indices)
    codes = [weather_codes[i] for i in morning_indices]
    avg_temp = sum(temps[i] for i in morning_indices) / len(morning_indices)

    return {
        "rain_probability": max_precip,
        "weather_codes": codes,
        "temperature": round(avg_temp, 1),
        "is_rainy": max_precip >= 30,
    }


def _weather_description(codes: list) -> str:
    """Convert WMO weather codes to a human-readable description."""
    # WMO code mapping (subset)
    wmo = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy",
        3: "Overcast", 45: "Foggy", 48: "Rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Heavy thunderstorm",
    }
    if not codes:
        return "Unknown"
    # Use the most severe code
    worst = max(codes)
    return wmo.get(worst, f"Code {worst}")


def get_commute_recommendation(departure_hour: float = 7.5) -> str:
    """Get a commute recommendation based on Jakarta's morning forecast.

    Args:
        departure_hour: Planned departure time as a decimal hour (e.g. 7.5 = 7:30 AM).
                        Defaults to 7.5 (7:30 AM).

    Returns:
        A clean recommendation string.
    """
    try:
        forecast = _fetch_morning_forecast()
    except Exception as exc:
        logger.error("Failed to fetch weather forecast: %s", exc)
        return "⚠️ Weather data unavailable. Check traffic apps before leaving."

    rain_prob = forecast["rain_probability"]
    weather_desc = _weather_description(forecast["weather_codes"])
    temp = forecast["temperature"]

    logger.info(
        "Jakarta forecast: %s, rain=%d%%, temp=%.1f°C",
        weather_desc, rain_prob, temp,
    )

    # ── Decision logic ───────────────────────────────────────────────────
    # Condition A: Rain
    if forecast["is_rainy"]:
        return (
            f"🌧️ Rain forecasted ({rain_prob}% chance, {weather_desc}). "
            "Take the 8:00 AM Train Shuttle. Bring an umbrella."
        )

    # Condition B: Clear + Peak Traffic (7:30 AM – 9:00 AM)
    if 7.5 <= departure_hour <= 9.0:
        return (
            f"☀️ Clear morning ({weather_desc}, {temp}°C). "
            "Traffic is peaking. The Bike is your optimal transport today."
        )

    # Condition C: Clear + Non-Peak
    return (
        f"☀️ Clear morning ({weather_desc}, {temp}°C). "
        "Non-peak hours. Taking the Car is optimal."
    )
