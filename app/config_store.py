import json
import os
from pathlib import Path
from typing import Any

from app.widgets import REGISTRY


class DashboardNotFound(Exception):
    pass


class InvalidDashboard(Exception):
    pass


REQUIRED_TOP_LEVEL = {"name", "size", "grid", "widgets"}
REQUIRED_WIDGET = {"id", "type", "pos", "config"}


class ConfigStore:
    def __init__(self, dashboards_dir: Path) -> None:
        self.dashboards_dir = Path(dashboards_dir)
        self.dashboards_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        if "/" in name or name.startswith("."):
            raise InvalidDashboard(f"illegal dashboard name: {name!r}")
        return self.dashboards_dir / f"{name}.json"

    def load(self, name: str) -> dict[str, Any]:
        path = self._path(name)
        if not path.exists():
            raise DashboardNotFound(name)
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, name: str, data: dict[str, Any]) -> None:
        self._validate(data)
        path = self._path(name)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def delete(self, name: str) -> None:
        path = self._path(name)
        if not path.exists():
            raise DashboardNotFound(name)
        path.unlink()

    def list(self) -> list[str]:
        return [p.stem for p in self.dashboards_dir.glob("*.json")]

    def _validate(self, data: dict[str, Any]) -> None:
        missing = REQUIRED_TOP_LEVEL - data.keys()
        if missing:
            raise InvalidDashboard(f"missing fields: {sorted(missing)}")
        if not isinstance(data["widgets"], list):
            raise InvalidDashboard("widgets must be a list")
        for w in data["widgets"]:
            w_missing = REQUIRED_WIDGET - w.keys()
            if w_missing:
                raise InvalidDashboard(f"widget missing fields: {sorted(w_missing)}")
            if w["type"] not in REGISTRY:
                raise InvalidDashboard(f"unknown widget type: {w['type']!r}")
