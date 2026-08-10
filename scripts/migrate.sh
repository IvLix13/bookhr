#!/usr/bin/env bash
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
if [[ "$TARGET" == "dev" ]]; then
  ENV_FILE=".env.dev"
  export APP_ENV=development
elif [[ "$TARGET" == "prod" ]]; then
  ENV_FILE=".env.prod"
  export APP_ENV=production
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ENV_FILE"
set +a

if [[ ! -d "backend/.venv" ]]; then
  python3 -m venv backend/.venv
fi
offline_pip_install "$ROOT_DIR/backend/.venv" "$ROOT_DIR/backend/requirements.txt"

if [[ "$TARGET" == "prod" ]]; then
  BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
  mkdir -p "$BACKUP_DIR"
  TS="$(date +%Y%m%d_%H%M%S)"
  BACKUP_FILE="$BACKUP_DIR/bookuchet_prod_${TS}.sql"
  echo "Creating backup before prod migration: $BACKUP_FILE"
  PG_URL="${DATABASE_URL/postgresql+psycopg/postgresql}"
  pg_dump "$PG_URL" > "$BACKUP_FILE"
fi

(
  cd backend
  export FLASK_APP=wsgi:app
  ../backend/.venv/bin/flask db upgrade
)

if [[ "$TARGET" == "dev" ]]; then
  (
    cd backend
    export FLASK_APP=wsgi:app
    ../backend/.venv/bin/flask seed
  )
fi

echo "Migration completed for $TARGET"
