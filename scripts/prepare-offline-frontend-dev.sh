#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENDOR_DIR="${1:-$ROOT_DIR/dist/offline/.staging/vendor}"
NPM_CACHE="$VENDOR_DIR/npm-cache"
FRONTEND_DIR="$ROOT_DIR/frontend"

offline_require_command() {
  command -v "$1" >/dev/null
}

for cmd in npm node; do
  if ! offline_require_command "$cmd"; then
    echo "Required command not found: $cmd"
    exit 1
  fi
done

mkdir -p "$NPM_CACHE"

echo "Installing frontend dependencies..."
(
  cd "$FRONTEND_DIR"
  npm ci
)

echo "Populating npm cache for offline reuse..."
npm ci --prefix "$FRONTEND_DIR" --cache "$NPM_CACHE"

echo "Copying node_modules snapshot into vendor..."
rm -rf "$VENDOR_DIR/node_modules"
cp -a "$FRONTEND_DIR/node_modules" "$VENDOR_DIR/node_modules"

echo "Verifying offline npm install from cache..."
VERIFY_DIR="$(mktemp -d)"
trap 'rm -rf "$VERIFY_DIR"' EXIT
rsync -a "$FRONTEND_DIR/" "$VERIFY_DIR/" --exclude node_modules
(
  cd "$VERIFY_DIR"
  npm ci --cache "$NPM_CACHE" --offline --prefer-offline
)

echo "Verifying offline frontend build..."
(
  cd "$FRONTEND_DIR"
  npm run build
  npm run typecheck
  npm test
)

cat > "$VENDOR_DIR/frontend-dev.json" <<JSON
{
  "node_version": "$(node --version)",
  "npm_version": "$(npm --version)",
  "prepared_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "supports_offline_dev": true,
  "supports_offline_build": true
}
JSON

echo "Frontend dev bundle prepared."
echo "  npm cache: $NPM_CACHE"
echo "  node_modules snapshot: $VENDOR_DIR/node_modules"
