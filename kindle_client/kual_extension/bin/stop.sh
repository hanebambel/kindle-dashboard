#!/bin/sh
PID_FILE="/tmp/kindled.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        eips 1 2 "kindled stopped"
    fi
    rm -f "$PID_FILE"
else
    eips 1 2 "kindled not running"
fi
