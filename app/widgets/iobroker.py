from typing import Any

import httpx

from app.widgets.base import WidgetError


class IobrokerStateWidget:
    type = "iobroker"
    template = "widgets/iobroker.html"
    config_schema = {
        "type": "object",
        "required": ["base_url", "state_id", "label"],
        "properties": {
            "base_url": {"type": "string", "title": "iobroker base URL",
                         "default": "http://localhost:8087"},
            "state_id": {"type": "string", "title": "State ID"},
            "label": {"type": "string", "title": "Label"},
            "unit": {"type": "string", "title": "Unit (suffix)", "default": ""},
        },
    }

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=cfg["base_url"], timeout=5.0) as client:
                resp = await client.get(f"/get/{cfg['state_id']}")
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WidgetError(f"iobroker fetch failed: {exc}") from exc

        val = data.get("val")
        return {
            "value": str(val),
            "label": cfg["label"],
            "unit": cfg.get("unit", ""),
        }
