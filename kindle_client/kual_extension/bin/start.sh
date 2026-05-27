#!/bin/sh
# Start the kindled daemon. Idempotent: if a pid file exists and the process is
# alive, do nothing.
EXT_DIR="/mnt/us/extensions/kindledashboard"
PID_FILE="/tmp/kindled.pid"
LOG_FILE="$EXT_DIR/kindledashboard.log"
CONF="/mnt/us/kindledashboard.conf"
BIN="$EXT_DIR/bin/kindled"

if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
    eips 1 2 "kindled already running (pid $(cat $PID_FILE))"
    exit 0
fi

if ! touch "$LOG_FILE" 2>/dev/null; then
    LOG_FILE="/tmp/kindledashboard.log"
    touch "$LOG_FILE" 2>/dev/null
fi

echo "=== start $(date) ===" >> "$LOG_FILE"

if [ ! -x "$BIN" ]; then
    echo "launcher: missing executable $BIN" >> "$LOG_FILE"
    eips 1 2 "kindled missing binary"
    exit 1
fi

if [ ! -f "$CONF" ]; then
    echo "launcher: missing config $CONF" >> "$LOG_FILE"
    eips 1 2 "config missing: $CONF"
    exit 1
fi

"$BIN" -config "$CONF" -log "$LOG_FILE" >> "$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"
sleep 1

if kill -0 "$PID" 2>/dev/null; then
    echo "launcher: started pid $PID" >> "$LOG_FILE"
    eips 1 2 "kindled started (pid $PID)"
    exit 0
fi

echo "launcher: process exited immediately" >> "$LOG_FILE"
rm -f "$PID_FILE"
eips 1 2 "kindled failed; see log"
exit 1
