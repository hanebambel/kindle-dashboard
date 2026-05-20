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
