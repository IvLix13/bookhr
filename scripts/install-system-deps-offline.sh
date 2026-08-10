#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="${1:-$ROOT_DIR/vendor}"

DEB_DIR="$VENDOR_DIR/debs"
if [[ ! -d "$DEB_DIR" ]]; then
  echo "System package directory not found: $DEB_DIR"
  echo "Install manually: postgresql, postgresql-client, python3, python3-venv, rsync"
  exit 1
fi

mapfile -t DEBS < <(find "$DEB_DIR" -maxdepth 1 -name '*.deb' | sort)
if [[ "${#DEBS[@]}" -eq 0 ]]; then
  echo "No .deb files found in $DEB_DIR"
  exit 1
fi

echo "Installing ${#DEBS[@]} local .deb package(s) without apt repositories..."

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Root privileges required. Re-run with sudo."
  exit 1
fi

dpkg -i "${DEBS[@]}" || true
apt-get install -f -y --allow-downgrades --no-download || true

echo "Local system packages installed."
