# Kindle Dashboard — Design

## Context

Reuse an old Kindle Paperwhite 1/2 as an e-ink wall dashboard. The Kindle runs
[kindle-dash](https://github.com/pascalw/kindle-dash) (a small on-device script
that polls a URL and displays the returned PNG). We need to build the server
side: a web app that lets the user arrange and configure widgets in a grid,
stores dashboard layouts as plain JSON, and serves rendered PNGs on demand.

The host is a Raspberry Pi 4 (4 GB) that already runs iobroker and Grafana
(consuming ~1–2 GB RAM). The dashboard server must coexist on the same Pi
without leaning heavily on memory — so headless Chromium is out, even though
it would otherwise be the obvious renderer.

Primary widgets in v1: clock, weather, Grafana panel, iobroker state value,
iCloud calendar items. Multiple named dashboards (e.g. `morning`, `evening`,
`livingroom`); time-of-day routing is handled Kindle-side by the kindle-dash
cron hitting different URLs at different times — the server stays stateless
about scheduling.

## Stack

- **Language:** Python 3.11+
- **Web framework:** FastAPI (async, lean, good fit for image-serving endpoints)
- **HTML → PNG:** WeasyPrint (no Chromium dependency, ~80 MB resident)
- **Image post-processing:** Pillow (grayscale conversion + Floyd-Steinberg dither)
- **Templating:** Jinja2 (bundled with FastAPI's `TemplateResponse`)
- **Editor UI:** HTMX + [Gridstack.js](https://gridstackjs.com/) (no JS build step)
- **HTTP client:** httpx (async, supports parallel widget fetches)
- **CalDAV (iCloud):** [`caldav`](https://pypi.org/project/caldav/) library
- **Storage:** plain JSON files, no database

Rejected:
- **Elixir/Phoenix** — LiveView upside doesn't justify the learning ramp; still
  needs an external renderer; Elixir compiles are painful on a Pi.
- **Headless Chromium (Playwright/Puppeteer)** — 300–400 MB resident is too
  tight on a 4 GB Pi already hosting iobroker + Grafana.
- **Pillow-only composition** — editor preview would drift from the rendered
  output; adding widgets becomes a code change instead of a template change.

## Architecture

```
┌────────────── Raspberry Pi 4 ──────────────┐
│                                             │       LAN
│  ┌────────────┐    ┌──────────────────┐    │   ┌──────────┐
│  │ iobroker   │◀───│ kindledashboard  │◀───┼───│  Kindle  │
│  │ + grafana  │    │   (FastAPI app)  │    │   │ PW1/PW2  │
│  └────────────┘    │                  │    │   │ kindle-  │
│         ▲          │  /editor   (UI)  │    │   │  dash    │
│         │          │  /dash/<name>.png│    │   └──────────┘
│         │          │  /preview/<name> │    │
│         │          └──────────────────┘    │
│         │                  │               │
│         │                  ▼               │
│         │           ┌────────────┐         │
│         │           │ config/    │         │
│         │           │  *.json    │         │
│         │           └────────────┘         │
└─────────┼───────────────────────────────────┘
          │
   weather API (Open-Meteo, no key)
   iCloud CalDAV
```

Three concerns share one FastAPI process:

1. **Editor UI** (`/editor`) — HTMX-rendered pages with a Gridstack.js canvas.
   Users drag widgets onto a 12×16 grid sized to 758×1024 px, edit per-widget
   config in a schema-driven side panel, and save explicitly.
2. **Renderer** (`/dash/<name>.png`) — loads dashboard JSON, fetches data from
   each widget in parallel, renders a Jinja template to HTML, hands it to
   WeasyPrint for HTML→PNG, then Pillow converts to grayscale + dithers,
   returns the PNG.
3. **Preview** (`/preview/<name>`) — returns the *exact same HTML* the renderer
   would rasterize, so the editor's "Preview" button shows what the Kindle
   will actually display.

**No JavaScript runs in the rendered HTML.** That's what lets us skip Chromium.
Every widget fetches its data server-side during template render. Grafana
panels are embedded as `<img src="...grafana render API...">` (Grafana
already produces PNGs via its `grafana-image-renderer` plugin), not as live
panels.

## Widget Layer

```
app/widgets/
├── base.py            # Widget protocol
├── clock.py           # ClockWidget
├── weather.py         # WeatherWidget   (Open-Meteo, no key needed)
├── grafana.py         # GrafanaPanelWidget
├── iobroker.py        # IobrokerStateWidget
└── calendar.py        # ICloudCalendarWidget
```

Widget protocol:

```python
class Widget(Protocol):
    type: str                              # e.g. "weather"
    config_schema: dict                    # drives the config form
    template: str                          # Jinja partial path
    async def fetch(self, cfg: dict) -> dict: ...   # returns template ctx
```

The dashboard template iterates layout items, calls `widget.fetch(cfg)`,
then includes `widget.template` with the returned context. Each partial is
self-contained HTML/CSS scoped to its grid cell.

**Widget specifics (v1):**

| Widget | Source | Cache TTL | Notes |
|---|---|---|---|
| Clock | render time | none | Re-renders on every request |
| Weather | Open-Meteo | 10 min | No API key; configurable lat/lon, forecast days |
| Grafana panel | `/render/d-solo/...` | 0 (Grafana caches) | Requires `grafana-image-renderer` plugin + API token |
| iobroker state | `simple-api` REST | 30 s | `http://pi:8087/get/<state-id>` |
| iCloud calendar | CalDAV via `caldav` lib | 5 min | App-specific password required |

**Failure mode:** if any widget's `fetch()` raises, that single cell renders
a "⚠ widget unavailable" box. The dashboard as a whole still ships.

## Configuration & Storage

```
config/
├── dashboards/
│   ├── morning.json
│   ├── evening.json
│   └── livingroom.json
└── secrets.json        # API tokens, app-passwords (gitignored)
```

Dashboard JSON shape:

```json
{
  "name": "morning",
  "size": { "w": 758, "h": 1024 },
  "grid": { "cols": 12, "rows": 16 },
  "dither": "fs",
  "widgets": [
    {
      "id": "w1",
      "type": "clock",
      "pos": { "x": 0, "y": 0, "w": 12, "h": 2 },
      "config": { "format": "HH:mm" }
    },
    {
      "id": "w2",
      "type": "weather",
      "pos": { "x": 0, "y": 2, "w": 6, "h": 4 },
      "config": { "lat": 48.137, "lon": 11.575, "days": 3 }
    },
    {
      "id": "w3",
      "type": "grafana",
      "pos": { "x": 6, "y": 2, "w": 6, "h": 4 },
      "config": {
        "url": "http://localhost:3000",
        "dashboard": "abc123/heating",
        "panel_id": 4,
        "token": "$grafana_token"
      }
    }
  ]
}
```

**Secrets** live in `config/secrets.json` and are referenced from widget
configs by `$name` (e.g. `"token": "$grafana_token"`). This keeps dashboard
JSONs committable to git if the user ever wants version control.

**Writes are atomic:** save to `<name>.json.tmp`, then `os.rename`. No
partial-write corruption if the Pi loses power mid-save.

A thin `ConfigStore` class wraps `json.load` / `json.dump` and validates
widgets against their `config_schema` on save.

## Render Pipeline

```
GET /dash/morning.png

1. Load config/dashboards/morning.json       (<5 ms)
2. For each widget: await widget.fetch(cfg)   (parallel via asyncio.gather)
3. Render Jinja template → HTML string       (CSS Grid sized 758×1024)
4. WeasyPrint:  HTML → PNG (RGBA, 758×1024)  (~200–400 ms)
5. Pillow:      RGBA → "L" (grayscale) →
                "1" with Floyd-Steinberg dither (per dashboard cfg)
                                              (~50 ms)
6. HTTP 200, Content-Type: image/png
                Cache-Control: no-store
```

Total budget: under ~1 second per render, even with cold widget fetches.
Warm-cache renders land at ~250 ms.

**Dither mode** is per-dashboard config:
- `"fs"` — Floyd-Steinberg, best for photo-heavy widgets
- `"none"` — 8-bit grayscale, better for text-heavy dashboards

## Editor UI

```
┌─ /editor ─────────────────────────────────────────────────┐
│  Dashboard: [ morning ▼ ]  [+ New] [Duplicate] [Delete]   │
├──────────────────────────────┬────────────────────────────┤
│                              │  Widget palette            │
│   ┌────────────────────┐     │  ⏰ Clock                  │
│   │                    │     │  🌦 Weather                │
│   │   Gridstack.js     │     │  📊 Grafana panel          │
│   │   canvas, scaled   │     │  🔌 iobroker state         │
│   │   758×1024 → CSS   │     │  📅 iCloud calendar        │
│   │                    │     │                            │
│   │   drag widgets,    │     │  Selected widget config    │
│   │   resize by grid   │     │  ─────────────             │
│   │                    │     │  (HTMX form rendered       │
│   └────────────────────┘     │   from widget schema)      │
│                              │                            │
│  [👁 Preview] [💾 Save]      │                            │
└──────────────────────────────┴────────────────────────────┘
```

Mechanics:
- **Gridstack.js** drives the drag/resize on a 12×16 grid (cell ≈ 63×64 px).
  On layout change, HTMX POSTs to `/api/dashboards/<name>/layout`.
- **Per-widget config form** is HTMX-driven. Clicking a widget on the canvas
  swaps the right panel via `GET /api/widgets/<id>/config-form`. The form
  is server-rendered from the widget's `config_schema`. Submit PATCHes to
  `/api/widgets/<id>`. No frontend framework, no build step.
- **Preview button** opens `/preview/<name>` in a new tab — the same HTML
  the renderer rasterizes.
- **Explicit save**, no live auto-save. Avoids races and surprise overwrites.

**Out of scope for v1:**
- Multi-user auth (LAN only; add nginx basic-auth if exposed later)
- Dashboard versioning / undo history
- Widget marketplace, theming, custom CSS editor
- A "compose dashboards into a schedule" UI (Kindle-side cron handles that)

## Error Handling

- **Widget fetch failure** → cell renders "⚠ widget unavailable" box; render
  succeeds.
- **Invalid dashboard config** → `/editor` shows inline validation;
  `/dash/<name>.png` returns 422 with a tiny static error PNG so the Kindle
  still shows *something* (not a frozen previous frame).
- **WeasyPrint failure** → fall back to a generic "render error" PNG with
  timestamp; full stack trace logged.
- **Network timeouts** on upstream APIs → 5 s default per fetch; treated as
  fetch failure (per-widget cell error).

## Testing

- **Unit:** each widget's `fetch()` mocked against fixture HTTP responses
  using `respx` (httpx mocking).
- **Template snapshot:** render each widget partial with fixture data,
  snapshot the HTML. Catches accidental layout breakage.
- **Render integration:** one test renders a fixture dashboard end-to-end
  and asserts the PNG is 758×1024, mode `L` or `1`, and non-empty.
- **No browser automation needed.** WeasyPrint is deterministic.

## Deployment

- `pip install` into a venv at `/opt/kindledashboard/venv`
- systemd unit `kindledashboard.service` runs
  `uvicorn app:app --host 0.0.0.0 --port 8080`
- System deps for WeasyPrint:
  `apt install libpango-1.0-0 libpangoft2-1.0-0`
- **No Chromium needed.**
- iobroker `simple-api` adapter must be installed (typically already is).
- Grafana `grafana-image-renderer` plugin: install via
  `grafana-cli plugins install grafana-image-renderer` if not already present.

Out of scope: Docker packaging, HTTPS (kindle-dash is happy with HTTP on
LAN), multi-tenant auth.

## Verification

End-to-end smoke test for the finished v1:

1. Start the service: `systemctl start kindledashboard`
2. Open `http://pi:8080/editor` in a browser. Create a new dashboard named
   `test`, drop a clock + weather widget, configure weather lat/lon, save.
3. Open `http://pi:8080/preview/test` — confirm it renders in the browser
   exactly as designed.
4. `curl -o /tmp/test.png http://pi:8080/dash/test.png` — confirm it returns
   a 758×1024 PNG within ~1 second.
5. Inspect `/tmp/test.png` — confirm grayscale and content matches the
   preview.
6. Configure kindle-dash on the Kindle to poll the URL; confirm the image
   displays on the device.
7. Restart the Pi — confirm the service comes back up via systemd, and
   `test.json` still loads (atomic-write didn't corrupt anything across
   reboot).

## Key Files (to be created)

- `app/main.py` — FastAPI app setup
- `app/routes/editor.py` — `/editor`, `/api/dashboards/...`
- `app/routes/render.py` — `/dash/<name>.png`, `/preview/<name>`
- `app/render.py` — WeasyPrint + Pillow pipeline
- `app/config_store.py` — JSON load/save with atomic writes + validation
- `app/widgets/base.py` — Widget protocol + registry
- `app/widgets/{clock,weather,grafana,iobroker,calendar}.py`
- `app/templates/dashboard.html` — root template with CSS Grid layout
- `app/templates/widgets/*.html` — per-widget partials
- `app/static/gridstack.{js,css}` — vendored
- `config/dashboards/example.json` — example config
- `deploy/kindledashboard.service` — systemd unit
- `tests/test_widgets.py`, `tests/test_render.py`
