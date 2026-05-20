from app.secrets import SecretsStore
from app.widgets.base import Widget, WidgetError
from app.widgets.calendar import ICloudCalendarWidget
from app.widgets.clock import ClockWidget
from app.widgets.grafana import GrafanaPanelWidget
from app.widgets.iobroker import IobrokerStateWidget
from app.widgets.weather import WeatherWidget

REGISTRY: dict[str, type[Widget]] = {
    ClockWidget.type: ClockWidget,
    WeatherWidget.type: WeatherWidget,
    IobrokerStateWidget.type: IobrokerStateWidget,
    GrafanaPanelWidget.type: GrafanaPanelWidget,
    ICloudCalendarWidget.type: ICloudCalendarWidget,
}

_NEEDS_SECRETS = {GrafanaPanelWidget.type, ICloudCalendarWidget.type}
_secrets: SecretsStore | None = None


def configure(secrets: SecretsStore) -> None:
    global _secrets
    _secrets = secrets


def get_widget(type_name: str) -> Widget:
    cls = REGISTRY.get(type_name)
    if cls is None:
        raise KeyError(f"Unknown widget type: {type_name}")
    if type_name in _NEEDS_SECRETS:
        return cls(secrets=_secrets)
    return cls()


__all__ = ["Widget", "WidgetError", "REGISTRY", "get_widget", "configure"]
