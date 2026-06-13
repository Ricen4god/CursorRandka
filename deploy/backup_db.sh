#!/bin/bash
set -euo pipefail

APP_DIR="/opt/randkapl"
BACKUP_DIR="$APP_DIR/backups"
DB_FILE="$APP_DIR/database.db"
KEEP_DAYS=14

mkdir -p "$BACKUP_DIR"

if [[ ! -f "$DB_FILE" ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') — база не найдена: $DB_FILE"
    exit 0
fi

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BACKUP_FILE="$BACKUP_DIR/database_${TIMESTAMP}.db"

cp "$DB_FILE" "$BACKUP_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') — бэкап создан: $BACKUP_FILE"

find "$BACKUP_DIR" -name "database_*.db" -type f -mtime +"$KEEP_DAYS" -delete
