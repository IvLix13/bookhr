#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/offline/common.sh"

if [[ -f ".env.prod" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.prod"
  set +a
fi

export APP_ENV=production

if [[ ! -d "backend/.venv" ]]; then
  python3 -m venv backend/.venv
fi
offline_pip_install "$ROOT_DIR/backend/.venv" "$ROOT_DIR/backend/requirements.txt"

if [[ ! -f "backend/static/index.html" ]]; then
  if offline_is_install "$ROOT_DIR"; then
    echo "Offline install requires prebuilt frontend in backend/static."
    exit 1
  fi
  bash scripts/build.sh production
fi

mkdir -p backend/uploads backend/static
cd backend
export FLASK_APP=wsgi:app
exec ../backend/.venv/bin/gunicorn --bind 127.0.0.1:3005 --workers 2 wsgi:app
