#!/usr/bin/env bash
cd "$(dirname "$0")"
./start.sh
printf '\nPress Ctrl-C to close this terminal. Use ./stop.sh to stop services.\n'
while true; do sleep 3600; done
