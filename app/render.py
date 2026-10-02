"""Dashboard render pipeline: widget fetch -> Jinja HTML -> WeasyPrint PDF ->
pypdfium2 raster -> grayscale PNG. (WeasyPrint 53+ has no PNG output, hence
the PDF hop.)"""
import asyncio
import io
import json
import time
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from weasyprint import HTML

from app import theme as theme_mod
from app.widgets import get_widget
from app.zones import BACK_STRIP_HEIGHT


TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
_FONTS_BASE_URL = (STATIC_DIR / "fonts").resolve().as_uri()
ZOOM_FACTOR = 2.5  # widget font scale in the full-screen zoom view
_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    enable_async=True,
)

# ponytail: unbounded, but keyed by widget config so it holds one entry per
# configured widget; add eviction if configs churn a lot.
_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


def _resolve_theme(dashboard: dict[str, Any]) -> dict[str, Any]:
    return theme_mod.resolve(dashboard.get("theme"), fonts_base=_FONTS_BASE_URL)


async def _fetch_ctx(widget_cfg: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return (template, ctx) for a widget, reusing a fresh cached ctx. Raises on failure."""
    widget = get_widget(widget_cfg["type"])
    cfg = widget_cfg.get("config", {})
    ttl = getattr(widget, "cache_ttl", 0)
    key = (widget_cfg["type"], json.dumps(cfg, sort_keys=True))
    hit = _cache.get(key)
    if ttl and hit and hit[0] > time.monotonic():
        return widget.template, hit[1]
    ctx = await widget.fetch(cfg)
    if ttl:
        _cache[key] = (time.monotonic() + ttl, ctx)
    return widget.template, ctx


async def _render_body(widget_cfg: dict[str, Any]) -> tuple[str, str | None]:
    """Return (body_html, error). Errors are per-widget so one bad widget never
    breaks the whole dashboard."""
    try:
        template, ctx = await _fetch_ctx(widget_cfg)
        return await _env.get_template(template).render_async(**ctx), None
    except Exception as exc:  # noqa: BLE001
        return "", str(exc) or type(exc).__name__


async def render_dashboard_html(dashboard: dict[str, Any]) -> str:
    bodies = await asyncio.gather(*[_render_body(w) for w in dashboard["widgets"]])
    items = [
        {"pos": w["pos"], "body": body, "error": error}
        for w, (body, error) in zip(dashboard["widgets"], bodies)
    ]
    return await _env.get_template("dashboard.html").render_async(
        width=dashboard["size"]["w"],
        height=dashboard["size"]["h"],
        cols=dashboard["grid"]["cols"],
        rows=dashboard["grid"]["rows"],
        items=items,
        theme=_resolve_theme(dashboard),
    )


async def render_zoom_html(dashboard: dict[str, Any], widget_id: str) -> str:
    widget_cfg = next((w for w in dashboard["widgets"] if w["id"] == widget_id), None)
    if widget_cfg is None:
        raise KeyError(f"widget {widget_id!r} not in dashboard {dashboard['name']!r}")
    body, error = await _render_body(widget_cfg)
    height = dashboard["size"]["h"]
    return await _env.get_template("zoom.html").render_async(
        width=dashboard["size"]["w"],
        height=height,
        body_h=height - BACK_STRIP_HEIGHT,
        strip_h=BACK_STRIP_HEIGHT,
        body=body,
        error=error,
        zoom_factor=ZOOM_FACTOR,
        theme=_resolve_theme(dashboard),
    )


def _html_to_gray_png(html: str, width: int, height: int, dither: str) -> bytes:
    pdf = pdfium.PdfDocument(HTML(string=html).write_pdf())
    # WeasyPrint lays out at 96 CSS px/inch; PDF points are 1/72 inch.
    img = pdf[0].render(scale=96 / 72).to_pil().convert("L")
    if img.size != (width, height):
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    if dither == "fs":
        img = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG).convert("L")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def _to_png(dashboard: dict[str, Any], html: str) -> bytes:
    return await asyncio.to_thread(
        _html_to_gray_png, html,
        dashboard["size"]["w"], dashboard["size"]["h"], dashboard.get("dither", "fs"),
    )


async def render_dashboard_png(dashboard: dict[str, Any]) -> bytes:
    return await _to_png(dashboard, await render_dashboard_html(dashboard))


async def render_zoom_png(dashboard: dict[str, Any], widget_id: str) -> bytes:
    return await _to_png(dashboard, await render_zoom_html(dashboard, widget_id))
