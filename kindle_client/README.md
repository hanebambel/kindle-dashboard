# Kindle Dashboard Client (kindled)

A single static Go binary for jailbroken Kindle Paperwhite 1/2. Polls the
backend for the dashboard PNG, displays it with `eips`, and forwards touch
events to `POST /tap/<name>`.

## Build

```bash
make build
```

Produces `build/kindled` — a statically-linked ARMv7 binary suitable for PW1/PW2.

## Install on the Kindle

1. Jailbreak your Kindle (https://kindlemodding.org/jailbreaking/).
2. Install KUAL (https://www.mobileread.com/forums/showthread.php?t=203326).
3. Copy this extension to the Kindle:
   ```bash
   # Connect Kindle via USB, then:
   KINDLE=/Volumes/Kindle   # macOS path; Linux: /media/$USER/Kindle
   mkdir -p $KINDLE/extensions/kindledashboard/bin
   cp kual_extension/config.xml $KINDLE/extensions/kindledashboard/
   cp kual_extension/menu.json  $KINDLE/extensions/kindledashboard/
   cp kual_extension/bin/*.sh   $KINDLE/extensions/kindledashboard/bin/
   cp build/kindled             $KINDLE/extensions/kindledashboard/bin/
   cp config.example.conf       $KINDLE/kindledashboard.conf
   ```
4. Edit `/mnt/us/kindledashboard.conf` on the Kindle (the file you just
   copied is at the root of the USB-visible drive). Set `server_url`,
   `dashboard`, `device_id`, `poll_interval`.
5. Eject the Kindle. Open KUAL → "Kindle Dashboard" → "Start dashboard".

## Logs

`/tmp/kindledashboard.log` on the Kindle.

## Auto-start on boot

Drop an upstart job at `/etc/init/kindled.conf` on the Kindle (requires
root via SSH or a hotfix):

```
start on started lab126_gui
stop on stopping lab126_gui
respawn
exec /mnt/us/extensions/kindledashboard/bin/start.sh
```

## What it does NOT do (v1)

- No tap visual feedback (the new image arriving is the feedback).
- No multi-touch, swipes, or long-press.
- Does not stop the native Kindle framework — status bar / notifications
  remain visible. (See `docs/superpowers/specs/2026-05-20-kindle-client-touch-design.md`.)
- No screen-rotation handling. Portrait orientation assumed.

## Troubleshooting

- **Black screen on start:** check `/tmp/kindledashboard.log`. Common
  causes: bad `server_url`, no Wi-Fi, server unreachable.
- **Touch does nothing:** confirm `cat /proc/bus/input/devices | grep -i name`
  shows your touchscreen. If the name doesn't match `cyttsp`, `synaptics`,
  or `_mt`, edit `internal/kindled/touch.go` `FindTouchscreen` matchers
  and rebuild.
- **Ghosting:** `kindled` calls `eips -f` (full refresh) every cycle, so
  this should not occur. If it does, ensure `eips` is `/usr/sbin/eips`.

## Layout

```
kindle_client/
├── go.mod
├── Makefile
├── README.md
├── config.example.conf
├── cmd/kindled/main.go
├── internal/kindled/
│   ├── config.go
│   ├── client.go
│   ├── display.go
│   └── touch.go
└── kual_extension/
    ├── config.xml
    ├── menu.json
    └── bin/{start,stop}.sh
```
