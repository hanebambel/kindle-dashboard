from app.config_store import ConfigStore


_store: ConfigStore | None = None


def configure_store(store: ConfigStore) -> None:
    """Called once at app startup from main.py."""
    global _store
    _store = store


def get_config_store() -> ConfigStore:
    """FastAPI dependency. Tests override via app.dependency_overrides."""
    if _store is None:
        raise RuntimeError("config store not configured")
    return _store
