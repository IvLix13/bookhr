#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/offline/common.sh"

ENV_NAME="${1:-development}"
ENV_FILE=".env.${ENV_NAME}"

if [[ "$ENV_NAME" == "development" ]]; then
  ENV_FILE=".env.dev"
elif [[ "$ENV_NAME" == "production" ]]; then
  ENV_FILE=".env.prod"
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
fi

export APP_ENV="${APP_ENV:-$ENV_NAME}"

if offline_is_install "$ROOT_DIR"; then
  if [[ -f "backend/static/index.html" ]]; then
    echo "Offline install detected, using existing backend/static build."
    exit 0
  fi
  echo "Offline install cannot download npm packages. Rebuild bundle on an online machine."
  exit 1
fi

if [[ ! -d "frontend/node_modules" ]]; then
  (cd frontend && npm ci)
fi

echo "Building frontend..."
(cd frontend && npm run build)

echo "Copying frontend build to backend/static..."
rm -rf backend/static/*
cp -r frontend/dist/* backend/static/

echo "Build completed."
