#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/bookuchet}"
ENV_FILE="${ENV_FILE:-/opt/bookuchet/.env.prod}"
TS="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

pg_dump "$DATABASE_URL" > "$BACKUP_DIR/bookuchet_${TS}.sql"
find "$BACKUP_DIR" -type f -name 'bookuchet_*.sql' -mtime +14 -delete
