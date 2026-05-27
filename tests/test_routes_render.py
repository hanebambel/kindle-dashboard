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
    assert img.mode == "L"


def test_dash_png_unknown_dashboard_returns_404(client: TestClient) -> None:
    response = client.get("/dash/nope.png")
    assert response.status_code == 404


@freeze_time("2026-05-20 09:00:00")
def test_preview_returns_html(client: TestClient) -> None:
    response = client.get("/preview/demo")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "09:00" in response.text


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
