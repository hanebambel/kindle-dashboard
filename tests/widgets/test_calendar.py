from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from app.widgets.calendar import ICloudCalendarWidget
from app.widgets.base import WidgetError
from app.secrets import SecretsStore


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

    with freeze_time(now), \
         patch("app.widgets.calendar.caldav.DAVClient", return_value=fake_client):
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
