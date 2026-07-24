#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_PATH="${1:-}"

if [[ -z "$BUNDLE_PATH" ]]; then
  echo "Usage: $0 /path/to/bookuchet-offline-<version>-linux-x64.tar.gz"
  exit 1
fi

VERIFY_DIR="$(mktemp -d)"
INSTALL_DIR="$VERIFY_DIR/install"
export INSTALL_DIR

echo "Verifying offline bundle in isolated directory..."
bash "$ROOT_DIR/scripts/install-offline.sh" "$BUNDLE_PATH"

test -f "$INSTALL_DIR/backend/.venv/bin/python"
test -d "$INSTALL_DIR/backend/static"
test -f "$INSTALL_DIR/backend/requirements.txt"

echo "Offline bundle verification passed."
