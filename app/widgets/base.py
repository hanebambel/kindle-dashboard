from typing import Any, Protocol


class WidgetError(Exception):
    """Raised by widgets when their fetch fails. Caught by the renderer to
    show a per-cell error box instead of failing the whole dashboard."""


class Widget(Protocol):
    type: str
    template: str
    config_schema: dict[str, Any]
    cache_ttl: int  # seconds the fetched context may be reused; 0 = never cache

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        """Return a Jinja template context dict. Raise WidgetError on failure."""
        ...


_TRUE = {"true", "on", "1", "yes"}


def coerce_config(schema: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce form values (usually strings) to the types the schema declares.

    Empty values are dropped so the widget's default applies. Raises
    ValueError on unparseable values or missing required fields."""
    props = schema.get("properties", {})
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None or value == "":
            continue
        kind = props.get(key, {}).get("type")
        try:
            if kind == "integer" and not isinstance(value, int):
                value = int(str(value).strip())
            elif kind == "number" and not isinstance(value, (int, float)):
                value = float(str(value).strip())
            elif kind == "boolean" and not isinstance(value, bool):
                value = str(value).strip().lower() in _TRUE
            elif kind == "string" and not isinstance(value, str):
                value = str(value)
        except ValueError:
            raise ValueError(f"{props[key].get('title', key)}: expected {kind}, got {value!r}") from None
        out[key] = value
    missing = [k for k in schema.get("required", []) if k not in out]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    return out
