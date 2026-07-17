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
FORCE_SETUP="${OPENMUSE_FORCE_SETUP:-0}"
if [ "${1:-}" = "--setup" ]; then
  FORCE_SETUP=1
fi

say() { printf '[openmuse] %s\n' "$*"; }
warn() { printf '[openmuse] warning: %s\n' "$*" >&2; }
die() { printf '[openmuse] error: %s\n' "$*" >&2; exit 1; }

first_run_setup() {
  local marker="$ROOT_DIR/.openmuse/setup-complete"
  local settings_file="$ROOT_DIR/.openmuse/settings.json"
  local answer=""
  local provider="mock"
  local api_key=""
  local api_base="https://api.minimaxi.com"
  local music_model="music-2.6"
  local cover_model="music-cover"

  if [ "$FORCE_SETUP" != "1" ] && { [ -f "$marker" ] || [ -f "$settings_file" ]; }; then
    return
  fi
  if [ ! -t 0 ] || [ ! -t 1 ]; then
    say "non-interactive install detected; skipping setup prompt"
    say "configure providers later from the OpenMuse UI"
    return
  fi

  printf '\n[openmuse] First-run setup\n'
  printf '[openmuse] This is optional. You can change these values later in Settings / Providers.\n'
  IFS= read -r -p "Use MiniMax as the music provider now? [y/N] " answer || answer=""
  case "$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')" in
    y|yes)
      provider="minimax"
      IFS= read -r -s -p "MiniMax API Key (hidden input): " api_key || api_key=""
      printf '\n'
      IFS= read -r -p "MiniMax API Base [$api_base]: " answer || answer=""
      [ -n "$answer" ] && api_base="$answer"
      IFS= read -r -p "Music model [$music_model]: " answer || answer=""
      [ -n "$answer" ] && music_model="$answer"
      IFS= read -r -p "Cover model [$cover_model]: " answer || answer=""
      [ -n "$answer" ] && cover_model="$answer"
      ;;
    *)
      printf '[openmuse] keeping Mock Provider; no API key was requested.\n'
      ;;
  esac

  OPENMUSE_SETUP_PROVIDER="$provider" \
  OPENMUSE_SETUP_API_KEY="$api_key" \
  OPENMUSE_SETUP_API_BASE="$api_base" \
  OPENMUSE_SETUP_MUSIC_MODEL="$music_model" \
  OPENMUSE_SETUP_COVER_MODEL="$cover_model" \
  python3 - "$settings_file" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
existing = {}
if path.exists():
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        existing = {}
existing.update(
    {
        "default_music_provider": os.environ["OPENMUSE_SETUP_PROVIDER"],
        "minimax_api_key": os.environ["OPENMUSE_SETUP_API_KEY"],
        "minimax_api_base": os.environ["OPENMUSE_SETUP_API_BASE"],
        "minimax_music_model": os.environ["OPENMUSE_SETUP_MUSIC_MODEL"],
        "minimax_cover_model": os.environ["OPENMUSE_SETUP_COVER_MODEL"],
    }
)
temporary = path.with_suffix(".json.tmp")
temporary.write_text(json.dumps(existing, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
os.chmod(temporary, 0o600)
temporary.replace(path)
PY
  touch "$marker"
  chmod 600 "$marker" "$settings_file"
  say "setup saved locally; secrets are not sent to the frontend or database"
}

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

first_run_setup

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
