from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import widgets
from app.config_store import ConfigStore
from app.deps import configure_store
from app.routes import editor as editor_routes
from app.routes import render as render_routes
from app.secrets import SecretsStore


CONFIG_DIR = Path(__file__).parent.parent / "config"
STATIC_DIR = Path(__file__).parent / "static"

configure_store(ConfigStore(dashboards_dir=CONFIG_DIR / "dashboards"))
widgets.configure(SecretsStore(path=CONFIG_DIR / "secrets.json"))

STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="kindledashboard")
app.include_router(render_routes.router)
app.include_router(editor_routes.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
