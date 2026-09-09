#!/usr/bin/env bash
set -euo pipefail

UNITS=(
  bookuchet-notifications.timer
  bookuchet-rules.timer
  bookuchet-notifications.service
  bookuchet-rules.service
  bookuchet.service
)

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must be run as root."
  echo "Use: sudo ./scripts/stop-prod.sh"
  exit 1
fi

echo "Stopping Bookuchet production services..."

# Stop timers first so they cannot start background jobs while prod is being stopped.
for unit in "${UNITS[@]}"; do
  if systemctl list-unit-files "$unit" --no-legend 2>/dev/null | grep -q "^${unit}"; then
    systemctl stop "$unit"
    echo "Stopped: $unit"
  else
    echo "Not installed, skipping: $unit"
  fi
done

echo
echo "Bookuchet production contour is stopped."
echo "nginx remains running; requests to /api/ will return an upstream error until prod is started again."
