import pytest
from fastapi.testclient import TestClient

from app.config_store import ConfigStore
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def store(tmp_path):
    dashboards = tmp_path / "dashboards"
    dashboards.mkdir()
    return ConfigStore(dashboards_dir=dashboards)
