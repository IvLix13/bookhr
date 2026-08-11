#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/offline/common.sh"

VERSION="${1:-$(date +%Y%m%d.%H%M%S)}"
OFFLINE_PYTHON_VERSION="${OFFLINE_PYTHON_VERSION:-3.11}"
export OFFLINE_PYTHON_VERSION
BUNDLE_NAME="bookuchet-offline-${VERSION}-py${OFFLINE_PYTHON_VERSION//./}-linux-x64"
BUNDLE_DIR="$ROOT_DIR/dist/offline/${BUNDLE_NAME}"
VENDOR_DIR="$BUNDLE_DIR/vendor"
ARCH="$(uname -m)"

if [[ "$ARCH" != "x86_64" ]]; then
  echo "Offline bundle supports only linux x86_64, current: $ARCH"
  exit 1
fi

for cmd in python3 npm node rsync tar sha256sum; do
  if ! command -v "$cmd" >/dev/null; then
    echo "Required command not found: $cmd"
    exit 1
  fi
done

echo "Preparing offline bundle $VERSION for Python ${OFFLINE_PYTHON_VERSION}"

rm -rf "$BUNDLE_DIR"
mkdir -p "$VENDOR_DIR/wheels" "$VENDOR_DIR/npm-cache" "$VENDOR_DIR/debs" "$BUNDLE_DIR/app"

TMP_VENV="$(mktemp -d)/venv"
python3 -m venv "$TMP_VENV"
"$TMP_VENV/bin/pip" install --upgrade pip wheel

echo "Downloading Python wheels..."
offline_download_python_wheels "$TMP_VENV/bin/pip" "$VENDOR_DIR/wheels" \
  "backend/requirements.txt" "backend/requirements-dev.txt"
offline_verify_bundle_wheels "$VENDOR_DIR/wheels" "$OFFLINE_PYTHON_VERSION"
rm -rf "$(dirname "$TMP_VENV")"

echo "Preparing frontend for offline development..."
bash "$ROOT_DIR/scripts/prepare-offline-frontend-dev.sh" "$VENDOR_DIR"

echo "Downloading system packages (Ubuntu/Debian)..."
bash "$ROOT_DIR/scripts/prepare-offline-system-packages.sh" "$VENDOR_DIR/debs" || true

echo "Copying application sources..."
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

cat > "$VENDOR_DIR/MANIFEST.json" <<JSON
{
  "name": "bookuchet-offline-bundle",
  "version": "${VERSION}",
  "platform": "linux-x64",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "python_version": "${OFFLINE_PYTHON_VERSION}",
  "python_tag": "cp${OFFLINE_PYTHON_VERSION//./}",
  "built_with_python": "$(python3 --version | awk '{print $2}')",
  "includes_frontend_build": true,
  "includes_python_wheels": true,
  "includes_npm_cache": true,
  "includes_node_modules": true,
  "includes_frontend_dev": true,
  "includes_system_debs": true
}
JSON

date -u +%Y-%m-%dT%H:%M:%SZ > "$BUNDLE_DIR/app/.offline-install"

(
  cd "$BUNDLE_DIR"
  find . -type f ! -name 'SHA256SUMS' -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

ARCHIVE="$ROOT_DIR/dist/offline/${BUNDLE_NAME}.tar.gz"
tar -C "$ROOT_DIR/dist/offline" -czf "$ARCHIVE" "$BUNDLE_NAME"

echo
echo "Bundle ready:"
echo "  $ARCHIVE"
echo
echo "Transfer to offline machine:"
echo "  scp \"$ARCHIVE\" user@offline-host:/tmp/"
echo
echo "On offline machine:"
echo "  tar -xzf /tmp/${BUNDLE_NAME}.tar.gz -C /tmp"
echo "  sudo OFFLINE_MODE=1 INSTALL_DIR=/opt/bookuchet /tmp/${BUNDLE_NAME}/app/scripts/deploy-offline-prod.sh /tmp/${BUNDLE_NAME}.tar.gz"
echo
echo "Or step-by-step:"
echo "  ./scripts/install-offline.sh /tmp/${BUNDLE_NAME}.tar.gz"
echo "  sudo ./scripts/install-system-deps-offline.sh vendor/debs"
echo "  ./scripts/setup-databases.sh"
echo "  OFFLINE_MODE=1 ./scripts/migrate.sh prod"
echo "  OFFLINE_MODE=1 ./scripts/run-prod.sh"
echo "  # run-prod / systemd also auto-apply pending migrations via ensure-migrations.sh"
echo
echo "Frontend development on offline machine:"
echo "  OFFLINE_MODE=1 ./scripts/setup-offline-frontend-dev.sh"
echo "  OFFLINE_MODE=1 ./scripts/dev-offline.sh"
