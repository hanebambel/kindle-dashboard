import pytest
import respx
from httpx import Response

from app.widgets.weather import WeatherWidget
from app.widgets.base import WidgetError


@pytest.mark.asyncio
async def test_weather_fetch_returns_current_and_forecast() -> None:
    fake = {
        "current": {"temperature_2m": 18.4, "weather_code": 3, "time": "2026-05-20T09:00"},
        "daily": {
            "time": ["2026-05-20", "2026-05-21", "2026-05-22"],
            "temperature_2m_max": [21.0, 19.5, 17.0],
            "temperature_2m_min": [12.0, 11.0, 10.0],
            "weather_code": [3, 61, 2],
        },
    }
    with respx.mock(base_url="https://api.open-meteo.com") as mock:
        mock.get("/v1/forecast").mock(return_value=Response(200, json=fake))
        widget = WeatherWidget()
        ctx = await widget.fetch({"lat": 48.1, "lon": 11.6, "days": 3})
    assert ctx["current_temp"] == 18
    assert len(ctx["forecast"]) == 3
    assert ctx["forecast"][0]["max"] == 21


@pytest.mark.asyncio
async def test_weather_fetch_raises_on_http_error() -> None:
    with respx.mock(base_url="https://api.open-meteo.com") as mock:
        mock.get("/v1/forecast").mock(return_value=Response(500))
        widget = WeatherWidget()
        with pytest.raises(WidgetError):
            await widget.fetch({"lat": 48.1, "lon": 11.6, "days": 3})


def test_weather_metadata() -> None:
    widget = WeatherWidget()
    assert widget.type == "weather"
    assert widget.template == "widgets/weather.html"
    schema_props = widget.config_schema["properties"]
    assert "lat" in schema_props and "lon" in schema_props
