#!/bin/bash
kill_process() {
    local pid=$1
    if [ -n "$pid" ]; then
        echo "Killing process with PID: $pid"
        kill -9 "$pid"
    fi
}
kill_process "$(ps -A | grep keep-running | awk '{print $1}')" 
kill_process "$(ps -A | grep python3.9 | awk '{print $1}')"
