"""Convert a raw touch (x, y) into a semantic hit, given the dashboard
config and the device's current view state."""
from typing import Any, Literal

from app.state import ViewState


BACK_STRIP_HEIGHT = 80
HitKind = Literal["widget", "background", "back", "interior"]


def resolve(
    dashboard: dict[str, Any],
    state: ViewState,
    x: int,
    y: int,
) -> tuple[HitKind, str | None]:
    size = dashboard["size"]
    grid = dashboard["grid"]
    cell_w = size["w"] / grid["cols"]
    cell_h = size["h"] / grid["rows"]

    if state.view == "widget":
        if y >= size["h"] - BACK_STRIP_HEIGHT:
            return ("back", None)
        return ("interior", state.widget_id)

    # dashboard view: locate the widget under (x, y)
    for w in dashboard["widgets"]:
        p = w["pos"]
        x0 = p["x"] * cell_w
        y0 = p["y"] * cell_h
        x1 = (p["x"] + p["w"]) * cell_w
        y1 = (p["y"] + p["h"]) * cell_h
        if x0 <= x < x1 and y0 <= y < y1:
            return ("widget", w["id"])
    return ("background", None)
