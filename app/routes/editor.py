from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app import theme as theme_mod
from app.config_store import ConfigStore, DashboardNotFound, InvalidDashboard
from app.deps import get_config_store, require_editor_auth
from app.widgets import REGISTRY, get_widget
from app.widgets.base import coerce_config


router = APIRouter(dependencies=[Depends(require_editor_auth)])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _default_dashboard(name: str) -> dict:
    return {
        "name": name,
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }


def _load_or_404(store: ConfigStore, name: str) -> dict[str, Any]:
    try:
        return store.load(name)
    except (DashboardNotFound, InvalidDashboard):
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")


def _widget_or_404(dash: dict[str, Any], wid: str) -> dict[str, Any]:
    for w in dash["widgets"]:
        if w["id"] == wid:
            return w
    raise HTTPException(status_code=404, detail=f"widget {wid!r} not found")


def _save_or_400(store: ConfigStore, name: str, dash: dict[str, Any]) -> None:
    try:
        store.save(name, dash)
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/editor", response_class=HTMLResponse)
def editor_index(
    request: Request,
    name: str | None = Query(default=None),
    store: ConfigStore = Depends(get_config_store),
) -> HTMLResponse:
    dashboards = sorted(store.list())
    selected = name if name in dashboards else (dashboards[0] if dashboards else None)
    return templates.TemplateResponse(
        request,
        "editor.html",
        {
            "dashboards": dashboards,
            "widget_types": sorted(REGISTRY.keys()),
            "selected": selected,
            "theme_presets": theme_mod.list_presets(),
            "theme_fonts": theme_mod.list_font_families(),
            "theme_borders": theme_mod.list_border_styles(),
            "theme_densities": theme_mod.list_densities(),
        },
    )


@router.post("/api/dashboards")
def create_dashboard(
    name: str = Form(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    name = name.strip()
    if name in store.list():
        raise HTTPException(status_code=409, detail=f"dashboard {name!r} already exists")
    _save_or_400(store, name, _default_dashboard(name))
    return {"name": name}


@router.delete("/api/dashboards/{name}")
def delete_dashboard(name: str, store: ConfigStore = Depends(get_config_store)) -> dict:
    try:
        store.delete(name)
    except (DashboardNotFound, InvalidDashboard):
        raise HTTPException(status_code=404)
    return {"deleted": name}


@router.get("/api/dashboards/{name}")
def get_dashboard(name: str, store: ConfigStore = Depends(get_config_store)) -> JSONResponse:
    return JSONResponse(_load_or_404(store, name))


@router.put("/api/dashboards/{name}/layout")
def put_layout(
    name: str,
    payload: dict[str, Any] = Body(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    dash = _load_or_404(store, name)
    if not isinstance(payload.get("widgets"), list):
        raise HTTPException(status_code=400, detail="widgets must be a list")
    dash["widgets"] = payload["widgets"]
    _save_or_400(store, name, dash)
    return {"saved": True}


@router.get("/api/dashboards/{name}/widgets/{wid}/config-form", response_class=HTMLResponse)
def widget_config_form(
    name: str,
    wid: str,
    request: Request,
    store: ConfigStore = Depends(get_config_store),
) -> HTMLResponse:
    widget_cfg = _widget_or_404(_load_or_404(store, name), wid)
    return templates.TemplateResponse(
        request,
        "_widget_form.html",
        {
            "dashboard": name,
            "widget": widget_cfg,
            "schema": get_widget(widget_cfg["type"]).config_schema,
        },
    )


@router.patch("/api/dashboards/{name}/widgets/{wid}")
def patch_widget(
    name: str,
    wid: str,
    payload: dict[str, Any] = Body(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    dash = _load_or_404(store, name)
    w = _widget_or_404(dash, wid)
    if "config" in payload:
        if not isinstance(payload["config"], dict):
            raise HTTPException(status_code=400, detail="config must be an object")
        try:
            w["config"] = coerce_config(get_widget(w["type"]).config_schema, payload["config"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    _save_or_400(store, name, dash)
    return {"saved": True, "config": w["config"]}



@router.patch("/api/dashboards/{name}/theme")
def patch_theme(
    name: str,
    payload: dict[str, Any] = Body(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    dash = _load_or_404(store, name)
    # Merge into the existing theme; null clears an override so the preset applies.
    merged = {k: v for k, v in {**(dash.get("theme") or {}), **payload}.items() if v is not None}
    dash["theme"] = merged
    _save_or_400(store, name, dash)
    return {"saved": True, "theme": merged}
