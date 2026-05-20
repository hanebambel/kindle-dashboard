import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, Response as FastAPIResponse

from app.config_store import ConfigStore, DashboardNotFound
from app.deps import get_config_store
from app.error_image import error_png
from app.render import render_dashboard_html, render_dashboard_png


log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dash/{name}.png")
async def dash_png(name: str, store: ConfigStore = Depends(get_config_store)) -> Response:
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")
    try:
        png = await render_dashboard_png(dashboard)
    except Exception as exc:  # noqa: BLE001
        log.exception("render failed for %s", name)
        png = error_png(f"{type(exc).__name__}: {exc}")
    return FastAPIResponse(
        content=png,
        media_type="image/png",
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
