#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env.prod" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.prod"
  set +a
fi

export APP_ENV=production

if [[ ! -d "backend/.venv" ]]; then
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -r backend/requirements.txt
fi

if [[ ! -f "backend/static/index.html" ]]; then
  bash scripts/build.sh production
fi

mkdir -p backend/uploads backend/static
cd backend
export FLASK_APP=wsgi:app
exec ../backend/.venv/bin/gunicorn --bind 127.0.0.1:3005 --workers 2 wsgi:app
