import pytest

from app.state import ViewState
from app.zones import resolve


DASH = {
    "name": "d",
    "size": {"w": 758, "h": 1024},
    "grid": {"cols": 12, "rows": 16},
    "widgets": [
        {"id": "top",    "type": "clock",   "pos": {"x": 0, "y": 0, "w": 12, "h": 8},  "config": {}},
        {"id": "bottom", "type": "weather", "pos": {"x": 0, "y": 8, "w": 12, "h": 8},  "config": {}},
    ],
}


@pytest.mark.parametrize("x,y,expected", [
    (379, 100, ("widget", "top")),
    (379, 700, ("widget", "bottom")),
    (379, 511, ("widget", "top")),     # exact boundary belongs to upper
    (379, 512, ("widget", "bottom")),
])
def test_dashboard_view_widget_hits(x, y, expected):
    state = ViewState(view="dashboard", widget_id=None)
    assert resolve(DASH, state, x, y) == expected


def test_dashboard_view_background_when_no_widget_covers_point():
    sparse = {**DASH, "widgets": [
        {"id": "tiny", "type": "clock", "pos": {"x": 0, "y": 0, "w": 1, "h": 1}, "config": {}},
    ]}
    state = ViewState(view="dashboard", widget_id=None)
    assert resolve(sparse, state, 700, 900) == ("background", None)


def test_dashboard_view_out_of_bounds_is_background():
    state = ViewState(view="dashboard", widget_id=None)
    assert resolve(DASH, state, -1, 100) == ("background", None)
    assert resolve(DASH, state, 100, 9999) == ("background", None)


def test_widget_view_back_strip():
    state = ViewState(view="widget", widget_id="top")
    # back strip is bottom 80px: y in [944, 1024)
    assert resolve(DASH, state, 400, 950) == ("back", None)
    assert resolve(DASH, state, 400, 944) == ("back", None)


def test_widget_view_interior_above_back_strip():
    state = ViewState(view="widget", widget_id="top")
    assert resolve(DASH, state, 400, 943) == ("interior", "top")
    assert resolve(DASH, state, 400, 100) == ("interior", "top")
