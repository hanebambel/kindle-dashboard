from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config_store import ConfigStore
from app.deps import get_config_store
from app.main import app
from app.widgets import REGISTRY
from app.widgets.base import WidgetError


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


def test_widget_config_form_renders_enum_select(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
                        "widgets": [{"id": "w1", "type": "calendar",
                                     "pos": {"x": 0, "y": 0, "w": 6, "h": 4},
                                     "config": {
                                         "username": "user@icloud.com",
                                         "password": "$icloud_app_password",
                                         "calendar_name": "Home",
                                     }}]})

    resp = c.get("/api/dashboards/demo/widgets/w1/config-form")

    assert resp.status_code == 200
    assert 'name="config[date_time_format]"' in resp.text
    assert '<option value="german">German</option>' in resp.text


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


def test_editor_marks_selected_dashboard(client) -> None:
    c, store = client
    base = {"size": {"w": 758, "h": 1024}, "grid": {"cols": 12, "rows": 16}, "dither": "fs", "widgets": []}
    store.save("morning", {"name": "morning", **base})
    store.save("evening", {"name": "evening", **base})
    resp = c.get("/editor?name=evening")
    assert resp.status_code == 200
    # The evening option should be marked selected; morning should not be.
    assert 'value="evening" selected' in resp.text
    assert 'value="morning" selected' not in resp.text


def test_editor_unknown_name_falls_back_to_first(client) -> None:
    c, store = client
    base = {"size": {"w": 758, "h": 1024}, "grid": {"cols": 12, "rows": 16}, "dither": "fs", "widgets": []}
    store.save("a", {"name": "a", **base})
    resp = c.get("/editor?name=nope")
    assert resp.status_code == 200
    # Should still render the editor with the first dashboard selected
    assert 'value="a" selected' in resp.text


def test_widget_preview_renders_html(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
                        "widgets": [{"id": "w1", "type": "clock",
                                     "pos": {"x": 0, "y": 0, "w": 6, "h": 4},
                                     "config": {"format": "HH:mm"}}]})
    resp = c.get("/api/dashboards/demo/widgets/w1/preview")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    # Should contain rendered clock-time element
    assert "clock-time" in resp.text


def test_widget_preview_shows_full_error_message(client, monkeypatch) -> None:
    c, store = client
    message = "missing token\nset grafana_token in config/secrets.json\nthen refresh the preview"

    class BrokenPreviewWidget:
        type = "broken-preview"
        template = "widgets/clock.html"
        config_schema = {}

        async def fetch(self, cfg: dict) -> dict:
            raise WidgetError(message)

    monkeypatch.setitem(REGISTRY, BrokenPreviewWidget.type, BrokenPreviewWidget)
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
                        "widgets": [{"id": "w1", "type": "broken-preview",
                                     "pos": {"x": 0, "y": 0, "w": 6, "h": 4},
                                     "config": {}}]})

    resp = c.get("/api/dashboards/demo/widgets/w1/preview")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert message in resp.text
    assert "white-space: pre-wrap" in resp.text
    assert "overflow-wrap: anywhere" in resp.text


def test_widget_preview_unknown_widget_returns_404(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
                        "widgets": []})
    resp = c.get("/api/dashboards/demo/widgets/nope/preview")
    assert resp.status_code == 404


def test_widget_preview_unknown_dashboard_returns_404(client) -> None:
    c, store = client
    resp = c.get("/api/dashboards/nodash/widgets/w1/preview")
    assert resp.status_code == 404


def test_delete_widget_removes_from_dashboard(client) -> None:
    c, store = client
    store.save("demo", {
        "name": "demo", "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
        "widgets": [
            {"id": "w1", "type": "clock", "pos": {"x": 0, "y": 0, "w": 6, "h": 3}, "config": {}},
            {"id": "w2", "type": "clock", "pos": {"x": 6, "y": 0, "w": 6, "h": 3}, "config": {}},
        ],
    })
    resp = c.delete("/api/dashboards/demo/widgets/w1")
    assert resp.status_code == 200
    remaining = [w["id"] for w in store.load("demo")["widgets"]]
    assert remaining == ["w2"]


def test_delete_widget_unknown_widget_returns_404(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs", "widgets": []})
    resp = c.delete("/api/dashboards/demo/widgets/nope")
    assert resp.status_code == 404


def test_delete_widget_unknown_dashboard_returns_404(client) -> None:
    c, _store = client
    resp = c.delete("/api/dashboards/nodash/widgets/w1")
    assert resp.status_code == 404


def test_patch_theme_sets_preset(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs", "widgets": []})
    resp = c.patch("/api/dashboards/demo/theme", json={"preset": "editorial"})
    assert resp.status_code == 200
    assert store.load("demo")["theme"] == {"preset": "editorial"}


def test_patch_theme_merges_overrides(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
                        "theme": {"preset": "editorial"}, "widgets": []})
    resp = c.patch("/api/dashboards/demo/theme",
                   json={"font_family": "JetBrains Mono", "font_scale": 1.2})
    assert resp.status_code == 200
    theme = store.load("demo")["theme"]
    assert theme["preset"] == "editorial"
    assert theme["font_family"] == "JetBrains Mono"
    assert theme["font_scale"] == 1.2


def test_patch_theme_null_clears_override(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs",
                        "theme": {"preset": "editorial", "font_family": "Lora"},
                        "widgets": []})
    resp = c.patch("/api/dashboards/demo/theme", json={"font_family": None})
    assert resp.status_code == 200
    theme = store.load("demo")["theme"]
    assert "font_family" not in theme
    assert theme["preset"] == "editorial"


def test_patch_theme_rejects_invalid_preset(client) -> None:
    c, store = client
    store.save("demo", {"name": "demo", "size": {"w": 758, "h": 1024},
                        "grid": {"cols": 12, "rows": 16}, "dither": "fs", "widgets": []})
    resp = c.patch("/api/dashboards/demo/theme", json={"preset": "bogus"})
    assert resp.status_code == 400


def test_list_themes_returns_presets_and_options(client) -> None:
    c, _store = client
    resp = c.get("/api/themes")
    assert resp.status_code == 200
    data = resp.json()
    assert {"presets", "fonts", "border_styles", "densities"} <= data.keys()
    assert any(p["name"] == "editorial" for p in data["presets"])
