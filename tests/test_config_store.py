import json
from pathlib import Path

import pytest

from app.config_store import ConfigStore, DashboardNotFound, InvalidDashboard


@pytest.fixture
def store(tmp_path: Path) -> ConfigStore:
    dashboards = tmp_path / "dashboards"
    dashboards.mkdir()
    return ConfigStore(dashboards_dir=dashboards)


def test_load_missing_raises(store: ConfigStore) -> None:
    with pytest.raises(DashboardNotFound):
        store.load("nope")


def test_save_and_load_roundtrip(store: ConfigStore) -> None:
    data = {
        "name": "morning",
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }
    store.save("morning", data)
    assert store.load("morning") == data


def test_save_is_atomic(store: ConfigStore, tmp_path: Path) -> None:
    data = {
        "name": "x",
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }
    store.save("x", data)
    # After save, no .tmp file should be left over
    assert list((tmp_path / "dashboards").glob("*.tmp")) == []


def test_list_returns_names(store: ConfigStore) -> None:
    base = {
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }
    store.save("a", {"name": "a", **base})
    store.save("b", {"name": "b", **base})
    assert sorted(store.list()) == ["a", "b"]


def test_validate_unknown_widget_type(store: ConfigStore) -> None:
    bad = {
        "name": "bad",
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [
            {"id": "w1", "type": "unicorn", "pos": {"x": 0, "y": 0, "w": 1, "h": 1}, "config": {}}
        ],
    }
    with pytest.raises(InvalidDashboard, match="unicorn"):
        store.save("bad", bad)


def test_validate_missing_required_fields(store: ConfigStore) -> None:
    bad = {"name": "bad"}
    with pytest.raises(InvalidDashboard):
        store.save("bad", bad)
