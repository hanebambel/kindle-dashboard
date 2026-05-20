"""HTML -> PNG -> grayscale render pipeline.

Note on PNG output:
  WeasyPrint removed ``HTML.write_png`` in v53; v60+ supports only PDF
  output. The plan's literal ``HTML(string=html).write_png(...)`` therefore
  cannot run against the installed WeasyPrint 68.x. As a minimal,
  Playwright-free workaround we render the dashboard to PDF via WeasyPrint
  and rasterize the first page to PNG with pypdfium2 (pure-Python wheel,
  no external system dependencies beyond what WeasyPrint already needs).
"""
import asyncio
import io
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from weasyprint import HTML

from app.widgets import get_widget


TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    enable_async=True,
)


async def _fetch_item(widget_cfg: dict[str, Any]) -> dict[str, Any]:
    try:
        widget = get_widget(widget_cfg["type"])
        ctx = await widget.fetch(widget_cfg.get("config", {}))
        return {
            "pos": widget_cfg["pos"],
            "template": widget.template,
            "ctx": ctx,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "pos": widget_cfg["pos"],
            "template": None,
            "ctx": {},
            "error": str(exc) or type(exc).__name__,
        }


async def render_widget_html(widget_cfg: dict[str, Any]) -> str:
    """Render one widget to standalone HTML (with dashboard styles) for previewing in the editor."""
    item = await _fetch_item(widget_cfg)
    body_html = ""
    if not item["error"]:
        widget_tpl = _env.get_template(item["template"])
        body_html = await widget_tpl.render_async(**item["ctx"])
    template = _env.get_template("widget_preview.html")
    return await template.render_async(
        body=body_html,
        error=item["error"],
        widget_type=widget_cfg["type"],
    )


async def render_dashboard_html(dashboard: dict[str, Any]) -> str:
    items = await asyncio.gather(*[_fetch_item(w) for w in dashboard["widgets"]])
    rendered_items = []
    for item in items:
        if item["error"] is None and item["template"]:
            widget_tpl = _env.get_template(item["template"])
            body_html = await widget_tpl.render_async(**item["ctx"])
        else:
            body_html = ""
        rendered_items.append({
            "pos": item["pos"],
            "error": item["error"],
            "body": body_html,
        })
    template = _env.get_template("dashboard.html")
    return await template.render_async(
        width=dashboard["size"]["w"],
        height=dashboard["size"]["h"],
        cols=dashboard["grid"]["cols"],
        rows=dashboard["grid"]["rows"],
        items=rendered_items,
    )


def _html_to_png_bytes(html: str, width: int, height: int) -> bytes:
    # WeasyPrint 60+ has no write_png; render to PDF then rasterize.
    pdf_bytes = HTML(string=html).write_pdf()
    pdf = pdfium.PdfDocument(pdf_bytes)
    page = pdf[0]
    # WeasyPrint's @page sized in CSS px lays out at 96 CSS px per inch.
    # PDF units are points (1/72 inch). pypdfium2 default render scale is 1.0
    # (= 72 DPI). Scale 96/72 yields exactly the requested CSS pixel size.
    pil = page.render(scale=96 / 72).to_pil().convert("RGBA")
    if pil.size != (width, height):
        pil = pil.resize((width, height), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def _to_grayscale(png_bytes: bytes, dither: str) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    if dither == "fs":
        img = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def render_dashboard_png(dashboard: dict[str, Any]) -> bytes:
    html = await render_dashboard_html(dashboard)
    width = dashboard["size"]["w"]
    height = dashboard["size"]["h"]
    rgba_png = await asyncio.to_thread(_html_to_png_bytes, html, width, height)
    dither = dashboard.get("dither", "fs")
    return await asyncio.to_thread(_to_grayscale, rgba_png, dither)


ZOOM_BACK_STRIP_PX = 80


def _find_widget_cfg(dashboard: dict[str, Any], widget_id: str) -> dict[str, Any]:
    for w in dashboard["widgets"]:
        if w["id"] == widget_id:
            return w
    raise KeyError(f"widget {widget_id!r} not in dashboard {dashboard['name']!r}")


async def _fetch_zoom_body(widget_cfg: dict[str, Any]) -> tuple[str, str | None]:
    """Returns (body_html, error). On error, body_html is ''."""
    try:
        widget = get_widget(widget_cfg["type"])
        fetch_detail = getattr(widget, "fetch_detail", widget.fetch)
        template_name = getattr(widget, "detail_template", None) or widget.template
        ctx = await fetch_detail(widget_cfg.get("config", {}))
        tpl = _env.get_template(template_name)
        body = await tpl.render_async(**ctx)
        return body, None
    except Exception as exc:  # noqa: BLE001
        return "", str(exc) or type(exc).__name__


async def render_zoom_html(dashboard: dict[str, Any], widget_id: str) -> str:
    widget_cfg = _find_widget_cfg(dashboard, widget_id)
    body, error = await _fetch_zoom_body(widget_cfg)
    if error is not None:
        body = f'<div class="widget widget-error">&#9888; {error}</div>'
    width = dashboard["size"]["w"]
    height = dashboard["size"]["h"]
    template = _env.get_template("zoom.html")
    return await template.render_async(
        width=width,
        height=height,
        body_h=height - ZOOM_BACK_STRIP_PX,
        strip_h=ZOOM_BACK_STRIP_PX,
        body=body,
    )


async def render_zoom_png(dashboard: dict[str, Any], widget_id: str) -> bytes:
    html = await render_zoom_html(dashboard, widget_id)
    width = dashboard["size"]["w"]
    height = dashboard["size"]["h"]
    rgba_png = await asyncio.to_thread(_html_to_png_bytes, html, width, height)
    dither = dashboard.get("dither", "fs")
    return await asyncio.to_thread(_to_grayscale, rgba_png, dither)
