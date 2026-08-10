#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEB_DIR="${1:-$ROOT_DIR/dist/offline/.staging/vendor/debs}"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "apt-get not found; skipping system package download."
  echo "Install PostgreSQL and python3-venv manually on the offline machine."
  exit 0
fi

mkdir -p "$DEB_DIR"

PACKAGES=(
  postgresql
  postgresql-client
  python3.11
  python3.11-venv
  python3-pip
  nodejs
  npm
  rsync
  adduser
  ca-certificates
)

echo "Downloading system packages into $DEB_DIR"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  apt-get update
  apt-get install -y --download-only -o Dir::Cache::Archives="$DEB_DIR" "${PACKAGES[@]}"
else
  echo "Running apt-get download without root (direct .deb files only)..."
  (
    cd "$DEB_DIR"
    for package in "${PACKAGES[@]}"; do
      apt-get download "$package" || true
    done
  )
fi

DEB_COUNT="$(find "$DEB_DIR" -maxdepth 1 -name '*.deb' | wc -l | tr -d ' ')"
if [[ "$DEB_COUNT" == "0" ]]; then
  echo "Warning: no .deb packages were downloaded."
  echo "Run this script on Ubuntu/Debian with apt access, or install system packages manually offline."
  exit 0
fi

echo "Downloaded $DEB_COUNT .deb package(s)."
