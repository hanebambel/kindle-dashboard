from typing import Any, Protocol, runtime_checkable


class WidgetError(Exception):
    """Raised by widgets when their fetch fails. Caught by the renderer to
    show a per-cell error box instead of failing the whole dashboard."""


@runtime_checkable
class Widget(Protocol):
    type: str
    template: str
    config_schema: dict[str, Any]

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        """Return a Jinja template context dict. Raise WidgetError on failure."""
        ...
