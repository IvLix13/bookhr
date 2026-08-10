#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/offline/common.sh"

BUNDLE_PATH="${1:-}"

if [[ -z "$BUNDLE_PATH" ]]; then
  BUNDLE_PATH="$(ls -1t "$ROOT_DIR/dist/offline/"bookuchet-offline-*-linux-x64.tar.gz 2>/dev/null | head -n1 || true)"
fi

if [[ -z "$BUNDLE_PATH" || ! -f "$BUNDLE_PATH" ]]; then
  echo "Usage: $0 /path/to/bookuchet-offline-<version>-py311-linux-x64.tar.gz"
  exit 1
fi

INSTALL_DIR="${INSTALL_DIR:-$HOME/bookuchet-offline}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Extracting bundle..."
tar -xzf "$BUNDLE_PATH" -C "$TMP_DIR"
BUNDLE_DIR="$(find "$TMP_DIR" -maxdepth 1 -type d -name 'bookuchet-offline-*' | head -n1)"
APP_DIR="$BUNDLE_DIR/app"
VENDOR_SRC="$BUNDLE_DIR/vendor"

if [[ ! -d "$APP_DIR" || ! -d "$VENDOR_SRC/wheels" ]]; then
  echo "Invalid bundle layout."
  exit 1
fi

(
  cd "$BUNDLE_DIR"
  sha256sum -c SHA256SUMS
)

mkdir -p "$INSTALL_DIR"
rsync -a "$APP_DIR/" "$INSTALL_DIR/"
rsync -a "$VENDOR_SRC/" "$INSTALL_DIR/vendor/"

export OFFLINE_MODE=1
date -u +%Y-%m-%dT%H:%M:%SZ > "$INSTALL_DIR/.offline-install"

echo "Creating Python virtualenv and installing wheels offline..."
offline_verify_bundle_wheels "$INSTALL_DIR/vendor/wheels" "$(offline_bundle_python_version "$INSTALL_DIR")"

if [[ "${OFFLINE_VERIFY_ONLY:-}" == "1" ]]; then
  if offline_python_cmd_for_version "$(offline_bundle_python_version "$INSTALL_DIR")" >/dev/null 2>&1; then
    offline_check_python_wheels "$INSTALL_DIR/vendor/wheels" "$INSTALL_DIR"
    PY_VERSION="$(offline_bundle_python_version "$INSTALL_DIR")"
    PYTHON_CMD="$(offline_python_cmd_for_version "$PY_VERSION")"
    "$PYTHON_CMD" -m venv "$INSTALL_DIR/backend/.venv"
    offline_pip_install "$INSTALL_DIR/backend/.venv" "$INSTALL_DIR/backend/requirements.txt"
  else
    PY_VERSION="$(offline_bundle_python_version "$INSTALL_DIR")"
    echo "Skipped venv creation during verification: Python ${PY_VERSION} is not installed on this machine."
  fi
else
  offline_check_python_wheels "$INSTALL_DIR/vendor/wheels" "$INSTALL_DIR"
  PY_VERSION="$(offline_bundle_python_version "$INSTALL_DIR")"
  PYTHON_CMD="$(offline_python_cmd_for_version "$PY_VERSION")"
  "$PYTHON_CMD" -m venv "$INSTALL_DIR/backend/.venv"
  offline_pip_install "$INSTALL_DIR/backend/.venv" "$INSTALL_DIR/backend/requirements.txt"
fi

if [[ "${SKIP_FRONTEND_DEV:-}" != "1" && -d "$INSTALL_DIR/vendor/node_modules" ]]; then
  echo "Restoring frontend node_modules from bundle..."
  rm -rf "$INSTALL_DIR/frontend/node_modules"
  cp -a "$INSTALL_DIR/vendor/node_modules" "$INSTALL_DIR/frontend/node_modules"
fi

if [[ "${SKIP_FRONTEND_DEV:-}" == "1" ]]; then
  echo "Skipped frontend node_modules restore (SKIP_FRONTEND_DEV=1)."
fi

if [[ ! -f "$INSTALL_DIR/backend/static/index.html" ]]; then
  echo "Frontend build is missing in bundle."
  exit 1
fi

if [[ ! -f "$INSTALL_DIR/.env.prod" && -f "$INSTALL_DIR/.env.example" ]]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env.prod"
fi

mkdir -p "$INSTALL_DIR/backend/uploads"

echo
echo "Offline install completed in $INSTALL_DIR"
echo
echo "Next steps:"
echo "  1. sudo $INSTALL_DIR/scripts/install-system-deps-offline.sh $INSTALL_DIR/vendor/debs"
echo "  2. Edit $INSTALL_DIR/.env.prod"
echo "  3. $INSTALL_DIR/scripts/setup-databases.sh"
echo "  4. OFFLINE_MODE=1 $INSTALL_DIR/scripts/migrate.sh prod"
echo "  5. OFFLINE_MODE=1 $INSTALL_DIR/scripts/run-prod.sh"
echo "  6. OFFLINE_MODE=1 $INSTALL_DIR/scripts/setup-offline-frontend-dev.sh"
echo "  7. OFFLINE_MODE=1 $INSTALL_DIR/scripts/dev-offline.sh"
