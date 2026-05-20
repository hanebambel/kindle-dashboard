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
