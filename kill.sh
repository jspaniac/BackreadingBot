#!/bin/bash
kill_process() {
    local name=$1
    local pid="$(ps -A | grep $name | awk '{print $1}')"
    if [ -n "$pid" ]; then
        echo "KILLING PROCESS WITH FOUND PID: $pid"
        kill -9 "$pid"
    fi
}

kill_process "keep-running" 
kill_process "python3.9"