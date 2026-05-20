# Kindle Client + Touch Backend — Design

## Context

We've already designed and planned the kindledashboard backend (see
`docs/superpowers/specs/2026-05-20-kindle-dashboard-design.md`). It renders
PNGs served from `/dash/<name>.png`, intended for the existing `kindle-dash`
shell script which polls a URL.

We now want to replace `kindle-dash` with a slightly smarter Kindle-side
client that also handles touch. When the user taps a widget, the backend
gets the touch coordinates, figures out which widget was hit, and returns a
zoomed view of that widget (with a small "back" zone to dismiss it). The
Kindle stays dumb: show an image, send touch coordinates, repeat. All view
logic lives in the backend.

The original `kindle-dash` is one-way (poll → display). Touch adds a second
data flow: tap → POST → response image. The backend must also keep
per-device view state so each Kindle remembers which widget it has zoomed.

This is **not** a rewrite of the backend — it's a focused extension plus a
new Kindle-side client living in `kindle_client/` inside the same repo.

## Architecture

```
┌────── Raspberry Pi 4 ──────┐                ┌─ Kindle PW1/PW2 ─┐
│                            │                │                  │
│  FastAPI app               │   poll image   │  kindle_client   │
│  ┌──────────────────┐      │ ◀──────────────│  ┌─ display loop │
│  │ /dash/<n>.png    │      │                │  │   every 60s   │
│  │   ?device=<id>   │      │   POST /tap    │  │   curl + eips │
│  │ /tap/<n>         │ ◀────┼────────────────│  │               │
│  │                  │      │  {device,x,y}  │  ├─ touch loop   │
│  │ view-state dict  │      │  → 200 PNG     │  │   /dev/input/ │
│  │ (in-memory)      │      │                │  │   event*      │
│  └──────────────────┘      │                │  └───────────────┘
└────────────────────────────┘                └──────────────────┘
```

Two new concerns in the FastAPI app:

1. **View state** — a per-(dashboard, device) record of what view that
   device should currently see. In-memory dict. No persistence.
2. **Zone resolution** — convert a raw touch `(x, y)` into either a widget
   id, the back zone, or the background, using the dashboard's existing
   grid layout.

The renderer learns one new mode (zoom), driven by view state.

## Backend Changes

### Routes

`GET /dash/<name>.png?device=<id>`

- Loads the dashboard config.
- Looks up view state for `(name, device)`. Default: `{view: "dashboard"}`.
- If `view == "dashboard"`: render as today.
- If `view == "widget"`: render the zoom frame around that widget's detail
  template.
- Returns PNG with `Cache-Control: no-store`.
- If `device` is omitted: behaves like the old route (always dashboard
  view). Keeps the URL backward-compatible with anyone still using plain
  `kindle-dash`.

`POST /tap/<name>`

Request body:

```json
{ "device": "kitchen", "x": 432, "y": 600 }
```

Behavior:

1. Look up current state for `(name, device)`.
2. Resolve the tap via `zones.resolve(dashboard, state, x, y)` → one of:
   - `("widget", widget_id)` — tap hit a widget zone (dashboard view).
   - `("back", None)` — tap hit the back strip (zoomed view).
   - `("interior", widget_id)` — tap on the widget area in zoomed view.
   - `("background", None)` — tap on empty space (dashboard view).
3. Mutate state per the table in the next section.
4. Render the new view and return `image/png` bytes (one round-trip; the
   Kindle does not need to re-poll after a tap).

### State machine

| Current view | Hit                     | New view             | Effect              |
| ------------ | ----------------------- | -------------------- | ------------------- |
| dashboard    | widget                  | widget(widget_id)    | zoom in             |
| dashboard    | background              | dashboard            | re-render (refresh) |
| widget       | back                    | dashboard            | zoom out            |
| widget       | interior                | widget(widget_id)    | re-render (refresh) |

Errors return a tiny static error PNG (matches the existing convention for
`/dash/<name>.png`) so the Kindle never shows a frozen frame.

### Modules to add

```
app/
├── state.py            # ViewState class + in-memory store
├── zones.py            # (x,y) → ("widget"|"back"|"interior"|"background", id|None)
├── routes/
│   └── tap.py          # POST /tap/<name>
└── templates/
    ├── zoom.html       # zoom frame: widget body + back strip
    └── widgets/
        └── *_detail.html   # optional per-widget detail templates
```

### Modules to modify

- `app/widgets/base.py` — extend `Widget` protocol with two optionals:
  ```python
  detail_template: str | None    # falls back to .template
  async def fetch_detail(self, cfg) -> dict   # falls back to .fetch
  ```
- `app/render.py` — add `render_zoom_png(dashboard, widget_id) -> bytes`.
- `app/routes/render.py` — add `device` query param handling; dispatch to
  `render_zoom_png` when state demands it.
- `app/main.py` — instantiate and inject the view-state store.

### Zone resolution

The dashboard JSON already has `grid.cols`, `grid.rows`, and each widget's
`pos: {x, y, w, h}` in grid units. Convert to pixel rects:

```
cell_w = size.w / grid.cols      # 758 / 12 ≈ 63.17 px
cell_h = size.h / grid.rows      # 1024 / 16 = 64 px
widget_rect = (
    pos.x * cell_w,  pos.y * cell_h,
    (pos.x + pos.w) * cell_w,  (pos.y + pos.h) * cell_h
)
```

In zoomed view, the back zone is the bottom strip:
`(0, size.h - 80, size.w, size.h)` → 80 px back strip.

No JSON schema changes. The same dashboard config works in both views.

### Zoom frame

`app/templates/zoom.html`:

```html
<!DOCTYPE html><html><head>...same @page setup as dashboard.html...
<style>
  .zoom-body { width: 758px; height: 944px; padding: 16px;
               box-sizing: border-box; overflow: hidden; }
  .back-strip { width: 758px; height: 80px; border-top: 2px solid #000;
                display: flex; align-items: center; justify-content: center;
                font-size: 32px; font-weight: 700; }
</style></head>
<body>
  <div class="zoom-body">{% include detail_template %}</div>
  <div class="back-strip">← back</div>
</body></html>
```

Widgets render with the full canvas minus the back strip. A widget with
neither `detail_template` nor `fetch_detail` defined uses its regular
template, just at full size.

## Kindle Client

Lives in `kindle_client/` inside the same repo. Language choice deferred
until we've poked at what's installed on the Kindle (typical PW1/PW2
jailbreak: BusyBox, curl, eips, maybe Python). The **protocol** is fully
specified so the choice is independent of the backend.

### Behavior

1. **Display loop** — every `poll_interval` seconds (default 60):
   ```
   curl -s "$server/dash/$dashboard.png?device=$device_id" -o /tmp/dash.png
   eips -f -g /tmp/dash.png
   ```
2. **Touch loop** — read `/dev/input/event*` (or `/dev/input/by-path/...`),
   detect a touch-up event with `(x, y)`. POST:
   ```
   curl -s -X POST "$server/tap/$dashboard" \
        -H 'Content-Type: application/json' \
        -d "{\"device\":\"$device_id\",\"x\":$x,\"y\":$y}" \
        -o /tmp/dash.png
   eips -f -g /tmp/dash.png
   ```
3. **Config file** at `/mnt/us/kindledashboard.conf`:
   ```
   server_url=http://pi:8080
   dashboard=morning
   device_id=kitchen
   poll_interval=60
   ```

### Layout

```
kindle_client/
├── README.md           # build + install instructions for the Kindle
├── config.example.conf
├── kual_extension/     # KUAL .xml + scripts to start/stop the client
│   ├── menu.json
│   └── bin/
└── src/                # client source — language TBD
```

### Touch coordinate handling

`/dev/input/event*` on Kindle PW1/PW2 reports touch events as
`(ABS_MT_POSITION_X, ABS_MT_POSITION_Y)` in raw device units, which on
these models match screen pixels 1:1 in portrait orientation. No
calibration needed for v1. If a future Kindle model differs, add a
`coord_transform` config knob — out of scope now.

### What the client does NOT do

- No knowledge of widgets or zones. It just forwards raw `(x, y)`.
- No tap visual feedback (no flash, no overlay). The new image arriving
  is the feedback.
- No multi-touch, swipes, or long-press in v1.

## Configuration & Storage

No new on-disk state for v1. View state is in-memory and resets on Pi
reboot — acceptable, since "I rebooted and lost which widget I was looking
at" is a harmless degradation.

Dashboard JSON is unchanged. No schema bump.

## Error Handling

- **Tap before dashboard exists** → 404 (same as `/dash/...`).
- **Tap with no device id** → 400 ("device required").
- **Tap with out-of-bounds coords** → treat as background tap (refresh).
- **Unknown widget id in state** (e.g., dashboard edited while a device
  has it zoomed) → silently reset to dashboard view.
- **Kindle client cannot reach server** → keep showing the last image; log
  to `/tmp/kindledashboard.log` on the device.

## Testing

- **Unit:** `zones.resolve` table-driven test covering all four hit kinds.
- **Unit:** `ViewState` transitions for every (state, hit) pair.
- **Integration:** `POST /tap/<name>` against an in-memory store, asserting
  the returned PNG dimensions and that state mutated.
- **Manual:** Kindle client tested on a real device — automated tests are
  not realistic for `/dev/input/event*` and `eips`.

## Verification

End-to-end smoke test, browser-only (no Kindle needed):

1. Start the backend.
2. Create a dashboard `test` with a clock (top half) and weather (bottom
   half), save it.
3. `curl -o /tmp/a.png "http://pi:8080/dash/test.png?device=mock1"` →
   confirm 758×1024 dashboard PNG.
4. `curl -X POST http://pi:8080/tap/test -H 'Content-Type: application/json' \
   -d '{"device":"mock1","x":380,"y":700}' -o /tmp/b.png` →
   confirm weather widget zoomed with back strip at bottom.
5. Tap the back strip: `... -d '{"device":"mock1","x":380,"y":1000}' ...`
   → confirm we're back on the dashboard.
6. Tap weather with a different device:
   `... -d '{"device":"mock2","x":380,"y":700}' ...` → confirm mock2 is
   zoomed; `curl ".../dash/test.png?device=mock1"` still shows dashboard
   (independent state).
7. Restart the backend. Hit `/dash/test.png?device=mock1` → confirm we're
   back to dashboard view (state was ephemeral, as designed).
8. On real Kindle: install client, configure `device_id=kitchen`, start
   it, confirm display polls and touches round-trip.

## Key Files

**To create:**
- `app/state.py`
- `app/zones.py`
- `app/routes/tap.py`
- `app/templates/zoom.html`
- `tests/test_state.py`
- `tests/test_zones.py`
- `tests/test_routes_tap.py`
- `kindle_client/README.md`
- `kindle_client/config.example.conf`
- `kindle_client/kual_extension/...`
- `kindle_client/src/...` (language TBD)

**To modify:**
- `app/widgets/base.py` — add optional `detail_template` and `fetch_detail`
- `app/render.py` — add `render_zoom_png`
- `app/routes/render.py` — accept `device` query param, dispatch to zoom
- `app/main.py` — inject view-state store
- `docs/superpowers/specs/2026-05-20-kindle-dashboard-design.md` — append a
  short note pointing to this design

## Out of scope (v1)

- Multi-touch, swipes, long-press
- Tap visual feedback on the Kindle (flash/overlay)
- Persisting view state across Pi reboots
- Multiple Kindles editing the same view collaboratively
- Cycling dashboards by tap (deferred — tap background = refresh only)
- Calibration for Kindle models with non-1:1 touch-to-pixel mapping
