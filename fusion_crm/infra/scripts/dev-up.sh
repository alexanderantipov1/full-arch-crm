#!/usr/bin/env bash
# dev-up.sh — start and keep alive all local dev services.
#
# Usage:  ./infra/scripts/dev-up.sh          (foreground, Ctrl-C stops all)
#         ./infra/scripts/dev-up.sh --check   (print status of all services)
#
# Services:
#   API     — uvicorn on :8000 (--reload)
#   Web     — next dev on :3000
#   Worker  — arq worker (Redis required on :6380)
#
# Each service auto-restarts after 3s if it exits unexpectedly.
# Logs: /tmp/fusion-{api,web,worker}.log

set -euo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

API_PORT=8000
WEB_PORT=3000
REDIS_PORT=6380
PG_PORT=5434

API_LOG=/tmp/fusion-api.log
WEB_LOG=/tmp/fusion-web.log
WORKER_LOG=/tmp/fusion-worker.log

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

check_port() {
  lsof -i :"$1" -t >/dev/null 2>&1
}

status_dot() {
  if check_port "$1"; then
    printf "${GREEN}●${NC} %-10s running (port %s)\n" "$2" "$1"
  else
    printf "${RED}●${NC} %-10s stopped (port %s)\n" "$2" "$1"
  fi
}

# --check mode: just print status and exit
if [[ "${1:-}" == "--check" ]]; then
  echo "=== Fusion CRM local services ==="
  status_dot "$PG_PORT"    "Postgres"
  status_dot "$REDIS_PORT" "Redis"
  status_dot "$API_PORT"   "API"
  status_dot "$WEB_PORT"   "Web"
  # Worker has no port; check process name
  if pgrep -f "arq apps.worker" >/dev/null 2>&1; then
    printf "${GREEN}●${NC} %-10s running\n" "Worker"
  else
    printf "${RED}●${NC} %-10s stopped\n" "Worker"
  fi
  exit 0
fi

# Preflight: Postgres and Redis must be running
if ! check_port "$PG_PORT"; then
  echo -e "${RED}Postgres not running on :${PG_PORT}${NC} — start Docker first (make up)"
  exit 1
fi
if ! check_port "$REDIS_PORT"; then
  echo -e "${RED}Redis not running on :${REDIS_PORT}${NC} — start Docker first (make up)"
  exit 1
fi

PIDS=()

cleanup() {
  echo ""
  echo "Stopping all services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

run_service() {
  local name=$1
  local logfile=$2
  shift 2
  while true; do
    echo -e "${GREEN}[dev-up]${NC} Starting ${name}..."
    "$@" >> "$logfile" 2>&1 || true
    echo -e "${YELLOW}[dev-up]${NC} ${name} exited, restarting in 3s..."
    sleep 3
  done
}

# Kill existing instances on our ports to avoid conflicts
for port in $API_PORT $WEB_PORT; do
  pid=$(lsof -i :"$port" -t 2>/dev/null | head -1 || true)
  if [[ -n "$pid" ]]; then
    echo -e "${YELLOW}[dev-up]${NC} Killing existing process on :${port} (PID ${pid})"
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi
done
# Kill existing arq worker
arq_pid=$(pgrep -f "arq apps.worker" 2>/dev/null || true)
if [[ -n "$arq_pid" ]]; then
  echo -e "${YELLOW}[dev-up]${NC} Killing existing arq worker (PID ${arq_pid})"
  kill "$arq_pid" 2>/dev/null || true
  sleep 1
fi

echo "=== Fusion CRM dev-up ==="
echo "  API log:    $API_LOG"
echo "  Web log:    $WEB_LOG"
echo "  Worker log: $WORKER_LOG"
echo "  Ctrl-C to stop all"
echo ""

# Truncate logs
: > "$API_LOG"
: > "$WEB_LOG"
: > "$WORKER_LOG"

# Start API
run_service "API" "$API_LOG" \
  .venv/bin/uvicorn apps.api.main:app --reload --host 127.0.0.1 --port "$API_PORT" \
  --reload-dir apps --reload-dir packages &
PIDS+=($!)

# Start Web
run_service "Web" "$WEB_LOG" \
  npm run --prefix apps/web dev -- -p "$WEB_PORT" &
PIDS+=($!)

# Start Worker
run_service "Worker" "$WORKER_LOG" \
  .venv/bin/arq apps.worker.main.WorkerSettings &
PIDS+=($!)

echo -e "${GREEN}[dev-up]${NC} All services started. Watching..."

# Health check loop — print status every 60s
while true; do
  sleep 60
  echo ""
  echo -e "${GREEN}[dev-up]${NC} Health check $(date +%H:%M:%S):"
  status_dot "$API_PORT"   "API"
  status_dot "$WEB_PORT"   "Web"
  if pgrep -f "arq apps.worker" >/dev/null 2>&1; then
    printf "${GREEN}●${NC} %-10s running\n" "Worker"
  else
    printf "${RED}●${NC} %-10s stopped\n" "Worker"
  fi
done
