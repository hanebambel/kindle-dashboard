import io
import pytest
from freezegun import freeze_time
from PIL import Image

from app.render import render_zoom_html, render_zoom_png


DASH = {
    "name": "d",
    "size": {"w": 758, "h": 1024},
    "grid": {"cols": 12, "rows": 16},
    "dither": "none",
    "widgets": [
        {"id": "w1", "type": "clock", "pos": {"x": 0, "y": 0, "w": 12, "h": 8},
         "config": {"format": "HH:mm"}},
    ],
}


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_zoom_html_includes_widget_body_and_back_strip():
    html = await render_zoom_html(DASH, "w1")
    assert "09:00" in html
    assert "back-strip" in html
    assert "&larr;" in html or "← back" in html


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_zoom_png_matches_dashboard_size():
    png_bytes = await render_zoom_png(DASH, "w1")
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (758, 1024)
    assert img.mode in ("L", "1")


@pytest.mark.asyncio
async def test_render_zoom_html_raises_for_unknown_widget():
    with pytest.raises(KeyError):
        await render_zoom_html(DASH, "does-not-exist")


@pytest.mark.asyncio
async def test_render_zoom_html_escapes_error_text(monkeypatch):
    from app.widgets import REGISTRY

    class Broken:
        type = "broken"
        template = "widgets/clock.html"
        config_schema = {}
        cache_ttl = 0

        async def fetch(self, cfg):
            raise RuntimeError("<script>x</script>")

    monkeypatch.setitem(REGISTRY, "broken", Broken)
    dash = {**DASH, "widgets": [{"id": "w1", "type": "broken", "pos": DASH["widgets"][0]["pos"], "config": {}}]}
    html = await render_zoom_html(dash, "w1")
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.asyncio
async def test_render_zoom_fits_one_page_so_back_strip_is_visible():
    from weasyprint import HTML
    html = await render_zoom_html(DASH, "w1")
    assert len(HTML(string=html).render().pages) == 1
