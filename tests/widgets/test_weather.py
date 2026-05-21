import pytest
import respx
from httpx import Response

from app.widgets.weather import WeatherWidget
from app.widgets.base import WidgetError


@pytest.fixture(autouse=True)
def _clear_weather_caches() -> None:
    """Reset module-level caches so tests don't leak state into each other."""
    import app.widgets.weather as w
    for attr in ("_GEOCODE_CACHE", "_ICON_SVG_CACHE"):
        cache = getattr(w, attr, None)
        if cache is not None:
            cache.clear()


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
    assert ctx["current_label"] == "Overcast"
    assert "<svg" in ctx["current_icon_svg"]
    assert len(ctx["forecast"]) == 3
    assert ctx["forecast"][0]["max"] == 21
    # Code 3 → "cloud" icon; code 61 → "cloud-rain"; code 2 → "cloud-sun".
    # We assert presence of distinguishing path snippets where useful, but the
    # cheap check is just that each day got a non-empty inline SVG.
    for day in ctx["forecast"]:
        assert "<svg" in day["icon_svg"]


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
    schema = widget.config_schema
    props = schema["properties"]
    assert "location" in props
    assert props["location"]["type"] == "string"
    assert "lat" in props and "lon" in props
    # location OR lat/lon is enforced inside fetch (the form generator
    # does not understand anyOf), so the schema must not require any
    # particular field.
    assert "required" not in schema or schema["required"] == []


from app.widgets.weather import _icon_name_for_code


@pytest.mark.parametrize(
    "code, expected",
    [
        (0, "sun"),
        (1, "sun"),
        (2, "cloud-sun"),
        (3, "cloud"),
        (45, "cloud-fog"),
        (48, "cloud-fog"),
        (51, "cloud-drizzle"),
        (53, "cloud-drizzle"),
        (55, "cloud-drizzle"),
        (61, "cloud-rain"),
        (63, "cloud-rain"),
        (65, "cloud-rain"),
        (71, "cloud-snow"),
        (73, "cloud-snow"),
        (75, "cloud-snow"),
        (80, "cloud-rain-wind"),
        (81, "cloud-rain-wind"),
        (82, "cloud-rain-wind"),
        (95, "cloud-lightning"),
    ],
)
def test_icon_name_for_code_known(code: int, expected: str) -> None:
    assert _icon_name_for_code(code) == expected


def test_icon_name_for_code_unknown_falls_back_to_cloud() -> None:
    assert _icon_name_for_code(99) == "cloud"
    assert _icon_name_for_code(-1) == "cloud"


from app.widgets.weather import _load_icon_svg


def test_load_icon_svg_returns_svg_markup() -> None:
    svg = _load_icon_svg("sun")
    assert svg.lstrip().startswith("<svg")
    assert "</svg>" in svg


def test_load_icon_svg_caches_result(monkeypatch) -> None:
    import app.widgets.weather as w

    # Prime cache, then sabotage Path.read_text — the cached value should still
    # be returned without touching the disk again.
    first = _load_icon_svg("cloud")

    def boom(*_a, **_k):  # pragma: no cover - should not be called
        raise AssertionError("read_text called after cache hit")

    monkeypatch.setattr(w.Path, "read_text", boom)
    second = _load_icon_svg("cloud")
    assert second == first


def test_load_icon_svg_unknown_name_raises() -> None:
    with pytest.raises(FileNotFoundError):
        _load_icon_svg("not-a-real-icon")


@pytest.mark.asyncio
async def test_geocode_returns_lat_lon() -> None:
    from app.widgets.weather import _geocode

    payload = {"results": [{"latitude": 48.137, "longitude": 11.575, "name": "Munich"}]}
    with respx.mock(base_url="https://geocoding-api.open-meteo.com") as mock:
        route = mock.get("/v1/search").mock(return_value=Response(200, json=payload))
        lat, lon = await _geocode("Munich")
    assert (lat, lon) == (48.137, 11.575)
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_geocode_caches_by_normalized_name() -> None:
    from app.widgets.weather import _geocode

    payload = {"results": [{"latitude": 48.137, "longitude": 11.575, "name": "Munich"}]}
    with respx.mock(base_url="https://geocoding-api.open-meteo.com") as mock:
        route = mock.get("/v1/search").mock(return_value=Response(200, json=payload))
        a = await _geocode("Munich")
        b = await _geocode("  munich  ")  # different case + whitespace
    assert a == b
    assert route.call_count == 1  # second call served from cache


@pytest.mark.asyncio
async def test_geocode_empty_results_raises_widget_error() -> None:
    from app.widgets.weather import _geocode

    with respx.mock(base_url="https://geocoding-api.open-meteo.com") as mock:
        mock.get("/v1/search").mock(return_value=Response(200, json={"results": []}))
        with pytest.raises(WidgetError, match="could not find"):
            await _geocode("Atlantis")


@pytest.mark.asyncio
async def test_geocode_missing_results_key_raises_widget_error() -> None:
    from app.widgets.weather import _geocode

    with respx.mock(base_url="https://geocoding-api.open-meteo.com") as mock:
        mock.get("/v1/search").mock(return_value=Response(200, json={}))
        with pytest.raises(WidgetError, match="could not find"):
            await _geocode("Nowhere")


@pytest.mark.asyncio
async def test_geocode_http_error_raises_widget_error() -> None:
    from app.widgets.weather import _geocode

    with respx.mock(base_url="https://geocoding-api.open-meteo.com") as mock:
        mock.get("/v1/search").mock(return_value=Response(500))
        with pytest.raises(WidgetError, match="geocode"):
            await _geocode("Munich")


_FORECAST_FIXTURE = {
    "current": {"temperature_2m": 18.4, "weather_code": 3, "time": "2026-05-20T09:00"},
    "daily": {
        "time": ["2026-05-20", "2026-05-21", "2026-05-22"],
        "temperature_2m_max": [21.0, 19.5, 17.0],
        "temperature_2m_min": [12.0, 11.0, 10.0],
        "weather_code": [3, 61, 2],
    },
}


@pytest.mark.asyncio
async def test_weather_fetch_uses_location_via_geocoding() -> None:
    geocode_payload = {
        "results": [{"latitude": 48.137, "longitude": 11.575, "name": "Munich"}]
    }
    with respx.mock(assert_all_called=True) as mock:
        geo_route = mock.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json=geocode_payload)
        )
        fc_route = mock.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(200, json=_FORECAST_FIXTURE)
        )
        widget = WeatherWidget()
        ctx = await widget.fetch({"location": "Munich", "days": 3})
    assert ctx["current_temp"] == 18
    assert geo_route.call_count == 1
    assert fc_route.call_count == 1
    # The forecast call should have used the geocoded coords.
    forecast_request = fc_route.calls[0].request
    assert "latitude=48.137" in str(forecast_request.url)
    assert "longitude=11.575" in str(forecast_request.url)


@pytest.mark.asyncio
async def test_weather_fetch_caches_geocoded_location_across_calls() -> None:
    geocode_payload = {
        "results": [{"latitude": 48.137, "longitude": 11.575, "name": "Munich"}]
    }
    with respx.mock() as mock:
        geo_route = mock.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json=geocode_payload)
        )
        fc_route = mock.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(200, json=_FORECAST_FIXTURE)
        )
        widget = WeatherWidget()
        await widget.fetch({"location": "Munich", "days": 3})
        await widget.fetch({"location": "Munich", "days": 3})
    assert geo_route.call_count == 1
    assert fc_route.call_count == 2


@pytest.mark.asyncio
async def test_weather_fetch_prefers_location_over_lat_lon() -> None:
    geocode_payload = {
        "results": [{"latitude": 48.137, "longitude": 11.575, "name": "Munich"}]
    }
    with respx.mock() as mock:
        mock.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json=geocode_payload)
        )
        fc_route = mock.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(200, json=_FORECAST_FIXTURE)
        )
        widget = WeatherWidget()
        await widget.fetch(
            {"location": "Munich", "lat": 1.0, "lon": 2.0, "days": 3}
        )
    forecast_request = fc_route.calls[0].request
    assert "latitude=48.137" in str(forecast_request.url)
    assert "latitude=1.0" not in str(forecast_request.url)


@pytest.mark.asyncio
async def test_weather_fetch_empty_location_falls_back_to_lat_lon() -> None:
    with respx.mock() as mock:
        fc_route = mock.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(200, json=_FORECAST_FIXTURE)
        )
        widget = WeatherWidget()
        await widget.fetch({"location": "  ", "lat": 1.0, "lon": 2.0, "days": 3})
    assert fc_route.call_count == 1
    forecast_request = fc_route.calls[0].request
    assert "latitude=1.0" in str(forecast_request.url)


@pytest.mark.asyncio
async def test_weather_fetch_requires_location_or_coords() -> None:
    widget = WeatherWidget()
    with pytest.raises(WidgetError, match="location or lat/lon required"):
        await widget.fetch({"days": 3})
