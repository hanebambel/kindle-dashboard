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
