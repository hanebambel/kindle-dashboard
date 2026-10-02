import json
import os
import re
from pathlib import Path
from typing import Any

from app import theme
from app.widgets import REGISTRY


class DashboardNotFound(Exception):
    pass


class InvalidDashboard(Exception):
    pass


REQUIRED_TOP_LEVEL = {"name", "size", "grid", "widgets"}
REQUIRED_WIDGET = {"id", "type", "pos", "config"}
DITHER_MODES = {"fs", "gray16", "none"}
_NAME_RE = re.compile(r"[\w-]{1,64}")


class ConfigStore:
    def __init__(self, dashboards_dir: Path) -> None:
        self.dashboards_dir = Path(dashboards_dir)
        self.dashboards_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        if not _NAME_RE.fullmatch(name):
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
        if data.get("dither", "fs") not in DITHER_MODES:
            raise InvalidDashboard(f"dither must be one of {sorted(DITHER_MODES)}")
        cols, rows = data["grid"]["cols"], data["grid"]["rows"]
        seen: set[str] = set()
        for w in data["widgets"]:
            if not isinstance(w, dict):
                raise InvalidDashboard("widget must be an object")
            w_missing = REQUIRED_WIDGET - w.keys()
            if w_missing:
                raise InvalidDashboard(f"widget missing fields: {sorted(w_missing)}")
            if w["type"] not in REGISTRY:
                raise InvalidDashboard(f"unknown widget type: {w['type']!r}")
            if w["id"] in seen:
                raise InvalidDashboard(f"duplicate widget id: {w['id']!r}")
            seen.add(w["id"])
            if not isinstance(w["config"], dict):
                raise InvalidDashboard(f"widget {w['id']!r}: config must be an object")
            _validate_pos(w["id"], w["pos"], cols, rows)
        if "theme" in data:
            try:
                theme.validate(data["theme"])
            except theme.InvalidTheme as exc:
                raise InvalidDashboard(f"invalid theme: {exc}") from exc


def _validate_pos(wid: str, pos: Any, cols: int, rows: int) -> None:
    if not isinstance(pos, dict) or not all(
        isinstance(pos.get(k), int) and not isinstance(pos.get(k), bool) for k in ("x", "y", "w", "h")
    ):
        raise InvalidDashboard(f"widget {wid!r}: pos needs integer x, y, w, h")
    if pos["x"] < 0 or pos["y"] < 0 or pos["w"] < 1 or pos["h"] < 1 \
            or pos["x"] + pos["w"] > cols or pos["y"] + pos["h"] > rows:
        raise InvalidDashboard(f"widget {wid!r}: pos {pos} outside {cols}x{rows} grid")
