# Railway — постоянная база (аккаунты не слетают)

Без Volume SQLite живёт **внутри контейнера** и **удаляется при каждом Deploy**.

## Настройка (один раз)

1. Railway → сервис **CursorRandka** → **Settings** → **Volumes**
2. **Add Volume** → Mount path: `/app/data`
3. **Variables** → `DB_PATH` = `/app/data/database.db`
4. Deploy

Код (build `2025-06-15-persist-v11`) сам создаёт папку `/app/data` и на Railway
переключает `database.db` → `/app/data/database.db`.

## Проверка в логах

```
build=2025-06-15-persist-v11 db=/app/data/database.db
Database path: /app/data/database.db (exists=True)
```

После первого `/start` и redeploy профиль **должен остаться**.
