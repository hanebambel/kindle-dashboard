# kindledashboard

A small FastAPI server that turns an old Kindle Paperwhite into a wall dashboard.
You arrange widgets in a web editor, and the Kindle polls a URL on your LAN to
display the rendered grayscale PNG.

```
┌────────── Raspberry Pi ──────────┐         ┌──── Kindle ────┐
│  kindledashboard (FastAPI)       │◀── PNG ─│  kindle-dash   │
│  /editor   /dash/<name>.png      │         │  (polls cron)  │
└──────────────────────────────────┘         └────────────────┘
```

Designed to run alongside iobroker + Grafana on a Pi 4 (no headless Chromium).
HTML is rendered to PDF via [WeasyPrint](https://weasyprint.org/), rasterized
with [pypdfium2](https://github.com/pypdfium2-team/pypdfium2), and
post-processed by Pillow (grayscale + Floyd–Steinberg dither).

## Built-in widgets

- **clock** — current time and date
- **weather** — current conditions + forecast via [Open-Meteo](https://open-meteo.com/) (no API key)
- **iobroker** — single state value via [simple-api](https://github.com/ioBroker/ioBroker.simple-api)
- **grafana** — panel image via Grafana's render API (needs a service-account token)
- **calendar** — upcoming events from an iCloud calendar via CalDAV

Adding a new widget is a few small files. See
[`.claude/skills/create-widget/SKILL.md`](.claude/skills/create-widget/SKILL.md)
— if you use Claude Code, just say "add a stocks widget" and the skill will
scaffold it.

## Server setup

### 1. System dependencies

WeasyPrint needs Pango. Install once per host:

- **Raspberry Pi OS / Debian / Ubuntu:**
  ```
  sudo apt install python3-venv libpango-1.0-0 libpangoft2-1.0-0
  ```
- **macOS:**
  ```
  brew install pango
  ```

Python 3.11 or newer is required.

### 2. Clone and install

```
git clone <this-repo> /opt/kindledashboard
cd /opt/kindledashboard
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

(Omit `[dev]` for a slimmer install without test deps.)

### 3. Configure secrets (optional)

Only needed for the Grafana and iCloud calendar widgets.

```
cp config/secrets.json.example config/secrets.json
$EDITOR config/secrets.json
```

Inside a widget config, reference a secret by name: `"token": "$grafana_token"`.

### 4. Run

```
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Then open `http://<host>:8080/editor` to create dashboards.

### 5. Deploy as a service (Raspberry Pi)

A systemd unit is provided in `deploy/kindledashboard.service`. It assumes
the repo lives at `/opt/kindledashboard` and a user named `pi`.

```
sudo cp deploy/kindledashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kindledashboard
sudo journalctl -u kindledashboard -f
```

## Building a dashboard

Open `http://<host>:8080/editor`:

1. Type a name and click **+ New** to create a dashboard.
2. Click a widget type in the right palette to add it to the canvas.
3. Drag and resize on the 12×16 grid (758×1024 px, the Kindle Paperwhite native size).
4. Click a tile to edit that widget's config in the side panel; save.
5. Click **💾 Save** to persist the layout.
6. Click **👁 Preview** to open the rendered HTML in a new tab. The PNG endpoint is at `/dash/<name>.png`.

Dashboards are plain JSON files under `config/dashboards/`. Editing them by
hand is also fine.

## Kindle setup

Two steps: jailbreak the Kindle, then install
[`kindle-dash`](https://github.com/pascalw/kindle-dash) on it.

### Jailbreak

Follow the device-specific guide at <https://kindlemodding.org>. It covers
all current models, the right exploit per firmware version, and how to
install developer tools (SSH, package manager).

### Install kindle-dash

`kindle-dash` is the on-device client: a small script that polls a URL on a
cron schedule, displays the returned PNG, and goes back to sleep. Follow the
install instructions at <https://github.com/pascalw/kindle-dash>.

Point it at your dashboard:

```
http://<pi-ip>:8080/dash/<dashboard-name>.png
```

Multiple dashboards are supported — just create more (`morning`, `evening`,
`livingroom`, …). Time-of-day routing is handled Kindle-side via the
kindle-dash cron schedule (different URLs at different times); the server
itself stays stateless about scheduling.

## Endpoints

| Method | Path                                   | Purpose                       |
|--------|----------------------------------------|-------------------------------|
| GET    | `/health`                              | liveness probe                |
| GET    | `/editor`                              | dashboard editor UI           |
| GET    | `/preview/<name>`                      | render dashboard as HTML      |
| GET    | `/dash/<name>.png`                     | render dashboard as PNG       |
| GET    | `/api/dashboards/<name>`               | dashboard config as JSON      |
| POST   | `/api/dashboards`                      | create empty dashboard        |
| PUT    | `/api/dashboards/<name>/layout`        | persist widget layout         |
| PATCH  | `/api/dashboards/<name>/widgets/<id>`  | update one widget's config    |
| DELETE | `/api/dashboards/<name>`               | delete a dashboard            |

If a render fails, `/dash/<name>.png` still returns a valid PNG (200) showing
the error message and timestamp — the Kindle never sees a 500.

## Development

```
.venv/bin/pytest -v          # full suite
.venv/bin/uvicorn app.main:app --reload --port 8080
```

Tests mock all external HTTP via `respx` and freeze time with `freezegun` —
no real network calls.

## Layout

```
app/
├── main.py             FastAPI app + route registration
├── render.py           HTML → PDF → PNG → grayscale pipeline
├── error_image.py      fallback PNG for render failures
├── config_store.py     atomic JSON dashboard storage
├── secrets.py          $name resolution against secrets.json
├── deps.py             FastAPI dependencies
├── routes/
│   ├── editor.py       /editor + /api/dashboards/...
│   └── render.py       /dash/<name>.png + /preview/<name>
├── widgets/            one module per widget type
├── templates/          Jinja templates (dashboard, editor, widget partials)
└── static/             gridstack.js + editor.js
config/
├── dashboards/         per-dashboard JSON
├── secrets.json        local-only, gitignored
└── secrets.json.example
deploy/
└── kindledashboard.service
docs/superpowers/
├── specs/              design spec
└── plans/              implementation plan
.claude/skills/
└── create-widget/      Claude skill for adding new widgets
```
