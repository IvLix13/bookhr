#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_PATH="${1:-}"

if [[ -z "$BUNDLE_PATH" ]]; then
  BUNDLE_PATH="$(ls -1t "$ROOT_DIR/dist/offline/"bookuchet-offline-*-linux-x64.tar.gz 2>/dev/null | head -n1 || true)"
fi

if [[ -z "$BUNDLE_PATH" || ! -f "$BUNDLE_PATH" ]]; then
  echo "Usage: $0 /path/to/bookuchet-offline-<version>-linux-x64.tar.gz"
  exit 1
fi

INSTALL_DIR="${INSTALL_DIR:-$HOME/bookuchet-offline}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

tar -xzf "$BUNDLE_PATH" -C "$TMP_DIR"
BUNDLE_DIR="$(find "$TMP_DIR" -maxdepth 1 -type d -name 'bookuchet-offline-*' | head -n1)"
APP_DIR="$BUNDLE_DIR/app"

(
  cd "$BUNDLE_DIR"
  sha256sum -c SHA256SUMS
)

mkdir -p "$INSTALL_DIR"
rsync -a "$APP_DIR/" "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/backend/.venv"
"$INSTALL_DIR/backend/.venv/bin/pip" install --no-index --find-links "$BUNDLE_DIR/vendor/wheels" -r "$INSTALL_DIR/backend/requirements.txt"

if command -v npm >/dev/null; then
  npm ci --prefix "$INSTALL_DIR/frontend" --cache "$BUNDLE_DIR/vendor/npm-cache" --offline || true
fi

if [[ ! -f "$INSTALL_DIR/.env.prod" ]]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env.prod"
fi

echo "Offline install completed in $INSTALL_DIR"
echo "Next steps:"
echo "  1. Edit $INSTALL_DIR/.env.prod"
echo "  2. Run $INSTALL_DIR/scripts/migrate.sh prod"
echo "  3. Run $INSTALL_DIR/scripts/run-prod.sh"
