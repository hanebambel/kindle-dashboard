"""POST /tap/{name} - touch handler.

Resolves a raw (x, y) to a semantic hit, mutates per-device view state per
the spec's state machine, and returns the freshly-rendered PNG."""
import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel

from app.config_store import ConfigStore, DashboardNotFound
from app.deps import get_config_store, get_view_state_store
from app.error_image import error_png
from app.render import render_dashboard_png, render_zoom_png
from app.state import ViewState, ViewStateStore
from app.zones import resolve


log = logging.getLogger(__name__)
router = APIRouter()


class TapRequest(BaseModel):
    device: str | None = None
    x: int
    y: int


@router.post("/tap/{name}")
async def tap(
    name: str,
    body: TapRequest = Body(...),
    store: ConfigStore = Depends(get_config_store),
    view_store: ViewStateStore = Depends(get_view_state_store),
) -> FastAPIResponse:
    if not body.device:
        raise HTTPException(status_code=400, detail="device required")
    try:
        dashboard = store.load(name)
    except DashboardNotFound:
        raise HTTPException(status_code=404, detail=f"dashboard {name!r} not found")

    state = view_store.get(name, body.device)
    kind, wid = resolve(dashboard, state, body.x, body.y)

    if state.view == "dashboard" and kind == "widget":
        new_state = ViewState(view="widget", widget_id=wid)
    elif state.view == "widget" and kind == "back":
        new_state = ViewState(view="dashboard", widget_id=None)
    elif state.view == "widget" and kind == "interior":
        new_state = state  # refresh same widget
    else:
        new_state = ViewState(view="dashboard", widget_id=None)
    view_store.set(name, body.device, new_state)

    try:
        if new_state.view == "widget":
            png = await render_zoom_png(dashboard, new_state.widget_id)
        else:
            png = await render_dashboard_png(dashboard)
    except Exception as exc:  # noqa: BLE001
        log.exception("tap render failed for %s", name)
        png = error_png(f"{type(exc).__name__}: {exc}")
    return FastAPIResponse(
        content=png, media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
