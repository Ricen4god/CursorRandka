# Seeding demo profiles on Railway

Demo profiles: **300 users** (20 personas × 15 cities), IDs **910001–910300**.

## Files that MUST be on GitHub / in the Docker image

| File / folder | Required |
|---------------|----------|
| `main.py` | **Yes** — registers `admin.register(dp)` and `/seed_demo` |
| `seed_logic.py` | **Yes** |
| `handlers/admin.py` | **Yes** (whole `handlers/` package) |
| `seed_data/genders.json` | **Yes** |
| `seed_data/photos.json` | **Yes** (file_ids from `upload_test_photos.py`) |
| `config.py`, `db.py`, `requirements.txt`, `Dockerfile` | **Yes** (base bot) |
| `seed_test_users.py`, `delete_test_users.py` | Optional (CLI); `/seed_demo` works without them |
| `upload_test_photos.py` | Optional (local only, to regenerate `photos.json`) |

Railway Variables:

- `BOT_TOKEN` — **must match** the token used when running `upload_test_photos.py`
- `ADMIN_ID` — your Telegram user id (only this user can run `/seed_demo`, `/seed_status`)

Local `.env` example: `BOT_TOKEN=8606520664:…`, `ADMIN_ID=8761183578`.  
If Railway uses a **different bot token**, committed `photos.json` file_ids are **invalid** — re-run `upload_test_photos.py` with the Railway token and push again.

## Admin commands (after deploy)

| Command | Action |
|---------|--------|
| `/seed_demo` | Delete old 900001–900030 / 910001+, insert 300 profiles (20 unique photos per city) |
| `/seed_status` | Count demo users in DB + browse hints for your city/age |

**After updating seed logic:** push → redeploy Railway → run `/seed_demo` again (old demo rows keep duplicate photos until reseeded).

## Option A — Railway CLI

```bash
railway login
railway link
railway run python delete_test_users.py
railway run python seed_test_users.py
# or: railway run python -c "from seed_logic import run_seed_cli; run_seed_cli('database.db')"
```

## Option B — Telegram (recommended after push)

1. Push all files above to GitHub.
2. Redeploy Railway (check logs for `build=2025-06-13-seed-fix-v6`).
3. As admin, send `/seed_demo` — this **deletes old demo users** (900001–900030, 910001+) and inserts fresh profiles. You must reseed after deploy; old rows keep stale photo assignments.
4. Confirm with `/seed_status` (should show **300/300** and unique photos per city).

## Local workflow (first time)

```bash
python delete_test_users.py
python upload_test_photos.py   # same BOT_TOKEN as Railway!
python seed_test_users.py
```

Then commit `seed_data/photos.json`, push, redeploy, `/seed_demo` on Railway.

## Profiles seeded but not visible in 🔎 Przeglądaj?

Seeding only fills the DB. The swipe feed filters candidates:

1. **City** — only users in your «🔍 Szukam w» city (⚙️ Ustawienia). Demo cities: Warszawa, Kraków, Wrocław, Łódź, Poznań, Gdańsk, Szczecin, Bydgoszcz, Lublin, Katowice, Białystok, **Opole**, Rzeszów, Toruń, Kielce.
2. **Age** — ±2 years from your profile age (`AGE_RANGE=2`). Demo ages are **18–22**.
3. **Gender** — mutual preference (M↔F).

Use `/seed_status` — it shows your search city and how many demo profiles match you.

## Notes

- Telegram `file_id` values work **only with the same bot token**.
- Paths on Linux/Railway: `seed_logic.py` uses `Path(__file__).parent / "seed_data"`.
- Without a persistent Railway volume, the SQLite DB is empty after redeploy — run `/seed_demo` again.
