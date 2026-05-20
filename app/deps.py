from app.config_store import ConfigStore
from app.state import ViewStateStore


_store: ConfigStore | None = None
_view_state: ViewStateStore | None = None


def configure_store(store: ConfigStore) -> None:
    """Called once at app startup from main.py."""
    global _store
    _store = store


def get_config_store() -> ConfigStore:
    """FastAPI dependency. Tests override via app.dependency_overrides."""
    if _store is None:
        raise RuntimeError("config store not configured")
    return _store


def configure_view_state_store(store: ViewStateStore) -> None:
    global _view_state
    _view_state = store


def get_view_state_store() -> ViewStateStore:
    if _view_state is None:
        raise RuntimeError("view state store not configured")
    return _view_state
