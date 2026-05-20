from app.state import ViewState, ViewStateStore


def test_default_view_is_dashboard():
    store = ViewStateStore()
    assert store.get("d", "kitchen") == ViewState(view="dashboard", widget_id=None)


def test_set_and_get_round_trip():
    store = ViewStateStore()
    store.set("d", "kitchen", ViewState(view="widget", widget_id="w2"))
    assert store.get("d", "kitchen").widget_id == "w2"


def test_devices_are_isolated():
    store = ViewStateStore()
    store.set("d", "a", ViewState(view="widget", widget_id="w1"))
    assert store.get("d", "b") == ViewState(view="dashboard", widget_id=None)


def test_dashboards_are_isolated():
    store = ViewStateStore()
    store.set("d1", "a", ViewState(view="widget", widget_id="w1"))
    assert store.get("d2", "a") == ViewState(view="dashboard", widget_id=None)


def test_view_state_is_frozen_dataclass():
    import dataclasses
    assert dataclasses.is_dataclass(ViewState)
    s = ViewState(view="dashboard", widget_id=None)
    try:
        s.view = "widget"  # type: ignore[misc]
        raise AssertionError("ViewState should be frozen")
    except dataclasses.FrozenInstanceError:
        pass
