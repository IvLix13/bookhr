#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-$(date +%Y%m%d.%H%M%S)}"
OFFLINE_PYTHON_VERSION="${OFFLINE_PYTHON_VERSION:-3.11}"
export OFFLINE_PYTHON_VERSION

bash "$ROOT_DIR/scripts/prepare-offline-bundle.sh" "$VERSION"
ARCHIVE="$ROOT_DIR/dist/offline/bookuchet-offline-${VERSION}-py${OFFLINE_PYTHON_VERSION//./}-linux-x64.tar.gz"
bash "$ROOT_DIR/scripts/verify-offline-bundle.sh" "$ARCHIVE"

echo
echo "Offline export is ready for transfer:"
echo "  $ARCHIVE"
