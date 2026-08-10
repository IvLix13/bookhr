#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/offline/common.sh"

export OFFLINE_MODE=1

bash "$ROOT_DIR/scripts/setup-offline-frontend-dev.sh"
offline_check_node_version 18
offline_check_frontend_toolchain "$ROOT_DIR"

if [[ -f ".env.dev" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.dev"
  set +a
else
  export APP_ENV=development
  export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://bookuchet_dev_user:change-me@localhost:5432/bookuchet_dev}"
fi

if [[ ! -d "backend/.venv" ]]; then
  python3 -m venv backend/.venv
fi
offline_pip_install "$ROOT_DIR/backend/.venv" "$ROOT_DIR/backend/requirements-dev.txt"

mkdir -p backend/uploads backend/static

echo "Starting Bookuchet offline dev environment..."
echo "Flask (local): http://127.0.0.1:3005"
echo "Vite (network): http://0.0.0.0:5173"

(
  cd backend
  export FLASK_APP=wsgi:app
  export FLASK_DEBUG=1
  ../backend/.venv/bin/flask run --host 127.0.0.1 --port 3005
) &
BACKEND_PID=$!

(
  cd frontend
  npm run dev -- --host 0.0.0.0 --port 5173
) &
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
