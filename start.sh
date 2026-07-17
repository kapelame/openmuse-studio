#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.openmuse/run"
LOG_DIR="$ROOT_DIR/.openmuse/logs"
ENV_FILE="$ROOT_DIR/.env"
export PATH="$HOME/.local/bin:$PATH"
mkdir -p "$RUN_DIR" "$LOG_DIR"

cd "$ROOT_DIR"

API_PORT="${OPENMUSE_API_PORT:-8000}"
WEB_PORT="${OPENMUSE_WEB_PORT:-3000}"
API_URL="http://127.0.0.1:${API_PORT}"
WEB_URL="http://127.0.0.1:${WEB_PORT}"

say() { printf '[openmuse] %s\n' "$*"; }
warn() { printf '[openmuse] warning: %s\n' "$*" >&2; }
die() { printf '[openmuse] error: %s\n' "$*" >&2; exit 1; }

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing '$1'. Install it and run ./start.sh again."
}

is_running() {
  [ -f "$RUN_DIR/$1.pid" ] && kill -0 "$(cat "$RUN_DIR/$1.pid")" 2>/dev/null
}

http_ready() {
  curl -fsS --max-time 2 "$1" >/dev/null 2>&1
}

openmuse_web_ready() {
  curl -fsS --max-time 2 "$WEB_URL/" 2>/dev/null | grep -q "OpenMuse"
}

redis_ready() {
  if command -v redis-cli >/dev/null 2>&1; then
    redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1
  elif command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx 'openmuse-redis'; then
    docker exec openmuse-redis redis-cli ping >/dev/null 2>&1
  else
    return 1
  fi
}

start_process() {
  local name="$1"
  local command="$2"
  if is_running "$name"; then
    say "$name already running (pid $(cat "$RUN_DIR/$name.pid"))"
    return
  fi
  say "starting $name"
  local pid
  pid="$(python3 - "$command" "$LOG_DIR/$name.log" <<'PY'
import subprocess
import sys

command, log_path = sys.argv[1:]
log = open(log_path, "ab", buffering=0)
process = subprocess.Popen(
    ["bash", "-lc", command],
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
print(process.pid)
PY
)"
  echo "$pid" >"$RUN_DIR/$name.pid"
}

wait_for() {
  local label="$1"
  local url="$2"
  local attempts=0
  until http_ready "$url"; do
    attempts=$((attempts + 1))
    [ "$attempts" -lt 40 ] || die "$label did not become ready. See $LOG_DIR/$3.log"
    sleep 0.5
  done
}

require_command curl
require_command ffmpeg
require_command ffprobe
require_command uv
require_command node
require_command npm
require_command python3

if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  say "created .env from .env.example"
fi

if [ ! -d "$ROOT_DIR/.venv" ]; then
  say "installing Python dependencies"
  uv sync
else
  uv sync --quiet
fi

if [ ! -x "$ROOT_DIR/apps/web/node_modules/.bin/next" ]; then
  say "installing web dependencies"
  npm --prefix apps/web install
fi

REDIS_URL="${REDIS_URL:-}"
if [ -z "$REDIS_URL" ] && [ -f "$ENV_FILE" ]; then
  REDIS_URL="$(awk -F= '$1 == "REDIS_URL" {print substr($0, index($0, "=") + 1); exit}' "$ENV_FILE" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
fi
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
export REDIS_URL

REDIS_READY=0
if redis_ready; then
  REDIS_READY=1
  say "using existing Redis at $REDIS_URL"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' | grep -qx 'openmuse-redis'; then
    REDIS_READY=1
    say "using existing Docker Redis"
  else
    say "starting Docker Redis"
    if docker run -d --rm --name openmuse-redis -p 6379:6379 redis:7-alpine >"$RUN_DIR/redis.container" 2>"$LOG_DIR/redis.log"; then
      echo 1 >"$RUN_DIR/redis.started"
      for _ in $(seq 1 20); do
        if redis_ready; then REDIS_READY=1; break; fi
        sleep 0.5
      done
    else
      warn "could not start Docker Redis; API will use local task fallback"
    fi
  fi
else
  warn "Docker is unavailable and redis-cli is missing; API will use local task fallback"
fi

if ! http_ready "$API_URL/api/health"; then
  start_process api "cd '$ROOT_DIR' && REDIS_URL='$REDIS_URL' PYTHONPATH=apps/api:. uv run uvicorn openmuse_api.main:app --app-dir apps/api --host 127.0.0.1 --port '$API_PORT'"
  wait_for api "$API_URL/api/health" api
else
  say "API already ready at $API_URL"
fi

if [ "$REDIS_READY" -eq 1 ]; then
  if ! is_running worker; then
    start_process worker "cd '$ROOT_DIR' && REDIS_URL='$REDIS_URL' PYTHONPATH=apps/api:. uv run python -m openmuse_api.worker"
  fi
else
  warn "worker not started because Redis is unavailable; BackgroundTasks fallback is active"
fi

if ! openmuse_web_ready; then
  start_process web "cd '$ROOT_DIR' && OPENMUSE_API_INTERNAL='$API_URL' NEXT_PUBLIC_API_BASE='' npm --prefix apps/web run dev -- --port '$WEB_PORT'"
  wait_for web "$WEB_URL/" web
else
  say "Web already ready at $WEB_URL"
fi

say "OpenMuse Studio is ready"
say "Web:    $WEB_URL"
say "API:    $API_URL/docs"
say "Logs:   $LOG_DIR"
say "Stop:   ./stop.sh"
