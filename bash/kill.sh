#!/bin/bash
kill_process() {
    local pid="$(ps -A | grep $1 | awk '{print $1}')"
    if [ -n "$pid" ]; then
        echo "KILLING PROCESS WITH FOUND PID: $pid"
        kill -9 "$pid"
    fi
}

kill_process "keep-running" 
kill_process "python3.9"