#!/usr/bin/env bash
# Полная замена данных PostgreSQL: bookuchet_dev → bookuchet_prod.
#
# Копирует схему и данные из .env.dev в БД из .env.prod.
# Перед заменой всегда делает бэкап prod в backups/.
#
# Usage:
#   ./scripts/copy-db-dev-to-prod.sh --dry-run
#   ./scripts/copy-db-dev-to-prod.sh --yes
#   ./scripts/copy-db-dev-to-prod.sh --yes --stop-services
#   ./scripts/copy-db-dev-to-prod.sh --yes --with-uploads
#
# Опции:
#   --yes             подтвердить разрушающую операцию над prod
#   --dry-run         только проверить подключения и показать сводку
#   --stop-services   остановить/запустить systemd unit'ы bookuchet*
#   --with-uploads    скопировать UPLOAD_DIR из dev в prod (если пути разные)
#   --keep-dump       не удалять промежуточный dump после успешного restore

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

YES=0
DRY_RUN=0
STOP_SERVICES=0
WITH_UPLOADS=0
KEEP_DUMP=0

usage() {
  cat <<EOF
Usage: $0 [--dry-run] [--yes] [--stop-services] [--with-uploads] [--keep-dump]

Копирует PostgreSQL из .env.dev в .env.prod (полная замена содержимого prod).
Без --yes выполняется только проверка (как --dry-run).
EOF
}

for arg in "$@"; do
  case "$arg" in
    --yes) YES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --stop-services) STOP_SERVICES=1 ;;
    --with-uploads) WITH_UPLOADS=1 ;;
    --keep-dump) KEEP_DUMP=1 ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f .env.dev ]]; then
  echo "Missing .env.dev"
  exit 1
fi
if [[ ! -f .env.prod ]]; then
  echo "Missing .env.prod"
  exit 1
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1"
    exit 1
  fi
}

require_cmd pg_dump
require_cmd psql
require_cmd pg_isready

# Load a single var from env file without polluting the parent shell.
load_env_value() {
  local file="$1"
  local key="$2"
  (
    set -a
    # shellcheck disable=SC1090
    source "$file"
    set +a
    eval "printf '%s' \"\${$key-}\""
  )
}

to_pg_url() {
  local url="$1"
  printf '%s' "${url/postgresql+psycopg:\/\//postgresql:\/\/}"
}

mask_url() {
  sed -E 's#://([^:/]+):([^@/]+)@#://\1:***@#'
}

db_name_from_url() {
  local url="$1"
  local path
  path="$(printf '%s' "$url" | sed -E 's#^[a-zA-Z0-9+.-]+://[^/]+/##; s#[?#].*$##')"
  printf '%s' "$path"
}

SRC_DATABASE_URL_RAW="$(load_env_value .env.dev DATABASE_URL)"
DST_DATABASE_URL_RAW="$(load_env_value .env.prod DATABASE_URL)"
SRC_UPLOAD_DIR="$(load_env_value .env.dev UPLOAD_DIR)"
DST_UPLOAD_DIR="$(load_env_value .env.prod UPLOAD_DIR)"

if [[ -z "$SRC_DATABASE_URL_RAW" || -z "$DST_DATABASE_URL_RAW" ]]; then
  echo "DATABASE_URL must be set in both .env.dev and .env.prod"
  exit 1
fi

SRC_URL="$(to_pg_url "$SRC_DATABASE_URL_RAW")"
DST_URL="$(to_pg_url "$DST_DATABASE_URL_RAW")"
SRC_DB="$(db_name_from_url "$SRC_URL")"
DST_DB="$(db_name_from_url "$DST_URL")"

if [[ -z "$SRC_DB" || -z "$DST_DB" ]]; then
  echo "Cannot parse database name from DATABASE_URL"
  exit 1
fi

if [[ "$SRC_URL" == "$DST_URL" || "$SRC_DB" == "$DST_DB" ]]; then
  echo "Refusing to copy: source and target databases are the same ($SRC_DB)"
  exit 1
fi

# Soft safety: prod target should look like a prod contour.
if [[ "$DST_DB" != *_prod && "$DST_DB" != *prod* ]]; then
  echo "WARNING: target DB name '$DST_DB' does not look like a prod database."
fi
if [[ "$SRC_DB" != *_dev && "$SRC_DB" != *dev* ]]; then
  echo "WARNING: source DB name '$SRC_DB' does not look like a dev database."
fi

echo "=== copy-db-dev-to-prod ==="
echo "Source: $(printf '%s' "$SRC_URL" | mask_url)  (db=$SRC_DB)"
echo "Target: $(printf '%s' "$DST_URL" | mask_url)  (db=$DST_DB)"
echo

echo "Checking connectivity..."
pg_isready -d "$SRC_URL" >/dev/null
pg_isready -d "$DST_URL" >/dev/null
psql "$SRC_URL" -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null
psql "$DST_URL" -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null
echo "OK: both databases are reachable"
echo

count_rows() {
  local url="$1"
  local label="$2"
  local db="$3"
  echo "--- $label ($db) ---"
  # Tables may be missing on a fresh empty DB — do not fail the script.
  psql "$url" -At <<'SQL' 2>/dev/null || true
SELECT 'alembic_version=' || COALESCE((SELECT version_num FROM alembic_version LIMIT 1), '(none)');
SELECT 'companies=' || count(*)::text FROM companies;
SELECT 'users=' || count(*)::text FROM users;
SELECT 'persons=' || count(*)::text FROM persons;
SELECT 'employments=' || count(*)::text FROM employments;
SELECT 'events=' || count(*)::text FROM events;
SELECT 'grade_catalog=' || count(*)::text FROM grade_catalog;
SQL
  echo
}

count_rows "$SRC_URL" "SOURCE" "$SRC_DB"
count_rows "$DST_URL" "TARGET (before)" "$DST_DB"

SRC_ALEMBIC="$(psql "$SRC_URL" -Atc "SELECT version_num FROM alembic_version LIMIT 1" 2>/dev/null || true)"
DST_ALEMBIC="$(psql "$DST_URL" -Atc "SELECT version_num FROM alembic_version LIMIT 1" 2>/dev/null || true)"
if [[ -n "$SRC_ALEMBIC" && -n "$DST_ALEMBIC" && "$SRC_ALEMBIC" != "$DST_ALEMBIC" ]]; then
  echo "WARNING: alembic_version differs (dev=$SRC_ALEMBIC, prod=$DST_ALEMBIC)."
  echo "         Dump includes schema from source; prod will match source after restore."
  echo
fi

if [[ "$DRY_RUN" -eq 1 || "$YES" -eq 0 ]]; then
  echo "Dry-run / no --yes: nothing was changed."
  echo "To replace prod with a full copy of dev, run:"
  echo "  $0 --yes"
  echo "Optional: --stop-services --with-uploads --keep-dump"
  exit 0
fi

BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
PROD_BACKUP="$BACKUP_DIR/bookuchet_prod_pre_copy_${TS}.sql"
DEV_DUMP="$BACKUP_DIR/bookuchet_dev_to_prod_${TS}.sql"

SERVICES=(bookuchet bookuchet-rules.timer bookuchet-notifications.timer)
STOPPED_SERVICES=()

stop_services_if_requested() {
  if [[ "$STOP_SERVICES" -ne 1 ]]; then
    return 0
  fi
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl not found; skipping --stop-services"
    return 0
  fi
  for svc in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
      echo "Stopping $svc"
      sudo systemctl stop "$svc"
      STOPPED_SERVICES+=("$svc")
    fi
  done
}

start_services_if_stopped() {
  if [[ ${#STOPPED_SERVICES[@]} -eq 0 ]]; then
    return 0
  fi
  for svc in "${STOPPED_SERVICES[@]}"; do
    echo "Starting $svc"
    sudo systemctl start "$svc" || true
  done
}

cleanup_on_error() {
  echo "ERROR: copy failed. Prod backup (if created): $PROD_BACKUP"
  start_services_if_stopped
}
trap cleanup_on_error ERR

stop_services_if_requested

echo "Creating prod backup: $PROD_BACKUP"
pg_dump --no-owner --no-acl "$DST_URL" > "$PROD_BACKUP"
echo "Prod backup size: $(wc -c < "$PROD_BACKUP") bytes"

echo "Dumping source (dev): $DEV_DUMP"
# --clean --if-exists: DROP objects on restore, then recreate from source.
pg_dump --clean --if-exists --no-owner --no-acl "$SRC_URL" > "$DEV_DUMP"
echo "Dev dump size: $(wc -c < "$DEV_DUMP") bytes"

echo "Restoring into prod (full replace)..."
psql -v ON_ERROR_STOP=1 "$DST_URL" < "$DEV_DUMP" >/dev/null

echo
count_rows "$DST_URL" "TARGET (after)" "$DST_DB"

AFTER_ALEMBIC="$(psql "$DST_URL" -Atc "SELECT version_num FROM alembic_version LIMIT 1" 2>/dev/null || true)"
if [[ -n "$SRC_ALEMBIC" && "$AFTER_ALEMBIC" != "$SRC_ALEMBIC" ]]; then
  echo "ERROR: alembic_version after restore ($AFTER_ALEMBIC) != source ($SRC_ALEMBIC)"
  exit 1
fi

if [[ "$WITH_UPLOADS" -eq 1 ]]; then
  if [[ -z "$SRC_UPLOAD_DIR" || -z "$DST_UPLOAD_DIR" ]]; then
    echo "WARNING: UPLOAD_DIR missing in env; skipping uploads copy"
  elif [[ "$SRC_UPLOAD_DIR" == "$DST_UPLOAD_DIR" ]]; then
    echo "UPLOAD_DIR is the same for dev and prod ($SRC_UPLOAD_DIR); nothing to copy"
  else
    require_cmd rsync
    mkdir -p "$DST_UPLOAD_DIR"
    echo "Copying uploads: $SRC_UPLOAD_DIR/ → $DST_UPLOAD_DIR/"
    rsync -a --delete "$SRC_UPLOAD_DIR/" "$DST_UPLOAD_DIR/"
  fi
fi

if [[ "$KEEP_DUMP" -eq 0 ]]; then
  rm -f "$DEV_DUMP"
  echo "Removed intermediate dump (prod backup kept): $PROD_BACKUP"
else
  echo "Kept intermediate dump: $DEV_DUMP"
  echo "Prod backup: $PROD_BACKUP"
fi

trap - ERR
start_services_if_stopped

echo
echo "Done. Prod database now matches data from $SRC_DB."
echo "Smoke-check login and calendar after restart if services were not stopped."
