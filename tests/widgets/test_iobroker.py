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
