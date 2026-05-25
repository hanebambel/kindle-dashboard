import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any

import caldav

from app.secrets import MissingSecret, SecretsStore
from app.widgets.base import WidgetError


ICLOUD_URL = "https://caldav.icloud.com"
DATE_TIME_FORMATS = {"default", "german"}
WEEKDAY_LABELS = {
    "default": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "german": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
}
ALL_DAY_LABELS = {
    "default": "all day",
    "german": "ganztags",
}


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
            "date_time_format": {
                "type": "string",
                "title": "Date/time format",
                "default": "default",
                "enum": ["default", "german"],
                "enum_titles": ["Default", "German"],
            },
        },
    }

    def __init__(self, secrets: SecretsStore | None = None) -> None:
        self.secrets = secrets

    def _normalize_date_time_format(self, cfg: dict[str, Any]) -> str:
        format_name = str(cfg.get("date_time_format", "default")).strip().lower()
        if format_name in DATE_TIME_FORMATS:
            return format_name
        return "default"

    def _format_event_start(self, start: date | datetime, format_name: str) -> dict[str, str]:
        weekday = WEEKDAY_LABELS[format_name][start.weekday()]
        date_label = f"{weekday} {start.day:02d}.{start.month:02d}."

        if isinstance(start, datetime):
            time_value = start.strftime("%H:%M")
            time_label = time_value if format_name == "default" else f"{time_value} Uhr"
        else:
            time_label = ALL_DAY_LABELS[format_name]

        return {
            "date_label": date_label,
            "time_label": time_label,
            "when": f"{date_label} {time_label}",
        }

    def _iter_vevents(self, event: Any) -> list[Any]:
        icalendar_instance = event.icalendar_instance
        vevent_list = getattr(icalendar_instance, "vevent_list", None)
        if vevent_list is not None:
            return list(vevent_list)

        walk = getattr(icalendar_instance, "walk", None)
        if callable(walk):
            return list(walk("VEVENT"))
        return []

    def _extract_dtstart(self, vevent: Any) -> date | datetime | None:
        dtstart_attr = getattr(vevent, "dtstart", None)
        dtstart_value = getattr(dtstart_attr, "value", None)
        if isinstance(dtstart_value, date | datetime):
            return dtstart_value

        dtstart = vevent.get("DTSTART")
        if dtstart is None:
            return None
        start = getattr(dtstart, "dt", dtstart)
        if isinstance(start, date | datetime):
            return start
        return None

    def _extract_summary(self, vevent: Any) -> str:
        summary_attr = getattr(vevent, "summary", None)
        summary_value = getattr(summary_attr, "value", None)
        if summary_value is not None:
            return str(summary_value)

        summary = vevent.get("SUMMARY", "")
        return str(getattr(summary, "value", summary))

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
        date_time_format = self._normalize_date_time_format(cfg)

        try:
            events = calendar.search(start=now, end=end, event=True, expand=True)
        except Exception as exc:  # noqa: BLE001
            raise WidgetError(f"caldav search failed: {exc}") from exc

        parsed = []
        for ev in events:
            for vevent in self._iter_vevents(ev):
                start = self._extract_dtstart(vevent)
                if start is None:
                    continue
                summary = self._extract_summary(vevent)
                parsed.append({
                    "summary": summary,
                    **self._format_event_start(start, date_time_format),
                    "sort": start,
                })
        parsed.sort(key=lambda e: e["sort"].isoformat() if isinstance(e["sort"], datetime) else str(e["sort"]))
        for e in parsed:
            e.pop("sort")
        return {"events": parsed[:max_events]}

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._fetch_sync, cfg)
