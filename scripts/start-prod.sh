#!/usr/bin/env bash
set -euo pipefail

WEB_UNIT="bookuchet.service"
TIMERS=(
  bookuchet-rules.timer
  bookuchet-notifications.timer
)

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must be run as root."
  echo "Use: sudo ./scripts/start-prod.sh"
  exit 1
fi

unit_installed() {
  local unit="$1"
  systemctl list-unit-files "$unit" --no-legend 2>/dev/null | grep -q "^${unit}"
}

echo "Starting Bookuchet production contour..."

if ! unit_installed "$WEB_UNIT"; then
  echo "Required unit is not installed: $WEB_UNIT"
  exit 1
fi

# Start the web application first. Its systemd unit performs the production
# migration check before Gunicorn starts accepting requests.
systemctl start "$WEB_UNIT"

if ! systemctl is-active --quiet "$WEB_UNIT"; then
  echo "Failed to start $WEB_UNIT"
  systemctl --no-pager --full status "$WEB_UNIT" || true
  exit 1
fi

echo "Started: $WEB_UNIT"

# Start timers only after the web service is healthy from systemd's point of view.
for unit in "${TIMERS[@]}"; do
  if unit_installed "$unit"; then
    systemctl start "$unit"
    echo "Started: $unit"
  else
    echo "Not installed, skipping: $unit"
  fi
done

echo
echo "Production status:"
systemctl --no-pager --full is-active "$WEB_UNIT" || true
for unit in "${TIMERS[@]}"; do
  if unit_installed "$unit"; then
    printf "%s: " "$unit"
    systemctl --no-pager is-active "$unit" || true
  fi
done

echo
echo "Bookuchet production contour is started."
