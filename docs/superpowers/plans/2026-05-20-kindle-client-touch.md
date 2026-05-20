# Kindle Client + Touch Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **After plan approval, this file should be moved to** `docs/superpowers/plans/2026-05-20-kindle-client-touch.md`.

**Goal:** Add per-device view state + tap-to-zoom to the FastAPI backend, and ship a Go-based Kindle PW1/PW2 client that polls the dashboard PNG and forwards touch events.

**Architecture:** Two independent subsystems delivered as two phases. Phase A extends the existing FastAPI app with an in-memory view-state store, a zone resolver, a zoom render path, a `device` query param on `/dash/{name}.png`, and a new `POST /tap/{name}` route — all verifiable end-to-end with `curl` and no Kindle. Phase B is a single static Go binary (`kindled`) for the Kindle that runs a display-poll loop and a touch-reader goroutine, packaged as a KUAL extension that runs alongside the native Kindle framework (kindle-dash style).

**Tech Stack:** FastAPI, Pillow, WeasyPrint, pypdfium2, pytest (backend) — Go 1.22 (`GOOS=linux GOARCH=arm GOARM=7 CGO_ENABLED=0`), KUAL, BusyBox `ash`, `eips`, `/dev/input/event*` (client).

**Spec:** [docs/superpowers/specs/2026-05-20-kindle-client-touch-design.md](docs/superpowers/specs/2026-05-20-kindle-client-touch-design.md)

---

## Context

The dashboard backend currently renders PNGs at `/dash/<name>.png` for any client that polls. We want to make the Kindle interactive: tap a widget → see it zoomed full-screen with a "back" strip → tap the strip to return. The Kindle stays dumb; all view logic lives server-side. View state is per-(dashboard, device), in-memory, ephemeral.

The existing `kindle-dash` shell script (one-way polling) is being replaced by a new client living in `kindle_client/` inside this repo. We chose a static Go binary because Python isn't stock on PW1/PW2 and shell parsing of `input_event` structs is awkward — Go cross-compiles to a single ARMv7 binary with no runtime deps.

This is a focused extension. No dashboard JSON schema change. No persistence.

---

## File Structure

**Phase A — Backend (create):**
- `app/state.py` — `ViewState` dataclass + `ViewStateStore` (in-memory dict)
- `app/zones.py` — `resolve(dashboard, view, x, y) -> (kind, widget_id|None)`
- `app/routes/tap.py` — `POST /tap/{name}`
- `app/templates/zoom.html` — zoom frame with widget body + back strip
- `tests/test_state.py`, `tests/test_zones.py`, `tests/test_routes_tap.py`, `tests/test_render_zoom.py`

**Phase A — Backend (modify):**
- `app/render.py` — add `render_zoom_html`, `render_zoom_png`; reuse `_env`, `_html_to_png_bytes`, `_to_grayscale`
- `app/routes/render.py` — accept `device` query param, dispatch to zoom rendering when state demands it
- `app/deps.py` — add `configure_view_state_store` + `get_view_state_store`
- `app/main.py` — instantiate `ViewStateStore`, configure dep, include tap router
- `docs/superpowers/specs/2026-05-20-kindle-dashboard-design.md` — append pointer

**Phase B — Kindle client (create):**
- `kindle_client/go.mod`, `kindle_client/Makefile`
- `kindle_client/src/main.go` — wires display loop + touch loop, signal handling
- `kindle_client/src/config.go` + `_test.go` — parse `key=value` config
- `kindle_client/src/client.go` + `_test.go` — HTTP fetch + tap POST, write PNG, run `eips`
- `kindle_client/src/touch.go` + `_test.go` — resolve touchscreen device, parse `input_event` structs, emit `(x, y)` on `BTN_TOUCH` up
- `kindle_client/kual_extension/config.xml`, `menu.json`, `bin/start.sh`, `bin/stop.sh`
- `kindle_client/config.example.conf`
- `kindle_client/README.md`

---

## Reused utilities (don't re-implement)

| Need | Already exists | Where |
|------|----------------|-------|
| Jinja env loading templates from `app/templates/` | `_env` | [app/render.py:25-29](app/render.py#L25-L29) |
| HTML → PNG bytes (WeasyPrint + pypdfium2) | `_html_to_png_bytes` | [app/render.py:90-103](app/render.py#L90-L103) |
| PNG → grayscale (FS dither) | `_to_grayscale` | [app/render.py:106-112](app/render.py#L106-L112) |
| Fallback error PNG | `error_png` | [app/error_image.py:6-19](app/error_image.py#L6-L19) |
| Widget protocol + registry | `Widget`, `REGISTRY`, `get_widget` | [app/widgets/base.py](app/widgets/base.py), [app/widgets/__init__.py](app/widgets/__init__.py) |
| Per-widget fetch (returns Jinja ctx) | `Widget.fetch` | [app/widgets/base.py:15-17](app/widgets/base.py#L15-L17) |
| Dashboard loader | `ConfigStore.load` | [app/config_store.py:31-35](app/config_store.py#L31-L35) |
| FastAPI dep pattern | `configure_store` / `get_config_store` | [app/deps.py](app/deps.py) |

For the zoom path, widgets without a `detail_template` attribute fall back to their regular `template`, and widgets without `fetch_detail` fall back to `fetch`. The renderer uses `getattr(widget, "detail_template", None) or widget.template` and `getattr(widget, "fetch_detail", widget.fetch)` — no Protocol changes needed, keeping existing widgets untouched.

---

# Phase A — Backend

### Task 1: View-state store

**Files:**
- Create: `app/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_state.py
from app.state import ViewState, ViewStateStore


def test_default_view_is_dashboard():
    store = ViewStateStore()
    assert store.get("d", "kitchen") == ViewState(view="dashboard", widget_id=None)


def test_set_and_get_round_trip():
    store = ViewStateStore()
    store.set("d", "kitchen", ViewState(view="widget", widget_id="w2"))
    assert store.get("d", "kitchen").widget_id == "w2"


def test_devices_are_isolated():
    store = ViewStateStore()
    store.set("d", "a", ViewState(view="widget", widget_id="w1"))
    assert store.get("d", "b") == ViewState(view="dashboard", widget_id=None)


def test_dashboards_are_isolated():
    store = ViewStateStore()
    store.set("d1", "a", ViewState(view="widget", widget_id="w1"))
    assert store.get("d2", "a") == ViewState(view="dashboard", widget_id=None)


def test_view_state_is_frozen_dataclass():
    import dataclasses
    assert dataclasses.is_dataclass(ViewState)
    s = ViewState(view="dashboard", widget_id=None)
    try:
        s.view = "widget"  # type: ignore[misc]
        raise AssertionError("ViewState should be frozen")
    except dataclasses.FrozenInstanceError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.state'`

- [ ] **Step 3: Implement `app/state.py`**

```python
"""In-memory per-(dashboard, device) view state. Resets on process restart."""
from dataclasses import dataclass
from typing import Literal


View = Literal["dashboard", "widget"]


@dataclass(frozen=True)
class ViewState:
    view: View
    widget_id: str | None


DEFAULT = ViewState(view="dashboard", widget_id=None)


class ViewStateStore:
    """Maps (dashboard_name, device_id) -> ViewState. Thread-safety not required:
    the FastAPI event loop serializes route handlers and we don't share state
    across processes."""

    def __init__(self) -> None:
        self._states: dict[tuple[str, str], ViewState] = {}

    def get(self, dashboard: str, device: str) -> ViewState:
        return self._states.get((dashboard, device), DEFAULT)

    def set(self, dashboard: str, device: str, state: ViewState) -> None:
        self._states[(dashboard, device)] = state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/state.py tests/test_state.py
git commit -m "feat: add in-memory ViewStateStore for per-device dashboard view"
```

---

### Task 2: Zone resolver

**Files:**
- Create: `app/zones.py`
- Test: `tests/test_zones.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_zones.py
import pytest

from app.state import ViewState
from app.zones import resolve


DASH = {
    "name": "d",
    "size": {"w": 758, "h": 1024},
    "grid": {"cols": 12, "rows": 16},
    "widgets": [
        {"id": "top",    "type": "clock",   "pos": {"x": 0, "y": 0, "w": 12, "h": 8},  "config": {}},
        {"id": "bottom", "type": "weather", "pos": {"x": 0, "y": 8, "w": 12, "h": 8},  "config": {}},
    ],
}


@pytest.mark.parametrize("x,y,expected", [
    (379, 100, ("widget", "top")),
    (379, 700, ("widget", "bottom")),
    (379, 511, ("widget", "top")),     # exact boundary belongs to upper
    (379, 512, ("widget", "bottom")),
])
def test_dashboard_view_widget_hits(x, y, expected):
    state = ViewState(view="dashboard", widget_id=None)
    assert resolve(DASH, state, x, y) == expected


def test_dashboard_view_background_when_no_widget_covers_point():
    sparse = {**DASH, "widgets": [
        {"id": "tiny", "type": "clock", "pos": {"x": 0, "y": 0, "w": 1, "h": 1}, "config": {}},
    ]}
    state = ViewState(view="dashboard", widget_id=None)
    assert resolve(sparse, state, 700, 900) == ("background", None)


def test_dashboard_view_out_of_bounds_is_background():
    state = ViewState(view="dashboard", widget_id=None)
    assert resolve(DASH, state, -1, 100) == ("background", None)
    assert resolve(DASH, state, 100, 9999) == ("background", None)


def test_widget_view_back_strip():
    state = ViewState(view="widget", widget_id="top")
    # back strip is bottom 80px: y in [944, 1024)
    assert resolve(DASH, state, 400, 950) == ("back", None)
    assert resolve(DASH, state, 400, 944) == ("back", None)


def test_widget_view_interior_above_back_strip():
    state = ViewState(view="widget", widget_id="top")
    assert resolve(DASH, state, 400, 943) == ("interior", "top")
    assert resolve(DASH, state, 400, 100) == ("interior", "top")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_zones.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.zones'`

- [ ] **Step 3: Implement `app/zones.py`**

```python
"""Convert a raw touch (x, y) into a semantic hit, given the dashboard
config and the device's current view state."""
from typing import Any, Literal

from app.state import ViewState


BACK_STRIP_HEIGHT = 80
HitKind = Literal["widget", "background", "back", "interior"]


def resolve(
    dashboard: dict[str, Any],
    state: ViewState,
    x: int,
    y: int,
) -> tuple[HitKind, str | None]:
    size = dashboard["size"]
    grid = dashboard["grid"]
    cell_w = size["w"] / grid["cols"]
    cell_h = size["h"] / grid["rows"]

    if state.view == "widget":
        if y >= size["h"] - BACK_STRIP_HEIGHT:
            return ("back", None)
        return ("interior", state.widget_id)

    # dashboard view: locate the widget under (x, y)
    for w in dashboard["widgets"]:
        p = w["pos"]
        x0 = p["x"] * cell_w
        y0 = p["y"] * cell_h
        x1 = (p["x"] + p["w"]) * cell_w
        y1 = (p["y"] + p["h"]) * cell_h
        if x0 <= x < x1 and y0 <= y < y1:
            return ("widget", w["id"])
    return ("background", None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_zones.py -v`
Expected: 8 passed (5 parametrized cases for first test + 4 more).

- [ ] **Step 5: Commit**

```bash
git add app/zones.py tests/test_zones.py
git commit -m "feat: add zone resolver mapping touch coords to widget/back/background"
```

---

### Task 3: Zoom template + render functions

**Files:**
- Create: `app/templates/zoom.html`
- Create: `tests/test_render_zoom.py`
- Modify: `app/render.py`

- [ ] **Step 1: Create `app/templates/zoom.html`**

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: {{ width }}px {{ height }}px; margin: 0; }
  html, body { margin: 0; padding: 0; width: {{ width }}px; height: {{ height }}px;
               font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; color: #000; }
  .zoom-body { width: {{ width }}px; height: {{ body_h }}px;
               padding: 16px; box-sizing: border-box; overflow: hidden; }
  .back-strip { width: {{ width }}px; height: {{ strip_h }}px;
                border-top: 2px solid #000;
                display: flex; align-items: center; justify-content: center;
                font-size: 32px; font-weight: 700; }
  /* Dashboard styles widgets may reference. Kept in sync with dashboard.html. */
  .widget { padding: 6px; }
  .widget-clock { text-align: center; }
  .clock-time { font-size: 200px; font-weight: 700; line-height: 1; }
  .clock-date { font-size: 56px; margin-top: 16px; }
  .widget-weather { display: flex; flex-direction: column; gap: 16px; }
  .weather-now { display: flex; align-items: baseline; gap: 24px; }
  .weather-temp { font-size: 140px; font-weight: 700; }
  .weather-label { font-size: 44px; }
  .weather-forecast { display: flex; gap: 12px; }
  .weather-day { flex: 1; border: 1px solid #000; padding: 8px; font-size: 28px; text-align: center; }
  .weather-day-date { font-weight: 700; }
  .widget-iobroker { text-align: center; }
  .iobroker-label { font-size: 36px; }
  .iobroker-value { font-size: 120px; font-weight: 700; }
  .widget-calendar { font-size: 32px; }
  .calendar-header { font-weight: 700; margin-bottom: 12px; }
  .calendar-events { list-style: none; padding: 0; margin: 0; }
  .calendar-events li { padding: 8px 0; border-bottom: 1px solid #000; }
  .cal-when { font-weight: 700; margin-right: 12px; }
  .widget-error { padding: 24px; font-size: 32px; }
</style>
</head>
<body>
  <div class="zoom-body">{{ body | safe }}</div>
  <div class="back-strip">&larr; back</div>
</body>
</html>
```

- [ ] **Step 2: Write the failing render tests**

```python
# tests/test_render_zoom.py
import io
import pytest
from freezegun import freeze_time
from PIL import Image

from app.render import render_zoom_html, render_zoom_png


DASH = {
    "name": "d",
    "size": {"w": 758, "h": 1024},
    "grid": {"cols": 12, "rows": 16},
    "dither": "none",
    "widgets": [
        {"id": "w1", "type": "clock", "pos": {"x": 0, "y": 0, "w": 12, "h": 8},
         "config": {"format": "HH:mm"}},
    ],
}


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_zoom_html_includes_widget_body_and_back_strip():
    html = await render_zoom_html(DASH, "w1")
    assert "09:00" in html
    assert "back-strip" in html
    assert "&larr;" in html or "← back" in html


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_zoom_png_matches_dashboard_size():
    png_bytes = await render_zoom_png(DASH, "w1")
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (758, 1024)
    assert img.mode in ("L", "1")


@pytest.mark.asyncio
async def test_render_zoom_html_raises_for_unknown_widget():
    with pytest.raises(KeyError):
        await render_zoom_html(DASH, "does-not-exist")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_render_zoom.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_zoom_html' from 'app.render'`.

- [ ] **Step 4: Extend `app/render.py`**

Add these constants and functions to the bottom of [app/render.py](app/render.py):

```python
ZOOM_BACK_STRIP_PX = 80


def _find_widget_cfg(dashboard: dict[str, Any], widget_id: str) -> dict[str, Any]:
    for w in dashboard["widgets"]:
        if w["id"] == widget_id:
            return w
    raise KeyError(f"widget {widget_id!r} not in dashboard {dashboard['name']!r}")


async def _fetch_zoom_body(widget_cfg: dict[str, Any]) -> tuple[str, str | None]:
    """Returns (body_html, error). On error, body_html is ''."""
    try:
        widget = get_widget(widget_cfg["type"])
        fetch_detail = getattr(widget, "fetch_detail", widget.fetch)
        template_name = getattr(widget, "detail_template", None) or widget.template
        ctx = await fetch_detail(widget_cfg.get("config", {}))
        tpl = _env.get_template(template_name)
        body = await tpl.render_async(**ctx)
        return body, None
    except Exception as exc:  # noqa: BLE001
        return "", str(exc) or type(exc).__name__


async def render_zoom_html(dashboard: dict[str, Any], widget_id: str) -> str:
    widget_cfg = _find_widget_cfg(dashboard, widget_id)
    body, error = await _fetch_zoom_body(widget_cfg)
    if error is not None:
        body = f'<div class="widget widget-error">&#9888; {error}</div>'
    width = dashboard["size"]["w"]
    height = dashboard["size"]["h"]
    template = _env.get_template("zoom.html")
    return await template.render_async(
        width=width,
        height=height,
        body_h=height - ZOOM_BACK_STRIP_PX,
        strip_h=ZOOM_BACK_STRIP_PX,
        body=body,
    )


async def render_zoom_png(dashboard: dict[str, Any], widget_id: str) -> bytes:
    html = await render_zoom_html(dashboard, widget_id)
    width = dashboard["size"]["w"]
    height = dashboard["size"]["h"]
    rgba_png = await asyncio.to_thread(_html_to_png_bytes, html, width, height)
    dither = dashboard.get("dither", "fs")
    return await asyncio.to_thread(_to_grayscale, rgba_png, dither)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_render_zoom.py -v`
Expected: 3 passed.

- [ ] **Step 6: Run the full test suite to confirm no regressions**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/templates/zoom.html app/render.py tests/test_render_zoom.py
git commit -m "feat: add zoom render path (zoom.html + render_zoom_png)"
```

---

### Task 4: ViewStateStore dependency wiring

**Files:**
- Modify: `app/deps.py`
- Modify: `app/main.py`

- [ ] **Step 1: Extend `app/deps.py`**

Add to [app/deps.py](app/deps.py):

```python
from app.state import ViewStateStore


_view_state: ViewStateStore | None = None


def configure_view_state_store(store: ViewStateStore) -> None:
    global _view_state
    _view_state = store


def get_view_state_store() -> ViewStateStore:
    if _view_state is None:
        raise RuntimeError("view state store not configured")
    return _view_state
```

- [ ] **Step 2: Wire it up in `app/main.py`**

Modify [app/main.py:1-18](app/main.py#L1-L18) so the imports and configuration include the new store:

```python
from app import widgets
from app.config_store import ConfigStore
from app.deps import configure_store, configure_view_state_store
from app.routes import editor as editor_routes
from app.routes import render as render_routes
from app.secrets import SecretsStore
from app.state import ViewStateStore


CONFIG_DIR = Path(__file__).parent.parent / "config"
STATIC_DIR = Path(__file__).parent / "static"

configure_store(ConfigStore(dashboards_dir=CONFIG_DIR / "dashboards"))
configure_view_state_store(ViewStateStore())
widgets.configure(SecretsStore(path=CONFIG_DIR / "secrets.json"))
```

(The tap router include happens in Task 6 — leave router registration alone for now.)

- [ ] **Step 3: Verify the app still imports cleanly**

Run: `python -c "from app.main import app; print(app.title)"`
Expected: `kindledashboard`

- [ ] **Step 4: Run full test suite**

Run: `pytest -v`
Expected: all tests pass (no behavior changed yet — store is just registered).

- [ ] **Step 5: Commit**

```bash
git add app/deps.py app/main.py
git commit -m "feat: wire ViewStateStore into app deps"
```

---

### Task 5: `device` query param on `/dash/{name}.png`

**Files:**
- Modify: `app/routes/render.py`
- Modify: `tests/test_routes_render.py`

- [ ] **Step 1: Add tests for the new behavior**

Append to [tests/test_routes_render.py](tests/test_routes_render.py):

```python
from app.deps import get_view_state_store
from app.state import ViewState, ViewStateStore


def test_dash_png_without_device_renders_dashboard(client: TestClient) -> None:
    response = client.get("/dash/demo.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


@freeze_time("2026-05-20 09:00:00")
def test_dash_png_with_device_in_widget_view_renders_zoom(client: TestClient) -> None:
    view_store = ViewStateStore()
    view_store.set("demo", "kitchen", ViewState(view="widget", widget_id="w1"))
    app.dependency_overrides[get_view_state_store] = lambda: view_store
    try:
        response = client.get("/dash/demo.png?device=kitchen")
        assert response.status_code == 200
        img = Image.open(io.BytesIO(response.content))
        assert img.size == (758, 1024)
    finally:
        app.dependency_overrides.pop(get_view_state_store, None)


def test_dash_png_with_unknown_widget_id_in_state_falls_back_to_dashboard(
    client: TestClient,
) -> None:
    view_store = ViewStateStore()
    view_store.set("demo", "kitchen", ViewState(view="widget", widget_id="ghost"))
    app.dependency_overrides[get_view_state_store] = lambda: view_store
    try:
        response = client.get("/dash/demo.png?device=kitchen")
        assert response.status_code == 200
        # After fall-back the state should have reset
        assert view_store.get("demo", "kitchen").view == "dashboard"
    finally:
        app.dependency_overrides.pop(get_view_state_store, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_render.py -v`
Expected: FAIL — the route doesn't accept `device` yet, the zoom test will return the dashboard PNG.

- [ ] **Step 3: Modify `app/routes/render.py`**

Replace the body of `dash_png` in [app/routes/render.py:16-31](app/routes/render.py#L16-L31):

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, Response as FastAPIResponse

from app.config_store import ConfigStore, DashboardNotFound
from app.deps import get_config_store, get_view_state_store
from app.error_image import error_png
from app.render import render_dashboard_png, render_dashboard_html, render_zoom_png
from app.state import ViewState, ViewStateStore


@router.get("/dash/{name}.png")
async def dash_png(
    name: str,
    device: str | None = Query(default=None),
    store: ConfigStore = Depends(get_config_store),
    view_store: ViewStateStore = Depends(get_view_state_store),
) -> Response:
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")
    state = view_store.get(name, device) if device else None
    try:
        if state and state.view == "widget":
            widget_ids = {w["id"] for w in dashboard["widgets"]}
            if state.widget_id not in widget_ids:
                # Stale widget id (dashboard edited). Reset and fall through.
                view_store.set(name, device, ViewState(view="dashboard", widget_id=None))
                png = await render_dashboard_png(dashboard)
            else:
                png = await render_zoom_png(dashboard, state.widget_id)
        else:
            png = await render_dashboard_png(dashboard)
    except Exception as exc:  # noqa: BLE001
        log.exception("render failed for %s", name)
        png = error_png(f"{type(exc).__name__}: {exc}")
    return FastAPIResponse(
        content=png, media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes_render.py -v`
Expected: all tests pass.

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/routes/render.py tests/test_routes_render.py
git commit -m "feat: dispatch /dash/{name}.png to zoom when device has widget view"
```

---

### Task 6: `POST /tap/{name}` route

**Files:**
- Create: `app/routes/tap.py`
- Create: `tests/test_routes_tap.py`
- Modify: `app/main.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routes_tap.py
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time
from PIL import Image

from app.config_store import ConfigStore
from app.deps import get_config_store, get_view_state_store
from app.main import app
from app.state import ViewState, ViewStateStore


DASH = {
    "name": "demo",
    "size": {"w": 758, "h": 1024},
    "grid": {"cols": 12, "rows": 16},
    "dither": "fs",
    "widgets": [
        {"id": "top",    "type": "clock",   "pos": {"x": 0, "y": 0, "w": 12, "h": 8},
         "config": {"format": "HH:mm"}},
        {"id": "bottom", "type": "clock",   "pos": {"x": 0, "y": 8, "w": 12, "h": 8},
         "config": {"format": "HH:mm"}},
    ],
}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    store = ConfigStore(dashboards_dir=tmp_path / "dashboards")
    store.save("demo", DASH)
    view_store = ViewStateStore()
    app.dependency_overrides[get_config_store] = lambda: store
    app.dependency_overrides[get_view_state_store] = lambda: view_store
    yield TestClient(app), view_store
    app.dependency_overrides.clear()


@freeze_time("2026-05-20 09:00:00")
def test_tap_widget_zooms(client):
    c, view_store = client
    r = c.post("/tap/demo", json={"device": "k", "x": 379, "y": 100})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    Image.open(io.BytesIO(r.content))  # decodes
    assert view_store.get("demo", "k") == ViewState(view="widget", widget_id="top")


@freeze_time("2026-05-20 09:00:00")
def test_tap_back_returns_to_dashboard(client):
    c, view_store = client
    view_store.set("demo", "k", ViewState(view="widget", widget_id="top"))
    r = c.post("/tap/demo", json={"device": "k", "x": 100, "y": 1000})
    assert r.status_code == 200
    assert view_store.get("demo", "k").view == "dashboard"


@freeze_time("2026-05-20 09:00:00")
def test_tap_interior_refreshes_same_widget(client):
    c, view_store = client
    view_store.set("demo", "k", ViewState(view="widget", widget_id="top"))
    r = c.post("/tap/demo", json={"device": "k", "x": 100, "y": 100})
    assert r.status_code == 200
    assert view_store.get("demo", "k") == ViewState(view="widget", widget_id="top")


@freeze_time("2026-05-20 09:00:00")
def test_tap_background_refreshes_dashboard(tmp_path):
    # Custom fixture: a sparse dashboard with empty space at (700, 900).
    sparse_store = ConfigStore(dashboards_dir=tmp_path / "sparse")
    sparse_store.save("demo", {**DASH, "widgets": [
        {"id": "tiny", "type": "clock", "pos": {"x": 0, "y": 0, "w": 1, "h": 1},
         "config": {"format": "HH:mm"}},
    ]})
    view_store = ViewStateStore()
    app.dependency_overrides[get_config_store] = lambda: sparse_store
    app.dependency_overrides[get_view_state_store] = lambda: view_store
    try:
        c = TestClient(app)
        r = c.post("/tap/demo", json={"device": "k", "x": 700, "y": 900})
        assert r.status_code == 200
        assert view_store.get("demo", "k").view == "dashboard"
    finally:
        app.dependency_overrides.clear()


def test_tap_missing_device_returns_400(client):
    c, _ = client
    r = c.post("/tap/demo", json={"x": 100, "y": 100})
    assert r.status_code == 400


def test_tap_unknown_dashboard_returns_404(client):
    c, _ = client
    r = c.post("/tap/nope", json={"device": "k", "x": 1, "y": 1})
    assert r.status_code == 404


def test_tap_out_of_bounds_treated_as_background(client):
    c, view_store = client
    view_store.set("demo", "k", ViewState(view="widget", widget_id="top"))
    # x out of bounds in widget view still triggers back/interior path; pick a value
    # that's clearly "background-ish" by being in dashboard view first:
    view_store.set("demo", "k", ViewState(view="dashboard", widget_id=None))
    r = c.post("/tap/demo", json={"device": "k", "x": -10, "y": 9999})
    assert r.status_code == 200
    assert view_store.get("demo", "k").view == "dashboard"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_tap.py -v`
Expected: FAIL — route doesn't exist yet (404 for all paths).

- [ ] **Step 3: Implement `app/routes/tap.py`**

```python
"""POST /tap/{name} — touch handler.

Resolves a raw (x, y) to a semantic hit, mutates per-device view state per
the spec's state machine, and returns the freshly-rendered PNG."""
import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel

from app.config_store import ConfigStore, DashboardNotFound
from app.deps import get_config_store, get_view_state_store
from app.error_image import error_png
from app.render import render_dashboard_png, render_zoom_png
from app.state import ViewState, ViewStateStore
from app.zones import resolve


log = logging.getLogger(__name__)
router = APIRouter()


class TapRequest(BaseModel):
    device: str | None = None
    x: int
    y: int


@router.post("/tap/{name}")
async def tap(
    name: str,
    body: TapRequest = Body(...),
    store: ConfigStore = Depends(get_config_store),
    view_store: ViewStateStore = Depends(get_view_state_store),
) -> FastAPIResponse:
    if not body.device:
        raise HTTPException(status_code=400, detail="device required")
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")

    state = view_store.get(name, body.device)
    kind, wid = resolve(dashboard, state, body.x, body.y)

    if state.view == "dashboard" and kind == "widget":
        new_state = ViewState(view="widget", widget_id=wid)
    elif state.view == "widget" and kind == "back":
        new_state = ViewState(view="dashboard", widget_id=None)
    elif state.view == "widget" and kind == "interior":
        new_state = state  # refresh same widget
    else:
        new_state = ViewState(view="dashboard", widget_id=None)
    view_store.set(name, body.device, new_state)

    try:
        if new_state.view == "widget":
            png = await render_zoom_png(dashboard, new_state.widget_id)
        else:
            png = await render_dashboard_png(dashboard)
    except Exception as exc:  # noqa: BLE001
        log.exception("tap render failed for %s", name)
        png = error_png(f"{type(exc).__name__}: {exc}")
    return FastAPIResponse(
        content=png, media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
```

- [ ] **Step 4: Include the router in `app/main.py`**

Modify [app/main.py:22-25](app/main.py#L22-L25):

```python
from app.routes import tap as tap_routes
# ...
app.include_router(render_routes.router)
app.include_router(editor_routes.router)
app.include_router(tap_routes.router)
```

- [ ] **Step 5: Run tap tests to verify they pass**

Run: `pytest tests/test_routes_tap.py -v`
Expected: all pass.

- [ ] **Step 6: Run full test suite**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add app/routes/tap.py app/main.py tests/test_routes_tap.py
git commit -m "feat: add POST /tap/{name} with state-machine-driven rendering"
```

---

### Task 7: End-to-end manual smoke test (browser-only)

- [ ] **Step 1: Start the dev server**

Run: `uvicorn app.main:app --port 8080`

- [ ] **Step 2: Verify the example dashboard renders**

Run in another shell: `curl -s -o /tmp/a.png "http://localhost:8080/dash/example.png?device=mock1" && file /tmp/a.png`
Expected: `PNG image data, 758 x 1024, 1-bit grayscale, non-interlaced` (or similar).

- [ ] **Step 3: Tap a widget**

Run: `curl -s -X POST http://localhost:8080/tap/example -H 'Content-Type: application/json' -d '{"device":"mock1","x":379,"y":120}' -o /tmp/b.png && file /tmp/b.png`
Expected: 758×1024 PNG. Open it (`open /tmp/b.png` on macOS) — confirm a zoomed widget with "← back" strip at the bottom.

- [ ] **Step 4: Tap back**

Run: `curl -s -X POST http://localhost:8080/tap/example -H 'Content-Type: application/json' -d '{"device":"mock1","x":379,"y":980}' -o /tmp/c.png && open /tmp/c.png`
Expected: dashboard view returned.

- [ ] **Step 5: Confirm per-device isolation**

Run: `curl -s -X POST http://localhost:8080/tap/example -H 'Content-Type: application/json' -d '{"device":"mock2","x":379,"y":120}' -o /tmp/d.png`
Then: `curl -s "http://localhost:8080/dash/example.png?device=mock1" -o /tmp/e.png`
Expected: `/tmp/d.png` is zoomed, `/tmp/e.png` is the dashboard.

- [ ] **Step 6: Restart server, confirm state resets**

Stop uvicorn (Ctrl-C), restart, then re-fetch `/dash/example.png?device=mock2` — expect dashboard view (state was ephemeral).

- [ ] **Step 7: Append spec pointer**

At the end of [docs/superpowers/specs/2026-05-20-kindle-dashboard-design.md](docs/superpowers/specs/2026-05-20-kindle-dashboard-design.md), add:

```markdown
## Update — touch + Kindle client

Touch handling and the in-repo Kindle client are designed in
[2026-05-20-kindle-client-touch-design.md](2026-05-20-kindle-client-touch-design.md).
```

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/specs/2026-05-20-kindle-dashboard-design.md
git commit -m "docs: point original spec at the touch + client follow-up"
```

**Phase A complete — backend is end-to-end verifiable without a Kindle.**

---

# Phase B — Kindle Go Client

The Kindle runs `kindled`, a single static Go binary that loops:

1. Every `poll_interval` seconds, GET `<server>/dash/<dashboard>.png?device=<id>`, save to `/tmp/kindled-dash.png`, run `eips -f -g /tmp/kindled-dash.png`.
2. In a goroutine, open the touchscreen `/dev/input/event*` device (resolved by name from `/proc/bus/input/devices`), parse `input_event` structs, and on each `BTN_TOUCH` release POST `{"device": id, "x": x, "y": y}` to `<server>/tap/<dashboard>`. Display the returned PNG with `eips`.

Native Kindle framework stays running (kindle-dash style). v1 = no framework stopping, no rotation handling, no calibration, no multi-touch.

### Task 8: Go module + config loader

**Files:**
- Create: `kindle_client/go.mod`
- Create: `kindle_client/internal/kindled/config.go`
- Create: `kindle_client/internal/kindled/config_test.go`

**Project layout (final, set up now):**

```
kindle_client/
├── go.mod
├── Makefile                # Task 13
├── README.md               # Task 15
├── config.example.conf     # Task 15
├── cmd/kindled/main.go     # Task 12
├── internal/kindled/
│   ├── config.go       config_test.go
│   ├── client.go       client_test.go
│   ├── display.go      display_test.go
│   └── touch.go        touch_test.go
└── kual_extension/         # Task 14
```

- [ ] **Step 1: Initialise the module**

Run:
```bash
mkdir -p kindle_client/internal/kindled kindle_client/cmd/kindled
cd kindle_client
go mod init github.com/jangabor/kindledashboard/kindle_client
```

- [ ] **Step 2: Write the failing config test**

Create `kindle_client/internal/kindled/config_test.go`:

```go
package kindled

import (
	"os"
	"path/filepath"
	"testing"
)

func writeConf(t *testing.T, body string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "k.conf")
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestLoadConfigParsesAllFields(t *testing.T) {
	path := writeConf(t,
		"server_url=http://pi:8080\n"+
			"dashboard=morning\n"+
			"device_id=kitchen\n"+
			"poll_interval=60\n",
	)
	c, err := LoadConfig(path)
	if err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	if c.ServerURL != "http://pi:8080" || c.Dashboard != "morning" ||
		c.DeviceID != "kitchen" || c.PollInterval != 60 {
		t.Errorf("got %+v", c)
	}
}

func TestLoadConfigTrimsWhitespaceAndIgnoresComments(t *testing.T) {
	path := writeConf(t,
		"# comment\n"+
			"  server_url =  http://pi:8080  \n"+
			"dashboard=m\n"+
			"device_id=k\n"+
			"poll_interval=10\n",
	)
	c, err := LoadConfig(path)
	if err != nil || c.ServerURL != "http://pi:8080" {
		t.Errorf("server_url=%q err=%v", c.ServerURL, err)
	}
}

func TestLoadConfigRequiresAllFields(t *testing.T) {
	path := writeConf(t, "server_url=http://x\n")
	if _, err := LoadConfig(path); err == nil {
		t.Errorf("expected missing-field error")
	}
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd kindle_client && go test ./internal/...`
Expected: FAIL — `LoadConfig undefined`.

- [ ] **Step 4: Implement `kindle_client/src/config.go`**

```go
package kindled

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	ServerURL    string
	Dashboard    string
	DeviceID     string
	PollInterval int
}

func LoadConfig(path string) (Config, error) {
	f, err := os.Open(path)
	if err != nil {
		return Config{}, err
	}
	defer f.Close()

	c := Config{}
	scan := bufio.NewScanner(f)
	for scan.Scan() {
		line := strings.TrimSpace(scan.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		k, v, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		k = strings.TrimSpace(k)
		v = strings.TrimSpace(v)
		switch k {
		case "server_url":
			c.ServerURL = v
		case "dashboard":
			c.Dashboard = v
		case "device_id":
			c.DeviceID = v
		case "poll_interval":
			n, err := strconv.Atoi(v)
			if err != nil {
				return c, fmt.Errorf("poll_interval not an int: %v", v)
			}
			c.PollInterval = n
		}
	}
	if err := scan.Err(); err != nil {
		return c, err
	}
	if c.ServerURL == "" || c.Dashboard == "" || c.DeviceID == "" || c.PollInterval == 0 {
		return c, fmt.Errorf("config missing required fields: %+v", c)
	}
	return c, nil
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd kindle_client && go test ./internal/...`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add kindle_client/go.mod kindle_client/internal/kindled/config.go kindle_client/internal/kindled/config_test.go
git commit -m "feat(client): config loader for kindled"
```

---

### Task 9: HTTP client (fetch dashboard PNG, POST tap)

**Files:**
- Create: `kindle_client/internal/kindled/client.go`
- Create: `kindle_client/internal/kindled/client_test.go`

- [ ] **Step 1: Write the failing tests**

```go
// kindle_client/internal/kindled/client_test.go
package kindled

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestFetchDashboardPNG(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/dash/morning.png" || r.URL.Query().Get("device") != "kitchen" {
			t.Errorf("unexpected: %s %s", r.URL.Path, r.URL.RawQuery)
		}
		w.Header().Set("Content-Type", "image/png")
		w.Write([]byte("PNGDATA"))
	}))
	defer srv.Close()

	c := &Client{ServerURL: srv.URL, Dashboard: "morning", DeviceID: "kitchen"}
	body, err := c.FetchDashboard()
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != "PNGDATA" {
		t.Errorf("body=%q", body)
	}
}

func TestPostTap(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/tap/morning" {
			t.Errorf("path=%s", r.URL.Path)
		}
		buf, _ := io.ReadAll(r.Body)
		s := string(buf)
		for _, want := range []string{`"device":"kitchen"`, `"x":42`, `"y":99`} {
			if !strings.Contains(s, want) {
				t.Errorf("body %q missing %q", s, want)
			}
		}
		w.Header().Set("Content-Type", "image/png")
		w.Write([]byte("TAPPNG"))
	}))
	defer srv.Close()

	c := &Client{ServerURL: srv.URL, Dashboard: "morning", DeviceID: "kitchen"}
	body, err := c.PostTap(42, 99)
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != "TAPPNG" {
		t.Errorf("body=%q", body)
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd kindle_client && go test ./internal/...`
Expected: FAIL — `Client undefined`.

- [ ] **Step 3: Implement `kindle_client/internal/kindled/client.go`**

```go
package kindled

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

type Client struct {
	ServerURL string
	Dashboard string
	DeviceID  string
	HTTP      *http.Client // optional; defaults to a 10s-timeout client
}

func (c *Client) http() *http.Client {
	if c.HTTP != nil {
		return c.HTTP
	}
	return &http.Client{Timeout: 10 * time.Second}
}

func (c *Client) FetchDashboard() ([]byte, error) {
	u, _ := url.Parse(c.ServerURL + "/dash/" + c.Dashboard + ".png")
	q := u.Query()
	q.Set("device", c.DeviceID)
	u.RawQuery = q.Encode()
	resp, err := c.http().Get(u.String())
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("GET %s: %s", u, resp.Status)
	}
	return io.ReadAll(resp.Body)
}

type tapBody struct {
	Device string `json:"device"`
	X      int    `json:"x"`
	Y      int    `json:"y"`
}

func (c *Client) PostTap(x, y int) ([]byte, error) {
	body, _ := json.Marshal(tapBody{Device: c.DeviceID, X: x, Y: y})
	u := c.ServerURL + "/tap/" + c.Dashboard
	resp, err := c.http().Post(u, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("POST %s: %s", u, resp.Status)
	}
	return io.ReadAll(resp.Body)
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd kindle_client && go test ./internal/...`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add kindle_client/internal/kindled/client.go kindle_client/internal/kindled/client_test.go
git commit -m "feat(client): HTTP fetch + tap POST"
```

---

### Task 10: eips display helper

**Files:**
- Create: `kindle_client/internal/kindled/display.go`
- Create: `kindle_client/internal/kindled/display_test.go`

- [ ] **Step 1: Write the failing test**

```go
// kindle_client/internal/kindled/display_test.go
package kindled

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDisplayWritesPNGAndRunsEips(t *testing.T) {
	dir := t.TempDir()
	pngPath := filepath.Join(dir, "dash.png")
	eipsArgs := [][]string{}

	d := &Display{
		PNGPath: pngPath,
		EipsRun: func(args ...string) error {
			eipsArgs = append(eipsArgs, args)
			return nil
		},
	}
	if err := d.Show([]byte("PNG-BYTES")); err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(pngPath)
	if string(got) != "PNG-BYTES" {
		t.Errorf("png=%q", got)
	}
	if len(eipsArgs) != 1 {
		t.Fatalf("eips calls=%d", len(eipsArgs))
	}
	want := []string{"-f", "-g", pngPath}
	for i := range want {
		if eipsArgs[0][i] != want[i] {
			t.Errorf("eips args=%v", eipsArgs[0])
			break
		}
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd kindle_client && go test ./internal/... -run Display`
Expected: FAIL — `Display undefined`.

- [ ] **Step 3: Implement `kindle_client/internal/kindled/display.go`**

```go
package kindled

import (
	"os"
	"os/exec"
)

type Display struct {
	PNGPath string
	// EipsRun is overridable for tests. Defaults to /usr/sbin/eips.
	EipsRun func(args ...string) error
}

func (d *Display) eips() func(args ...string) error {
	if d.EipsRun != nil {
		return d.EipsRun
	}
	return func(args ...string) error {
		return exec.Command("/usr/sbin/eips", args...).Run()
	}
}

func (d *Display) Show(png []byte) error {
	if err := os.WriteFile(d.PNGPath, png, 0644); err != nil {
		return err
	}
	return d.eips()("-f", "-g", d.PNGPath)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd kindle_client && go test ./internal/...`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add kindle_client/internal/kindled/display.go kindle_client/internal/kindled/display_test.go
git commit -m "feat(client): write PNG to tmp and call eips for display"
```

---

### Task 11: Touch event reader

**Files:**
- Create: `kindle_client/internal/kindled/touch.go`
- Create: `kindle_client/internal/kindled/touch_test.go`

Touch events on PW1/PW2 arrive as 16-byte `input_event` structs:
`struct { struct timeval time; __u16 type; __u16 code; __s32 value; }` — on 32-bit ARM with old kernels `timeval` is `int32_t sec; int32_t usec` so the total is 16 bytes. Newer 64-bit kernels are 24 bytes. PW1/PW2 are 32-bit ARM, so 16 bytes.

We care about:
- `type=EV_ABS (3) code=ABS_MT_POSITION_X (53) / ABS_MT_POSITION_Y (54)` → accumulate
- `type=EV_KEY (1) code=BTN_TOUCH (330) value=0` → tap release → emit

- [ ] **Step 1: Write the failing test**

```go
// kindle_client/internal/kindled/touch_test.go
package kindled

import (
	"bytes"
	"encoding/binary"
	"io"
	"testing"
)

func packEvent(t uint16, c uint16, v int32) []byte {
	buf := make([]byte, 16)
	// sec, usec, type, code, value (little-endian on ARM)
	binary.LittleEndian.PutUint32(buf[0:4], 0)
	binary.LittleEndian.PutUint32(buf[4:8], 0)
	binary.LittleEndian.PutUint16(buf[8:10], t)
	binary.LittleEndian.PutUint16(buf[10:12], c)
	binary.LittleEndian.PutUint32(buf[12:16], uint32(v))
	return buf
}

func TestReadTapsEmitsOnButtonRelease(t *testing.T) {
	var buf bytes.Buffer
	buf.Write(packEvent(3, 53, 432))  // EV_ABS ABS_MT_POSITION_X=432
	buf.Write(packEvent(3, 54, 600))  // EV_ABS ABS_MT_POSITION_Y=600
	buf.Write(packEvent(1, 330, 1))   // EV_KEY BTN_TOUCH down
	buf.Write(packEvent(0, 0, 0))     // EV_SYN
	buf.Write(packEvent(1, 330, 0))   // EV_KEY BTN_TOUCH up   <-- emit here

	taps := make(chan Tap, 4)
	err := ReadTaps(io.NopCloser(&buf), taps)
	if err != nil && err != io.EOF {
		t.Fatalf("ReadTaps: %v", err)
	}
	close(taps)

	var got []Tap
	for tap := range taps {
		got = append(got, tap)
	}
	if len(got) != 1 || got[0].X != 432 || got[0].Y != 600 {
		t.Errorf("taps=%+v", got)
	}
}

func TestReadTapsIgnoresMoveWithoutRelease() {
	// no-op: covered by absence of emit; trivial
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd kindle_client && go test ./internal/...`
Expected: FAIL — `ReadTaps undefined`.

- [ ] **Step 3: Implement `kindle_client/internal/kindled/touch.go`**

```go
package kindled

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"os"
	"regexp"
	"strings"
)

const (
	evSyn = 0
	evKey = 1
	evAbs = 3

	btnTouch        = 330
	absMtPositionX  = 53
	absMtPositionY  = 54
)

type Tap struct{ X, Y int }

// ReadTaps parses input_event structs from r (16 bytes each) and pushes a Tap
// onto out for each BTN_TOUCH release. Returns when r returns EOF/error.
func ReadTaps(r io.ReadCloser, out chan<- Tap) error {
	defer r.Close()
	br := bufio.NewReader(r)
	buf := make([]byte, 16)
	var x, y int
	for {
		if _, err := io.ReadFull(br, buf); err != nil {
			if err == io.EOF || err == io.ErrUnexpectedEOF {
				return io.EOF
			}
			return err
		}
		etype := binary.LittleEndian.Uint16(buf[8:10])
		code := binary.LittleEndian.Uint16(buf[10:12])
		value := int32(binary.LittleEndian.Uint32(buf[12:16]))
		switch etype {
		case evAbs:
			switch code {
			case absMtPositionX:
				x = int(value)
			case absMtPositionY:
				y = int(value)
			}
		case evKey:
			if code == btnTouch && value == 0 {
				out <- Tap{X: x, Y: y}
			}
		case evSyn:
			// no-op
		}
	}
}

// FindTouchscreen scans /proc/bus/input/devices and returns /dev/input/eventN
// for the first device whose Name contains any of the substrings.
// Defaults to looking for "cyttsp", "synaptics", or "_mt".
func FindTouchscreen(matchers ...string) (string, error) {
	if len(matchers) == 0 {
		matchers = []string{"cyttsp", "synaptics", "_mt"}
	}
	body, err := os.ReadFile("/proc/bus/input/devices")
	if err != nil {
		return "", err
	}
	blocks := strings.Split(string(body), "\n\n")
	re := regexp.MustCompile(`event\d+`)
	for _, blk := range blocks {
		lower := strings.ToLower(blk)
		match := false
		for _, m := range matchers {
			if strings.Contains(lower, strings.ToLower(m)) {
				match = true
				break
			}
		}
		if !match {
			continue
		}
		if dev := re.FindString(blk); dev != "" {
			return "/dev/input/" + dev, nil
		}
	}
	return "", fmt.Errorf("no touchscreen found")
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd kindle_client && go test ./internal/...`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add kindle_client/internal/kindled/touch.go kindle_client/internal/kindled/touch_test.go
git commit -m "feat(client): parse input_event structs and emit taps"
```

---

### Task 12: Main daemon

**Files:**
- Create: `kindle_client/cmd/kindled/main.go`

- [ ] **Step 1: Implement `kindle_client/cmd/kindled/main.go`**

```go
package main

import (
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jangabor/kindledashboard/kindle_client/internal/kindled"
)

func main() {
	cfgPath := flag.String("config", "/mnt/us/kindledashboard.conf", "config file")
	logPath := flag.String("log", "/tmp/kindledashboard.log", "log file (- for stderr)")
	flag.Parse()

	if *logPath != "-" {
		f, err := os.OpenFile(*logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
		if err == nil {
			log.SetOutput(f)
			defer f.Close()
		}
	}

	cfg, err := kindled.LoadConfig(*cfgPath)
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	client := &kindled.Client{
		ServerURL: cfg.ServerURL,
		Dashboard: cfg.Dashboard,
		DeviceID:  cfg.DeviceID,
	}
	disp := &kindled.Display{PNGPath: "/tmp/kindled-dash.png"}

	// Initial draw
	if png, err := client.FetchDashboard(); err == nil {
		_ = disp.Show(png)
	} else {
		log.Printf("initial fetch failed: %v", err)
	}

	// Touch goroutine
	taps := make(chan kindled.Tap, 8)
	go func() {
		for {
			path, err := kindled.FindTouchscreen()
			if err != nil {
				log.Printf("find touchscreen: %v", err)
				time.Sleep(10 * time.Second)
				continue
			}
			f, err := os.Open(path)
			if err != nil {
				log.Printf("open %s: %v", path, err)
				time.Sleep(5 * time.Second)
				continue
			}
			if err := kindled.ReadTaps(f, taps); err != nil {
				log.Printf("read taps: %v", err)
			}
			time.Sleep(time.Second)
		}
	}()

	tick := time.NewTicker(time.Duration(cfg.PollInterval) * time.Second)
	defer tick.Stop()
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGTERM, syscall.SIGINT)

	for {
		select {
		case <-sigs:
			log.Printf("shutdown")
			return
		case <-tick.C:
			png, err := client.FetchDashboard()
			if err != nil {
				log.Printf("fetch: %v", err)
				continue
			}
			if err := disp.Show(png); err != nil {
				log.Printf("display: %v", err)
			}
		case tap := <-taps:
			png, err := client.PostTap(tap.X, tap.Y)
			if err != nil {
				log.Printf("tap post: %v", err)
				continue
			}
			if err := disp.Show(png); err != nil {
				log.Printf("display: %v", err)
			}
		}
	}
}
```

- [ ] **Step 2: Verify the binary builds for ARMv7**

Run:
```bash
cd kindle_client
GOOS=linux GOARCH=arm GOARM=7 CGO_ENABLED=0 go build -o kindled ./cmd/kindled
file kindled
```
Expected: `kindled: ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), statically linked, ...`

- [ ] **Step 3: Verify it builds for the dev host (for smoke testing locally)**

Run: `cd kindle_client && go build -o /tmp/kindled-host ./cmd/kindled`
Expected: success.

- [ ] **Step 4: Commit**

```bash
git add kindle_client/cmd/kindled/main.go
git commit -m "feat(client): main daemon (poll + touch loop, signal handling)"
```

---

### Task 13: Cross-compile Makefile

**Files:**
- Create: `kindle_client/Makefile`

- [ ] **Step 1: Write the Makefile**

```makefile
.PHONY: build clean test

GOOS    ?= linux
GOARCH  ?= arm
GOARM   ?= 7
BIN     := build/kindled

build: $(BIN)

$(BIN):
	mkdir -p build
	GOOS=$(GOOS) GOARCH=$(GOARCH) GOARM=$(GOARM) CGO_ENABLED=0 \
		go build -ldflags="-s -w" -o $(BIN) ./cmd/kindled

test:
	go test ./...

clean:
	rm -rf build
```

- [ ] **Step 2: Verify it builds**

Run: `cd kindle_client && make clean build && file build/kindled`
Expected: ARM ELF binary as above.

- [ ] **Step 3: Commit**

```bash
git add kindle_client/Makefile
git commit -m "build(client): Makefile for ARMv7 cross-compile"
```

---

### Task 14: KUAL extension files

**Files:**
- Create: `kindle_client/kual_extension/config.xml`
- Create: `kindle_client/kual_extension/menu.json`
- Create: `kindle_client/kual_extension/bin/start.sh`
- Create: `kindle_client/kual_extension/bin/stop.sh`

- [ ] **Step 1: `config.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<extension>
  <information>
    <name>Kindle Dashboard</name>
    <version>1.0</version>
    <author>kindledashboard</author>
    <id>kindledashboard</id>
  </information>
  <menus>
    <menu type="json" dynamic="false">menu.json</menu>
  </menus>
</extension>
```

- [ ] **Step 2: `menu.json`**

```json
{
  "items": [
    {
      "name": "Start dashboard",
      "priority": 1,
      "action": "bin/start.sh",
      "params": "",
      "status": "exitmenu",
      "exitmenu": "true"
    },
    {
      "name": "Stop dashboard",
      "priority": 2,
      "action": "bin/stop.sh",
      "params": "",
      "exitmenu": "true"
    }
  ]
}
```

- [ ] **Step 3: `bin/start.sh`**

```sh
#!/bin/sh
# Start the kindled daemon. Idempotent: if a pid file exists and the process is
# alive, do nothing.
EXT_DIR="/mnt/us/extensions/kindledashboard"
PID_FILE="/tmp/kindled.pid"
LOG_FILE="/tmp/kindledashboard.log"
CONF="/mnt/us/kindledashboard.conf"

if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
    eips 1 2 "kindled already running (pid $(cat $PID_FILE))"
    exit 0
fi

if [ ! -f "$CONF" ]; then
    eips 1 2 "config missing: $CONF"
    exit 1
fi

nohup "$EXT_DIR/bin/kindled" -config "$CONF" -log "$LOG_FILE" >/dev/null 2>&1 &
echo $! > "$PID_FILE"
eips 1 2 "kindled started (pid $!)"
```

- [ ] **Step 4: `bin/stop.sh`**

```sh
#!/bin/sh
PID_FILE="/tmp/kindled.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        eips 1 2 "kindled stopped"
    fi
    rm -f "$PID_FILE"
else
    eips 1 2 "kindled not running"
fi
```

- [ ] **Step 5: Mark scripts executable + commit**

```bash
chmod +x kindle_client/kual_extension/bin/*.sh
git add kindle_client/kual_extension/
git commit -m "feat(client): KUAL extension files (config.xml, menu.json, start/stop)"
```

---

### Task 15: README + example config

**Files:**
- Create: `kindle_client/config.example.conf`
- Create: `kindle_client/README.md`

- [ ] **Step 1: `config.example.conf`**

```
# kindledashboard client config
# Copy to /mnt/us/kindledashboard.conf on the Kindle.

server_url=http://192.168.1.10:8080
dashboard=morning
device_id=kitchen
poll_interval=60
```

- [ ] **Step 2: `README.md`**

```markdown
# Kindle Dashboard Client (kindled)

A single static Go binary for jailbroken Kindle Paperwhite 1/2. Polls the
backend for the dashboard PNG, displays it with `eips`, and forwards touch
events to `POST /tap/<name>`.

## Build

```bash
make build
```

Produces `build/kindled` — a statically-linked ARMv7 binary suitable for PW1/PW2.

## Install on the Kindle

1. Jailbreak your Kindle (https://kindlemodding.org/jailbreaking/).
2. Install KUAL (https://www.mobileread.com/forums/showthread.php?t=203326).
3. Copy this extension to the Kindle:
   ```bash
   # Connect Kindle via USB, then:
   KINDLE=/Volumes/Kindle   # macOS path; Linux: /media/$USER/Kindle
   mkdir -p $KINDLE/extensions/kindledashboard/bin
   cp kual_extension/config.xml $KINDLE/extensions/kindledashboard/
   cp kual_extension/menu.json  $KINDLE/extensions/kindledashboard/
   cp kual_extension/bin/*.sh   $KINDLE/extensions/kindledashboard/bin/
   cp build/kindled             $KINDLE/extensions/kindledashboard/bin/
   cp config.example.conf       $KINDLE/kindledashboard.conf
   ```
4. Edit `/mnt/us/kindledashboard.conf` on the Kindle (the file you just
   copied is at the root of the USB-visible drive). Set `server_url`,
   `dashboard`, `device_id`, `poll_interval`.
5. Eject the Kindle. Open KUAL → "Kindle Dashboard" → "Start dashboard".

## Logs

`/tmp/kindledashboard.log` on the Kindle.

## Auto-start on boot

Drop an upstart job at `/etc/init/kindled.conf` on the Kindle (requires
root via SSH or a hotfix):

```
start on started lab126_gui
stop on stopping lab126_gui
respawn
exec /mnt/us/extensions/kindledashboard/bin/start.sh
```

## What it does NOT do (v1)

- No tap visual feedback (the new image arriving is the feedback).
- No multi-touch, swipes, or long-press.
- Does not stop the native Kindle framework — status bar / notifications
  remain visible. (See `docs/superpowers/specs/2026-05-20-kindle-client-touch-design.md`.)
- No screen-rotation handling. Portrait orientation assumed.

## Troubleshooting

- **Black screen on start:** check `/tmp/kindledashboard.log`. Common
  causes: bad `server_url`, no Wi-Fi, server unreachable.
- **Touch does nothing:** confirm `cat /proc/bus/input/devices | grep -i name`
  shows your touchscreen. If the name doesn't match `cyttsp`, `synaptics`,
  or `_mt`, edit `internal/kindled/touch.go` `FindTouchscreen` matchers
  and rebuild.
- **Ghosting:** `kindled` calls `eips -f` (full refresh) every cycle, so
  this should not occur. If it does, ensure `eips` is `/usr/sbin/eips`.

## Layout

```
kindle_client/
├── go.mod
├── Makefile
├── README.md
├── config.example.conf
├── cmd/kindled/main.go
├── internal/kindled/
│   ├── config.go
│   ├── client.go
│   ├── display.go
│   └── touch.go
└── kual_extension/
    ├── config.xml
    ├── menu.json
    └── bin/{start,stop}.sh
```
```

- [ ] **Step 3: Commit**

```bash
git add kindle_client/README.md kindle_client/config.example.conf
git commit -m "docs(client): README + example config"
```

---

### Task 16: On-Kindle smoke test (manual)

These steps require physical hardware — not automatable.

- [ ] **Step 1: Build and install**

Build: `make -C kindle_client build`. Copy `build/kindled` + KUAL extension to the Kindle as per the README.

- [ ] **Step 2: Configure**

Edit `/mnt/us/kindledashboard.conf` on the Kindle. Use the backend reachable from the Kindle's IP.

- [ ] **Step 3: Start**

KUAL → Kindle Dashboard → Start dashboard. Within `poll_interval` seconds, the dashboard PNG should appear.

- [ ] **Step 4: Tap a widget**

Confirm the screen updates to a zoomed widget with "← back" strip.

- [ ] **Step 5: Tap back**

Confirm the dashboard view returns.

- [ ] **Step 6: Inspect logs**

`ssh root@<kindle-ip>` (or via USBNetwork) and `tail -f /tmp/kindledashboard.log`. Confirm no repeating errors.

- [ ] **Step 7: Stop cleanly**

KUAL → Kindle Dashboard → Stop dashboard. Confirm pid file is removed and the process is gone.

---

## Verification (end of plan)

**Phase A verification (no Kindle needed):**
- `pytest -v` — all tests pass.
- Manual `curl` smoke tests in Task 7 pass.

**Phase B verification (Kindle needed):**
- `cd kindle_client && make test` — Go tests pass.
- `cd kindle_client && make build && file build/kindled` — produces ARMv7 ELF.
- Manual on-device smoke test in Task 16 passes.

---

## Out of scope (v1)

- Multi-touch, swipes, long-press.
- Tap visual feedback on the Kindle (no flash/overlay).
- Persisting view state across Pi reboots.
- Stopping the native Kindle framework (lab126_gui/framework/webreader).
- Calibration for Kindle models with non-1:1 touch-to-pixel mapping.
- Auto-start on boot via upstart (documented in README but not installed).
- Detail templates per widget (`fetch_detail`, `widgets/*_detail.html`).
  The renderer already falls back to `widget.template` and `widget.fetch`,
  so v1 zooms use the same templates at full size. Detail templates can be
  added per-widget later without backend changes.

---

## Self-review notes

- All four state transitions from the spec table are tested in
  `tests/test_routes_tap.py` (Task 6).
- All four zone kinds (widget / background / back / interior) are tested
  in `tests/test_zones.py` (Task 2).
- Stale-widget-id reset (spec §"Error Handling") is tested in
  `tests/test_routes_render.py` (Task 5) and again indirectly via the tap
  route.
- The `device` query param is optional, preserving the existing `kindle-dash`
  contract — covered by `test_dash_png_without_device_renders_dashboard`.
- Function names are consistent across tasks: `render_zoom_png(dashboard,
  widget_id)`, `ViewStateStore.get(name, device)`, `ViewStateStore.set(...)`,
  `resolve(dashboard, state, x, y)`, `Client.FetchDashboard()`,
  `Client.PostTap(x, y)`.
