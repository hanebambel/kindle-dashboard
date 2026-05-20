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


class WeatherWidget:
    type = "weather"
    template = "widgets/weather.html"
    config_schema = {
        "type": "object",
        "required": ["lat", "lon"],
        "properties": {
            "lat": {"type": "number", "title": "Latitude"},
            "lon": {"type": "number", "title": "Longitude"},
            "days": {"type": "integer", "title": "Forecast days", "default": 3, "minimum": 1, "maximum": 7},
        },
    }

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        days = int(cfg.get("days", 3))
        params = {
            "latitude": cfg["lat"],
            "longitude": cfg["lon"],
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
        return {
            "current_temp": round(current["temperature_2m"]),
            "current_label": WEATHER_CODES.get(current["weather_code"], "?"),
            "forecast": [
                {
                    "date": daily["time"][i],
                    "max": round(daily["temperature_2m_max"][i]),
                    "min": round(daily["temperature_2m_min"][i]),
                    "label": WEATHER_CODES.get(daily["weather_code"][i], "?"),
                }
                for i in range(len(daily["time"]))
            ],
        }
