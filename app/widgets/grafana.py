import base64
from typing import Any

import httpx

from app.secrets import MissingSecret, SecretsStore
from app.widgets.base import WidgetError


class GrafanaPanelWidget:
    type = "grafana"
    template = "widgets/grafana.html"
    config_schema = {
        "type": "object",
        "required": ["base_url", "dashboard_uid", "dashboard_slug", "panel_id"],
        "properties": {
            "base_url": {"type": "string", "title": "Grafana base URL",
                         "default": "http://localhost:3000"},
            "dashboard_uid": {"type": "string", "title": "Dashboard UID"},
            "dashboard_slug": {"type": "string", "title": "Dashboard slug"},
            "panel_id": {"type": "integer", "title": "Panel ID"},
            "width": {"type": "integer", "title": "Width (px)", "default": 500},
            "height": {"type": "integer", "title": "Height (px)", "default": 300},
            "token": {"type": "string", "title": "API token (use $name for secrets)",
                      "default": "$grafana_token"},
        },
    }

    def __init__(self, secrets: SecretsStore | None = None) -> None:
        self.secrets = secrets

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            token = self.secrets.resolve(cfg["token"]) if self.secrets else cfg["token"]
        except MissingSecret as exc:
            raise WidgetError(f"missing secret: {exc}") from exc

        path = f"/render/d-solo/{cfg['dashboard_uid']}/{cfg['dashboard_slug']}"
        params = {
            "panelId": cfg["panel_id"],
            "width": cfg.get("width", 500),
            "height": cfg.get("height", 300),
            "tz": "Europe/Berlin",
        }
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with httpx.AsyncClient(base_url=cfg["base_url"], timeout=10.0) as client:
                resp = await client.get(path, params=params, headers=headers)
                resp.raise_for_status()
                png = resp.content
        except httpx.HTTPError as exc:
            raise WidgetError(f"grafana fetch failed: {exc}") from exc

        b64 = base64.b64encode(png).decode("ascii")
        return {
            "src": f"data:image/png;base64,{b64}",
            "width": cfg.get("width", 500),
            "height": cfg.get("height", 300),
        }
