# CursorRandka 💕

Bot randkowy na Telegramie w stylu Davinchi — w pełni po polsku.

## Wymagania

- Python 3.13+
- Token bota od [@BotFather](https://t.me/BotFather)

## Instalacja

1. Skopiuj plik konfiguracyjny:
   ```
   copy .env.example .env
   ```

2. Edytuj `.env` — wstaw swój `BOT_TOKEN` i `ADMIN_ID` (Twoje ID Telegram).

3. Zainstaluj zależności:
   ```
   pip install -r requirements.txt
   ```

4. Uruchom bota:
   ```
   start.bat
   ```
   lub:
   ```
   python main.py
   ```

## Funkcje

- Rejestracja profilu (wiek 16+, płeć, preferencje, miasto, zdjęcie)
- Podział urządzeń: 📱 Telefon (GPS) / 💻 Komputer (tylko miasto)
- Przeglądanie profili ze swipe (pomiń, lubię, napisz, uśpij)
- Wzajemne sympatie z powiadomieniem obu stron
- Profil: edycja bio, zdjęcia, miasta, statystyki, usuwanie konta
- Uśpienie profilu (ukrycie przed innymi)
- Zgłaszanie i blokowanie użytkowników
- Limit 50 polubień dziennie
- Panel admina: `/stats`, `/ban <user_id>`

## Struktura

```
CursorRandka/
├── main.py              — punkt wejścia
├── config.py            — konfiguracja z .env
├── db.py                — baza SQLite
├── handlers/            — handlery aiogram
├── keyboards.py         — klawiatury
├── states.py            — stany FSM
└── utils.py             — pomocnicze funkcje
```

## Admin

Ustaw `ADMIN_ID` w `.env` na swoje Telegram user ID.

- `/stats` — statystyki bota
- `/ban <user_id>` — ban użytkownika

## Licencja

Projekt edukacyjny. CursorRandka nie jest powiązany z Davinchi/LeoMatch.
