"""Iran weather + air quality for Jan Kalam.

Weather:
  Open-Meteo forecast API.

Air quality:
  Primary: Iran Department of Environment national AQMS, following the public
  endpoint/session strategy documented and implemented by ZethRise/AirCheck.
  Fallback: Open-Meteo Air Quality / CAMS model, clearly labelled as estimate.

The GitHub Actions runner is outside Iran, while the DOE endpoint can be
network-restricted. The fallback keeps the page useful without presenting model
data as an official measurement.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math
import re

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

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
DOE_BASE = "https://aqms.doe.ir/"
TEHRAN = ZoneInfo("Asia/Tehran")

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

POLLUTANTS = [
    ("pm25", "PM2.5"),
    ("pm10", "PM10"),
    ("o3", "O₃"),
    ("no2", "NO₂"),
    ("so2", "SO₂"),
    ("co", "CO"),
]


def _cond(code) -> tuple[str, str]:
    try:
        return _CODES.get(int(code), ("—", "🌡️"))
    except (TypeError, ValueError):
        return ("—", "🌡️")


def _norm_fa(value: str | None) -> str:
    s = str(value or "")
    s = s.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک").replace("‌", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _aqi_category(aqi: int | float | None) -> tuple[str, str]:
    """US AQI categories used by AirCheck / DOE display logic."""
    try:
        v = int(round(float(aqi)))
    except (TypeError, ValueError):
        return ("unknown", "نامشخص")
    if v <= 50:
        return ("good", "خوب")
    if v <= 100:
        return ("moderate", "قابل قبول")
    if v <= 150:
        return ("sensitive", "ناسالم برای گروه‌های حساس")
    if v <= 200:
        return ("unhealthy", "ناسالم")
    if v <= 300:
        return ("very-unhealthy", "بسیار ناسالم")
    return ("hazardous", "خطرناک")


def _dominant_from_subindices(subs: dict[str, int | None]) -> list[str]:
    vals = [(k, v) for k, v in subs.items() if isinstance(v, (int, float))]
    if not vals:
        return []
    top = max(v for _, v in vals)
    label = dict(POLLUTANTS)
    return [label[k] for k, v in vals if v == top and k in label]


def _safe_int(v):
    try:
        if v is None:
            return None
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _parse_doe_city_row(row: dict, observed_at: str | None) -> dict | None:
    aqi = _safe_int(row.get("AQI"))
    if aqi is None:
        return None
    subs = {
        "pm25": _safe_int(row.get("PM2_5")),
        "pm10": _safe_int(row.get("PM10")),
        "o3": _safe_int(row.get("O3")),
        "no2": _safe_int(row.get("NO2")),
        "so2": _safe_int(row.get("SO2")),
        "co": _safe_int(row.get("CO")),
    }
    raw_dom = str(row.get("Pollutant") or "")
    dom_map = {
        "PM 2.5": "PM2.5", "PM2.5": "PM2.5", "PM 10": "PM10", "PM10": "PM10",
        "O3": "O₃", "NO2": "NO₂", "SO2": "SO₂", "CO": "CO",
    }
    dominant = [dom_map.get(x.strip(), x.strip()) for x in raw_dom.split(",") if x.strip()]
    if not dominant:
        dominant = _dominant_from_subindices(subs)
    cls, label = _aqi_category(aqi)
    return {
        "aqi": aqi,
        "aqi_class": cls,
        "aqi_label": label,
        "dominant": dominant,
        "pollutants": subs,
        "air_source": "doe",
        "air_source_fa": "شبکه ملی پایش کیفیت هوای سازمان حفاظت محیط‌زیست",
        "air_estimated": False,
        "air_observed_at": row.get("Date_Shamsi") or observed_at,
    }


def _fetch_doe_air(timeout: float = 18.0) -> dict[str, dict]:
    """Fetch DOE official city readings using the same public endpoints as AirCheck.

    A persistent client is required because aqms.doe.ir establishes a cookie
    session on LoadAQIMap before its POST endpoints are used.
    """
    headers = {
        "user-agent": "JanKalam/1.0 (+https://github.com/nimania/jan-kalam; AirCheck-compatible AQMS client)",
        "accept": "application/json,text/plain,*/*",
    }
    try:
        with httpx.Client(base_url=DOE_BASE, headers=headers, timeout=timeout, follow_redirects=True) as client:
            map_resp = client.get("Home/LoadAQIMap", params={"id": 2})
            map_resp.raise_for_status()
            map_data = map_resp.json()
            observed = map_data.get("T")

            if not observed:
                raise ValueError("DOE map response has no timestamp")

            region_resp = client.post(
                "Home/GetAQIDataByRegion/",
                data={"Date": observed, "type": 2},
                headers={"x-requested-with": "XMLHttpRequest"},
            )
            region_resp.raise_for_status()
            region_data = region_resp.json()
            rows = region_data.get("Data") or []

        wanted = {_norm_fa(name): name for name, _, _ in CITIES}
        out: dict[str, dict] = {}
        for row in rows:
            city = _norm_fa(row.get("Region_Fa"))
            if city not in wanted:
                continue
            parsed = _parse_doe_city_row(row, observed)
            if parsed:
                out[wanted[city]] = parsed

        # If a city row is missing, the map still gives official station AQIs.
        # Average only fresh station rows assigned to the exact city. This follows
        # AirCheck's documented city fallback idea, while keeping it clearly marked.
        station_groups: dict[str, list[dict]] = {}
        for st in map_data.get("D") or []:
            if not st.get("V", True):
                continue
            region = _norm_fa(st.get("R"))
            parts = [p.strip() for p in region.split(" - ", 1)]
            city = parts[1] if len(parts) > 1 else ""
            if city not in wanted or wanted[city] in out:
                continue
            aqi = _safe_int(st.get("A"))
            if aqi is None:
                continue
            station_groups.setdefault(wanted[city], []).append(st)

        for city_name, stations in station_groups.items():
            aqis = [_safe_int(x.get("A")) for x in stations]
            aqis = [x for x in aqis if x is not None]
            if not aqis:
                continue
            aqi = int(round(sum(aqis) / len(aqis)))
            cls, label = _aqi_category(aqi)
            dominant = []
            for st in stations:
                raw = str(st.get("P") or "").strip()
                if raw and raw not in dominant:
                    dominant.append(raw.replace("PM 2.5", "PM2.5").replace("PM 10", "PM10"))
            out[city_name] = {
                "aqi": aqi,
                "aqi_class": cls,
                "aqi_label": label,
                "dominant": dominant,
                "pollutants": {},
                "air_source": "doe-stations",
                "air_source_fa": "میانگین ایستگاه‌های رسمی سازمان حفاظت محیط‌زیست",
                "air_estimated": False,
                "air_observed_at": observed,
            }

        logger.info("fetched official DOE air quality for %d cities", len(out))
        return out
    except Exception as exc:
        logger.warning("could not fetch DOE air quality: %s", exc)
        return {}


def _nearest_hour_index(times: list[str]) -> int | None:
    if not times:
        return None
    now = datetime.now(TEHRAN).replace(minute=0, second=0, microsecond=0)
    target = now.strftime("%Y-%m-%dT%H:00")
    if target in times:
        return times.index(target)

    # Fallback to the closest parseable hour.
    best = None
    for i, raw in enumerate(times):
        try:
            dt = datetime.fromisoformat(raw).replace(tzinfo=TEHRAN)
            dist = abs((dt - now).total_seconds())
            if best is None or dist < best[0]:
                best = (dist, i)
        except (TypeError, ValueError):
            continue
    return best[1] if best else None


def _fetch_model_air(timeout: float = 20.0) -> dict[str, dict]:
    """Open-Meteo/CAMS fallback and forecast context for all configured cities."""
    lats = ",".join(str(c[1]) for c in CITIES)
    lons = ",".join(str(c[2]) for c in CITIES)
    hourly = (
        "us_aqi,pm2_5,pm10,dust,us_aqi_pm2_5,us_aqi_pm10,"
        "us_aqi_nitrogen_dioxide,us_aqi_ozone,us_aqi_sulphur_dioxide,"
        "us_aqi_carbon_monoxide"
    )
    params = {
        "latitude": lats,
        "longitude": lons,
        "hourly": hourly,
        "past_days": 1,
        "forecast_days": 3,
        "timezone": "Asia/Tehran",
    }
    try:
        resp = httpx.get(
            AIR_URL, params=params, timeout=timeout,
            headers={"user-agent": "JanKalam/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("could not fetch Open-Meteo air quality: %s", exc)
        return {}

    locs = data if isinstance(data, list) else [data]
    out: dict[str, dict] = {}
    for (name, _lat, _lon), loc in zip(CITIES, locs):
        h = loc.get("hourly") or {}
        times = h.get("time") or []
        idx = _nearest_hour_index(times)
        if idx is None:
            continue

        def at(key):
            vals = h.get(key) or []
            return vals[idx] if idx < len(vals) else None

        aqi = _safe_int(at("us_aqi"))
        if aqi is None:
            continue
        subs = {
            "pm25": _safe_int(at("us_aqi_pm2_5")),
            "pm10": _safe_int(at("us_aqi_pm10")),
            "o3": _safe_int(at("us_aqi_ozone")),
            "no2": _safe_int(at("us_aqi_nitrogen_dioxide")),
            "so2": _safe_int(at("us_aqi_sulphur_dioxide")),
            "co": _safe_int(at("us_aqi_carbon_monoxide")),
        }
        cls, label = _aqi_category(aqi)

        # A few future AQI checkpoints provide compact trend context.
        forecast = []
        for hours_ahead in (6, 12, 24):
            j = idx + hours_ahead
            vals = h.get("us_aqi") or []
            if j < len(vals) and vals[j] is not None:
                forecast.append({"hours": hours_ahead, "aqi": _safe_int(vals[j])})

        out[name] = {
            "aqi": aqi,
            "aqi_class": cls,
            "aqi_label": label,
            "dominant": _dominant_from_subindices(subs),
            "pollutants": subs,
            "air_source": "open-meteo-cams",
            "air_source_fa": "برآورد Open-Meteo / Copernicus CAMS",
            "air_estimated": True,
            "air_observed_at": times[idx] if idx < len(times) else None,
            "pm25_concentration": at("pm2_5"),
            "pm10_concentration": at("pm10"),
            "dust_concentration": at("dust"),
            "air_forecast": forecast,
        }
    logger.info("fetched model air quality for %d cities", len(out))
    return out


def _fetch_weather_only(timeout: float = 20.0) -> list[dict]:
    lats = ",".join(f"{c[1]}" for c in CITIES)
    lons = ",".join(f"{c[2]}" for c in CITIES)
    params = {
        "latitude": lats, "longitude": lons,
        "current": "temperature_2m,weather_code",
        "hourly": "temperature_2m",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto", "forecast_days": 2, "past_days": 1,
    }
    try:
        resp = httpx.get(
            WEATHER_URL, params=params, timeout=timeout,
            headers={"user-agent": "JanKalam/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("could not fetch weather: %s", exc)
        return []

    locs = data if isinstance(data, list) else [data]
    out: list[dict] = []
    for (name, _lat, _lon), loc in zip(CITIES, locs):
        try:
            cur = loc.get("current", {})
            daily = loc.get("daily", {})
            cond_fa, icon = _cond(cur.get("weather_code"))
            temp = round(cur.get("temperature_2m"))
            delta24 = None
            times = loc.get("hourly", {}).get("time", [])
            temps = loc.get("hourly", {}).get("temperature_2m", [])
            current_time = cur.get("time")
            if current_time in times:
                idx = times.index(current_time)
                if idx >= 24 and idx < len(temps) and temps[idx - 24] is not None:
                    delta24 = round(float(cur.get("temperature_2m")) - float(temps[idx - 24]), 1)
            maxs = daily.get("temperature_2m_max") or []
            mins = daily.get("temperature_2m_min") or []
            out.append({
                "city_fa": name, "temp": temp,
                "max": round(maxs[0]) if maxs and maxs[0] is not None else None,
                "min": round(mins[0]) if mins and mins[0] is not None else None,
                "cond_fa": cond_fa, "icon": icon, "delta24": delta24,
            })
        except (TypeError, ValueError, IndexError):
            continue
    return out


def fetch_weather(timeout: float = 20.0) -> list[dict]:
    """Return weather rows enriched with official/fallback air-quality data."""
    weather = _fetch_weather_only(timeout=timeout)
    if not weather:
        return []

    official = _fetch_doe_air(timeout=min(timeout, 18.0))
    model = _fetch_model_air(timeout=timeout)

    for row in weather:
        city = row["city_fa"]
        # Preserve official DOE values where available, but attach the model
        # forecast because DOE's public current endpoint is not a forecast feed.
        air = official.get(city) or model.get(city)
        if not air:
            continue
        merged = dict(air)
        if city in official and city in model:
            merged["air_forecast"] = model[city].get("air_forecast", [])
            merged["pm25_concentration_model"] = model[city].get("pm25_concentration")
            merged["pm10_concentration_model"] = model[city].get("pm10_concentration")
            merged["dust_concentration_model"] = model[city].get("dust_concentration")
        row.update(merged)

    logger.info(
        "fetched weather for %d cities; official air=%d, model air=%d",
        len(weather), len(official), len(model),
    )
    return weather
