# Kindle Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI server that lets the user arrange and configure widgets in a grid via a web editor, stores layouts as JSON, and serves rendered grayscale PNGs to a Kindle Paperwhite running kindle-dash.

**Architecture:** Single FastAPI process. Editor UI uses HTMX + Gridstack.js (no JS build). Renderer uses WeasyPrint (HTML→PNG, no Chromium) + Pillow (grayscale + dither). Widgets are pluggable Python modules with a tiny protocol; adding a new widget is just dropping files in `app/widgets/` and `app/templates/widgets/`. A Claude skill (`create-widget`) generates that scaffolding.

**Tech Stack:** Python 3.11+, FastAPI, WeasyPrint, Pillow, Jinja2, httpx, caldav, HTMX, Gridstack.js, pytest + respx + freezegun.

**Spec:** `docs/superpowers/specs/2026-05-20-kindle-dashboard-design.md`

---

## File Structure

```
kindledashboard/
├── pyproject.toml
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, route registration
│   ├── deps.py              # FastAPI dependencies (DI for ConfigStore)
│   ├── config_store.py      # JSON load/save, atomic writes, validation
│   ├── secrets.py           # secrets.json loader + $name resolver
│   ├── render.py            # WeasyPrint + Pillow pipeline
│   ├── error_image.py       # generates fallback error PNGs
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── editor.py        # /editor + /api/dashboards/...
│   │   └── render.py        # /dash/<name>.png + /preview/<name>
│   ├── widgets/
│   │   ├── __init__.py      # registry
│   │   ├── base.py          # Widget protocol + errors
│   │   ├── clock.py
│   │   ├── weather.py
│   │   ├── grafana.py
│   │   ├── iobroker.py
│   │   └── calendar.py
│   ├── templates/
│   │   ├── editor.html
│   │   ├── dashboard.html
│   │   ├── _widget_form.html
│   │   └── widgets/
│   │       ├── clock.html
│   │       ├── weather.html
│   │       ├── grafana.html
│   │       ├── iobroker.html
│   │       └── calendar.html
│   └── static/
│       ├── gridstack.min.js
│       ├── gridstack.min.css
│       └── editor.js
├── config/
│   ├── dashboards/
│   │   └── example.json
│   └── secrets.json.example
├── deploy/
│   └── kindledashboard.service
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   └── example_dashboard.json
│   ├── test_config_store.py
│   ├── test_secrets.py
│   ├── test_render.py
│   ├── test_routes_render.py
│   ├── test_routes_editor.py
│   └── widgets/
│       ├── __init__.py
│       ├── test_clock.py
│       ├── test_weather.py
│       ├── test_grafana.py
│       ├── test_iobroker.py
│       └── test_calendar.py
└── .claude/
    └── skills/
        └── create-widget/
            └── SKILL.md
```

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "kindledashboard"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
    "weasyprint>=60",
    "pillow>=10",
    "httpx>=0.27",
    "caldav>=1.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
    "freezegun>=1.4",
    "httpx[cli]",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
config/secrets.json
config/dashboards/*.json
!config/dashboards/example.json
*.tmp
.DS_Store
```

- [ ] **Step 3: Write `app/__init__.py`** (empty file)

- [ ] **Step 4: Write `app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="kindledashboard")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Write `tests/__init__.py`** (empty file)

- [ ] **Step 6: Write `tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

- [ ] **Step 7: Write `tests/test_main.py`**

```python
def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 8: Create venv and install**

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Expected: clean install. WeasyPrint may complain about missing system libs — install with `brew install pango` on macOS or `apt install libpango-1.0-0 libpangoft2-1.0-0` on the Pi if needed.

- [ ] **Step 9: Run tests**

```bash
.venv/bin/pytest -v
```

Expected: 1 test passes (`test_health`).

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with FastAPI health endpoint"
```

---

## Task 2: Widget protocol + Clock widget

**Files:**
- Create: `app/widgets/__init__.py`
- Create: `app/widgets/base.py`
- Create: `app/widgets/clock.py`
- Create: `app/templates/widgets/clock.html`
- Create: `tests/widgets/__init__.py`
- Create: `tests/widgets/test_clock.py`

- [ ] **Step 1: Write `tests/widgets/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test `tests/widgets/test_clock.py`**

```python
from datetime import datetime

import pytest
from freezegun import freeze_time

from app.widgets.clock import ClockWidget


@pytest.mark.asyncio
@freeze_time("2026-05-20 14:37:00")
async def test_clock_fetch_returns_formatted_time() -> None:
    widget = ClockWidget()
    ctx = await widget.fetch({"format": "HH:mm"})
    assert ctx == {"time": "14:37", "date": "2026-05-20"}


@pytest.mark.asyncio
@freeze_time("2026-05-20 14:37:00")
async def test_clock_fetch_respects_custom_format() -> None:
    widget = ClockWidget()
    ctx = await widget.fetch({"format": "HH:mm:ss"})
    assert ctx["time"] == "14:37:00"


def test_clock_metadata() -> None:
    widget = ClockWidget()
    assert widget.type == "clock"
    assert widget.template == "widgets/clock.html"
    assert "format" in widget.config_schema["properties"]
```

- [ ] **Step 3: Run the test (expect fail)**

```bash
.venv/bin/pytest tests/widgets/test_clock.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.widgets.clock'`.

- [ ] **Step 4: Write `app/widgets/base.py`**

```python
from typing import Any, Protocol, runtime_checkable


class WidgetError(Exception):
    """Raised by widgets when their fetch fails. Caught by the renderer to
    show a per-cell error box instead of failing the whole dashboard."""


@runtime_checkable
class Widget(Protocol):
    type: str
    template: str
    config_schema: dict[str, Any]

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        """Return a Jinja template context dict. Raise WidgetError on failure."""
        ...
```

- [ ] **Step 5: Write `app/widgets/clock.py`**

```python
from datetime import datetime
from typing import Any


class ClockWidget:
    type = "clock"
    template = "widgets/clock.html"
    config_schema = {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "title": "Time format",
                "default": "HH:mm",
            },
        },
    }

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now()
        fmt = cfg.get("format", "HH:mm")
        # Translate human format to strftime
        strftime_fmt = (
            fmt.replace("HH", "%H")
            .replace("mm", "%M")
            .replace("ss", "%S")
        )
        return {
            "time": now.strftime(strftime_fmt),
            "date": now.strftime("%Y-%m-%d"),
        }
```

- [ ] **Step 6: Write `app/widgets/__init__.py` (registry)**

```python
from app.widgets.base import Widget, WidgetError
from app.widgets.clock import ClockWidget

REGISTRY: dict[str, type[Widget]] = {
    ClockWidget.type: ClockWidget,
}


def get_widget(type_name: str) -> Widget:
    cls = REGISTRY.get(type_name)
    if cls is None:
        raise KeyError(f"Unknown widget type: {type_name}")
    return cls()


__all__ = ["Widget", "WidgetError", "REGISTRY", "get_widget"]
```

- [ ] **Step 7: Write `app/templates/widgets/clock.html`**

```html
<div class="widget widget-clock">
  <div class="clock-time">{{ time }}</div>
  <div class="clock-date">{{ date }}</div>
</div>
```

- [ ] **Step 8: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/widgets/test_clock.py -v
```

Expected: 3 tests pass.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: widget protocol and clock widget"
```

---

## Task 3: Config store with atomic writes

**Files:**
- Create: `app/config_store.py`
- Create: `tests/test_config_store.py`
- Create: `tests/fixtures/example_dashboard.json`

- [ ] **Step 1: Write `tests/fixtures/example_dashboard.json`**

```json
{
  "name": "example",
  "size": { "w": 758, "h": 1024 },
  "grid": { "cols": 12, "rows": 16 },
  "dither": "fs",
  "widgets": [
    {
      "id": "w1",
      "type": "clock",
      "pos": { "x": 0, "y": 0, "w": 12, "h": 2 },
      "config": { "format": "HH:mm" }
    }
  ]
}
```

- [ ] **Step 2: Write failing tests `tests/test_config_store.py`**

```python
import json
from pathlib import Path

import pytest

from app.config_store import ConfigStore, DashboardNotFound, InvalidDashboard


@pytest.fixture
def store(tmp_path: Path) -> ConfigStore:
    dashboards = tmp_path / "dashboards"
    dashboards.mkdir()
    return ConfigStore(dashboards_dir=dashboards)


def test_load_missing_raises(store: ConfigStore) -> None:
    with pytest.raises(DashboardNotFound):
        store.load("nope")


def test_save_and_load_roundtrip(store: ConfigStore) -> None:
    data = {
        "name": "morning",
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }
    store.save("morning", data)
    assert store.load("morning") == data


def test_save_is_atomic(store: ConfigStore, tmp_path: Path) -> None:
    data = {
        "name": "x",
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }
    store.save("x", data)
    # After save, no .tmp file should be left over
    assert list((tmp_path / "dashboards").glob("*.tmp")) == []


def test_list_returns_names(store: ConfigStore) -> None:
    base = {
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }
    store.save("a", {"name": "a", **base})
    store.save("b", {"name": "b", **base})
    assert sorted(store.list()) == ["a", "b"]


def test_validate_unknown_widget_type(store: ConfigStore) -> None:
    bad = {
        "name": "bad",
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [
            {"id": "w1", "type": "unicorn", "pos": {"x": 0, "y": 0, "w": 1, "h": 1}, "config": {}}
        ],
    }
    with pytest.raises(InvalidDashboard, match="unicorn"):
        store.save("bad", bad)


def test_validate_missing_required_fields(store: ConfigStore) -> None:
    bad = {"name": "bad"}
    with pytest.raises(InvalidDashboard):
        store.save("bad", bad)
```

- [ ] **Step 3: Run tests (expect fail)**

```bash
.venv/bin/pytest tests/test_config_store.py -v
```

Expected: all FAIL — module doesn't exist yet.

- [ ] **Step 4: Write `app/config_store.py`**

```python
import json
import os
from pathlib import Path
from typing import Any

from app.widgets import REGISTRY


class DashboardNotFound(Exception):
    pass


class InvalidDashboard(Exception):
    pass


REQUIRED_TOP_LEVEL = {"name", "size", "grid", "widgets"}
REQUIRED_WIDGET = {"id", "type", "pos", "config"}


class ConfigStore:
    def __init__(self, dashboards_dir: Path) -> None:
        self.dashboards_dir = Path(dashboards_dir)
        self.dashboards_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        if "/" in name or name.startswith("."):
            raise InvalidDashboard(f"illegal dashboard name: {name!r}")
        return self.dashboards_dir / f"{name}.json"

    def load(self, name: str) -> dict[str, Any]:
        path = self._path(name)
        if not path.exists():
            raise DashboardNotFound(name)
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, name: str, data: dict[str, Any]) -> None:
        self._validate(data)
        path = self._path(name)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def delete(self, name: str) -> None:
        path = self._path(name)
        if not path.exists():
            raise DashboardNotFound(name)
        path.unlink()

    def list(self) -> list[str]:
        return [p.stem for p in self.dashboards_dir.glob("*.json")]

    def _validate(self, data: dict[str, Any]) -> None:
        missing = REQUIRED_TOP_LEVEL - data.keys()
        if missing:
            raise InvalidDashboard(f"missing fields: {sorted(missing)}")
        if not isinstance(data["widgets"], list):
            raise InvalidDashboard("widgets must be a list")
        for w in data["widgets"]:
            w_missing = REQUIRED_WIDGET - w.keys()
            if w_missing:
                raise InvalidDashboard(f"widget missing fields: {sorted(w_missing)}")
            if w["type"] not in REGISTRY:
                raise InvalidDashboard(f"unknown widget type: {w['type']!r}")
```

- [ ] **Step 5: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/test_config_store.py -v
```

Expected: 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: ConfigStore with atomic writes and validation"
```

---

## Task 4: Render pipeline (HTML → PNG → grayscale)

**Files:**
- Create: `app/render.py`
- Create: `app/templates/dashboard.html`
- Create: `tests/test_render.py`
- Modify: `tests/conftest.py` (add config_store fixture)

- [ ] **Step 1: Update `tests/conftest.py` to add a config store fixture**

```python
import pytest
from fastapi.testclient import TestClient

from app.config_store import ConfigStore
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def store(tmp_path):
    dashboards = tmp_path / "dashboards"
    dashboards.mkdir()
    return ConfigStore(dashboards_dir=dashboards)
```

- [ ] **Step 2: Write failing tests `tests/test_render.py`**

```python
import io

import pytest
from freezegun import freeze_time
from PIL import Image

from app.render import render_dashboard_html, render_dashboard_png


CLOCK_DASHBOARD = {
    "name": "test",
    "size": {"w": 758, "h": 1024},
    "grid": {"cols": 12, "rows": 16},
    "dither": "none",
    "widgets": [
        {
            "id": "w1",
            "type": "clock",
            "pos": {"x": 0, "y": 0, "w": 12, "h": 4},
            "config": {"format": "HH:mm"},
        }
    ],
}


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_html_contains_widget_content() -> None:
    html = await render_dashboard_html(CLOCK_DASHBOARD)
    assert "09:00" in html
    assert "2026-05-20" in html
    # Layout should be present
    assert "grid-column" in html or "grid-area" in html


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_png_dimensions_and_mode() -> None:
    png_bytes = await render_dashboard_png(CLOCK_DASHBOARD)
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (758, 1024)
    assert img.mode in ("L", "1")


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_png_dither_modes() -> None:
    no_dither = await render_dashboard_png({**CLOCK_DASHBOARD, "dither": "none"})
    fs_dither = await render_dashboard_png({**CLOCK_DASHBOARD, "dither": "fs"})
    assert Image.open(io.BytesIO(no_dither)).mode == "L"
    assert Image.open(io.BytesIO(fs_dither)).mode == "1"
```

- [ ] **Step 3: Run tests (expect fail)**

```bash
.venv/bin/pytest tests/test_render.py -v
```

Expected: FAIL — `render` module missing.

- [ ] **Step 4: Write `app/templates/dashboard.html`**

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: {{ width }}px {{ height }}px; margin: 0; }
  html, body { margin: 0; padding: 0; width: {{ width }}px; height: {{ height }}px;
               font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; color: #000; }
  .dash {
    display: grid;
    width: {{ width }}px;
    height: {{ height }}px;
    grid-template-columns: repeat({{ cols }}, 1fr);
    grid-template-rows: repeat({{ rows }}, 1fr);
    gap: 4px;
    padding: 4px;
    box-sizing: border-box;
  }
  .cell {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid #000;
  }
  .widget { flex: 1; padding: 6px; overflow: hidden; }
  .widget-clock { text-align: center; }
  .clock-time { font-size: 64px; font-weight: 700; line-height: 1; }
  .clock-date { font-size: 22px; margin-top: 4px; }
  .widget-error { color: #000; font-size: 14px; padding: 8px;
                  display: flex; align-items: center; justify-content: center; }
</style>
</head>
<body>
<div class="dash">
  {% for item in items %}
    <div class="cell" style="grid-column: {{ item.pos.x + 1 }} / span {{ item.pos.w }};
                              grid-row: {{ item.pos.y + 1 }} / span {{ item.pos.h }};">
      {% if item.error %}
        <div class="widget widget-error">⚠ {{ item.error }}</div>
      {% else %}
        {% include item.template %}
      {% endif %}
    </div>
  {% endfor %}
</div>
</body>
</html>
```

- [ ] **Step 5: Write `app/render.py`**

```python
import asyncio
import io
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from weasyprint import HTML

from app.widgets import WidgetError, get_widget


TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    enable_async=True,
)


async def _fetch_item(widget_cfg: dict[str, Any]) -> dict[str, Any]:
    try:
        widget = get_widget(widget_cfg["type"])
        ctx = await widget.fetch(widget_cfg.get("config", {}))
        return {
            "pos": widget_cfg["pos"],
            "template": widget.template,
            "ctx": ctx,
            "error": None,
        }
    except (WidgetError, KeyError, Exception) as exc:  # noqa: BLE001
        return {
            "pos": widget_cfg["pos"],
            "template": None,
            "ctx": {},
            "error": str(exc) or type(exc).__name__,
        }


async def render_dashboard_html(dashboard: dict[str, Any]) -> str:
    items = await asyncio.gather(*[_fetch_item(w) for w in dashboard["widgets"]])
    # Inline ctx into the template-include path: Jinja's `include with`
    # needs a per-item context, so we flatten by passing the merged dict per item.
    rendered_items = []
    for item in items:
        rendered_items.append({
            "pos": item["pos"],
            "template": item["template"],
            "error": item["error"],
            **item["ctx"],
        })
    template = _env.get_template("dashboard.html")
    return await template.render_async(
        width=dashboard["size"]["w"],
        height=dashboard["size"]["h"],
        cols=dashboard["grid"]["cols"],
        rows=dashboard["grid"]["rows"],
        items=rendered_items,
    )


def _html_to_png_bytes(html: str, width: int, height: int) -> bytes:
    # WeasyPrint renders at 96 DPI by default; we want 1:1 px output.
    png_bytes = HTML(string=html).write_png(resolution=96)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _to_grayscale(png_bytes: bytes, dither: str) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    if dither == "fs":
        img = img.convert("1", dither=Image.FLOYDSTEINBERG)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def render_dashboard_png(dashboard: dict[str, Any]) -> bytes:
    html = await render_dashboard_html(dashboard)
    width = dashboard["size"]["w"]
    height = dashboard["size"]["h"]
    # WeasyPrint is sync; run in a thread to avoid blocking the loop.
    rgba_png = await asyncio.to_thread(_html_to_png_bytes, html, width, height)
    dither = dashboard.get("dither", "fs")
    return await asyncio.to_thread(_to_grayscale, rgba_png, dither)
```

- [ ] **Step 6: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/test_render.py -v
```

Expected: 3 tests pass. If WeasyPrint complains about missing system libs, install them per Task 1 Step 8.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: render pipeline with WeasyPrint and Pillow"
```

---

## Task 5: Render routes (/dash and /preview)

**Files:**
- Create: `app/routes/__init__.py`
- Create: `app/deps.py`
- Create: `app/routes/render.py`
- Modify: `app/main.py`
- Create: `tests/test_routes_render.py`

- [ ] **Step 1: Write `app/routes/__init__.py`** (empty file)

- [ ] **Step 2: Write `app/deps.py`**

```python
from app.config_store import ConfigStore


_store: ConfigStore | None = None


def configure_store(store: ConfigStore) -> None:
    """Called once at app startup from main.py."""
    global _store
    _store = store


def get_config_store() -> ConfigStore:
    """FastAPI dependency. Tests override via app.dependency_overrides."""
    if _store is None:
        raise RuntimeError("config store not configured")
    return _store
```

- [ ] **Step 3: Write failing tests `tests/test_routes_render.py`**

```python
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time
from PIL import Image

from app.config_store import ConfigStore
from app.deps import get_config_store
from app.main import app


CLOCK_DASHBOARD = {
    "name": "demo",
    "size": {"w": 758, "h": 1024},
    "grid": {"cols": 12, "rows": 16},
    "dither": "fs",
    "widgets": [
        {
            "id": "w1",
            "type": "clock",
            "pos": {"x": 0, "y": 0, "w": 12, "h": 4},
            "config": {"format": "HH:mm"},
        }
    ],
}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    store = ConfigStore(dashboards_dir=tmp_path / "dashboards")
    store.save("demo", CLOCK_DASHBOARD)
    app.dependency_overrides[get_config_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


@freeze_time("2026-05-20 09:00:00")
def test_dash_png_returns_grayscale_image(client: TestClient) -> None:
    response = client.get("/dash/demo.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    img = Image.open(io.BytesIO(response.content))
    assert img.size == (758, 1024)
    assert img.mode in ("L", "1")


def test_dash_png_unknown_dashboard_returns_404(client: TestClient) -> None:
    response = client.get("/dash/nope.png")
    assert response.status_code == 404


@freeze_time("2026-05-20 09:00:00")
def test_preview_returns_html(client: TestClient) -> None:
    response = client.get("/preview/demo")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "09:00" in response.text
```

- [ ] **Step 4: Run tests (expect fail)**

```bash
.venv/bin/pytest tests/test_routes_render.py -v
```

Expected: FAIL — render routes don't exist.

- [ ] **Step 5: Write `app/routes/render.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, Response as FastAPIResponse

from app.config_store import ConfigStore, DashboardNotFound
from app.deps import get_config_store
from app.render import render_dashboard_html, render_dashboard_png


router = APIRouter()


@router.get("/dash/{name}.png")
async def dash_png(name: str, store: ConfigStore = Depends(get_config_store)) -> Response:
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")
    png = await render_dashboard_png(dashboard)
    return FastAPIResponse(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/preview/{name}")
async def preview(name: str, store: ConfigStore = Depends(get_config_store)) -> HTMLResponse:
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")
    html = await render_dashboard_html(dashboard)
    return HTMLResponse(content=html)
```

- [ ] **Step 6: Rewrite `app/main.py`**

```python
from pathlib import Path

from fastapi import FastAPI

from app.config_store import ConfigStore
from app.deps import configure_store
from app.routes import render as render_routes


CONFIG_DIR = Path(__file__).parent.parent / "config"
configure_store(ConfigStore(dashboards_dir=CONFIG_DIR / "dashboards"))


app = FastAPI(title="kindledashboard")
app.include_router(render_routes.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/test_routes_render.py -v
```

Expected: 3 tests pass.

- [ ] **Step 8: Run the full suite**

```bash
.venv/bin/pytest -v
```

Expected: all previously-passing tests still pass.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: /dash/<name>.png and /preview/<name> routes"
```

---

## Task 6: Weather widget (Open-Meteo)

**Files:**
- Create: `app/widgets/weather.py`
- Create: `app/templates/widgets/weather.html`
- Modify: `app/widgets/__init__.py`
- Create: `tests/widgets/test_weather.py`

- [ ] **Step 1: Write failing test `tests/widgets/test_weather.py`**

```python
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
```

- [ ] **Step 2: Run test (expect fail)**

```bash
.venv/bin/pytest tests/widgets/test_weather.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Write `app/widgets/weather.py`**

```python
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
```

- [ ] **Step 4: Write `app/templates/widgets/weather.html`**

```html
<div class="widget widget-weather">
  <div class="weather-now">
    <span class="weather-temp">{{ current_temp }}°</span>
    <span class="weather-label">{{ current_label }}</span>
  </div>
  <div class="weather-forecast">
    {% for day in forecast %}
      <div class="weather-day">
        <div class="weather-day-date">{{ day.date[5:] }}</div>
        <div class="weather-day-temps">{{ day.max }}° / {{ day.min }}°</div>
        <div class="weather-day-label">{{ day.label }}</div>
      </div>
    {% endfor %}
  </div>
</div>
```

Also add CSS for `.widget-weather` to `app/templates/dashboard.html` `<style>` block:

```css
.widget-weather { display: flex; flex-direction: column; gap: 8px; }
.weather-now { display: flex; align-items: baseline; gap: 12px; }
.weather-temp { font-size: 48px; font-weight: 700; }
.weather-label { font-size: 18px; }
.weather-forecast { display: flex; gap: 8px; }
.weather-day { flex: 1; border: 1px solid #000; padding: 4px; font-size: 12px; text-align: center; }
.weather-day-date { font-weight: 700; }
```

- [ ] **Step 5: Register in `app/widgets/__init__.py`**

```python
from app.widgets.base import Widget, WidgetError
from app.widgets.clock import ClockWidget
from app.widgets.weather import WeatherWidget

REGISTRY: dict[str, type[Widget]] = {
    ClockWidget.type: ClockWidget,
    WeatherWidget.type: WeatherWidget,
}


def get_widget(type_name: str) -> Widget:
    cls = REGISTRY.get(type_name)
    if cls is None:
        raise KeyError(f"Unknown widget type: {type_name}")
    return cls()


__all__ = ["Widget", "WidgetError", "REGISTRY", "get_widget"]
```

- [ ] **Step 6: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/widgets/test_weather.py -v
```

Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: weather widget via Open-Meteo"
```

---

## Task 7: iobroker widget (simple-api REST)

**Files:**
- Create: `app/widgets/iobroker.py`
- Create: `app/templates/widgets/iobroker.html`
- Modify: `app/widgets/__init__.py`
- Create: `tests/widgets/test_iobroker.py`

- [ ] **Step 1: Write failing test `tests/widgets/test_iobroker.py`**

```python
import pytest
import respx
from httpx import Response

from app.widgets.iobroker import IobrokerStateWidget
from app.widgets.base import WidgetError


@pytest.mark.asyncio
async def test_iobroker_fetch_returns_value_and_label() -> None:
    fake = {"val": 21.5, "ack": True, "ts": 1716195000000}
    with respx.mock(base_url="http://pi:8087") as mock:
        mock.get("/get/system.adapter.admin.0.cpu").mock(return_value=Response(200, json=fake))
        widget = IobrokerStateWidget()
        ctx = await widget.fetch({
            "base_url": "http://pi:8087",
            "state_id": "system.adapter.admin.0.cpu",
            "label": "CPU",
            "unit": "%",
        })
    assert ctx == {"value": "21.5", "label": "CPU", "unit": "%"}


@pytest.mark.asyncio
async def test_iobroker_fetch_raises_on_http_error() -> None:
    with respx.mock(base_url="http://pi:8087") as mock:
        mock.get("/get/foo").mock(return_value=Response(404))
        widget = IobrokerStateWidget()
        with pytest.raises(WidgetError):
            await widget.fetch({"base_url": "http://pi:8087", "state_id": "foo", "label": "X"})


def test_iobroker_metadata() -> None:
    widget = IobrokerStateWidget()
    assert widget.type == "iobroker"
    assert "state_id" in widget.config_schema["properties"]
```

- [ ] **Step 2: Run test (expect fail)**

```bash
.venv/bin/pytest tests/widgets/test_iobroker.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write `app/widgets/iobroker.py`**

```python
from typing import Any

import httpx

from app.widgets.base import WidgetError


class IobrokerStateWidget:
    type = "iobroker"
    template = "widgets/iobroker.html"
    config_schema = {
        "type": "object",
        "required": ["base_url", "state_id", "label"],
        "properties": {
            "base_url": {"type": "string", "title": "iobroker base URL",
                         "default": "http://localhost:8087"},
            "state_id": {"type": "string", "title": "State ID"},
            "label": {"type": "string", "title": "Label"},
            "unit": {"type": "string", "title": "Unit (suffix)", "default": ""},
        },
    }

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=cfg["base_url"], timeout=5.0) as client:
                resp = await client.get(f"/get/{cfg['state_id']}")
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WidgetError(f"iobroker fetch failed: {exc}") from exc

        val = data.get("val")
        return {
            "value": str(val),
            "label": cfg["label"],
            "unit": cfg.get("unit", ""),
        }
```

- [ ] **Step 4: Write `app/templates/widgets/iobroker.html`**

```html
<div class="widget widget-iobroker">
  <div class="iobroker-label">{{ label }}</div>
  <div class="iobroker-value">{{ value }}{{ unit }}</div>
</div>
```

Add CSS to `dashboard.html`:

```css
.widget-iobroker { text-align: center; }
.iobroker-label { font-size: 14px; }
.iobroker-value { font-size: 40px; font-weight: 700; }
```

- [ ] **Step 5: Register in `app/widgets/__init__.py`**

```python
from app.widgets.base import Widget, WidgetError
from app.widgets.clock import ClockWidget
from app.widgets.iobroker import IobrokerStateWidget
from app.widgets.weather import WeatherWidget

REGISTRY: dict[str, type[Widget]] = {
    ClockWidget.type: ClockWidget,
    WeatherWidget.type: WeatherWidget,
    IobrokerStateWidget.type: IobrokerStateWidget,
}


def get_widget(type_name: str) -> Widget:
    cls = REGISTRY.get(type_name)
    if cls is None:
        raise KeyError(f"Unknown widget type: {type_name}")
    return cls()


__all__ = ["Widget", "WidgetError", "REGISTRY", "get_widget"]
```

- [ ] **Step 6: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/widgets/test_iobroker.py -v
```

Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: iobroker state widget via simple-api REST"
```

---

## Task 8: Grafana widget (panel image via render API)

**Files:**
- Create: `app/secrets.py`
- Create: `app/widgets/grafana.py`
- Create: `app/templates/widgets/grafana.html`
- Modify: `app/widgets/__init__.py`
- Create: `config/secrets.json.example`
- Create: `tests/test_secrets.py`
- Create: `tests/widgets/test_grafana.py`

- [ ] **Step 1: Write failing test `tests/test_secrets.py`**

```python
import json
from pathlib import Path

import pytest

from app.secrets import SecretsStore, MissingSecret


def test_resolve_plain_value_unchanged(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.json"
    secrets_file.write_text("{}")
    store = SecretsStore(secrets_file)
    assert store.resolve("hello") == "hello"


def test_resolve_dollar_reference(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.json"
    secrets_file.write_text(json.dumps({"grafana_token": "abc123"}))
    store = SecretsStore(secrets_file)
    assert store.resolve("$grafana_token") == "abc123"


def test_resolve_missing_raises(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.json"
    secrets_file.write_text("{}")
    store = SecretsStore(secrets_file)
    with pytest.raises(MissingSecret):
        store.resolve("$nope")


def test_resolve_missing_file_no_secrets(tmp_path: Path) -> None:
    store = SecretsStore(tmp_path / "absent.json")
    assert store.resolve("plain") == "plain"
    with pytest.raises(MissingSecret):
        store.resolve("$anything")
```

- [ ] **Step 2: Write failing test `tests/widgets/test_grafana.py`**

```python
import pytest
import respx
from httpx import Response

from app.widgets.grafana import GrafanaPanelWidget
from app.widgets.base import WidgetError
from app.secrets import SecretsStore


@pytest.mark.asyncio
async def test_grafana_fetch_downloads_png_and_returns_data_uri(tmp_path) -> None:
    secrets = SecretsStore(tmp_path / "s.json")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    with respx.mock(base_url="http://grafana:3000") as mock:
        mock.get("/render/d-solo/abc/dash").mock(return_value=Response(200, content=png, headers={"Content-Type": "image/png"}))
        widget = GrafanaPanelWidget(secrets=secrets)
        ctx = await widget.fetch({
            "base_url": "http://grafana:3000",
            "dashboard_uid": "abc",
            "dashboard_slug": "dash",
            "panel_id": 4,
            "width": 300,
            "height": 200,
            "token": "plain-token",
        })
    assert ctx["src"].startswith("data:image/png;base64,")
    assert ctx["width"] == 300


@pytest.mark.asyncio
async def test_grafana_fetch_uses_secrets_for_token(tmp_path) -> None:
    import json as _json
    sf = tmp_path / "s.json"
    sf.write_text(_json.dumps({"gtoken": "secret-abc"}))
    secrets = SecretsStore(sf)
    png = b"\x89PNG\r\n\x1a\n"

    captured = {}
    def _handler(request):
        captured["auth"] = request.headers.get("authorization")
        return Response(200, content=png, headers={"Content-Type": "image/png"})

    with respx.mock(base_url="http://grafana:3000") as mock:
        mock.get("/render/d-solo/abc/dash").mock(side_effect=_handler)
        widget = GrafanaPanelWidget(secrets=secrets)
        await widget.fetch({
            "base_url": "http://grafana:3000",
            "dashboard_uid": "abc", "dashboard_slug": "dash",
            "panel_id": 1, "width": 100, "height": 100,
            "token": "$gtoken",
        })
    assert captured["auth"] == "Bearer secret-abc"


@pytest.mark.asyncio
async def test_grafana_fetch_raises_on_error(tmp_path) -> None:
    secrets = SecretsStore(tmp_path / "s.json")
    with respx.mock(base_url="http://grafana:3000") as mock:
        mock.get("/render/d-solo/abc/dash").mock(return_value=Response(500))
        widget = GrafanaPanelWidget(secrets=secrets)
        with pytest.raises(WidgetError):
            await widget.fetch({
                "base_url": "http://grafana:3000",
                "dashboard_uid": "abc", "dashboard_slug": "dash",
                "panel_id": 1, "width": 100, "height": 100,
                "token": "plain",
            })
```

- [ ] **Step 3: Run tests (expect fail)**

```bash
.venv/bin/pytest tests/test_secrets.py tests/widgets/test_grafana.py -v
```

Expected: all FAIL.

- [ ] **Step 4: Write `app/secrets.py`**

```python
import json
from pathlib import Path


class MissingSecret(Exception):
    pass


class SecretsStore:
    """Resolves config values. A value starting with '$' is looked up in
    secrets.json; any other string passes through unchanged."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def resolve(self, value: str) -> str:
        if not isinstance(value, str) or not value.startswith("$"):
            return value
        key = value[1:]
        secrets = self._load()
        if key not in secrets:
            raise MissingSecret(key)
        return secrets[key]
```

- [ ] **Step 5: Write `config/secrets.json.example`**

```json
{
  "grafana_token": "REPLACE_WITH_GRAFANA_SERVICE_ACCOUNT_TOKEN",
  "icloud_app_password": "REPLACE_WITH_ICLOUD_APP_SPECIFIC_PASSWORD"
}
```

- [ ] **Step 6: Write `app/widgets/grafana.py`**

```python
import base64
from typing import Any

import httpx

from app.secrets import MissingSecret, SecretsStore
from app.widgets.base import WidgetError


class GrafanaPanelWidget:
    type = "grafana"
    template = "widgets/grafana.html"
    config_schema = {
        "type": "object",
        "required": ["base_url", "dashboard_uid", "dashboard_slug", "panel_id"],
        "properties": {
            "base_url": {"type": "string", "title": "Grafana base URL",
                         "default": "http://localhost:3000"},
            "dashboard_uid": {"type": "string", "title": "Dashboard UID"},
            "dashboard_slug": {"type": "string", "title": "Dashboard slug"},
            "panel_id": {"type": "integer", "title": "Panel ID"},
            "width": {"type": "integer", "title": "Width (px)", "default": 500},
            "height": {"type": "integer", "title": "Height (px)", "default": 300},
            "token": {"type": "string", "title": "API token (use $name for secrets)",
                      "default": "$grafana_token"},
        },
    }

    def __init__(self, secrets: SecretsStore | None = None) -> None:
        self.secrets = secrets

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            token = self.secrets.resolve(cfg["token"]) if self.secrets else cfg["token"]
        except MissingSecret as exc:
            raise WidgetError(f"missing secret: {exc}") from exc

        path = f"/render/d-solo/{cfg['dashboard_uid']}/{cfg['dashboard_slug']}"
        params = {
            "panelId": cfg["panel_id"],
            "width": cfg.get("width", 500),
            "height": cfg.get("height", 300),
            "tz": "Europe/Berlin",
        }
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with httpx.AsyncClient(base_url=cfg["base_url"], timeout=10.0) as client:
                resp = await client.get(path, params=params, headers=headers)
                resp.raise_for_status()
                png = resp.content
        except httpx.HTTPError as exc:
            raise WidgetError(f"grafana fetch failed: {exc}") from exc

        b64 = base64.b64encode(png).decode("ascii")
        return {
            "src": f"data:image/png;base64,{b64}",
            "width": cfg.get("width", 500),
            "height": cfg.get("height", 300),
        }
```

- [ ] **Step 7: Write `app/templates/widgets/grafana.html`**

```html
<div class="widget widget-grafana">
  <img src="{{ src }}" alt="grafana panel"
       style="width: 100%; height: 100%; object-fit: contain;">
</div>
```

- [ ] **Step 8: Update `app/widgets/__init__.py`**

```python
from app.secrets import SecretsStore
from app.widgets.base import Widget, WidgetError
from app.widgets.clock import ClockWidget
from app.widgets.grafana import GrafanaPanelWidget
from app.widgets.iobroker import IobrokerStateWidget
from app.widgets.weather import WeatherWidget

# Widget classes that don't need extra construction args
_SIMPLE: dict[str, type] = {
    ClockWidget.type: ClockWidget,
    WeatherWidget.type: WeatherWidget,
    IobrokerStateWidget.type: IobrokerStateWidget,
}

REGISTRY: dict[str, type[Widget]] = {
    **_SIMPLE,
    GrafanaPanelWidget.type: GrafanaPanelWidget,
}


_secrets: SecretsStore | None = None


def configure(secrets: SecretsStore) -> None:
    global _secrets
    _secrets = secrets


def get_widget(type_name: str) -> Widget:
    if type_name not in REGISTRY:
        raise KeyError(f"Unknown widget type: {type_name}")
    if type_name == GrafanaPanelWidget.type:
        return GrafanaPanelWidget(secrets=_secrets)
    return REGISTRY[type_name]()


__all__ = ["Widget", "WidgetError", "REGISTRY", "get_widget", "configure"]
```

- [ ] **Step 9: Wire secrets in `app/main.py`**

Modify `app/main.py`:

```python
from pathlib import Path

from fastapi import FastAPI

from app import widgets
from app.config_store import ConfigStore
from app.deps import configure_store
from app.routes import render as render_routes
from app.secrets import SecretsStore


CONFIG_DIR = Path(__file__).parent.parent / "config"
configure_store(ConfigStore(dashboards_dir=CONFIG_DIR / "dashboards"))
widgets.configure(SecretsStore(path=CONFIG_DIR / "secrets.json"))


app = FastAPI(title="kindledashboard")
app.include_router(render_routes.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 10: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/test_secrets.py tests/widgets/test_grafana.py -v
```

Expected: 7 tests pass.

- [ ] **Step 11: Full suite still passes**

```bash
.venv/bin/pytest -v
```

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "feat: grafana widget and secrets store"
```

---

## Task 9: iCloud calendar widget (CalDAV)

**Files:**
- Create: `app/widgets/calendar.py`
- Create: `app/templates/widgets/calendar.html`
- Modify: `app/widgets/__init__.py`
- Create: `tests/widgets/test_calendar.py`

- [ ] **Step 1: Write failing test `tests/widgets/test_calendar.py`**

```python
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.widgets.calendar import ICloudCalendarWidget
from app.widgets.base import WidgetError
from app.secrets import SecretsStore


def _make_event(start: datetime, summary: str):
    ev = MagicMock()
    instance = MagicMock()
    instance.vevent.summary.value = summary
    instance.vevent.dtstart.value = start
    ev.icalendar_instance.vevent_list = [instance.vevent]
    return ev


@pytest.mark.asyncio
async def test_calendar_fetch_returns_upcoming_events(tmp_path) -> None:
    secrets = SecretsStore(tmp_path / "s.json")
    now = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)

    fake_cal = MagicMock()
    e1_inst = MagicMock(); e1_inst.summary.value = "Standup"
    e1_inst.dtstart.value = now + timedelta(hours=1)
    e2_inst = MagicMock(); e2_inst.summary.value = "Lunch"
    e2_inst.dtstart.value = now + timedelta(hours=4)
    ev1 = MagicMock(); ev1.icalendar_instance.vevent_list = [e1_inst]
    ev2 = MagicMock(); ev2.icalendar_instance.vevent_list = [e2_inst]
    fake_cal.search.return_value = [ev1, ev2]

    fake_principal = MagicMock()
    fake_principal.calendar.return_value = fake_cal
    fake_client = MagicMock()
    fake_client.principal.return_value = fake_principal

    with patch("app.widgets.calendar.caldav.DAVClient", return_value=fake_client), \
         patch("app.widgets.calendar.datetime") as dt_mock:
        dt_mock.now.return_value = now
        dt_mock.side_effect = lambda *a, **kw: datetime(*a, **kw)
        widget = ICloudCalendarWidget(secrets=secrets)
        ctx = await widget.fetch({
            "username": "user@icloud.com",
            "password": "plain-pw",
            "calendar_name": "Home",
            "max_events": 5,
        })

    assert len(ctx["events"]) == 2
    assert ctx["events"][0]["summary"] == "Standup"


@pytest.mark.asyncio
async def test_calendar_fetch_raises_on_connection_error(tmp_path) -> None:
    secrets = SecretsStore(tmp_path / "s.json")
    with patch("app.widgets.calendar.caldav.DAVClient", side_effect=ConnectionError("boom")):
        widget = ICloudCalendarWidget(secrets=secrets)
        with pytest.raises(WidgetError):
            await widget.fetch({
                "username": "u", "password": "p", "calendar_name": "C", "max_events": 5,
            })


def test_calendar_metadata() -> None:
    widget = ICloudCalendarWidget(secrets=None)
    assert widget.type == "calendar"
    assert "username" in widget.config_schema["properties"]
```

- [ ] **Step 2: Run test (expect fail)**

```bash
.venv/bin/pytest tests/widgets/test_calendar.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write `app/widgets/calendar.py`**

```python
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import caldav

from app.secrets import MissingSecret, SecretsStore
from app.widgets.base import WidgetError


ICLOUD_URL = "https://caldav.icloud.com"


class ICloudCalendarWidget:
    type = "calendar"
    template = "widgets/calendar.html"
    config_schema = {
        "type": "object",
        "required": ["username", "password", "calendar_name"],
        "properties": {
            "username": {"type": "string", "title": "iCloud username (email)"},
            "password": {"type": "string", "title": "App-specific password (use $name for secrets)",
                         "default": "$icloud_app_password"},
            "calendar_name": {"type": "string", "title": "Calendar name"},
            "max_events": {"type": "integer", "title": "Max events", "default": 5, "minimum": 1, "maximum": 20},
            "lookahead_days": {"type": "integer", "title": "Lookahead days", "default": 7},
        },
    }

    def __init__(self, secrets: SecretsStore | None = None) -> None:
        self.secrets = secrets

    def _fetch_sync(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            password = self.secrets.resolve(cfg["password"]) if self.secrets else cfg["password"]
        except MissingSecret as exc:
            raise WidgetError(f"missing secret: {exc}") from exc

        try:
            client = caldav.DAVClient(url=ICLOUD_URL, username=cfg["username"], password=password)
            principal = client.principal()
            calendar = principal.calendar(name=cfg["calendar_name"])
        except (caldav.lib.error.AuthorizationError, ConnectionError, OSError) as exc:
            raise WidgetError(f"caldav connect failed: {exc}") from exc

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=int(cfg.get("lookahead_days", 7)))
        max_events = int(cfg.get("max_events", 5))

        try:
            events = calendar.search(start=now, end=end, event=True, expand=True)
        except Exception as exc:  # noqa: BLE001
            raise WidgetError(f"caldav search failed: {exc}") from exc

        parsed = []
        for ev in events:
            for vevent in ev.icalendar_instance.vevent_list:
                start = vevent.dtstart.value
                if isinstance(start, datetime):
                    when = start.strftime("%a %d.%m. %H:%M")
                else:
                    when = start.strftime("%a %d.%m.") + " · all day"
                parsed.append({"summary": str(vevent.summary.value), "when": when, "sort": start})
        parsed.sort(key=lambda e: e["sort"].isoformat() if isinstance(e["sort"], datetime) else str(e["sort"]))
        for e in parsed:
            e.pop("sort")
        return {"events": parsed[:max_events]}

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._fetch_sync, cfg)
```

- [ ] **Step 4: Write `app/templates/widgets/calendar.html`**

```html
<div class="widget widget-calendar">
  <div class="calendar-header">Upcoming</div>
  <ul class="calendar-events">
    {% for ev in events %}
      <li><span class="cal-when">{{ ev.when }}</span> <span class="cal-summary">{{ ev.summary }}</span></li>
    {% endfor %}
    {% if not events %}<li class="cal-empty">No events</li>{% endif %}
  </ul>
</div>
```

Add to `dashboard.html` CSS:

```css
.widget-calendar { font-size: 14px; }
.calendar-header { font-weight: 700; margin-bottom: 4px; }
.calendar-events { list-style: none; padding: 0; margin: 0; }
.calendar-events li { padding: 2px 0; border-bottom: 1px solid #000; }
.cal-when { font-weight: 700; margin-right: 6px; }
```

- [ ] **Step 5: Update `app/widgets/__init__.py`**

```python
from app.secrets import SecretsStore
from app.widgets.base import Widget, WidgetError
from app.widgets.calendar import ICloudCalendarWidget
from app.widgets.clock import ClockWidget
from app.widgets.grafana import GrafanaPanelWidget
from app.widgets.iobroker import IobrokerStateWidget
from app.widgets.weather import WeatherWidget

REGISTRY: dict[str, type[Widget]] = {
    ClockWidget.type: ClockWidget,
    WeatherWidget.type: WeatherWidget,
    IobrokerStateWidget.type: IobrokerStateWidget,
    GrafanaPanelWidget.type: GrafanaPanelWidget,
    ICloudCalendarWidget.type: ICloudCalendarWidget,
}

_NEEDS_SECRETS = {GrafanaPanelWidget.type, ICloudCalendarWidget.type}
_secrets: SecretsStore | None = None


def configure(secrets: SecretsStore) -> None:
    global _secrets
    _secrets = secrets


def get_widget(type_name: str) -> Widget:
    cls = REGISTRY.get(type_name)
    if cls is None:
        raise KeyError(f"Unknown widget type: {type_name}")
    if type_name in _NEEDS_SECRETS:
        return cls(secrets=_secrets)
    return cls()


__all__ = ["Widget", "WidgetError", "REGISTRY", "get_widget", "configure"]
```

- [ ] **Step 6: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/widgets/test_calendar.py -v
```

Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: iCloud calendar widget via CalDAV"
```

---

## Task 10: Editor — list dashboards + create/delete

**Files:**
- Create: `app/routes/editor.py`
- Create: `app/templates/editor.html`
- Modify: `app/main.py`
- Create: `tests/test_routes_editor.py`

- [ ] **Step 1: Write failing test `tests/test_routes_editor.py`**

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config_store import ConfigStore
from app.deps import get_config_store
from app.main import app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    store = ConfigStore(dashboards_dir=tmp_path / "dashboards")
    app.dependency_overrides[get_config_store] = lambda: store
    yield TestClient(app), store
    app.dependency_overrides.clear()


def test_editor_lists_dashboards(client) -> None:
    c, store = client
    store.save("morning", {
        "name": "morning", "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16}, "dither": "fs", "widgets": [],
    })
    resp = c.get("/editor")
    assert resp.status_code == 200
    assert "morning" in resp.text


def test_create_dashboard(client) -> None:
    c, store = client
    resp = c.post("/api/dashboards", data={"name": "new"})
    assert resp.status_code == 200
    assert "new" in store.list()


def test_delete_dashboard(client) -> None:
    c, store = client
    store.save("doomed", {
        "name": "doomed", "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16}, "dither": "fs", "widgets": [],
    })
    resp = c.delete("/api/dashboards/doomed")
    assert resp.status_code == 200
    assert "doomed" not in store.list()
```

- [ ] **Step 2: Run test (expect fail)**

```bash
.venv/bin/pytest tests/test_routes_editor.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write `app/routes/editor.py`**

```python
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.config_store import ConfigStore, DashboardNotFound, InvalidDashboard
from app.deps import get_config_store
from app.widgets import REGISTRY


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _default_dashboard(name: str) -> dict:
    return {
        "name": name,
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }


@router.get("/editor", response_class=HTMLResponse)
def editor_index(request: Request, store: ConfigStore = Depends(get_config_store)) -> HTMLResponse:
    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "dashboards": sorted(store.list()),
            "widget_types": sorted(REGISTRY.keys()),
        },
    )


@router.post("/api/dashboards")
def create_dashboard(
    name: str = Form(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    try:
        store.save(name, _default_dashboard(name))
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"name": name}


@router.delete("/api/dashboards/{name}")
def delete_dashboard(name: str, store: ConfigStore = Depends(get_config_store)) -> dict:
    try:
        store.delete(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    return {"deleted": name}
```

- [ ] **Step 4: Write `app/templates/editor.html`**

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Kindle Dashboard Editor</title>
<link rel="stylesheet" href="/static/gridstack.min.css">
<script src="/static/gridstack.min.js"></script>
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
<style>
  body { font-family: -apple-system, sans-serif; margin: 0; padding: 16px; }
  h1 { margin-top: 0; }
  .layout { display: grid; grid-template-columns: auto 320px; gap: 16px; }
  .canvas-wrap { background: #fafafa; padding: 8px; border: 1px solid #ccc; }
  .grid-stack { width: 758px; height: 1024px; border: 1px solid #000; background: #fff; }
  .panel { display: flex; flex-direction: column; gap: 12px; }
  .panel > section { border: 1px solid #ccc; padding: 12px; }
  .palette-btn { display: block; width: 100%; padding: 6px; margin-bottom: 4px;
                 background: #f0f0f0; border: 1px solid #ccc; cursor: grab; }
  form.inline { display: inline; }
  .topbar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
</style>
</head>
<body>
<h1>Kindle Dashboard Editor</h1>

<div class="topbar">
  <label>Dashboard:
    <select id="dashboard-select" onchange="location.href='/editor?name=' + this.value">
      {% for name in dashboards %}
        <option value="{{ name }}">{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <form class="inline" hx-post="/api/dashboards" hx-target="#dashboards-list" hx-swap="none">
    <input name="name" placeholder="New dashboard name">
    <button type="submit">+ New</button>
  </form>
</div>

<div class="layout">
  <div class="canvas-wrap">
    <div class="grid-stack"></div>
    <div style="margin-top: 8px;">
      <button onclick="saveLayout()">💾 Save</button>
      <a id="preview-link" href="/preview/" target="_blank">👁 Preview</a>
    </div>
  </div>
  <aside class="panel">
    <section>
      <h3>Widgets</h3>
      {% for t in widget_types %}
        <button class="palette-btn" data-widget-type="{{ t }}"
                onclick="addWidget('{{ t }}')">+ {{ t }}</button>
      {% endfor %}
    </section>
    <section>
      <h3>Widget config</h3>
      <div id="widget-config">Select a widget on the canvas.</div>
    </section>
    <section id="dashboards-list">
      <h3>All dashboards</h3>
      <ul>
        {% for name in dashboards %}
          <li>{{ name }}
            <button hx-delete="/api/dashboards/{{ name }}"
                    hx-confirm="Delete {{ name }}?" hx-target="closest li" hx-swap="outerHTML">×</button>
          </li>
        {% endfor %}
      </ul>
    </section>
  </aside>
</div>

<script src="/static/editor.js"></script>
</body>
</html>
```

- [ ] **Step 5: Wire editor routes in `app/main.py`**

Replace `app/main.py` body:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import widgets
from app.config_store import ConfigStore
from app.deps import configure_store
from app.routes import editor as editor_routes
from app.routes import render as render_routes
from app.secrets import SecretsStore


CONFIG_DIR = Path(__file__).parent.parent / "config"
STATIC_DIR = Path(__file__).parent / "static"

configure_store(ConfigStore(dashboards_dir=CONFIG_DIR / "dashboards"))
widgets.configure(SecretsStore(path=CONFIG_DIR / "secrets.json"))

STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="kindledashboard")
app.include_router(render_routes.router)
app.include_router(editor_routes.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/test_routes_editor.py -v
```

Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: editor index, create and delete dashboard routes"
```

---

## Task 11: Editor — Gridstack canvas, save layout, widget config form

**Files:**
- Create: `app/static/editor.js`
- Create: `app/templates/_widget_form.html`
- Modify: `app/routes/editor.py`
- Modify: `app/templates/editor.html`
- Modify: `tests/test_routes_editor.py`

- [ ] **Step 1: Download Gridstack.js (vendored)**

```bash
curl -L -o app/static/gridstack.min.js https://cdn.jsdelivr.net/npm/gridstack@10.1.2/dist/gridstack-all.js
curl -L -o app/static/gridstack.min.css https://cdn.jsdelivr.net/npm/gridstack@10.1.2/dist/gridstack.min.css
```

Verify both files exist and are non-empty.

- [ ] **Step 2: Add failing tests for layout save and widget config form**

Append to `tests/test_routes_editor.py`:

```python
def test_get_dashboard_returns_json(client) -> None:
    c, store = client
    data = {
        "name": "demo", "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
        "widgets": [{"id": "w1", "type": "clock", "pos": {"x": 0, "y": 0, "w": 12, "h": 2}, "config": {}}],
    }
    store.save("demo", data)
    resp = c.get("/api/dashboards/demo")
    assert resp.status_code == 200
    assert resp.json() == data


def test_put_layout_persists(client) -> None:
    c, store = client
    base = {"name": "demo", "size": {"w": 758, "h": 1024},
            "grid": {"cols": 12, "rows": 16}, "dither": "fs", "widgets": []}
    store.save("demo", base)
    new_widgets = [
        {"id": "w1", "type": "clock", "pos": {"x": 0, "y": 0, "w": 6, "h": 3}, "config": {"format": "HH:mm"}}
    ]
    resp = c.put("/api/dashboards/demo/layout", json={"widgets": new_widgets})
    assert resp.status_code == 200
    assert store.load("demo")["widgets"] == new_widgets


def test_widget_config_form_renders(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
                        "widgets": [{"id": "w1", "type": "weather",
                                     "pos": {"x": 0, "y": 0, "w": 6, "h": 4},
                                     "config": {"lat": 48.1, "lon": 11.6}}]})
    resp = c.get("/api/dashboards/demo/widgets/w1/config-form")
    assert resp.status_code == 200
    assert "lat" in resp.text
    assert "lon" in resp.text


def test_patch_widget_config(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
                        "widgets": [{"id": "w1", "type": "weather",
                                     "pos": {"x": 0, "y": 0, "w": 6, "h": 4},
                                     "config": {"lat": 0, "lon": 0}}]})
    resp = c.patch("/api/dashboards/demo/widgets/w1",
                   json={"config": {"lat": 50, "lon": 8, "days": 3}})
    assert resp.status_code == 200
    assert store.load("demo")["widgets"][0]["config"] == {"lat": 50, "lon": 8, "days": 3}
```

- [ ] **Step 3: Run tests (expect fail)**

```bash
.venv/bin/pytest tests/test_routes_editor.py -v
```

Expected: 4 new tests FAIL.

- [ ] **Step 4: Extend `app/routes/editor.py`**

Replace the file with:

```python
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.config_store import ConfigStore, DashboardNotFound, InvalidDashboard
from app.deps import get_config_store
from app.widgets import REGISTRY, get_widget


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _default_dashboard(name: str) -> dict:
    return {
        "name": name,
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }


@router.get("/editor", response_class=HTMLResponse)
def editor_index(request: Request, store: ConfigStore = Depends(get_config_store)) -> HTMLResponse:
    return templates.TemplateResponse("editor.html", {
        "request": request,
        "dashboards": sorted(store.list()),
        "widget_types": sorted(REGISTRY.keys()),
    })


@router.post("/api/dashboards")
def create_dashboard(name: str = Form(...), store: ConfigStore = Depends(get_config_store)) -> dict:
    try:
        store.save(name, _default_dashboard(name))
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"name": name}


@router.delete("/api/dashboards/{name}")
def delete_dashboard(name: str, store: ConfigStore = Depends(get_config_store)) -> dict:
    try:
        store.delete(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    return {"deleted": name}


@router.get("/api/dashboards/{name}")
def get_dashboard(name: str, store: ConfigStore = Depends(get_config_store)) -> JSONResponse:
    try:
        return JSONResponse(store.load(name))
    except DashboardNotFound:
        raise HTTPException(status_code=404)


@router.put("/api/dashboards/{name}/layout")
def put_layout(
    name: str,
    payload: dict[str, Any] = Body(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    try:
        dash = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    dash["widgets"] = payload["widgets"]
    try:
        store.save(name, dash)
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"saved": True}


@router.get("/api/dashboards/{name}/widgets/{wid}/config-form", response_class=HTMLResponse)
def widget_config_form(name: str, wid: str, request: Request,
                       store: ConfigStore = Depends(get_config_store)) -> HTMLResponse:
    try:
        dash = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    widget_cfg = next((w for w in dash["widgets"] if w["id"] == wid), None)
    if widget_cfg is None:
        raise HTTPException(status_code=404)
    schema = get_widget(widget_cfg["type"]).config_schema
    return templates.TemplateResponse("_widget_form.html", {
        "request": request,
        "dashboard": name,
        "widget": widget_cfg,
        "schema": schema,
    })


@router.patch("/api/dashboards/{name}/widgets/{wid}")
def patch_widget(name: str, wid: str,
                 payload: dict[str, Any] = Body(...),
                 store: ConfigStore = Depends(get_config_store)) -> dict:
    try:
        dash = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    for w in dash["widgets"]:
        if w["id"] == wid:
            if "config" in payload:
                w["config"] = payload["config"]
            break
    else:
        raise HTTPException(status_code=404)
    try:
        store.save(name, dash)
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"saved": True}
```

- [ ] **Step 5: Write `app/templates/_widget_form.html`**

```html
<form hx-patch="/api/dashboards/{{ dashboard }}/widgets/{{ widget.id }}"
      hx-ext="json-enc" hx-trigger="submit" hx-swap="none">
  <h4>{{ widget.type }} ({{ widget.id }})</h4>
  {% for key, prop in schema.properties.items() %}
    <label style="display:block; margin: 6px 0;">
      {{ prop.title or key }}
      {% set value = widget.config.get(key, prop.default if 'default' in prop else '') %}
      {% if prop.type == "integer" or prop.type == "number" %}
        <input type="number" name="config[{{ key }}]" value="{{ value }}"
               {% if prop.type == 'integer' %}step="1"{% else %}step="any"{% endif %}>
      {% else %}
        <input type="text" name="config[{{ key }}]" value="{{ value }}">
      {% endif %}
    </label>
  {% endfor %}
  <button type="submit">Save widget</button>
</form>
<script>
  // Convert flat form fields config[key]=value to nested {config:{key:value}}
  document.body.addEventListener('htmx:configRequest', (ev) => {
    const params = ev.detail.parameters;
    if (Object.keys(params).some(k => k.startsWith('config['))) {
      const config = {};
      for (const k of Object.keys(params)) {
        const m = k.match(/^config\[(.+)\]$/);
        if (m) {
          let v = params[k];
          if (v !== '' && !isNaN(v)) v = Number(v);
          config[m[1]] = v;
          delete params[k];
        }
      }
      ev.detail.parameters = { config };
    }
  });
</script>
```

- [ ] **Step 6: Write `app/static/editor.js`**

```javascript
const params = new URLSearchParams(location.search);
const dashboardName = params.get('name') || document.getElementById('dashboard-select')?.value;
document.getElementById('preview-link').href = '/preview/' + dashboardName;
document.getElementById('dashboard-select').value = dashboardName;

const grid = GridStack.init({
  column: 12,
  cellHeight: 1024 / 16,
  margin: 2,
  float: true,
}, '.grid-stack');

let nextId = 1;

async function loadDashboard() {
  const res = await fetch('/api/dashboards/' + dashboardName);
  if (!res.ok) return;
  const dash = await res.json();
  grid.removeAll();
  for (const w of dash.widgets) {
    const num = parseInt(w.id.replace(/\D/g, ''), 10);
    if (num >= nextId) nextId = num + 1;
    grid.addWidget(buildItem(w));
  }
}

function buildItem(w) {
  const el = document.createElement('div');
  el.classList.add('grid-stack-item');
  el.dataset.id = w.id;
  el.dataset.type = w.type;
  el.setAttribute('gs-x', w.pos.x);
  el.setAttribute('gs-y', w.pos.y);
  el.setAttribute('gs-w', w.pos.w);
  el.setAttribute('gs-h', w.pos.h);
  const content = document.createElement('div');
  content.classList.add('grid-stack-item-content');
  content.textContent = w.type + ' (' + w.id + ')';
  content.style.cursor = 'pointer';
  content.onclick = () => loadConfigForm(w.id);
  el.appendChild(content);
  return el;
}

function loadConfigForm(wid) {
  htmx.ajax('GET',
    '/api/dashboards/' + dashboardName + '/widgets/' + wid + '/config-form',
    { target: '#widget-config' });
}

window.addWidget = function(type) {
  const id = 'w' + (nextId++);
  const item = buildItem({ id, type, pos: { x: 0, y: 0, w: 4, h: 3 }, config: {} });
  grid.addWidget(item);
  // Persist immediately so the new widget exists for config-form
  saveLayout().then(() => loadConfigForm(id));
};

window.saveLayout = async function() {
  const widgets = grid.getGridItems().map(el => ({
    id: el.dataset.id,
    type: el.dataset.type,
    pos: {
      x: parseInt(el.getAttribute('gs-x'), 10),
      y: parseInt(el.getAttribute('gs-y'), 10),
      w: parseInt(el.getAttribute('gs-w'), 10),
      h: parseInt(el.getAttribute('gs-h'), 10),
    },
    // Preserve existing config: fetch current dashboard, look it up
    config: window._configCache?.[el.dataset.id] || {},
  }));
  // Merge in known configs from server
  const current = await fetch('/api/dashboards/' + dashboardName).then(r => r.ok ? r.json() : { widgets: [] });
  const cfgById = Object.fromEntries(current.widgets.map(w => [w.id, w.config]));
  for (const w of widgets) {
    if (cfgById[w.id]) w.config = cfgById[w.id];
  }
  const resp = await fetch('/api/dashboards/' + dashboardName + '/layout', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ widgets }),
  });
  if (!resp.ok) alert('Save failed: ' + resp.status);
};

loadDashboard();
```

- [ ] **Step 7: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/test_routes_editor.py -v
```

Expected: 7 tests pass.

- [ ] **Step 8: Manual smoke test**

```bash
.venv/bin/uvicorn app.main:app --reload --port 8080
```

In a browser, open `http://localhost:8080/editor`. Create a dashboard "smoke", add a clock widget, drag it, save. Open `http://localhost:8080/preview/smoke` and `http://localhost:8080/dash/smoke.png` and confirm both show the clock.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: editor canvas with Gridstack.js and widget config forms"
```

---

## Task 12: Error handling polish (cell errors + render-error PNG)

**Files:**
- Create: `app/error_image.py`
- Modify: `app/routes/render.py`
- Create: `tests/test_error_image.py`
- Modify: `tests/test_routes_render.py`

- [ ] **Step 1: Write failing tests `tests/test_error_image.py`**

```python
import io

from PIL import Image

from app.error_image import error_png


def test_error_png_returns_correct_size_and_mode() -> None:
    png = error_png("boom", width=758, height=1024)
    img = Image.open(io.BytesIO(png))
    assert img.size == (758, 1024)
    assert img.mode in ("L", "1")
```

- [ ] **Step 2: Add a failing route test for malformed config**

Append to `tests/test_routes_render.py`:

```python
def test_dash_png_returns_error_png_when_config_invalid(client: TestClient, tmp_path: Path) -> None:
    # Force an invalid config by writing directly to disk, bypassing validation
    import json as _json
    bad = tmp_path / "dashboards" / "broken.json"
    bad.write_text(_json.dumps({"name": "broken"}))  # missing required fields
    response = client.get("/dash/broken.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    # Should be a valid PNG even though config is broken
    img = Image.open(io.BytesIO(response.content))
    assert img.size == (758, 1024)
```

- [ ] **Step 3: Run tests (expect fail)**

```bash
.venv/bin/pytest tests/test_error_image.py tests/test_routes_render.py -v
```

Expected: new tests FAIL.

- [ ] **Step 4: Write `app/error_image.py`**

```python
import io

from PIL import Image, ImageDraw, ImageFont


def error_png(message: str, width: int = 758, height: int = 1024) -> bytes:
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 20), "⚠ render error", fill=0, font=font)
    draw.text((20, 60), message[:200], fill=0, font=font)
    from datetime import datetime
    draw.text((20, height - 40), datetime.now().isoformat(timespec="seconds"), fill=0, font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 5: Update `app/routes/render.py`**

```python
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, Response as FastAPIResponse

from app.config_store import ConfigStore, DashboardNotFound
from app.deps import get_config_store
from app.error_image import error_png
from app.render import render_dashboard_html, render_dashboard_png


log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dash/{name}.png")
async def dash_png(name: str, store: ConfigStore = Depends(get_config_store)) -> Response:
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")
    try:
        png = await render_dashboard_png(dashboard)
    except Exception as exc:  # noqa: BLE001
        log.exception("render failed for %s", name)
        png = error_png(f"{type(exc).__name__}: {exc}")
    return FastAPIResponse(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/preview/{name}")
async def preview(name: str, store: ConfigStore = Depends(get_config_store)) -> HTMLResponse:
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")
    html = await render_dashboard_html(dashboard)
    return HTMLResponse(content=html)
```

- [ ] **Step 6: Run tests (expect pass)**

```bash
.venv/bin/pytest tests/test_error_image.py tests/test_routes_render.py -v
```

Expected: all pass.

- [ ] **Step 7: Full suite passes**

```bash
.venv/bin/pytest -v
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: error PNG fallback so the Kindle never sees a stale frame"
```

---

## Task 13: Deployment (systemd unit + README of system deps)

**Files:**
- Create: `deploy/kindledashboard.service`
- Create: `config/dashboards/example.json`

- [ ] **Step 1: Write `deploy/kindledashboard.service`**

```ini
[Unit]
Description=Kindle Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/kindledashboard
Environment="PATH=/opt/kindledashboard/.venv/bin"
ExecStart=/opt/kindledashboard/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write `config/dashboards/example.json`**

```json
{
  "name": "example",
  "size": { "w": 758, "h": 1024 },
  "grid": { "cols": 12, "rows": 16 },
  "dither": "fs",
  "widgets": [
    {
      "id": "w1",
      "type": "clock",
      "pos": { "x": 0, "y": 0, "w": 12, "h": 3 },
      "config": { "format": "HH:mm" }
    },
    {
      "id": "w2",
      "type": "weather",
      "pos": { "x": 0, "y": 3, "w": 12, "h": 5 },
      "config": { "lat": 48.137, "lon": 11.575, "days": 3 }
    }
  ]
}
```

- [ ] **Step 3: Smoke-test the example dashboard locally**

```bash
.venv/bin/uvicorn app.main:app --port 8080 &
SERVER_PID=$!
sleep 2
curl -s -o /tmp/example.png -w "%{http_code}\n" http://localhost:8080/dash/example.png
kill $SERVER_PID
file /tmp/example.png
```

Expected: HTTP 200, file is `PNG image data, 758 x 1024, 1-bit grayscale` or similar.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: example dashboard and systemd unit"
```

---

## Task 14: Claude skill for creating new widgets

**Files:**
- Create: `.claude/skills/create-widget/SKILL.md`

- [ ] **Step 1: Write `.claude/skills/create-widget/SKILL.md`**

````markdown
---
name: create-widget
description: Use when the user asks to add a new widget type to the Kindle dashboard. Triggers on phrases like "add a new widget", "create a [name] widget", "I want a widget that shows X", or "/create-widget". Generates the widget module, template, registration, and tests following the project's Widget protocol.
---

# Create Widget

Add a new widget type to the Kindle dashboard. Each widget consists of:

1. A Python module at `app/widgets/<name>.py` implementing the `Widget` protocol
2. A Jinja partial at `app/templates/widgets/<name>.html`
3. A test file at `tests/widgets/test_<name>.py`
4. Registration in `app/widgets/__init__.py`
5. CSS (added to `app/templates/dashboard.html`)

## Gather Requirements

Ask the user, one at a time:

1. **Snake-case name** (e.g. `stocks`, `traffic`, `air_quality`). Must be a valid Python identifier and unique in `app/widgets/`.
2. **Display label** (e.g. "Stock Prices").
3. **Data source** — what API, library, or local resource provides the data? URL or library name.
4. **Auth** — does the data source need credentials? If yes, they belong in `config/secrets.json` and the config schema references them via `$name`.
5. **Config fields the user sets per-instance** — e.g. "ticker symbol, refresh interval". For each field: name, type (`string`/`integer`/`number`/`boolean`), required (yes/no), default.
6. **What the rendered output looks like** — what data fields are in the template context? What's the rough HTML layout?

## Constraints (read these before generating)

- **Async first.** `fetch()` is `async`. Use `httpx.AsyncClient` for HTTP. If the data library is sync-only (like `caldav`), wrap with `asyncio.to_thread(...)`.
- **No JavaScript runs in the rendered widget HTML.** WeasyPrint doesn't execute JS. Inline images via data URIs if needed.
- **Errors → `WidgetError`.** Any failure to fetch data must raise `WidgetError`. The renderer turns this into a per-cell error box.
- **Secrets resolution.** If the widget takes a credential, add `secrets: SecretsStore | None = None` to `__init__`, call `self.secrets.resolve(cfg["password"])`, and update `_NEEDS_SECRETS` in `app/widgets/__init__.py`.
- **No `print()` or logging.info in fetch.** Errors are signaled by exceptions.
- **Tests use respx for HTTP mocking** or `unittest.mock` for non-HTTP. Never make real network calls in tests.
- **No state outside `fetch()`.** Widget instances may be reused; don't store fetched data on `self`.
- **CSS scoping.** Add CSS rules under `.widget-<name>` to `app/templates/dashboard.html`. Don't ship a separate stylesheet.

## Templates

### Widget module: `app/widgets/<name>.py`

```python
from typing import Any

import httpx

from app.widgets.base import WidgetError


class <ClassName>Widget:
    type = "<name>"
    template = "widgets/<name>.html"
    config_schema = {
        "type": "object",
        "required": [<required-fields-as-strings>],
        "properties": {
            # Fill from user requirements:
            # "field_name": {"type": "string"|"integer"|"number"|"boolean",
            #                "title": "Human label", "default": ...},
        },
    }

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(<url-from-cfg>)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WidgetError(f"<name> fetch failed: {exc}") from exc

        return {
            # Template-context fields the partial expects
        }
```

If the widget needs secrets, use this skeleton instead:

```python
from typing import Any

from app.secrets import MissingSecret, SecretsStore
from app.widgets.base import WidgetError


class <ClassName>Widget:
    type = "<name>"
    template = "widgets/<name>.html"
    config_schema = {
        "type": "object",
        "required": [...],
        "properties": {
            "token": {"type": "string", "title": "API token", "default": "$<name>_token"},
            # other fields
        },
    }

    def __init__(self, secrets: SecretsStore | None = None) -> None:
        self.secrets = secrets

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            token = self.secrets.resolve(cfg["token"]) if self.secrets else cfg["token"]
        except MissingSecret as exc:
            raise WidgetError(f"missing secret: {exc}") from exc
        # ... HTTP call using token
```

### Template: `app/templates/widgets/<name>.html`

```html
<div class="widget widget-<name>">
  <!-- Use only static HTML. No script tags. Reference fields from
       the dict returned by fetch(). -->
</div>
```

### Test: `tests/widgets/test_<name>.py`

```python
import pytest
import respx
from httpx import Response

from app.widgets.<name> import <ClassName>Widget
from app.widgets.base import WidgetError


@pytest.mark.asyncio
async def test_<name>_fetch_returns_context() -> None:
    fake_response = {...}  # mirror the API
    with respx.mock(base_url="<api-base>") as mock:
        mock.get("<path>").mock(return_value=Response(200, json=fake_response))
        widget = <ClassName>Widget()
        ctx = await widget.fetch({...minimal valid cfg...})
    # Assert specific fields
    assert ctx[...] == ...


@pytest.mark.asyncio
async def test_<name>_fetch_raises_on_http_error() -> None:
    with respx.mock(base_url="<api-base>") as mock:
        mock.get("<path>").mock(return_value=Response(500))
        widget = <ClassName>Widget()
        with pytest.raises(WidgetError):
            await widget.fetch({...minimal valid cfg...})


def test_<name>_metadata() -> None:
    widget = <ClassName>Widget()
    assert widget.type == "<name>"
    assert widget.template == "widgets/<name>.html"
```

### Registration in `app/widgets/__init__.py`

Add an import and entry to `REGISTRY`. If the widget needs secrets, also add its `type` to `_NEEDS_SECRETS`. Read the current file before editing — match the existing pattern exactly.

### CSS in `app/templates/dashboard.html`

Add styles under the `.widget-<name>` selector inside the `<style>` block of `dashboard.html`. Keep rules simple — WeasyPrint supports most modern CSS but not all (no flexbox `gap` quirks; modern grid works fine).

## Workflow

1. Confirm requirements with the user (snake-case name + display label + fields + data source + auth).
2. Read `app/widgets/clock.py` and `app/widgets/weather.py` first as reference. If the new widget needs secrets, also read `app/widgets/grafana.py`.
3. Create the widget module file.
4. Create the Jinja partial.
5. Create the test file.
6. Update `app/widgets/__init__.py` with the new entry (and `_NEEDS_SECRETS` if applicable).
7. Add CSS rules under `.widget-<name>` to `app/templates/dashboard.html`.
8. Run `.venv/bin/pytest tests/widgets/test_<name>.py -v`. All tests must pass.
9. Run the full suite: `.venv/bin/pytest -v`. Confirm nothing else broke.
10. Commit with message `feat: <name> widget`.

## When NOT to use this skill

- If the user wants to *modify* an existing widget. Edit the file directly.
- If the user wants to add a non-widget feature (e.g. a new route, a new auth mechanism). This skill only generates widget scaffolding.
- If the widget the user wants would require running JavaScript at render time. WeasyPrint can't run JS. Push back and offer an alternative (e.g. server-side data fetch + static HTML).
````

- [ ] **Step 2: Verify the skill file exists**

```bash
ls -la .claude/skills/create-widget/SKILL.md
cat .claude/skills/create-widget/SKILL.md | head -5
```

Expected: file exists, starts with `---\nname: create-widget`.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: claude skill for generating new widgets"
```

---

## Verification (end-to-end smoke test)

After all tasks complete, run this manually:

- [ ] **Full test suite passes**

```bash
.venv/bin/pytest -v
```

- [ ] **Server starts and serves**

```bash
.venv/bin/uvicorn app.main:app --port 8080 &
SERVER_PID=$!
sleep 2
curl -sf http://localhost:8080/health
```

Expected: `{"status":"ok"}`.

- [ ] **Editor renders**

Open `http://localhost:8080/editor` in a browser. The page should load, show the example dashboard in the dropdown, and the Gridstack canvas should be visible. Create a new dashboard called `smoke`, add a clock widget, drag it to fill the top half, save.

- [ ] **Preview matches**

Open `http://localhost:8080/preview/smoke` — should show the same layout in HTML.

- [ ] **PNG endpoint produces a valid grayscale PNG**

```bash
curl -sf -o /tmp/smoke.png http://localhost:8080/dash/smoke.png
file /tmp/smoke.png
```

Expected: `PNG image data, 758 x 1024, 1-bit grayscale` (or 8-bit gray if dither is `none`).

- [ ] **Kindle integration**

Configure kindle-dash on the device to poll `http://<pi-ip>:8080/dash/smoke.png`. Confirm the image displays on the Kindle.

- [ ] **Cleanup**

```bash
kill $SERVER_PID
```

- [ ] **Test the create-widget skill**

In a fresh Claude session, say: "Add a stocks widget that shows AAPL price". The skill should activate and produce a working widget end-to-end.

---

## Notes on extending

- **Time-of-day routing** is Kindle-side: configure the kindle-dash cron to hit `http://pi:8080/dash/morning.png` before 10:00 and `http://pi:8080/dash/evening.png` after. No server change needed.
- **More Kindles:** make a new dashboard per device, point each kindle-dash at its own URL.
- **HTTPS / auth:** out of scope for v1. Add via nginx reverse-proxy + basic auth when you expose the Pi outside LAN.
