#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUNDLE_PATH="${1:-}"

if [[ -z "$BUNDLE_PATH" ]]; then
  echo "Usage: $0 /path/to/bookuchet-offline-<version>-linux-x64.tar.gz"
  exit 1
fi

VERIFY_DIR="$(mktemp -d)"
INSTALL_DIR="$VERIFY_DIR/install"
export INSTALL_DIR
export OFFLINE_MODE=1
export OFFLINE_VERIFY_ONLY=1

echo "Verifying offline bundle in isolated directory..."
bash "$ROOT_DIR/scripts/install-offline.sh" "$BUNDLE_PATH"

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/offline/common.sh"
PY_VERSION="$(offline_bundle_python_version "$INSTALL_DIR")"

if offline_python_cmd_for_version "$PY_VERSION" >/dev/null 2>&1; then
  test -f "$INSTALL_DIR/backend/.venv/bin/python"
fi
test -d "$INSTALL_DIR/backend/static"
test -f "$INSTALL_DIR/backend/static/index.html"
test -d "$INSTALL_DIR/vendor/wheels"
test -f "$INSTALL_DIR/.offline-install"

WHEEL_COUNT="$(find "$INSTALL_DIR/vendor/wheels" -name '*.whl' | wc -l | tr -d ' ')"
if [[ "$WHEEL_COUNT" -lt 5 ]]; then
  echo "Too few Python wheels in bundle: $WHEEL_COUNT"
  exit 1
fi

offline_verify_bundle_wheels "$INSTALL_DIR/vendor/wheels" "$PY_VERSION"

if command -v unshare >/dev/null 2>&1 && offline_python_cmd_for_version "$PY_VERSION" >/dev/null 2>&1; then
  PYTHON_CMD="$(offline_python_cmd_for_version "$PY_VERSION")"
  echo "Checking that pip install works without network (Python ${PY_VERSION})..."
  TEST_DIR="$VERIFY_DIR/network-test"
  mkdir -p "$TEST_DIR"
  rsync -a "$INSTALL_DIR/" "$TEST_DIR/"
  rm -rf "$TEST_DIR/backend/.venv"
  if unshare -n bash -c "cd '$TEST_DIR' && OFFLINE_MODE=1 '$PYTHON_CMD' -m venv backend/.venv && source scripts/offline/common.sh && offline_pip_install backend/.venv backend/requirements.txt" 2>/dev/null; then
    echo "Network-isolated pip install check passed."
  else
    echo "Skipped network-isolated pip check (unshare unavailable in this environment)."
  fi
elif ! offline_python_cmd_for_version "$PY_VERSION" >/dev/null 2>&1; then
  echo "Skipped venv install check: Python ${PY_VERSION} is not installed on this machine."
  echo "Wheel contents for Python ${PY_VERSION} were verified successfully."
fi

echo "Offline bundle verification passed."
