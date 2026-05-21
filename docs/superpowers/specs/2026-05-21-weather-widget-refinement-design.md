# Weather widget refinement — design

Date: 2026-05-21

## Goal

Refine the existing `weather` widget so dashboards can be configured by **town name** (in addition to the existing lat/lon), and so weather conditions are shown as **icons** alongside the textual labels.

## Non-goals

- No change to the rendering pipeline (HTML → PDF → PNG → grayscale stays as is).
- No change to other widgets.
- No new dependencies; geocoding uses Open-Meteo's existing free endpoint.
- No detail/zoom-specific template — the zoom view continues to use the same template at a larger scale.

## Background

The current widget ([app/widgets/weather.py](../../../app/widgets/weather.py)) requires `lat` and `lon` and renders a textual label for each condition (e.g., "Partly cloudy"). The widget form is auto-generated from `config_schema` ([app/templates/_widget_form.html](../../../app/templates/_widget_form.html)) and only understands number/integer/text inputs — no `anyOf`/conditional support.

## Design

### Location input

The widget config gains a `location` (string) field. `lat` and `lon` become optional. Resolution order at fetch time:

1. If `location` is set and non-empty → geocode via Open-Meteo's search endpoint:
   `GET https://geocoding-api.open-meteo.com/v1/search?name=<location>&count=1&language=en&format=json`
   Use `results[0].latitude` and `results[0].longitude`. If `results` is empty, raise `WidgetError(f"weather: could not find location '{location}'")`.
2. Else if `lat` and `lon` are both set → use them (existing behaviour).
3. Else → raise `WidgetError("weather: location or lat/lon required")`.

**Caching.** Geocode results are cached in a module-level dict keyed by the stripped, lowercased location string. No TTL — towns don't move. The cache lives for the lifetime of the process.

**Schema.** `config_schema` becomes:

```python
{
    "type": "object",
    "properties": {
        "location": {"type": "string", "title": "Location (town name)"},
        "lat": {"type": "number", "title": "Latitude"},
        "lon": {"type": "number", "title": "Longitude"},
        "days": {"type": "integer", "title": "Forecast days", "default": 3,
                 "minimum": 1, "maximum": 7},
    },
}
```

`required` is removed; validation happens in `fetch`. Existing dashboards (`config/dashboards/example.json` uses `lat`/`lon`) keep working untouched.

### Icons

Ship a small set of Lucide SVGs at [app/static/icons/weather/](../../../app/static/icons/weather/) (Lucide is ISC-licensed; no attribution required in dist). Nine files total:

`sun.svg`, `cloud-sun.svg`, `cloud.svg`, `cloud-fog.svg`, `cloud-drizzle.svg`, `cloud-rain.svg`, `cloud-snow.svg`, `cloud-rain-wind.svg`, `cloud-lightning.svg`.

Mapping from Open-Meteo `weather_code` lives in `weather.py` next to the existing `WEATHER_CODES`:

| codes              | icon name           |
|--------------------|---------------------|
| 0, 1               | `sun`               |
| 2                  | `cloud-sun`         |
| 3                  | `cloud`             |
| 45, 48             | `cloud-fog`         |
| 51, 53, 55         | `cloud-drizzle`     |
| 61, 63, 65         | `cloud-rain`        |
| 71, 73, 75         | `cloud-snow`        |
| 80, 81, 82         | `cloud-rain-wind`   |
| 95                 | `cloud-lightning`   |
| anything else      | `cloud` (fallback)  |

The `fetch` context gains an `icon_svg` string (inline SVG markup) for `current` and for each forecast `day` (daytime-only — no day/night variants). SVGs are loaded into a module-level dict at import time so each render is just a lookup. Inlining (rather than `<img src=...>`) avoids the URL-resolution problem that WeasyPrint has with relative paths in HTML strings — the same approach the project already uses for fonts via `file://` URIs is sidestepped entirely here.

### Layout

**Current block** — icon on the left, temp + label stacked to the right:

```
[ ☼ ]   18°
        Partly cloudy
```

**Forecast tile** — icon centred at top, then temps, then date:

```
   ┌──────────┐
   │   [☁]    │
   │ 21°/12°  │
   │  05-20   │
   └──────────┘
```

Template updates in [app/templates/widgets/weather.html](../../../app/templates/widgets/weather.html) — render `{{ icon_svg | safe }}` wrapped in a sized container (`.weather-icon` / `.weather-day-icon`) for the current and each forecast day. New CSS rules live in both [app/templates/dashboard.html](../../../app/templates/dashboard.html) (used by the WeasyPrint render) and [app/templates/widget_preview.html](../../../app/templates/widget_preview.html) (used by the editor iframe preview). The Lucide SVGs use `stroke="currentColor"`, so the icon colour follows CSS `color` — and on a 1-bit dithered Kindle output, everything resolves to black anyway. Icon sizes scale with `--font-scale` so the zoom view automatically renders larger icons (e.g. ~48px for the current icon, ~24px for forecast tiles, both multiplied by `--font-scale`).

WeasyPrint embeds inline `<svg>` as a vector into the PDF; output stays crisp through the PDF → PNG → grayscale pipeline.

## Data flow

```
config{location?, lat?, lon?, days?}
    │
    ▼
_resolve_coords(cfg)  ──► (lat, lon)         # geocode + cache, or pass-through
    │
    ▼
GET /v1/forecast → { current, daily }
    │
    ▼
build context: { current_temp, current_label, current_icon_svg, forecast[{date, max, min, label, icon_svg}] }
    │
    ▼
template renders <img> tags + text → HTML → PDF → PNG → grayscale
```

## Error handling

- Geocoding HTTP error → `WidgetError("weather geocode failed: ...")`.
- Geocoding returns empty `results` → `WidgetError(f"weather: could not find location '{name}'")`.
- Forecast HTTP error → existing `WidgetError("weather fetch failed: ...")` (unchanged).
- Missing all of `location`/`lat`/`lon` → `WidgetError("weather: location or lat/lon required")`.

All errors are caught by `app/render.py::_fetch_item` and rendered as a per-cell error box, same as today.

## Testing

Extend [tests/widgets/test_weather.py](../../../tests/widgets/test_weather.py) with `respx`-mocked tests:

1. **Geocoded fetch** — `location: "Munich"`, no lat/lon: mocks the geocoding endpoint and the forecast endpoint; asserts both were called and the result contains expected temps + icons.
2. **Geocode cache** — call `fetch` twice with the same `location`; assert geocoding endpoint hit once, forecast hit twice.
3. **Geocode not found** — geocoding returns `{"results": []}`; expect `WidgetError` containing "could not find".
4. **Geocode HTTP error** — geocoding returns 500; expect `WidgetError` containing "geocode".
5. **Lat/lon still works** — no `location`, with `lat`/`lon`: behaves exactly as today (existing test, kept).
6. **Missing location and coords** — empty config (no `location`, no `lat`, no `lon`): `WidgetError("location or lat/lon required")`.
7. **Icon mapping (pure helper)** — for a representative set of weather codes (0, 2, 3, 45, 61, 75, 82, 95), assert the `_icon_name_for_code` helper returns the expected names from the mapping table.
8. **Unknown code fallback** — a synthetic code (e.g., 99) maps to `cloud`.
9. **Context contains inline SVG** — the happy-path fetch context has non-empty `current_icon_svg` and `forecast[i].icon_svg` strings containing `<svg`.

Metadata test (`test_weather_metadata`) updates to assert `location` is in the schema properties and `required` is absent.

## Files touched

- `app/widgets/weather.py` — geocode helper + cache, resolution logic, icon name mapping, inline-SVG loader, context fields.
- `app/templates/widgets/weather.html` — inline-SVG icons; layout adjustment.
- `app/templates/dashboard.html` — new CSS rules for `.weather-icon`, `.weather-day-icon`.
- `app/templates/widget_preview.html` — matching CSS rules for the editor iframe preview.
- `app/static/icons/weather/*.svg` — 9 new files (Lucide).
- `tests/widgets/test_weather.py` — new tests as listed above.

No changes to `example.json`, `render.py`, `theme.py`, or any other widget.
