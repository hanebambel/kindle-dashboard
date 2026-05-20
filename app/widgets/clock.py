from datetime import datetime
from typing import Any


class ClockWidget:
    type = "clock"
    template = "widgets/clock.html"
    config_schema = {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "title": "Time format",
                "default": "HH:mm",
            },
        },
    }

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now()
        fmt = cfg.get("format", "HH:mm")
        # Translate human format to strftime
        strftime_fmt = (
            fmt.replace("HH", "%H")
            .replace("mm", "%M")
            .replace("ss", "%S")
        )
        return {
            "time": now.strftime(strftime_fmt),
            "date": now.strftime("%Y-%m-%d"),
        }
