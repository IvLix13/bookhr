#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/offline/common.sh"

export OFFLINE_MODE="${OFFLINE_MODE:-1}"

if ! offline_is_install "$ROOT_DIR"; then
  echo "Warning: .offline-install marker not found."
  echo "This script is intended for offline installations."
fi

offline_require_command node
offline_require_command npm
offline_check_node_version 18
offline_check_frontend_toolchain "$ROOT_DIR"

if [[ ! -d "$ROOT_DIR/vendor/node_modules" ]]; then
  echo "Missing vendor/node_modules."
  echo "Install the offline bundle first or rebuild it on an online machine:"
  echo "  ./scripts/prepare-offline-frontend-dev.sh"
  exit 1
fi

offline_restore_node_modules "$ROOT_DIR"

if [[ -d "$ROOT_DIR/vendor/npm-cache" ]]; then
  offline_verify_npm_cache "$ROOT_DIR"
else
  echo "npm cache not found, using copied node_modules only."
fi

if [[ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]]; then
  echo "Vite is missing from restored node_modules."
  exit 1
fi

echo
echo "Frontend development environment is ready."
echo
echo "Start full offline dev stack:"
echo "  OFFLINE_MODE=1 $ROOT_DIR/scripts/dev-offline.sh"
echo
echo "Frontend only:"
echo "  cd $ROOT_DIR/frontend && npm run dev -- --host 0.0.0.0 --port 5173"
echo
echo "Rebuild production static files offline:"
echo "  cd $ROOT_DIR/frontend && npm run build"
echo "  rsync -a dist/ ../backend/static/"
