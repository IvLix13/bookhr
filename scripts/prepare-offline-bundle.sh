#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VERSION="${1:-$(date +%Y%m%d.%H%M%S)}"
BUNDLE_DIR="$ROOT_DIR/dist/offline/bookuchet-offline-${VERSION}-linux-x64"
VENDOR_DIR="$BUNDLE_DIR/vendor"
ARCH="$(uname -m)"

if [[ "$ARCH" != "x86_64" ]]; then
  echo "Offline bundle supports only linux x86_64, current: $ARCH"
  exit 1
fi

command -v python3 >/dev/null
command -v npm >/dev/null
command -v node >/dev/null

echo "Preparing offline bundle $VERSION"

rm -rf "$BUNDLE_DIR"
mkdir -p "$VENDOR_DIR/wheels" "$VENDOR_DIR/npm-cache" "$BUNDLE_DIR/app"

if [[ ! -d "backend/.venv" ]]; then
  python3 -m venv backend/.venv
fi

backend/.venv/bin/pip install --upgrade pip wheel
backend/.venv/bin/pip download -r backend/requirements.txt -d "$VENDOR_DIR/wheels"
backend/.venv/bin/pip download -r backend/requirements-dev.txt -d "$VENDOR_DIR/wheels"

(
  cd frontend
  npm ci
  npm run build
)

npm_config_cache="$VENDOR_DIR/npm-cache" npm ci --prefix frontend --cache "$VENDOR_DIR/npm-cache"

rsync -a \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'node_modules' \
  --exclude 'dist/offline' \
  --exclude '.git' \
  ./ "$BUNDLE_DIR/app/"

mkdir -p "$BUNDLE_DIR/app/backend/static"
cp -r frontend/dist/* "$BUNDLE_DIR/app/backend/static/"

(
  cd "$BUNDLE_DIR"
  find . -type f ! -name 'SHA256SUMS' -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

tar -C "$ROOT_DIR/dist/offline" -czf "$ROOT_DIR/dist/offline/bookuchet-offline-${VERSION}-linux-x64.tar.gz" "bookuchet-offline-${VERSION}-linux-x64"

echo "Bundle ready:"
echo "$ROOT_DIR/dist/offline/bookuchet-offline-${VERSION}-linux-x64.tar.gz"
