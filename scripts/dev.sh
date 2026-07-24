#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

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
  backend/.venv/bin/pip install -r backend/requirements-dev.txt
fi

if [[ ! -d "frontend/node_modules" ]]; then
  (cd frontend && npm ci)
fi

mkdir -p backend/uploads backend/static

echo "Starting Bookuchet dev environment..."
echo "Flask: http://127.0.0.1:5000"
echo "Vite:  http://127.0.0.1:5173"

(
  cd backend
  export FLASK_APP=wsgi:app
  export FLASK_DEBUG=1
  ../backend/.venv/bin/flask run --host 127.0.0.1 --port 5000
) &
BACKEND_PID=$!

(
  cd frontend
  npm run dev -- --host 127.0.0.1 --port 5173
) &
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
