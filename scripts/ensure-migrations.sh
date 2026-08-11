#!/usr/bin/env bash
# Ensure Alembic migrations are applied when the DB is behind heads.
# Intended for offline/prod startup (run-prod, systemd ExecStartPre, dev-offline).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/offline/common.sh"

TARGET="${1:-}"
if [[ "$TARGET" != "dev" && "$TARGET" != "prod" ]]; then
  echo "Usage: $0 dev|prod"
  exit 1
fi

ENV_FILE=".env.${TARGET}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ENV_FILE"
set +a

if [[ "$TARGET" == "prod" ]]; then
  export APP_ENV=production
else
  export APP_ENV=development
fi

if [[ ! -d "backend/.venv" ]]; then
  python3 -m venv backend/.venv
fi
offline_pip_install "$ROOT_DIR/backend/.venv" "$ROOT_DIR/backend/requirements.txt"

offline_ensure_migrations "$ROOT_DIR" "$TARGET"
