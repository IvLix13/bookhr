#!/usr/bin/env bash
# Полное удаление всех сотрудников из БД.
# Справочник грейдов (grade_catalog), пользователи, компании и настройки
# уведомлений не затрагиваются.
#
# Usage:
#   ./scripts/purge-employees.sh dev --yes
#   ./scripts/purge-employees.sh prod --yes
#
# Без --yes скрипт только покажет предупреждение и завершится.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/offline/common.sh"

TARGET="${1:-}"
shift || true

if [[ "$TARGET" != "dev" && "$TARGET" != "prod" ]]; then
  echo "Usage: $0 dev|prod [--yes]"
  exit 1
fi

ENV_FILE=".env.dev"
export APP_ENV=development
if [[ "$TARGET" == "prod" ]]; then
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

cd backend
export FLASK_APP=wsgi:app

if [[ "${1:-}" != "--yes" ]]; then
  echo "ВНИМАНИЕ: будут безвозвратно удалены все сотрудники и связанные данные:"
  echo "  - persons, employments, договоры, грейды сотрудников, паспорта, награды за стаж"
  echo "  - поощрения, события сотрудников, истории импорта employees/rewards"
  echo "Справочник grade_catalog останется без изменений."
  echo
  echo "Для подтверждения добавьте --yes:"
  echo "  $0 $TARGET --yes"
  exit 1
fi

../backend/.venv/bin/flask purge-employees --yes
