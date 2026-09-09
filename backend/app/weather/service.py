"""Iran weather for the home page + a dedicated weather view.

Source: Open-Meteo (open-meteo.com) — free, keyless, no registration, reachable
from GitHub's servers. One request covers all cities (comma-separated coords).
Returns current temperature plus today's high/low and a condition label. Best
effort: on any failure returns [] and the weather sections simply hide.
"""
from __future__ import annotations

import httpx

from app.core.logging import get_logger

logger = get_logger("weather")

# name_fa, latitude, longitude — first four are the ones shown on the home page.
CITIES = [
    ("نوشهر", 36.6547, 51.4964),
    ("کرمان", 30.2839, 57.0834),
    ("تهران", 35.6892, 51.3890),
    ("چالوس", 36.6556, 51.4204),
    ("مشهد", 36.2605, 59.6168),
    ("اصفهان", 32.6539, 51.6660),
    ("تبریز", 38.0800, 46.2919),
    ("شیراز", 29.5918, 52.5837),
    ("اهواز", 31.3183, 48.6706),
    ("رشت", 37.2808, 49.5832),
    ("بندرعباس", 27.1865, 56.2808),
    ("یزد", 31.8974, 54.3569),
]

URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes → (Persian label, emoji)
_CODES = {
    0: ("صاف", "☀️"),
    1: ("کمی ابری", "🌤️"), 2: ("نیمه‌ابری", "⛅"), 3: ("ابری", "☁️"),
    45: ("مه", "🌫️"), 48: ("مه", "🌫️"),
    51: ("نم‌نم باران", "🌦️"), 53: ("نم‌نم باران", "🌦️"), 55: ("نم‌نم باران", "🌦️"),
    61: ("بارانی", "🌧️"), 63: ("بارانی", "🌧️"), 65: ("باران شدید", "🌧️"),
    66: ("باران یخ‌زده", "🌧️"), 67: ("باران یخ‌زده", "🌧️"),
    71: ("برف", "🌨️"), 73: ("برف", "🌨️"), 75: ("برف سنگین", "❄️"), 77: ("دانه برف", "🌨️"),
    80: ("رگبار", "🌦️"), 81: ("رگبار", "🌦️"), 82: ("رگبار شدید", "⛈️"),
    85: ("بارش برف", "🌨️"), 86: ("بارش برف", "🌨️"),
    95: ("رعدوبرق", "⛈️"), 96: ("رعدوبرق", "⛈️"), 99: ("رعدوبرق", "⛈️"),
}


def _cond(code) -> tuple[str, str]:
    try:
        return _CODES.get(int(code), ("—", "🌡️"))
    except (TypeError, ValueError):
        return ("—", "🌡️")


def fetch_weather(timeout: float = 20.0) -> list[dict]:
    """Return [{city_fa, temp, max, min, cond_fa, icon}] or [] on failure."""
    lats = ",".join(f"{c[1]}" for c in CITIES)
    lons = ",".join(f"{c[2]}" for c in CITIES)
    params = {
        "latitude": lats, "longitude": lons,
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto", "forecast_days": 1,
    }
    try:
        resp = httpx.get(URL, params=params, timeout=timeout,
                         headers={"user-agent": "JanKalam/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("could not fetch weather: %s", exc)
        return []

    # With multiple coordinates Open-Meteo returns a list; normalise to one.
    locs = data if isinstance(data, list) else [data]
    out: list[dict] = []
    for (name, _lat, _lon), loc in zip(CITIES, locs):
        try:
            cur = loc.get("current", {})
            daily = loc.get("daily", {})
            cond_fa, icon = _cond(cur.get("weather_code"))
            out.append({
                "city_fa": name,
                "temp": round(cur.get("temperature_2m")),
                "max": round(daily.get("temperature_2m_max", [None])[0]),
                "min": round(daily.get("temperature_2m_min", [None])[0]),
                "cond_fa": cond_fa,
                "icon": icon,
            })
        except (TypeError, ValueError, IndexError):
            continue
    logger.info("fetched weather for %d cities", len(out))
    return out
