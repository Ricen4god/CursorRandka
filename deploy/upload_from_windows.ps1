# Загрузка CursorRandka на VPS через scp (Windows PowerShell)
# Перед запуском: замените YOUR_SERVER_IP на IP вашего сервера

$SERVER_IP = "YOUR_SERVER_IP"
$SERVER_USER = "root"
$LOCAL_PATH = "C:\Users\nazar\OneDrive\Рабочий стол\CursorRandka"
$REMOTE_PATH = "/opt/randkapl"

if ($SERVER_IP -eq "YOUR_SERVER_IP") {
    Write-Host "Ошибка: укажите IP сервера в переменной SERVER_IP" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $LOCAL_PATH)) {
    Write-Host "Ошибка: папка не найдена: $LOCAL_PATH" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "$LOCAL_PATH\.env")) {
    Write-Host "Внимание: файл .env не найден. Создайте его из .env.example с BOT_TOKEN." -ForegroundColor Yellow
}

Write-Host "Создание папки на сервере..." -ForegroundColor Cyan
ssh "${SERVER_USER}@${SERVER_IP}" "mkdir -p $REMOTE_PATH"

Write-Host "Загрузка файлов (без venv и __pycache__)..." -ForegroundColor Cyan
scp -r `
    "$LOCAL_PATH\main.py" `
    "$LOCAL_PATH\config.py" `
    "$LOCAL_PATH\db.py" `
    "$LOCAL_PATH\utils.py" `
    "$LOCAL_PATH\keyboards.py" `
    "$LOCAL_PATH\states.py" `
    "$LOCAL_PATH\requirements.txt" `
    "$LOCAL_PATH\.env" `
    "$LOCAL_PATH\.env.example" `
    "$LOCAL_PATH\handlers" `
    "$LOCAL_PATH\deploy" `
    "${SERVER_USER}@${SERVER_IP}:${REMOTE_PATH}/"

if (Test-Path "$LOCAL_PATH\database.db") {
    Write-Host "Загрузка существующей базы данных..." -ForegroundColor Cyan
    scp "$LOCAL_PATH\database.db" "${SERVER_USER}@${SERVER_IP}:${REMOTE_PATH}/"
}

Write-Host ""
Write-Host "Готово! Файлы загружены в $REMOTE_PATH" -ForegroundColor Green
Write-Host "Дальше на сервере выполните:" -ForegroundColor Yellow
Write-Host "  ssh ${SERVER_USER}@${SERVER_IP}" -ForegroundColor White
Write-Host "  cd /opt/randkapl && sudo bash deploy/install.sh" -ForegroundColor White
