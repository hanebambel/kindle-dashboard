---
name: create-widget
description: Use when the user asks to add a new widget type to the Kindle dashboard. Triggers on phrases like "add a new widget", "create a [name] widget", "I want a widget that shows X", or "/create-widget". Generates the widget module, template, registration, and tests following the project's Widget protocol.
---

# Create Widget

Add a new widget type to the Kindle dashboard. Each widget consists of:

1. A Python module at `app/widgets/<name>.py` implementing the `Widget` protocol
2. A Jinja partial at `app/templates/widgets/<name>.html`
3. A test file at `tests/widgets/test_<name>.py`
4. Registration in `app/widgets/__init__.py`
5. CSS (added to `app/templates/dashboard.html`)

## Gather Requirements

Ask the user, one at a time:

1. **Snake-case name** (e.g. `stocks`, `traffic`, `air_quality`). Must be a valid Python identifier and unique in `app/widgets/`.
2. **Display label** (e.g. "Stock Prices").
3. **Data source** — what API, library, or local resource provides the data? URL or library name.
4. **Auth** — does the data source need credentials? If yes, they belong in `config/secrets.json` and the config schema references them via `$name`.
5. **Config fields the user sets per-instance** — e.g. "ticker symbol, refresh interval". For each field: name, type (`string`/`integer`/`number`/`boolean`), required (yes/no), default.
6. **What the rendered output looks like** — what data fields are in the template context? What's the rough HTML layout?

## Constraints (read these before generating)

- **Async first.** `fetch()` is `async`. Use `httpx.AsyncClient` for HTTP. If the data library is sync-only (like `caldav`), wrap with `asyncio.to_thread(...)`.
- **No JavaScript runs in the rendered widget HTML.** WeasyPrint doesn't execute JS. Inline images via data URIs if needed.
- **Errors → `WidgetError`.** Any failure to fetch data must raise `WidgetError`. The renderer turns this into a per-cell error box.
- **Secrets resolution.** If the widget takes a credential, add `secrets: SecretsStore | None = None` to `__init__`, call `self.secrets.resolve(cfg["password"])`, and update `_NEEDS_SECRETS` in `app/widgets/__init__.py`.
- **No `print()` or logging.info in fetch.** Errors are signaled by exceptions.
- **Tests use respx for HTTP mocking** or `unittest.mock` for non-HTTP. Never make real network calls in tests.
- **No state outside `fetch()`.** Widget instances may be reused; don't store fetched data on `self`.
- **CSS scoping.** Add CSS rules under `.widget-<name>` to `app/templates/dashboard.html`. Don't ship a separate stylesheet.

## Templates

### Widget module: `app/widgets/<name>.py`

```python
from typing import Any

import httpx

from app.widgets.base import WidgetError


class <ClassName>Widget:
    type = "<name>"
    template = "widgets/<name>.html"
    config_schema = {
        "type": "object",
        "required": [<required-fields-as-strings>],
        "properties": {
            # Fill from user requirements:
            # "field_name": {"type": "string"|"integer"|"number"|"boolean",
            #                "title": "Human label", "default": ...},
        },
    }

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(<url-from-cfg>)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WidgetError(f"<name> fetch failed: {exc}") from exc

        return {
            # Template-context fields the partial expects
        }
```

If the widget needs secrets, use this skeleton instead:

```python
from typing import Any

from app.secrets import MissingSecret, SecretsStore
from app.widgets.base import WidgetError


class <ClassName>Widget:
    type = "<name>"
    template = "widgets/<name>.html"
    config_schema = {
        "type": "object",
        "required": [...],
        "properties": {
            "token": {"type": "string", "title": "API token", "default": "$<name>_token"},
            # other fields
        },
    }

    def __init__(self, secrets: SecretsStore | None = None) -> None:
        self.secrets = secrets

    async def fetch(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            token = self.secrets.resolve(cfg["token"]) if self.secrets else cfg["token"]
        except MissingSecret as exc:
            raise WidgetError(f"missing secret: {exc}") from exc
        # ... HTTP call using token
```

### Template: `app/templates/widgets/<name>.html`

```html
<div class="widget widget-<name>">
  <!-- Use only static HTML. No script tags. Reference fields from
       the dict returned by fetch(). -->
</div>
```

### Test: `tests/widgets/test_<name>.py`

```python
import pytest
import respx
from httpx import Response

from app.widgets.<name> import <ClassName>Widget
from app.widgets.base import WidgetError


@pytest.mark.asyncio
async def test_<name>_fetch_returns_context() -> None:
    fake_response = {...}  # mirror the API
    with respx.mock(base_url="<api-base>") as mock:
        mock.get("<path>").mock(return_value=Response(200, json=fake_response))
        widget = <ClassName>Widget()
        ctx = await widget.fetch({...minimal valid cfg...})
    # Assert specific fields
    assert ctx[...] == ...


@pytest.mark.asyncio
async def test_<name>_fetch_raises_on_http_error() -> None:
    with respx.mock(base_url="<api-base>") as mock:
        mock.get("<path>").mock(return_value=Response(500))
        widget = <ClassName>Widget()
        with pytest.raises(WidgetError):
            await widget.fetch({...minimal valid cfg...})


def test_<name>_metadata() -> None:
    widget = <ClassName>Widget()
    assert widget.type == "<name>"
    assert widget.template == "widgets/<name>.html"
```

### Registration in `app/widgets/__init__.py`

Add an import and entry to `REGISTRY`. If the widget needs secrets, also add its `type` to `_NEEDS_SECRETS`. Read the current file before editing — match the existing pattern exactly.

### CSS in `app/templates/dashboard.html`

Add styles under the `.widget-<name>` selector inside the `<style>` block of `dashboard.html`. Keep rules simple — WeasyPrint supports most modern CSS but not all (no flexbox `gap` quirks; modern grid works fine).

## Workflow

1. Confirm requirements with the user (snake-case name + display label + fields + data source + auth).
2. Read `app/widgets/clock.py` and `app/widgets/weather.py` first as reference. If the new widget needs secrets, also read `app/widgets/grafana.py`.
3. Create the widget module file.
4. Create the Jinja partial.
5. Create the test file.
6. Update `app/widgets/__init__.py` with the new entry (and `_NEEDS_SECRETS` if applicable).
7. Add CSS rules under `.widget-<name>` to `app/templates/dashboard.html`.
8. Run `.venv/bin/pytest tests/widgets/test_<name>.py -v`. All tests must pass.
9. Run the full suite: `.venv/bin/pytest -v`. Confirm nothing else broke.
10. Commit with message `feat: <name> widget`.

## When NOT to use this skill

- If the user wants to *modify* an existing widget. Edit the file directly.
- If the user wants to add a non-widget feature (e.g. a new route, a new auth mechanism). This skill only generates widget scaffolding.
- If the widget the user wants would require running JavaScript at render time. WeasyPrint can't run JS. Push back and offer an alternative (e.g. server-side data fetch + static HTML).
