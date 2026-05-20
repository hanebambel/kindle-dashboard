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
            for vevent in ev.icalendar_instance.walk("VEVENT"):
                dtstart = vevent.get("DTSTART")
                if dtstart is None:
                    continue
                start = dtstart.dt
                if isinstance(start, datetime):
                    when = start.strftime("%a %d.%m. %H:%M")
                else:
                    when = start.strftime("%a %d.%m.") + " · all day"
                summary = str(vevent.get("SUMMARY", ""))
                parsed.append({"summary": summary, "when": when, "sort": start})
        parsed.sort(key=lambda e: e["sort"].isoformat() if isinstance(e["sort"], datetime) else str(e["sort"]))
        for e in parsed:
            e.pop("sort")
        return {"events": parsed[:max_events]}

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._fetch_sync, cfg)
