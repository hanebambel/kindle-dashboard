import io

from PIL import Image, ImageDraw, ImageFont


def error_png(message: str, width: int = 758, height: int = 1024) -> bytes:
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 20), "⚠ render error", fill=0, font=font)
    draw.text((20, 60), message[:200], fill=0, font=font)
    from datetime import datetime
    draw.text((20, height - 40), datetime.now().isoformat(timespec="seconds"), fill=0, font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
