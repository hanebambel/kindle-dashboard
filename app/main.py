import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import widgets
from app.config_store import ConfigStore
from app.deps import configure_store, configure_view_state_store
from app.routes import editor as editor_routes
from app.routes import render as render_routes
from app.routes import tap as tap_routes
from app.secrets import SecretsStore
from app.state import ViewStateStore


CONFIG_DIR = Path(__file__).parent.parent / "config"
STATIC_DIR = Path(__file__).parent / "static"

configure_store(ConfigStore(dashboards_dir=CONFIG_DIR / "dashboards"))
configure_view_state_store(ViewStateStore())
widgets.configure(SecretsStore(path=CONFIG_DIR / "secrets.json"))

if not os.environ.get("KD_EDITOR_PASSWORD"):
    logging.getLogger(__name__).warning(
        "KD_EDITOR_PASSWORD not set: /editor and /api are open to anyone on the network"
    )

app = FastAPI(title="kindledashboard")
app.include_router(render_routes.router)
app.include_router(editor_routes.router)
app.include_router(tap_routes.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
