#!/usr/bin/env bash
# +1 день к окончаниям всех договоров выбранной базы. Без --yes только просмотр.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-}"
if [[ "$TARGET" != "dev" && "$TARGET" != "prod" ]]; then
  echo "Usage: bash $0 dev|prod [--dry-run|--yes]"
  [[ "$TARGET" == "--help" || "$TARGET" == "-h" ]] && exit 0
  exit 1
fi
shift
cd "$ROOT_DIR"
ENV_FILE="$ROOT_DIR/.env.$TARGET"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env.$TARGET" >&2
  exit 1
fi
unset DATABASE_URL
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must be set in .env.$TARGET" >&2
  exit 1
fi
if [[ "$TARGET" == "prod" ]]; then export APP_ENV=production; else export APP_ENV=development; fi
PYTHON="$ROOT_DIR/backend/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Missing backend/.venv/bin/python. Use the existing backend environment." >&2
  exit 1
fi
echo "Контур: $TARGET (.env.$TARGET). Даты начала договоров не изменяются."
cd "$ROOT_DIR/backend"
exec "$PYTHON" -m flask --app app:create_app extend-contracts-one-day "$@"
