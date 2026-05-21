# Weather Widget Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow weather widget config by town name (resolved via Open-Meteo geocoding) and render Lucide weather icons inline next to the current temperature and on each forecast tile.

**Architecture:** Extend [app/widgets/weather.py](../../../app/widgets/weather.py) with (a) a module-level icon-name map keyed on Open-Meteo weather codes, (b) a module-level dict of inline-SVG strings loaded once from `app/static/icons/weather/*.svg`, and (c) a geocode helper with a process-local cache. `fetch()` resolves coordinates from `location` (geocoded) or `lat`/`lon` (passthrough), then enriches the existing context with `current_icon_svg` plus per-day `icon_svg`. Templates inline the SVG markup so the same widget body works in both the WeasyPrint pipeline and the editor's browser preview iframe — no `/static/` URL resolution required.

**Tech Stack:** Python 3.13, FastAPI, httpx (existing), respx + pytest-asyncio for tests (existing), Jinja2 (existing), Lucide SVG icons (ISC licensed).

**Spec:** [docs/superpowers/specs/2026-05-21-weather-widget-refinement-design.md](../specs/2026-05-21-weather-widget-refinement-design.md)

---

## File Structure

**Created**

- `app/static/icons/weather/sun.svg`
- `app/static/icons/weather/cloud.svg`
- `app/static/icons/weather/cloud-sun.svg`
- `app/static/icons/weather/cloud-fog.svg`
- `app/static/icons/weather/cloud-drizzle.svg`
- `app/static/icons/weather/cloud-rain.svg`
- `app/static/icons/weather/cloud-snow.svg`
- `app/static/icons/weather/cloud-rain-wind.svg`
- `app/static/icons/weather/cloud-lightning.svg`

**Modified**

- [app/widgets/weather.py](../../../app/widgets/weather.py) — geocoding + cache, coordinate resolution, icon mapping, inline-SVG loader, expanded context.
- [app/templates/widgets/weather.html](../../../app/templates/widgets/weather.html) — inline SVG icons, refreshed layout (icon-left current, icon-on-top forecast tiles).
- [app/templates/dashboard.html](../../../app/templates/dashboard.html) — new CSS for `.weather-icon` and `.weather-day-icon`.
- [app/templates/widget_preview.html](../../../app/templates/widget_preview.html) — matching (smaller) CSS for the editor iframe preview.
- [tests/widgets/test_weather.py](../../../tests/widgets/test_weather.py) — expanded test suite (geocoding, cache, icon mapping, schema metadata, inline-SVG context).

No other files touched.

---

## Task 1: Icon-name mapping helper

A pure function `_icon_name_for_code(code: int) -> str` returning the Lucide icon name for an Open-Meteo weather code, falling back to `"cloud"` for unknown codes. No I/O — easy to TDD.

**Files:**

- Test: `tests/widgets/test_weather.py`
- Modify: `app/widgets/weather.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/widgets/test_weather.py`:

```python
import pytest

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/widgets/test_weather.py::test_icon_name_for_code_unknown_falls_back_to_cloud -v`
Expected: FAIL with `ImportError: cannot import name '_icon_name_for_code'`.

- [ ] **Step 3: Implement the mapping**

In `app/widgets/weather.py`, after the existing `WEATHER_CODES` dict, add:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/widgets/test_weather.py -v -k icon_name`
Expected: 20 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/widgets/weather.py tests/widgets/test_weather.py
git commit -m "feat(weather): add icon-name mapping for weather codes"
```

---

## Task 2: Add Lucide SVG icon assets

Download nine Lucide icon files into a new directory. These are static, vector-only, ~500 bytes each.

**Files:**

- Create: `app/static/icons/weather/{sun,cloud,cloud-sun,cloud-fog,cloud-drizzle,cloud-rain,cloud-snow,cloud-rain-wind,cloud-lightning}.svg`

- [ ] **Step 1: Create the directory and download the icons**

Run:

```bash
mkdir -p app/static/icons/weather
cd app/static/icons/weather
for name in sun cloud cloud-sun cloud-fog cloud-drizzle cloud-rain cloud-snow cloud-rain-wind cloud-lightning; do
  curl -fsSL -o "${name}.svg" "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/${name}.svg"
done
cd -
```

Expected: nine `*.svg` files in `app/static/icons/weather/`, each containing an `<svg ... stroke="currentColor" ...>` root.

- [ ] **Step 2: Verify the downloads**

Run: `ls app/static/icons/weather/ && head -1 app/static/icons/weather/sun.svg`
Expected: nine `.svg` filenames listed; first line of `sun.svg` starts with `<svg ` and includes `stroke="currentColor"`.

If any download is empty or returned HTML, abort and investigate — do not commit broken icons. (Lucide names are stable; `cloud-snow.svg` is one canonical example to spot-check.)

- [ ] **Step 3: Commit**

```bash
git add app/static/icons/weather/
git commit -m "feat(weather): add Lucide SVG icons for weather conditions"
```

---

## Task 3: SVG loader helper

A small helper `_load_icon_svg(name: str) -> str` that reads the SVG file's content and caches it in a module-level dict. We load lazily on first request rather than at import time (keeps the test path clean: unknown names raise a clear error, present names just work). Tests live alongside the rest in `tests/widgets/test_weather.py`.

**Files:**

- Test: `tests/widgets/test_weather.py`
- Modify: `app/widgets/weather.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/widgets/test_weather.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/widgets/test_weather.py -v -k icon_svg`
Expected: 3 tests FAIL with `ImportError: cannot import name '_load_icon_svg'`.

- [ ] **Step 3: Implement the loader**

In `app/widgets/weather.py`, add at the top of the file:

```python
from pathlib import Path
```

And below `_icon_name_for_code` from Task 1, add:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/widgets/test_weather.py -v -k icon_svg`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/widgets/weather.py tests/widgets/test_weather.py
git commit -m "feat(weather): add cached SVG loader for weather icons"
```

---

## Task 4: Add `current_icon_svg` and per-day `icon_svg` to fetch context

Extend the existing `WeatherWidget.fetch` to populate `current_icon_svg` and `forecast[i].icon_svg` using the helpers from tasks 1 and 3. No change to coordinate handling yet — that comes in tasks 5/6.

**Files:**

- Modify: `app/widgets/weather.py:30-62`
- Test: `tests/widgets/test_weather.py:10-26` (extend existing happy-path test)

- [ ] **Step 1: Extend the existing happy-path test**

Replace `test_weather_fetch_returns_current_and_forecast` in `tests/widgets/test_weather.py` with:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/widgets/test_weather.py::test_weather_fetch_returns_current_and_forecast -v`
Expected: FAIL on `KeyError: 'current_icon_svg'` (or AssertionError that the key is missing).

- [ ] **Step 3: Wire icons into the fetch context**

In `app/widgets/weather.py`, replace the return block of `fetch` (currently lines ~50-62) with:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/widgets/test_weather.py::test_weather_fetch_returns_current_and_forecast -v`
Expected: PASS.

Also run the full weather test module to verify nothing else regressed:

Run: `uv run pytest tests/widgets/test_weather.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/widgets/weather.py tests/widgets/test_weather.py
git commit -m "feat(weather): include inline icon SVGs in fetch context"
```

---

## Task 5: Geocode helper with in-memory cache

A `_geocode(name: str) -> tuple[float, float]` coroutine that calls Open-Meteo's geocoding endpoint, caches results in a module-level dict keyed by the lowercased+stripped name, and raises `WidgetError` for HTTP errors or empty results.

**Files:**

- Test: `tests/widgets/test_weather.py`
- Modify: `app/widgets/weather.py`

- [ ] **Step 1: Add an autouse fixture to clear the geocode cache between tests**

At the top of `tests/widgets/test_weather.py` (after the existing imports), add:

```python
@pytest.fixture(autouse=True)
def _clear_weather_caches() -> None:
    """Reset module-level caches so tests don't leak state into each other.
    Defensive about the attribute because it gets added later in this same task."""
    import app.widgets.weather as w
    cache = getattr(w, "_GEOCODE_CACHE", None)
    if cache is not None:
        cache.clear()
```

- [ ] **Step 2: Write the failing geocode tests**

Append to `tests/widgets/test_weather.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/widgets/test_weather.py -v -k geocode`
Expected: 5 tests FAIL — all with `ImportError: cannot import name '_geocode'`. (The autouse fixture is defensive about the cache attribute, so it does not contribute extra failures.)

- [ ] **Step 4: Implement `_geocode` and the cache**

In `app/widgets/weather.py`, below the icon helpers, add:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/widgets/test_weather.py -v -k geocode`
Expected: 5 tests PASS.

Also run the whole weather test module:

Run: `uv run pytest tests/widgets/test_weather.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/widgets/weather.py tests/widgets/test_weather.py
git commit -m "feat(weather): add geocoding helper with in-memory cache"
```

---

## Task 6: Wire location resolution into `fetch`

Add coordinate-resolution logic to `fetch`: if `location` is set use `_geocode`, else use `lat`/`lon`, else raise. Also expand the integration tests to cover the geocoded path and the missing-config error.

**Files:**

- Test: `tests/widgets/test_weather.py`
- Modify: `app/widgets/weather.py:30-62`

- [ ] **Step 1: Write the failing tests for the new behaviour**

Append to `tests/widgets/test_weather.py`:

```python
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
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/widgets/test_weather.py -v -k "location or requires"`
Expected: 5 tests FAIL — the widget currently doesn't honour `location` at all.

- [ ] **Step 3: Refactor `fetch` to resolve coordinates first**

In `app/widgets/weather.py`, replace the entire `fetch` method with:

```python
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
```

- [ ] **Step 4: Run all weather tests to verify they pass**

Run: `uv run pytest tests/widgets/test_weather.py -v`
Expected: all tests PASS, including the original `test_weather_fetch_returns_current_and_forecast` (lat/lon path is preserved) and the new location-based tests.

- [ ] **Step 5: Commit**

```bash
git add app/widgets/weather.py tests/widgets/test_weather.py
git commit -m "feat(weather): resolve coords from location (geocode) or lat/lon"
```

---

## Task 7: Update the config schema (form metadata)

Drop `required: ["lat", "lon"]`, add `location` as a string property. Update the metadata test to assert the new shape.

**Files:**

- Modify: `app/widgets/weather.py:20-28`
- Test: `tests/widgets/test_weather.py:38-43`

- [ ] **Step 1: Update the metadata test**

Replace the existing `test_weather_metadata` in `tests/widgets/test_weather.py` with:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/widgets/test_weather.py::test_weather_metadata -v`
Expected: FAIL on `assert "location" in props`.

- [ ] **Step 3: Update the schema**

In `app/widgets/weather.py`, replace the `config_schema` class attribute with:

```python
    config_schema = {
        "type": "object",
        "properties": {
            "location": {"type": "string", "title": "Location (town name)"},
            "lat": {"type": "number", "title": "Latitude"},
            "lon": {"type": "number", "title": "Longitude"},
            "days": {"type": "integer", "title": "Forecast days", "default": 3, "minimum": 1, "maximum": 7},
        },
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/widgets/test_weather.py::test_weather_metadata -v`
Expected: PASS.

Also run the full weather test module:

Run: `uv run pytest tests/widgets/test_weather.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/widgets/weather.py tests/widgets/test_weather.py
git commit -m "feat(weather): expose 'location' in widget config schema"
```

---

## Task 8: Update the weather widget template

Add inline SVG icons to the current and forecast tiles. The Lucide SVGs use `stroke="currentColor"` so they pick up the surrounding text colour.

**Files:**

- Modify: `app/templates/widgets/weather.html`

- [ ] **Step 1: Replace the template**

Overwrite `app/templates/widgets/weather.html` with:

```html
<div class="widget widget-weather">
  <div class="weather-now">
    <div class="weather-icon">{{ current_icon_svg | safe }}</div>
    <div class="weather-now-text">
      <div class="weather-temp">{{ current_temp }}°</div>
      <div class="weather-label">{{ current_label }}</div>
    </div>
  </div>
  <div class="weather-forecast">
    {% for day in forecast %}
      <div class="weather-day">
        <div class="weather-day-icon">{{ day.icon_svg | safe }}</div>
        <div class="weather-day-temps">{{ day.max }}° / {{ day.min }}°</div>
        <div class="weather-day-date">{{ day.date[5:] }}</div>
      </div>
    {% endfor %}
  </div>
</div>
```

Notes:

- The current block is restructured into a flex row: icon on the left, temp+label stacked on the right.
- Each forecast day now leads with the icon, then temps, then the abbreviated date — matching the spec's mockup.

- [ ] **Step 2: Verify the template parses by rendering the editor preview HTML**

Run: `uv run pytest tests/test_routes_editor.py -v -k preview`
Expected: existing editor-preview route tests still PASS (template renders without Jinja errors).

If there are no preview-specific tests, instead run the full test suite to confirm nothing regressed:

Run: `uv run pytest -v`
Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add app/templates/widgets/weather.html
git commit -m "feat(weather): inline SVG icons in widget template"
```

---

## Task 9: Style the icons in dashboard.html and widget_preview.html

Add CSS rules so the inline SVGs sit at sensible sizes in both contexts. Sizes scale with `--font-scale` so zoom view automatically renders larger icons.

**Files:**

- Modify: `app/templates/dashboard.html:39-45`
- Modify: `app/templates/widget_preview.html:19-25`

- [ ] **Step 1: Update dashboard.html weather styles**

In `app/templates/dashboard.html`, locate the existing `.widget-weather` / `.weather-*` rule block (around lines 39-45) and replace it with:

```css
  .widget-weather { display: flex; flex-direction: column; gap: 8px; }
  .weather-now { display: flex; align-items: center; gap: 12px; }
  .weather-icon { flex: 0 0 auto; line-height: 0; }
  .weather-icon svg { width: calc(56px * var(--font-scale)); height: calc(56px * var(--font-scale)); }
  .weather-now-text { display: flex; flex-direction: column; }
  .weather-temp { font-size: calc(48px * var(--font-scale)); font-weight: 700; line-height: 1; }
  .weather-label { font-size: calc(18px * var(--font-scale)); }
  .weather-forecast { display: flex; gap: 8px; }
  .weather-day { flex: 1; border: var(--border); padding: var(--cell-padding); font-size: calc(12px * var(--font-scale)); text-align: center; display: flex; flex-direction: column; align-items: center; gap: 2px; }
  .weather-day-icon { line-height: 0; }
  .weather-day-icon svg { width: calc(28px * var(--font-scale)); height: calc(28px * var(--font-scale)); }
  .weather-day-temps { font-weight: 700; }
  .weather-day-date { color: #000; opacity: 0.8; }
```

- [ ] **Step 2: Update widget_preview.html weather styles**

In `app/templates/widget_preview.html`, locate the existing `.widget-weather` / `.weather-*` rule block (around lines 19-25) and replace it with the same structure, scaled down to fit the editor iframe:

```css
  .widget-weather { display: flex; flex-direction: column; gap: 4px; }
  .weather-now { display: flex; align-items: center; gap: 8px; }
  .weather-icon { flex: 0 0 auto; line-height: 0; }
  .weather-icon svg { width: calc(34px * var(--font-scale)); height: calc(34px * var(--font-scale)); }
  .weather-now-text { display: flex; flex-direction: column; }
  .weather-temp { font-size: calc(28px * var(--font-scale)); font-weight: 700; line-height: 1; }
  .weather-label { font-size: calc(13px * var(--font-scale)); }
  .weather-forecast { display: flex; gap: 4px; }
  .weather-day { flex: 1; border: var(--border); padding: var(--cell-padding); font-size: calc(10px * var(--font-scale)); text-align: center; display: flex; flex-direction: column; align-items: center; gap: 1px; }
  .weather-day-icon { line-height: 0; }
  .weather-day-icon svg { width: calc(18px * var(--font-scale)); height: calc(18px * var(--font-scale)); }
  .weather-day-temps { font-weight: 700; }
  .weather-day-date { color: #000; opacity: 0.8; }
```

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS — these are CSS-only changes, no behaviour changed.

- [ ] **Step 4: Commit**

```bash
git add app/templates/dashboard.html app/templates/widget_preview.html
git commit -m "feat(weather): style inline icons in dashboard and editor preview"
```

---

## Task 10: Manual verification

Verify the widget renders correctly in both the editor preview (browser) and the dashboard PNG (WeasyPrint pipeline). This is the only step that exercises the full stack end-to-end.

**Files:** none

- [ ] **Step 1: Start the dev server**

Run (in a separate terminal or background process):

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Expected: server starts without error, listening on `http://127.0.0.1:8000`.

- [ ] **Step 2: Hit the dashboard PNG endpoint to exercise the WeasyPrint pipeline with the existing lat/lon config**

Run:

```bash
curl -fsS -o /tmp/dash-latlon.png http://127.0.0.1:8000/dashboards/example/render.png && file /tmp/dash-latlon.png
```

Expected: file is a PNG image, ~hundreds of kB. Open `/tmp/dash-latlon.png` (e.g. `open /tmp/dash-latlon.png` on macOS) and visually confirm:

- The current temperature is shown with a Lucide icon to its left.
- Each forecast tile shows an icon above the temps and date.
- Icons are crisp (vector) and rendered in pure black-and-white.

- [ ] **Step 3: Edit the example dashboard to use a town name, then re-render**

Edit `config/dashboards/example.json` and replace the weather widget's `config` block with:

```json
"config": {
  "location": "Munich",
  "days": 3
}
```

Then re-hit the render endpoint:

```bash
curl -fsS -o /tmp/dash-location.png http://127.0.0.1:8000/dashboards/example/render.png && file /tmp/dash-location.png
```

Expected: file is a PNG image. Open it and confirm the weather section still renders correctly — temps and condition labels appear, icons line up. (Open-Meteo should resolve "Munich" → Munich, Germany; temperatures may differ from before but the layout should be identical.)

- [ ] **Step 4: Visit the editor preview for the weather widget**

Open in a browser:

```
http://127.0.0.1:8000/editor/example
```

Click the weather widget; confirm:

- The form now has a "Location (town name)" field (in addition to Latitude/Longitude).
- The preview iframe shows the icon-enriched layout.
- Editing the location field and saving updates the preview correctly.

- [ ] **Step 5: Revert the example dashboard change**

The location change in `config/dashboards/example.json` was for verification only. Restore the original lat/lon config:

```bash
git checkout -- config/dashboards/example.json
```

Expected: `git status` shows no remaining changes in `config/`.

- [ ] **Step 6: Stop the dev server**

Stop the uvicorn process (Ctrl+C in its terminal, or kill the background PID).

- [ ] **Step 7: Final test sweep**

Run the full suite one more time as a sanity check:

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 8: No additional commit required**

Steps 3 and 5 cancel each other out; nothing else changed on disk. If `git status` shows unexpected changes, investigate before continuing.

---

## Verification Checklist

After all tasks above are complete, confirm:

- [ ] `uv run pytest -v` reports green across the suite, including the new geocode, cache, icon-mapping, and metadata tests.
- [ ] The editor preview for the weather widget shows icons and accepts a town name in the form.
- [ ] The dashboard PNG (`/dashboards/example/render.png`) renders icons crisply in black-and-white.
- [ ] `git log` shows 7-8 small, focused commits (one per task with code changes).
- [ ] `config/dashboards/example.json` is unchanged on disk.
