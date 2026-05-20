#!/bin/sh
# Start the kindled daemon. Idempotent: if a pid file exists and the process is
# alive, do nothing.
EXT_DIR="/mnt/us/extensions/kindledashboard"
PID_FILE="/tmp/kindled.pid"
LOG_FILE="/tmp/kindledashboard.log"
CONF="/mnt/us/kindledashboard.conf"

if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
    eips 1 2 "kindled already running (pid $(cat $PID_FILE))"
    exit 0
fi

if [ ! -f "$CONF" ]; then
    eips 1 2 "config missing: $CONF"
    exit 1
fi

nohup "$EXT_DIR/bin/kindled" -config "$CONF" -log "$LOG_FILE" >/dev/null 2>&1 &
echo $! > "$PID_FILE"
eips 1 2 "kindled started (pid $!)"
