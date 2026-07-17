#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.openmuse/run"

stop_pid() {
  local name="$1"
  local file="$RUN_DIR/$name.pid"
  if [ -f "$file" ]; then
    local pid
    pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then
      printf '[openmuse] stopping %s (pid %s)\n' "$name" "$pid"
      # start.sh gives each service its own session; terminate the whole session so
      # the shell wrapper cannot leave uvicorn/Next children behind.
      kill -TERM -- "-$pid" 2>/dev/null || true
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.25
      done
    fi
    rm -f "$file"
  fi
}

stop_pid web
stop_pid worker
stop_pid api

if [ -f "$RUN_DIR/redis.started" ] && command -v docker >/dev/null 2>&1; then
  printf '[openmuse] stopping Docker Redis\n'
  docker stop openmuse-redis >/dev/null 2>&1 || true
  rm -f "$RUN_DIR/redis.started" "$RUN_DIR/redis.container"
fi

printf '[openmuse] stopped\n'
