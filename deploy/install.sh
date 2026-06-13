#!/bin/bash
set -euo pipefail

APP_DIR="/opt/randkapl"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "$APP_DIR/main.py" ]]; then
    echo "Ошибка: $APP_DIR/main.py не найден."
    echo "Сначала загрузите файлы бота в $APP_DIR"
    exit 1
fi

echo "==> Установка системных пакетов..."
apt update
apt install -y python3 python3-pip python3-venv

echo "==> Создание виртуального окружения..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f "$APP_DIR/.env" ]]; then
    echo ""
    echo "ВНИМАНИЕ: файл .env не найден в $APP_DIR"
    echo "Скопируйте .env с BOT_TOKEN перед запуском бота:"
    echo "  cp .env.example .env && nano .env"
    echo ""
fi

echo "==> Настройка systemd-сервиса..."
bash "$SCRIPT_DIR/setup_service.sh"

echo "==> Настройка ежедневного бэкапа базы..."
chmod +x "$SCRIPT_DIR/backup_db.sh"
CRON_LINE="0 3 * * * $SCRIPT_DIR/backup_db.sh >> /var/log/randkapl-backup.log 2>&1"
(crontab -l 2>/dev/null | grep -Fv "backup_db.sh"; echo "$CRON_LINE") | crontab -

echo ""
echo "Готово! Бот установлен и запущен."
echo "Проверка статуса: systemctl status randkapl"
echo "Логи:           journalctl -u randkapl -f"
