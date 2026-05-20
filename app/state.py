"""In-memory per-(dashboard, device) view state. Resets on process restart."""
from dataclasses import dataclass
from typing import Literal


View = Literal["dashboard", "widget"]


@dataclass(frozen=True)
class ViewState:
    view: View
    widget_id: str | None


DEFAULT = ViewState(view="dashboard", widget_id=None)


class ViewStateStore:
    """Maps (dashboard_name, device_id) -> ViewState. Thread-safety not required:
    the FastAPI event loop serializes route handlers and we don't share state
    across processes."""

    def __init__(self) -> None:
        self._states: dict[tuple[str, str], ViewState] = {}

    def get(self, dashboard: str, device: str) -> ViewState:
        return self._states.get((dashboard, device), DEFAULT)

    def set(self, dashboard: str, device: str, state: ViewState) -> None:
        self._states[(dashboard, device)] = state
