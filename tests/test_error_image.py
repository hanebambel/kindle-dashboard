import io

from PIL import Image

from app.error_image import error_png


def test_error_png_returns_correct_size_and_mode() -> None:
    png = error_png("boom", width=758, height=1024)
    img = Image.open(io.BytesIO(png))
    assert img.size == (758, 1024)
    assert img.mode in ("L", "1")
