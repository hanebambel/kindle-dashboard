"""Dashboard theming: presets + per-field overrides resolved into CSS variables.

A dashboard's ``theme`` key is an optional object:

    {
      "preset": "editorial",          # one of PRESETS, or None -> "default"
      "font_family": "JetBrains Mono",# or None to inherit from preset
      "font_scale": 1.1,              # or None
      "border_style": "none",         # or None
      "density": "roomy",             # or None
      "custom_font_url": "https://..."# optional @import URL
    }

``resolve(theme)`` returns a flat dict of CSS variable values consumed by the
dashboard template:

    --font-family, --font-scale, --border, --cell-padding, --divider,
    plus a ``font_face_css`` string (any @font-face / @import declarations)
    and the resolved family/preset metadata.
"""
from __future__ import annotations

from typing import Any


FONT_FAMILIES: dict[str, str] = {
    "Inter": "'Inter', -apple-system, 'Helvetica Neue', Arial, sans-serif",
    "Source Serif 4": "'Source Serif 4', 'Source Serif', Georgia, serif",
    "Lora": "'Lora', Georgia, serif",
    "JetBrains Mono": "'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace",
}


BORDER_STYLES: dict[str, dict[str, str]] = {
    "none":    {"border": "none",                   "divider": "none"},
    "thin":    {"border": "1px solid #000",         "divider": "1px solid #000"},
    "divider": {"border": "none",                   "divider": "1px solid #000"},
    "boxed":   {"border": "2px solid #000",         "divider": "1px solid #000"},
}


DENSITIES: dict[str, str] = {
    "dense":  "2px",
    "normal": "4px",
    "roomy":  "8px",
}


PRESETS: dict[str, dict[str, Any]] = {
    "default": {
        "label": "Default",
        "font_family": "Inter",
        "font_scale": 1.0,
        "border_style": "thin",
        "density": "normal",
    },
    "editorial": {
        "label": "Editorial",
        "font_family": "Source Serif 4",
        "font_scale": 1.1,
        "border_style": "none",
        "density": "roomy",
    },
    "terminal": {
        "label": "Terminal",
        "font_family": "JetBrains Mono",
        "font_scale": 0.95,
        "border_style": "thin",
        "density": "dense",
    },
    "soft": {
        "label": "Soft",
        "font_family": "Inter",
        "font_scale": 1.05,
        "border_style": "divider",
        "density": "roomy",
    },
}


# @font-face for the bundled fonts. Paths are served from /static/fonts/
# WeasyPrint resolves relative URLs against the document's base URL, but the
# rendered HTML is a string with no base. We use absolute file:// URLs at
# render time (injected by render.py); the template only emits this CSS.
FONT_FACE_CSS_TEMPLATE = """
@font-face {{ font-family: 'Inter'; src: url('{fonts_base}/Inter-Regular.woff2') format('woff2'); font-weight: 400; font-style: normal; }}
@font-face {{ font-family: 'Inter'; src: url('{fonts_base}/Inter-SemiBold.woff2') format('woff2'); font-weight: 600 900; font-style: normal; }}
@font-face {{ font-family: 'JetBrains Mono'; src: url('{fonts_base}/JetBrainsMono-Regular.woff2') format('woff2'); font-weight: 400; font-style: normal; }}
@font-face {{ font-family: 'JetBrains Mono'; src: url('{fonts_base}/JetBrainsMono-SemiBold.woff2') format('woff2'); font-weight: 600 900; font-style: normal; }}
@font-face {{ font-family: 'Source Serif 4'; src: url('{fonts_base}/SourceSerif4-Regular.ttf') format('truetype-variations'); font-weight: 100 900; font-style: normal; }}
@font-face {{ font-family: 'Lora'; src: url('{fonts_base}/Lora-Regular.ttf') format('truetype-variations'); font-weight: 100 900; font-style: normal; }}
"""


VALID_AXIS_KEYS = {"preset", "font_family", "font_scale", "border_style", "density", "custom_font_url"}


class InvalidTheme(ValueError):
    pass


def validate(theme: dict[str, Any] | None) -> None:
    """Raises InvalidTheme if the theme object is malformed."""
    if theme is None:
        return
    if not isinstance(theme, dict):
        raise InvalidTheme("theme must be an object")
    unknown = set(theme.keys()) - VALID_AXIS_KEYS
    if unknown:
        raise InvalidTheme(f"unknown theme keys: {sorted(unknown)}")
    preset = theme.get("preset")
    if preset is not None and preset not in PRESETS:
        raise InvalidTheme(f"unknown preset: {preset!r}")
    font_family = theme.get("font_family")
    if font_family is not None and font_family not in FONT_FAMILIES:
        raise InvalidTheme(f"unknown font_family: {font_family!r}")
    border_style = theme.get("border_style")
    if border_style is not None and border_style not in BORDER_STYLES:
        raise InvalidTheme(f"unknown border_style: {border_style!r}")
    density = theme.get("density")
    if density is not None and density not in DENSITIES:
        raise InvalidTheme(f"unknown density: {density!r}")
    font_scale = theme.get("font_scale")
    if font_scale is not None:
        if not isinstance(font_scale, (int, float)) or isinstance(font_scale, bool):
            raise InvalidTheme("font_scale must be a number")
        if not (0.5 <= float(font_scale) <= 2.0):
            raise InvalidTheme("font_scale must be between 0.5 and 2.0")
    custom_font_url = theme.get("custom_font_url")
    if custom_font_url is not None and not isinstance(custom_font_url, str):
        raise InvalidTheme("custom_font_url must be a string")


def resolve(theme: dict[str, Any] | None, fonts_base: str = "/static/fonts") -> dict[str, Any]:
    """Resolve a (possibly partial / None) theme into render-ready values.

    Returns a dict with these keys:
      preset: str          -- resolved preset name
      font_family: str     -- bundled font key, e.g. "Inter"
      font_family_css: str -- CSS font-family value (full fallback stack)
      font_scale: float
      border: str          -- CSS border value, or "none"
      divider: str         -- CSS border value used for internal dividers
      cell_padding: str    -- CSS length, e.g. "4px"
      font_face_css: str   -- @font-face + optional @import declarations
    """
    theme = theme or {}
    preset_name = theme.get("preset") or "default"
    if preset_name not in PRESETS:
        preset_name = "default"
    preset = PRESETS[preset_name]

    font_family = theme.get("font_family") or preset["font_family"]
    font_scale = theme.get("font_scale") if theme.get("font_scale") is not None else preset["font_scale"]
    border_style = theme.get("border_style") or preset["border_style"]
    density = theme.get("density") or preset["density"]

    border_decls = BORDER_STYLES[border_style]
    cell_padding = DENSITIES[density]

    font_face_css = FONT_FACE_CSS_TEMPLATE.format(fonts_base=fonts_base)
    custom_font_url = theme.get("custom_font_url")
    if custom_font_url:
        font_face_css = f"@import url('{custom_font_url}');\n" + font_face_css

    return {
        "preset": preset_name,
        "font_family": font_family,
        "font_family_css": FONT_FAMILIES.get(font_family, font_family),
        "font_scale": float(font_scale),
        "border": border_decls["border"],
        "divider": border_decls["divider"],
        "cell_padding": cell_padding,
        "font_face_css": font_face_css,
    }


def list_presets() -> list[dict[str, Any]]:
    """Return preset metadata for the editor's theme picker."""
    return [
        {"name": name, **{k: v for k, v in p.items()}}
        for name, p in PRESETS.items()
    ]


def list_font_families() -> list[str]:
    return list(FONT_FAMILIES.keys())


def list_border_styles() -> list[str]:
    return list(BORDER_STYLES.keys())


def list_densities() -> list[str]:
    return list(DENSITIES.keys())
