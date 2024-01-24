#!/bin/bash
while :
do
  pythonProcesses=$(ps -A | grep python3.9)
  if [ -z "$pythonProcesses" ]; then
    python3.9 src/bot.py &
  fi
done
