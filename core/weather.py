"""
A — weather. open-meteo geocoding + forecast, NO API key. Plumbing, no model.
"""
import os
import requests

DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Dubai")

# WMO weather-code -> human text (open-meteo current.weather_code).
_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "rime fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "rain showers", 81: "rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "snow showers", 95: "thunderstorm",
    96: "thunderstorm w/ hail", 99: "thunderstorm w/ hail",
}


def _geocode(place: str):
    r = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                     params={"name": place, "count": 1}, timeout=8)
    res = (r.json() or {}).get("results") or []
    if not res:
        return None
    g = res[0]
    return {"lat": g["latitude"], "lon": g["longitude"],
            "name": g.get("name", place), "country": g.get("country", "")}


def get_weather(place: str = "") -> dict:
    place = (place or DEFAULT_CITY).strip()
    try:
        loc = _geocode(place)
        if not loc:
            return {"success": False, "message": f"Couldn't find '{place}', boss.", "data": {}}
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": loc["lat"], "longitude": loc["lon"],
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": 2,
        }, timeout=8)
        d = r.json() or {}
        cur = d.get("current", {})
        daily = d.get("daily", {})
        temp = cur.get("temperature_2m")
        cond = _WMO.get(cur.get("weather_code"), "—")
        hi = (daily.get("temperature_2m_max") or [None])[0]
        lo = (daily.get("temperature_2m_min") or [None])[0]
        rain = (daily.get("precipitation_probability_max") or [None])[0]
        where = f"{loc['name']}{', ' + loc['country'] if loc['country'] else ''}"
        msg = f"{where}: {temp}°C, {cond}. High {hi}° / low {lo}°, {rain}% chance of rain today."
        return {"success": True, "message": msg,
                "data": {"temp": temp, "cond": cond, "hi": hi, "lo": lo, "rain": rain,
                         "place": where, "daily": daily}}
    except Exception as e:
        return {"success": False, "message": f"Weather lookup failed: {str(e)[:60]}", "data": {}}


def will_rain(place: str = "", day: str = "today") -> dict:
    w = get_weather(place)
    if not w.get("success"):
        return w
    daily = w["data"].get("daily", {})
    probs = daily.get("precipitation_probability_max") or []
    idx = 1 if "tomorrow" in (day or "").lower() and len(probs) > 1 else 0
    p = probs[idx] if probs else None
    when = "tomorrow" if idx == 1 else "today"
    if p is None:
        return {"success": True, "message": f"No rain data for {w['data']['place']}.", "data": {}}
    verdict = "yes, likely" if p >= 50 else "probably not" if p < 30 else "maybe"
    return {"success": True,
            "message": f"{w['data']['place']} {when}: {verdict} — {p}% chance of rain.",
            "data": {"rain": p, "day": when}}
