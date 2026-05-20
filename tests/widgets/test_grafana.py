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
