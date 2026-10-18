# kindledashboard

A small FastAPI server that turns an old Kindle Paperwhite into a wall dashboard.
You arrange widgets in a web editor, and the Kindle polls a URL on your LAN to
display the rendered grayscale PNG.

```
┌────────── Raspberry Pi ──────────┐         ┌──── Kindle ────┐
│  kindledashboard (FastAPI)       │◀── PNG ─│  kindled (Go)  │
│  /editor   /dash/<name>.png      │── tap ─▶│  KUAL launcher │
└──────────────────────────────────┘         └────────────────┘
```

Designed to run alongside iobroker + Grafana on a Pi 4 (no headless Chromium).
HTML is rendered to PDF via [WeasyPrint](https://weasyprint.org/), rasterized
with [pypdfium2](https://github.com/pypdfium2-team/pypdfium2), and
post-processed by Pillow into the Kindle's 16 grey levels with Floyd–Steinberg
dithering (per dashboard: `"dither": "gray16"` (default), `"fs"` for pure black/white, or `"none"`).

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

Set `KD_EDITOR_PASSWORD` to protect `/editor` and `/api/*` with HTTP Basic auth
(any username). Without it the editor is open to everyone on your network and
a warning is logged at startup. The Kindle endpoints (`/dash`, `/tap`) stay open.

### 5. Deploy as a service (Raspberry Pi)

A systemd unit is provided in `deploy/kindledashboard.service`. It assumes
the repo lives at `/opt/kindledashboard` and a user named `pi`.

```
echo 'KD_EDITOR_PASSWORD=change-me' | sudo tee /opt/kindledashboard/.env
sudo cp deploy/kindledashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kindledashboard
sudo journalctl -u kindledashboard -f
```

## Building a dashboard

Open `http://<host>:8080/editor`:

1. Click **New** to create a dashboard.
2. Click a widget type under **Add widget**; it lands in the first free spot.
3. Drag and resize on the 12×16 grid (758×1024 px, the Kindle Paperwhite native size).
   With a tile focused, arrow keys move it and <kbd>Del</kbd> removes it.
4. Click a tile to edit its config in the side panel.

Everything saves automatically. The canvas shows the real rendered PNG (the same
image the Kindle gets) behind the grid, and it refreshes after every change.

Dashboards are plain JSON files under `config/dashboards/`. Editing them by
hand is also fine.

## Grafana widget setup

The grafana widget fetches a PNG from Grafana's `/render/d-solo/...` endpoint.
Grafana can't render images by itself. It needs the separate
**Grafana Image Renderer** service, which runs headless Chromium. Since Grafana 12
the renderer is no longer offered as a plugin, so run it as a Docker container
(images exist for amd64 and arm64; on a Pi this needs 64-bit OS, `uname -m` →
`aarch64`).

1. **Start the renderer.** It listens on 8081 inside the container; map it to any
   free host port (8083 here):
   ```
   curl -fsSL https://get.docker.com | sh      # if Docker isn't installed yet
   sudo docker run -d --name grafana-renderer --restart unless-stopped \
     -p 8083:8081 grafana/grafana-image-renderer:latest
   ```

2. **Point Grafana at it.** In `/etc/grafana/grafana.ini`:
   ```ini
   [rendering]
   server_url = http://localhost:8083/render
   callback_url = http://172.17.0.1:3000/
   ```
   `callback_url` is the address the renderer uses to open Grafana. From inside the
   container `localhost` is the container itself, so use the Docker bridge
   address `172.17.0.1` (or the host's LAN IP). Grafana must listen on that
   interface (leave `http_addr` empty). Then restart Grafana:
   `sudo systemctl restart grafana-server`.

3. **Create a token.** In Grafana go to *Administration → Service accounts*,
   create one with the *Viewer* role, add a token, and store it as
   `grafana_token` in `config/secrets.json`.

4. **Test it** on the Grafana host:
   ```
   curl -s -o /tmp/p.png -w '%{http_code} %{time_total}s\n' \
     -H "Authorization: Bearer <token>" \
     "http://localhost:3000/render/d-solo/<uid>/<slug>?panelId=<id>&width=500&height=300"
   ```
   `200` means it works. On a Pi 4 expect ~15s per render; the widget allows
   60s and caches the image for 2 min.

**Widget config.** Take `base_url`, `dashboard_uid` and `dashboard_slug` from
the dashboard URL, e.g.
`http://fuji:3000/d/80f95ab5-ae26-4e2d-afe4-934faaac4dde/heizung` →
`http://fuji:3000`, `80f95ab5-…`, `heizung`. Panel IDs start at 1. You can see
a panel's ID under *Share → Link → Rendered image* (`panelId=` in the URL), or
list all panels with:
```
curl -s -H "Authorization: Bearer <token>" http://<grafana>:3000/api/dashboards/uid/<uid> \
  | python3 -c "import json,sys; [print(p['id'], p['title']) for p in json.load(sys.stdin)['dashboard']['panels']]"
```
The panel renders with the dashboard's default time range.

**Troubleshooting** (`sudo docker logs grafana-renderer`):

| Symptom | Cause |
|---|---|
| "No image renderer available/installed" | `[rendering] server_url` not set, or Grafana not restarted |
| renderer log: `bind: address already in use` | the host port is taken, so pick another `-p <port>:8081` |
| renderer log: `net::ERR_CONNECTION_REFUSED` | `callback_url` points at `localhost`; use `172.17.0.1` |
| widget shows `ReadTimeout` | render took longer than 60s; check the Pi's load and RAM |
| image says "Panel not found" | wrong `panel_id` |

## Kindle setup

Jailbreak the Kindle (<https://kindlemodding.org>), install KUAL, then install
the bundled Go client: see [`kindle_client/README.md`](kindle_client/README.md).
It polls `/dash/<name>.png`, shows it with `eips`, and forwards taps to
`/tap/<name>`. Tapping a widget zooms it full-screen; tap "back" to return.

Multiple dashboards are supported — just create more (`morning`, `evening`,
`livingroom`, …).

## Endpoints

| Method | Path                                          | Purpose                                 |
|--------|-----------------------------------------------|-----------------------------------------|
| GET    | `/health`                                     | liveness probe                          |
| GET    | `/dash/<name>.png?device=<id>`                | render PNG (per-device zoom state)      |
| POST   | `/tap/<name>` `{device,x,y}`                  | handle a touch, return the new PNG      |
| GET    | `/preview/<name>`                             | render dashboard as HTML                |
| GET    | `/editor`                                     | dashboard editor UI 🔒                  |
| POST   | `/api/dashboards` (form `name`)               | create empty dashboard (409 if exists) 🔒 |
| GET    | `/api/dashboards/<name>`                      | dashboard config as JSON 🔒             |
| DELETE | `/api/dashboards/<name>`                      | delete a dashboard 🔒                   |
| PUT    | `/api/dashboards/<name>/layout`               | replace the widget list 🔒              |
| GET    | `/api/dashboards/<name>/widgets/<id>/config-form` | widget settings form (HTML) 🔒      |
| PATCH  | `/api/dashboards/<name>/widgets/<id>`         | update one widget's config 🔒           |
| PATCH  | `/api/dashboards/<name>` `{dither}`          | change shading mode 🔒                  |
| PATCH  | `/api/dashboards/<name>/theme`                | merge theme overrides (`null` clears) 🔒 |

🔒 = requires `KD_EDITOR_PASSWORD` when set.

Widget data is cached per widget config for the widget's `cache_ttl` (clock 0s,
iobroker 30s, grafana 2 min, calendar 5 min, weather 10 min), so the Kindle's
poll doesn't hit every upstream API each minute.

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
├── templates/          Jinja templates (dashboard, zoom, editor, widget partials;
│                       _widgets.css holds the widget styles shared by dashboard + zoom)
└── static/             gridstack.js + editor.js/.css + fonts + icons
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
