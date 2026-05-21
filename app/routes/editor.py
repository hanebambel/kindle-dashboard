from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app import theme as theme_mod
from app.config_store import ConfigStore, DashboardNotFound, InvalidDashboard
from app.deps import get_config_store
from app.render import render_widget_html
from app.widgets import REGISTRY, get_widget


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _default_dashboard(name: str) -> dict:
    return {
        "name": name,
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "fs",
        "widgets": [],
    }


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


@router.get("/api/themes")
def list_themes() -> dict:
    return {
        "presets": theme_mod.list_presets(),
        "fonts": theme_mod.list_font_families(),
        "border_styles": theme_mod.list_border_styles(),
        "densities": theme_mod.list_densities(),
    }


@router.post("/api/dashboards")
def create_dashboard(
    name: str = Form(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    try:
        store.save(name, _default_dashboard(name))
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"name": name}


@router.delete("/api/dashboards/{name}")
def delete_dashboard(name: str, store: ConfigStore = Depends(get_config_store)) -> dict:
    try:
        store.delete(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    return {"deleted": name}


@router.get("/api/dashboards/{name}")
def get_dashboard(name: str, store: ConfigStore = Depends(get_config_store)) -> JSONResponse:
    try:
        return JSONResponse(store.load(name))
    except DashboardNotFound:
        raise HTTPException(status_code=404)


@router.put("/api/dashboards/{name}/layout")
def put_layout(
    name: str,
    payload: dict[str, Any] = Body(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    try:
        dash = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    dash["widgets"] = payload["widgets"]
    try:
        store.save(name, dash)
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"saved": True}


@router.get("/api/dashboards/{name}/widgets/{wid}/config-form", response_class=HTMLResponse)
def widget_config_form(
    name: str,
    wid: str,
    request: Request,
    store: ConfigStore = Depends(get_config_store),
) -> HTMLResponse:
    try:
        dash = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    widget_cfg = next((w for w in dash["widgets"] if w["id"] == wid), None)
    if widget_cfg is None:
        raise HTTPException(status_code=404)
    schema = get_widget(widget_cfg["type"]).config_schema
    return templates.TemplateResponse(
        request,
        "_widget_form.html",
        {
            "dashboard": name,
            "widget": widget_cfg,
            "schema": schema,
        },
    )


@router.get("/api/dashboards/{name}/widgets/{wid}/preview", response_class=HTMLResponse)
async def widget_preview(name: str, wid: str,
                         store: ConfigStore = Depends(get_config_store)) -> HTMLResponse:
    try:
        dash = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    widget_cfg = next((w for w in dash["widgets"] if w["id"] == wid), None)
    if widget_cfg is None:
        raise HTTPException(status_code=404)
    html = await render_widget_html(widget_cfg, dashboard=dash)
    return HTMLResponse(content=html)


@router.patch("/api/dashboards/{name}/widgets/{wid}")
def patch_widget(
    name: str,
    wid: str,
    payload: dict[str, Any] = Body(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    try:
        dash = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    for w in dash["widgets"]:
        if w["id"] == wid:
            if "config" in payload:
                w["config"] = payload["config"]
            break
    else:
        raise HTTPException(status_code=404)
    try:
        store.save(name, dash)
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"saved": True}


@router.delete("/api/dashboards/{name}/widgets/{wid}")
def delete_widget(
    name: str,
    wid: str,
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    try:
        dash = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    before = len(dash["widgets"])
    dash["widgets"] = [w for w in dash["widgets"] if w["id"] != wid]
    if len(dash["widgets"]) == before:
        raise HTTPException(status_code=404)
    try:
        store.save(name, dash)
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deleted": wid}


@router.patch("/api/dashboards/{name}/theme")
def patch_theme(
    name: str,
    payload: dict[str, Any] = Body(...),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    try:
        dash = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404)
    # Merge payload into existing theme; allow nulls to clear overrides.
    current = dash.get("theme") or {}
    merged = {**current, **payload}
    # Drop keys explicitly set to None so resolver inherits from preset.
    merged = {k: v for k, v in merged.items() if v is not None}
    dash["theme"] = merged
    try:
        store.save(name, dash)
    except InvalidDashboard as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"saved": True, "theme": merged}
