import io

import pytest
from freezegun import freeze_time
from PIL import Image

from app.render import render_dashboard_html, render_dashboard_png


CLOCK_DASHBOARD = {
    "name": "test",
    "size": {"w": 758, "h": 1024},
    "grid": {"cols": 12, "rows": 16},
    "dither": "none",
    "widgets": [
        {
            "id": "w1",
            "type": "clock",
            "pos": {"x": 0, "y": 0, "w": 12, "h": 4},
            "config": {"format": "HH:mm"},
        }
    ],
}


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_html_contains_widget_content() -> None:
    html = await render_dashboard_html(CLOCK_DASHBOARD)
    assert "09:00" in html
    assert "2026-05-20" in html
    # Layout should be present
    assert "grid-column" in html or "grid-area" in html


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_png_dimensions_and_mode() -> None:
    png_bytes = await render_dashboard_png(CLOCK_DASHBOARD)
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (758, 1024)
    assert img.mode in ("L", "1")


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_png_dither_modes() -> None:
    no_dither = await render_dashboard_png({**CLOCK_DASHBOARD, "dither": "none"})
    fs_dither = await render_dashboard_png({**CLOCK_DASHBOARD, "dither": "fs"})
    assert Image.open(io.BytesIO(no_dither)).mode == "L"
    assert Image.open(io.BytesIO(fs_dither)).mode == "1"


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_html_emits_default_theme_when_unset() -> None:
    html = await render_dashboard_html(CLOCK_DASHBOARD)
    assert "--font-family" in html
    assert "Inter" in html
    # Default preset uses thin borders (1px solid #000)
    assert "1px solid #000" in html


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_html_uses_preset_theme() -> None:
    dash = {**CLOCK_DASHBOARD, "theme": {"preset": "editorial"}}
    html = await render_dashboard_html(dash)
    assert "Source Serif 4" in html
    # editorial has border_style=none
    assert "--border: none" in html


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_html_applies_theme_override() -> None:
    dash = {**CLOCK_DASHBOARD, "theme": {"preset": "editorial", "font_family": "JetBrains Mono"}}
    html = await render_dashboard_html(dash)
    assert "JetBrains Mono" in html


@pytest.mark.asyncio
@freeze_time("2026-05-20 09:00:00")
async def test_render_html_isolates_widget_errors() -> None:
    dashboard = {
        "name": "broken",
        "size": {"w": 758, "h": 1024},
        "grid": {"cols": 12, "rows": 16},
        "dither": "none",
        "widgets": [
            {
                "id": "w1",
                "type": "nonexistent",
                "pos": {"x": 0, "y": 0, "w": 6, "h": 4},
                "config": {},
            },
            {
                "id": "w2",
                "type": "clock",
                "pos": {"x": 6, "y": 0, "w": 6, "h": 4},
                "config": {"format": "HH:mm"},
            },
        ],
    }
    html = await render_dashboard_html(dashboard)
    # Failing widget renders an error cell instead of the whole render failing
    assert "widget-error" in html
    # Other widgets still rendered
    assert "clock-time" in html
    # Layout still emitted
    assert "grid-column" in html
