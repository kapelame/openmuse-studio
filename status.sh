#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.openmuse/run"
API_PORT="${OPENMUSE_API_PORT:-8000}"
WEB_PORT="${OPENMUSE_WEB_PORT:-3000}"

check_http() {
  local label="$1"
  local url="$2"
  if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
    printf '%-8s ready  %s\n' "$label" "$url"
  else
    printf '%-8s down   %s\n' "$label" "$url"
  fi
}

redis_ready() {
  local url="${REDIS_URL:-redis://127.0.0.1:6379/0}"
  if command -v redis-cli >/dev/null 2>&1; then
    redis-cli -u "$url" ping >/dev/null 2>&1
  elif command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx 'openmuse-redis'; then
    docker exec openmuse-redis redis-cli ping >/dev/null 2>&1
  else
    return 1
  fi
}

check_http web "http://127.0.0.1:${WEB_PORT}/"
check_http api "http://127.0.0.1:${API_PORT}/api/health"

if [ -f "$RUN_DIR/worker.pid" ] && kill -0 "$(cat "$RUN_DIR/worker.pid")" 2>/dev/null; then
  printf '%-8s ready  pid %s\n' worker "$(cat "$RUN_DIR/worker.pid")"
else
  printf '%-8s down\n' worker
fi

if redis_ready; then
  printf '%-8s ready  %s\n' redis "${REDIS_URL:-redis://127.0.0.1:6379/0}"
else
  printf '%-8s fallback local BackgroundTasks\n' redis
fi
