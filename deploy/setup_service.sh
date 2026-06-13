#!/bin/bash
set -euo pipefail

APP_DIR="/opt/randkapl"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/randkapl.service"

cp "$SERVICE_FILE" /etc/systemd/system/randkapl.service
systemctl daemon-reload
systemctl enable randkapl
systemctl restart randkapl

echo "Сервис randkapl включён и запущен."
systemctl status randkapl --no-pager
