import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, Response as FastAPIResponse

from app.config_store import ConfigStore, DashboardNotFound
from app.deps import get_config_store, get_view_state_store
from app.error_image import error_png
from app.render import render_dashboard_html, render_dashboard_png, render_zoom_png
from app.state import ViewState, ViewStateStore


log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dash/{name}.png")
async def dash_png(
    name: str,
    device: str | None = Query(default=None),
    store: ConfigStore = Depends(get_config_store),
    view_store: ViewStateStore = Depends(get_view_state_store),
) -> Response:
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")
    state = view_store.get(name, device) if device else None
    try:
        if state and state.view == "widget":
            widget_ids = {w["id"] for w in dashboard["widgets"]}
            if state.widget_id not in widget_ids:
                # Stale widget id (dashboard edited). Reset and fall through.
                view_store.set(name, device, ViewState(view="dashboard", widget_id=None))
                png = await render_dashboard_png(dashboard)
            else:
                png = await render_zoom_png(dashboard, state.widget_id)
        else:
            png = await render_dashboard_png(dashboard)
    except Exception as exc:  # noqa: BLE001
        log.exception("render failed for %s", name)
        png = error_png(f"{type(exc).__name__}: {exc}")
    return FastAPIResponse(
        content=png, media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/preview/{name}")
async def preview(name: str, store: ConfigStore = Depends(get_config_store)) -> HTMLResponse:
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")
    html = await render_dashboard_html(dashboard)
    return HTMLResponse(content=html)
