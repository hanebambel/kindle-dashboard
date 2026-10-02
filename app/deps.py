import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

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


_security = HTTPBasic(auto_error=False)


def require_editor_auth(creds: HTTPBasicCredentials | None = Depends(_security)) -> None:
    """HTTP Basic guard for the editor + JSON API. Password from KD_EDITOR_PASSWORD;
    unset means open (local dev) — main.py logs a warning at startup."""
    password = os.environ.get("KD_EDITOR_PASSWORD")
    if not password:
        return
    if creds is None or not secrets.compare_digest(creds.password.encode(), password.encode()):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": 'Basic realm="kindledashboard"'})
