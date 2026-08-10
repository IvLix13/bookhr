#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_PATH="${1:-}"

if [[ -z "$BUNDLE_PATH" ]]; then
  echo "Usage: $0 /path/to/bookuchet-offline-<version>-linux-x64.tar.gz"
  exit 1
fi

INSTALL_DIR="${INSTALL_DIR:-/opt/bookuchet}"
export INSTALL_DIR
export OFFLINE_MODE=1

echo "Installing Bookuchet offline into $INSTALL_DIR"
bash "$SCRIPT_DIR/install-offline.sh" "$BUNDLE_PATH"

if [[ -d "$INSTALL_DIR/vendor/debs" ]] && [[ "${SKIP_SYSTEM_DEPS:-}" != "1" ]]; then
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    bash "$INSTALL_DIR/scripts/install-system-deps-offline.sh" "$INSTALL_DIR/vendor/debs"
  else
    echo "Skipping system packages (run as root to install automatically):"
    echo "  sudo $INSTALL_DIR/scripts/install-system-deps-offline.sh $INSTALL_DIR/vendor/debs"
  fi
fi

if ! id bookuchet >/dev/null 2>&1; then
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    adduser --system --group --home "$INSTALL_DIR" --no-create-home bookuchet
    chown -R bookuchet:bookuchet "$INSTALL_DIR"
  else
    echo "Create system user manually:"
    echo "  sudo adduser --system --group --home $INSTALL_DIR --no-create-home bookuchet"
    echo "  sudo chown -R bookuchet:bookuchet $INSTALL_DIR"
  fi
fi

if [[ ! -f "$INSTALL_DIR/.env.prod" ]]; then
  bash "$INSTALL_DIR/scripts/setup-databases.sh"
else
  echo "Using existing $INSTALL_DIR/.env.prod"
fi

(
  cd "$INSTALL_DIR"
  OFFLINE_MODE=1 bash scripts/migrate.sh prod
)

if [[ "${EUID:-$(id -u)}" -eq 0 && "${SKIP_SYSTEMD:-}" != "1" ]]; then
  sed "s|/opt/bookuchet|$INSTALL_DIR|g" "$INSTALL_DIR/deploy/bookuchet.service" > /etc/systemd/system/bookuchet.service
  sed "s|/opt/bookuchet|$INSTALL_DIR|g" "$INSTALL_DIR/deploy/bookuchet-rules.service" > /etc/systemd/system/bookuchet-rules.service
  sed "s|/opt/bookuchet|$INSTALL_DIR|g" "$INSTALL_DIR/deploy/bookuchet-notifications.service" > /etc/systemd/system/bookuchet-notifications.service
  cp "$INSTALL_DIR/deploy/bookuchet-rules.timer" /etc/systemd/system/
  cp "$INSTALL_DIR/deploy/bookuchet-notifications.timer" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now bookuchet.service bookuchet-rules.timer bookuchet-notifications.timer
  echo "Systemd services enabled."
else
  echo "Install systemd units manually from $INSTALL_DIR/deploy/"
fi

echo
echo "Offline deployment completed."
echo "Application directory: $INSTALL_DIR"
echo "Start manually:"
echo "  cd $INSTALL_DIR && OFFLINE_MODE=1 ./scripts/run-prod.sh"
