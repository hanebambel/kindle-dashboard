from pathlib import Path
from typing import Any

import httpx

from app.widgets.base import WidgetError


WEATHER_CODES = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Showers",
    81: "Heavy showers", 82: "Violent showers", 95: "Thunderstorm",
}

# Open-Meteo weather code → Lucide icon name. Codes not listed
# fall back to "cloud" via _icon_name_for_code below.
_ICON_NAMES: dict[int, str] = {
    0: "sun", 1: "sun",
    2: "cloud-sun",
    3: "cloud",
    45: "cloud-fog", 48: "cloud-fog",
    51: "cloud-drizzle", 53: "cloud-drizzle", 55: "cloud-drizzle",
    61: "cloud-rain", 63: "cloud-rain", 65: "cloud-rain",
    71: "cloud-snow", 73: "cloud-snow", 75: "cloud-snow",
    80: "cloud-rain-wind", 81: "cloud-rain-wind", 82: "cloud-rain-wind",
    95: "cloud-lightning",
}


def _icon_name_for_code(code: int) -> str:
    return _ICON_NAMES.get(code, "cloud")


_ICONS_DIR = Path(__file__).resolve().parent.parent / "static" / "icons" / "weather"
_ICON_SVG_CACHE: dict[str, str] = {}


def _load_icon_svg(name: str) -> str:
    """Return the inline SVG markup for the named icon. Cached in-process."""
    cached = _ICON_SVG_CACHE.get(name)
    if cached is not None:
        return cached
    svg = (_ICONS_DIR / f"{name}.svg").read_text(encoding="utf-8")
    _ICON_SVG_CACHE[name] = svg
    return svg


_GEOCODE_BASE_URL = "https://geocoding-api.open-meteo.com"
_GEOCODE_CACHE: dict[str, tuple[float, float]] = {}


async def _geocode(name: str) -> tuple[float, float]:
    """Resolve a town name to (latitude, longitude) using Open-Meteo's
    geocoding API. Results are cached in-process by normalized name."""
    key = name.strip().lower()
    cached = _GEOCODE_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(base_url=_GEOCODE_BASE_URL, timeout=5.0) as client:
            resp = await client.get(
                "/v1/search",
                params={"name": name, "count": 1, "language": "en", "format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WidgetError(f"weather geocode failed: {exc}") from exc

    results = data.get("results") or []
    if not results:
        raise WidgetError(f"weather: could not find location {name!r}")
    top = results[0]
    coords = (float(top["latitude"]), float(top["longitude"]))
    _GEOCODE_CACHE[key] = coords
    return coords


class WeatherWidget:
    type = "weather"
    template = "widgets/weather.html"
    config_schema = {
        "type": "object",
        "properties": {
            "location": {"type": "string", "title": "Location (town name)"},
            "lat": {"type": "number", "title": "Latitude"},
            "lon": {"type": "number", "title": "Longitude"},
            "days": {"type": "integer", "title": "Forecast days", "default": 3, "minimum": 1, "maximum": 7},
        },
    }

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        lat, lon = await self._resolve_coords(cfg)
        days = int(cfg.get("days", 3))
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,weather_code",
            "forecast_days": days,
            "timezone": "auto",
        }
        try:
            async with httpx.AsyncClient(base_url="https://api.open-meteo.com", timeout=5.0) as client:
                resp = await client.get("/v1/forecast", params=params)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WidgetError(f"weather fetch failed: {exc}") from exc

        current = data["current"]
        daily = data["daily"]
        current_code = current["weather_code"]
        return {
            "current_temp": round(current["temperature_2m"]),
            "current_label": WEATHER_CODES.get(current_code, "?"),
            "current_icon_svg": _load_icon_svg(_icon_name_for_code(current_code)),
            "forecast": [
                {
                    "date": daily["time"][i],
                    "max": round(daily["temperature_2m_max"][i]),
                    "min": round(daily["temperature_2m_min"][i]),
                    "label": WEATHER_CODES.get(daily["weather_code"][i], "?"),
                    "icon_svg": _load_icon_svg(
                        _icon_name_for_code(daily["weather_code"][i])
                    ),
                }
                for i in range(len(daily["time"]))
            ],
        }

    @staticmethod
    async def _resolve_coords(cfg: dict[str, Any]) -> tuple[float, float]:
        location = cfg.get("location")
        if isinstance(location, str) and location.strip():
            return await _geocode(location)
        lat, lon = cfg.get("lat"), cfg.get("lon")
        if lat is not None and lon is not None:
            return float(lat), float(lon)
        raise WidgetError("weather: location or lat/lon required")
