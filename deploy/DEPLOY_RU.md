# CursorRandka — деплой на VPS 24/7

Полная инструкция для запуска Telegram-бота на дешёвом сервере.
Все скрипты уже подготовлены — вам нужно только купить VPS и выполнить шаги ниже.

---

## Что купить (небольшой бюджет)

### Вариант A — РЕКОМЕНДУЕТСЯ: Hetzner CX22

| Параметр | Значение |
|----------|----------|
| Цена | ~4.51 EUR/мес (~20 zł) |
| ОС | Ubuntu 22.04 |
| RAM | 2 GB |
| CPU | 2 vCPU |
| Диск | 40 GB SSD |

**Почему Hetzner:** простая регистрация, понятная панель, стабильная работа, достаточно ресурсов для бота. Идеально для начинающих.

**Где создать:** [hetzner.com](https://www.hetzner.com/cloud) → Cloud → Create Server → CX22 → Ubuntu 22.04 → Location: **Falkenstein** или **Helsinki**.

---

### Вариант B — БЕСПЛАТНО: Oracle Cloud Always Free

| Параметр | Значение |
|----------|----------|
| Цена | 0 zł |
| ОС | Ubuntu 22.04 (ARM) |
| RAM | до 24 GB (на несколько инстансов) |
| Сложность | Высокая |

**Минусы:** долгая регистрация (иногда отклоняют карту), ARM-процессор (нужно проверять совместимость), сложнее настроить firewall и сеть.

**Вывод:** если вы новичок — берите **Hetzner CX22**. Oracle — только если готовы потратить несколько часов на настройку ради экономии.

---

## Что уже подготовлено в проекте

```
deploy/
├── DEPLOY_RU.md          ← эта инструкция
├── QUICK_START_RU.txt    ← краткая шпаргалка (5 шагов)
├── install.sh            ← одна команда — полная установка
├── setup_service.sh      ← настройка systemd
├── randkapl.service      ← автозапуск бота 24/7
├── backup_db.sh          ← ежедневный бэкап базы
└── upload_from_windows.ps1  ← загрузка с Windows

Dockerfile                ← альтернатива через Docker
docker-compose.yml
```

---

## Пошаговая инструкция (Hetzner)

### Шаг 1. Создать сервер

1. Зарегистрируйтесь на [hetzner.com](https://www.hetzner.com/cloud).
2. Создайте проект → **Add Server**.
3. Выберите:
   - **Location:** Falkenstein (DE) или Helsinki (FI)
   - **Image:** Ubuntu 22.04
   - **Type:** CX22 (2 vCPU, 2 GB RAM)
   - **SSH Key:** можно пропустить (будет пароль root)
4. Нажмите **Create & Buy Now**.
5. Запишите:
   - **IP-адрес** сервера (например `123.45.67.89`)
   - **Пароль root** (придёт на email или покажется в панели)

---

### Шаг 2. Подключиться к серверу

**Из Windows (PowerShell или CMD):**

```powershell
ssh root@123.45.67.89
```

При первом подключении введите `yes`, затем пароль root.

**Альтернатива:** программа [PuTTY](https://www.putty.org/) — Host Name = IP, Port = 22, Login = root.

---

### Шаг 3. Загрузить бота на сервер

#### Способ A — PowerShell-скрипт (рекомендуется)

1. Откройте файл `deploy/upload_from_windows.ps1` в блокноте.
2. Замените `YOUR_SERVER_IP` на IP вашего сервера.
3. Запустите в PowerShell:

```powershell
cd "C:\Users\nazar\OneDrive\Рабочий стол\CursorRandka\deploy"
.\upload_from_windows.ps1
```

> Если ошибка «скрипты отключены»: `Set-ExecutionPolicy -Scope Process Bypass`

#### Способ B — WinSCP (графический интерфейс)

1. Скачайте [WinSCP](https://winscp.net/).
2. Подключитесь: протокол SFTP, хост = IP, пользователь = root, пароль = ваш пароль.
3. Создайте папку `/opt/randkapl` на сервере.
4. Перетащите все файлы проекта в `/opt/randkapl` (кроме `venv`, `__pycache__`, `.git`).

#### Способ C — scp вручную

```powershell
ssh root@123.45.67.89 "mkdir -p /opt/randkapl"
scp -r "C:\Users\nazar\OneDrive\Рабочий стол\CursorRandka\*" root@123.45.67.89:/opt/randkapl/
```

---

### Шаг 4. Настроить .env с токеном бота

Файл `.env` содержит секреты — **не загружайте его в Git**.

**На Windows** создайте `.env` из примера:

```
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_ID=987654321
DB_PATH=database.db
```

- `BOT_TOKEN` — получите у [@BotFather](https://t.me/BotFather) в Telegram.
- `ADMIN_ID` — ваш Telegram ID (узнайте у [@userinfobot](https://t.me/userinfobot)).

**Загрузите .env на сервер:**

```powershell
scp "C:\Users\nazar\OneDrive\Рабочий стол\CursorRandka\.env" root@123.45.67.89:/opt/randkapl/.env
```

**Или на сервере:**

```bash
cd /opt/randkapl
cp .env.example .env
nano .env
# вставьте токен, сохраните: Ctrl+O, Enter, Ctrl+X
```

---

### Шаг 5. Запустить установку (одна команда)

На сервере выполните:

```bash
cd /opt/randkapl
sudo bash deploy/install.sh
```

Скрипт автоматически:
- установит Python 3 и зависимости;
- создаст виртуальное окружение;
- установит пакеты из `requirements.txt`;
- настроит systemd (автозапуск при перезагрузке);
- запустит бота;
- настроит ежедневный бэкап базы в 03:00.

**Готово!** Бот работает 24/7.

---

## Проверка и управление

```bash
# Статус бота
systemctl status randkapl

# Логи в реальном времени
journalctl -u randkapl -f

# Перезапуск после изменений
systemctl restart randkapl

# Остановка
systemctl stop randkapl
```

Если всё OK, в логах будет: `CursorRandka bot started!`

---

## Обновление бота

1. Загрузите новые файлы (WinSCP или `upload_from_windows.ps1`).
2. На сервере:

```bash
cd /opt/randkapl
source venv/bin/activate
pip install -r requirements.txt
systemctl restart randkapl
```

База данных `database.db` сохранится — пользователи не потеряются.

---

## Бэкапы

- Автоматически каждый день в 03:00 → `/opt/randkapl/backups/`
- Хранятся последние 14 дней
- Ручной бэкап: `bash /opt/randkapl/deploy/backup_db.sh`

**Скачать бэкап на Windows:**

```powershell
scp root@123.45.67.89:/opt/randkapl/backups/database_*.db .
```

---

## Альтернатива: Docker

Если предпочитаете Docker вместо systemd:

```bash
cd /opt/randkapl
mkdir -p data backups
# убедитесь что .env на месте
docker compose up -d --build
docker compose logs -f
```

Остановка: `docker compose down`

---

## Частые проблемы

### Бот не запускается — «Brak BOT_TOKEN»

Файл `.env` не найден или пустой. Проверьте:

```bash
cat /opt/randkapl/.env
```

### ssh: connect refused

Подождите 1–2 минуты после создания сервера. Проверьте IP в панели Hetzner.

### Permission denied (publickey)

Используйте пароль root, не SSH-ключ. В PuTTY: Connection → SSH → Auth → отключите ключи.

### Бот падал после перезагрузки сервера

```bash
systemctl enable randkapl
systemctl start randkapl
```

`install.sh` делает это автоматически.

---

## Итого: что делает пользователь

| # | Действие |
|---|----------|
| 1 | Купить Hetzner CX22 (~20 zł/мес) |
| 2 | Записать IP и пароль |
| 3 | Загрузить файлы (`upload_from_windows.ps1`) |
| 4 | Загрузить `.env` с BOT_TOKEN |
| 5 | Выполнить `sudo bash deploy/install.sh` |

**Всё остальное уже готово в папке `deploy/`.**
