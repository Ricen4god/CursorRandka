"""Shared constants and helpers for demo profile seeding."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SEED_DATA_DIR = Path(__file__).resolve().parent / "seed_data"
PHOTOS_JSON = SEED_DATA_DIR / "photos.json"
GENDERS_JSON = SEED_DATA_DIR / "genders.json"

OLD_TEST_ID_START = 900001
OLD_TEST_ID_END = 900030

TEST_ID_START = 910001
TEST_ID_END = 910300
PERSONA_COUNT = 20
CITY_COUNT = 15

CITIES = [
    "Warszawa",
    "Kraków",
    "Wrocław",
    "Łódź",
    "Poznań",
    "Gdańsk",
    "Szczecin",
    "Bydgoszcz",
    "Lublin",
    "Katowice",
    "Białystok",
    "Opole",
    "Rzeszów",
    "Toruń",
    "Kielce",
]

BIOS: dict[str, list[str]] = {
    "M": [
        "Uczeń/student, lubię sport i spotkania z ekipą ⚽",
        "Gram w piłkę i jeżdżę na deskorolce po mieście 🛹",
        "Fan muzyki i koncertów, szukam kogoś pozytywnego 🎸",
        "Kocham gry, filmy i dobre rozmowy do późna 🎮",
        "Aktywny, lubię biegać i odkrywać nowe miejsca 🏃",
        "Programuję po lekcjach, kawa to mój fuel ☕",
        "Weekendy na mieście, w tygodniu nauka 📚",
    ],
    "F": [
        "Studentka, kocham kawę i spacery po mieście ☕",
        "Lubię książki, muzykę i dobre jedzenie 🍕",
        "Szukam szczerych ludzi i dobrego humoru 💕",
        "Uwielbiam tańczyć i chodzić na koncerty 🎤",
        "Miłośniczka seriali i długich rozmów ✨",
        "Kocham zwierzęta i fotografię 📷",
        "Lubię rower i odkrywać nowe kawiarnie 🚲",
    ],
}

INSERT_SQL = """
INSERT OR REPLACE INTO users (
    user_id, username, age, gender, looking_for, city,
    latitude, longitude, device_type, name, bio, photo_file_id,
    is_active, is_banned, is_shadow_banned, ban_reason,
    views_count, likes_received, created_at, last_active, search_city
) VALUES (
    ?, ?, ?, ?, ?, ?,
    NULL, NULL, '', ?, ?, ?,
    1, 0, 0, NULL,
    0, 0, datetime('now'), datetime('now'), ?
)
"""


def persona_user_id(persona: int, city_index: int) -> int:
    """persona 1–20, city_index 0–14 → 910001–910300."""
    return TEST_ID_START + (persona - 1) * CITY_COUNT + city_index


def load_genders() -> dict[str, dict]:
    if not GENDERS_JSON.is_file():
        raise FileNotFoundError(f"Missing {GENDERS_JSON}")
    raw = json.loads(GENDERS_JSON.read_text(encoding="utf-8"))
    result: dict[str, dict] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            result[str(key)] = value
        else:
            gender = str(value)
            result[str(key)] = {
                "gender": gender,
                "looking_for": "F" if gender == "M" else "M",
                "name": f"Demo{key}",
                "age": 18 + (int(key) % 5),
            }
    for i in range(1, PERSONA_COUNT + 1):
        if str(i) not in result:
            raise ValueError(f"genders.json missing entry for photo {i}")
    return result


def load_photos() -> dict[str, str]:
    if not PHOTOS_JSON.is_file():
        raise FileNotFoundError(
            f"Missing {PHOTOS_JSON}. Run: python upload_test_photos.py"
        )
    data = json.loads(PHOTOS_JSON.read_text(encoding="utf-8"))
    missing = [
        str(i)
        for i in range(1, PERSONA_COUNT + 1)
        if not (data.get(str(i)) or "").strip()
    ]
    if missing:
        raise ValueError(
            f"photos.json missing file_id for: {', '.join(missing)}. "
            "Run upload_test_photos.py first."
        )
    return {str(k): v.strip() for k, v in data.items()}


def save_photos(photos: dict[str, str]) -> None:
    SEED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PHOTOS_JSON.write_text(
        json.dumps(photos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _bio_for(gender: str, persona_index: int, city: str) -> str:
    pool = BIOS[gender]
    base = pool[(persona_index - 1) % len(pool)]
    return base.replace("po mieście", f"w {city}").replace(
        "Weekendy na mieście", f"Weekendy w {city}"
    )


def _username(name: str, user_id: int) -> str:
    slug = (
        name.lower()
        .replace("ł", "l")
        .replace("ą", "a")
        .replace("ę", "e")
        .replace("ó", "o")
        .replace("ś", "s")
        .replace("ź", "z")
        .replace("ż", "z")
        .replace("ć", "c")
        .replace("ń", "n")
    )
    return f"demo_{slug}_{user_id}"


def build_test_users(
    genders: dict[str, dict] | None = None,
    photos: dict[str, str] | None = None,
) -> list[dict]:
    gender_map = genders or load_genders()
    photo_map = photos or load_photos()
    users: list[dict] = []

    for persona in range(1, PERSONA_COUNT + 1):
        key = str(persona)
        persona_data = gender_map[key]
        gender = persona_data["gender"]
        looking_for = persona_data["looking_for"]
        name = persona_data["name"]
        age = int(persona_data["age"])
        photo_file_id = photo_map[key]

        for city_index, city in enumerate(CITIES):
            user_id = persona_user_id(persona, city_index)
            users.append(
                {
                    "user_id": user_id,
                    "username": _username(name, user_id),
                    "name": name,
                    "age": age,
                    "gender": gender,
                    "looking_for": looking_for,
                    "city": city,
                    "search_city": city,
                    "bio": _bio_for(gender, persona, city),
                    "photo_file_id": photo_file_id,
                    "persona": persona,
                }
            )

    return users


def delete_test_user(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.execute(
        "DELETE FROM views WHERE viewer_id = ? OR viewed_id = ?",
        (user_id, user_id),
    )
    conn.execute(
        "DELETE FROM likes WHERE from_user_id = ? OR to_user_id = ?",
        (user_id, user_id),
    )
    conn.execute("DELETE FROM daily_likes WHERE user_id = ?", (user_id,))
    conn.execute(
        "DELETE FROM matches WHERE user1_id = ? OR user2_id = ?",
        (user_id, user_id),
    )
    conn.execute(
        "DELETE FROM blocks WHERE blocker_id = ? OR blocked_id = ?",
        (user_id, user_id),
    )
    conn.execute(
        "DELETE FROM reports WHERE reporter_id = ? OR reported_id = ?",
        (user_id, user_id),
    )


def delete_all_test_users(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if not row:
        raise RuntimeError(
            "Таблица users не найдена. Сначала запустите бота (main.py) — "
            "init_db() создаёт схему БД, затем выполните /seed_demo."
        )

    before = conn.execute(
        """SELECT COUNT(*) FROM users
           WHERE user_id BETWEEN ? AND ?
              OR user_id BETWEEN ? AND ?
              OR user_id >= 910000""",
        (OLD_TEST_ID_START, OLD_TEST_ID_END, TEST_ID_START, TEST_ID_END),
    ).fetchone()[0]

    ids = [
        row[0]
        for row in conn.execute(
            """SELECT user_id FROM users
               WHERE user_id BETWEEN ? AND ?
                  OR user_id BETWEEN ? AND ?
                  OR user_id >= 910000""",
            (OLD_TEST_ID_START, OLD_TEST_ID_END, TEST_ID_START, TEST_ID_END),
        ).fetchall()
    ]
    for user_id in ids:
        delete_test_user(conn, user_id)
    conn.commit()
    return before


def seed_test_users_db(
    db_path: str,
    photos: dict[str, str] | None = None,
    genders: dict[str, dict] | None = None,
) -> int:
    users = build_test_users(genders=genders, photos=photos)
    conn = sqlite3.connect(db_path)
    try:
        for u in users:
            conn.execute(
                INSERT_SQL,
                (
                    u["user_id"],
                    u["username"],
                    u["age"],
                    u["gender"],
                    u["looking_for"],
                    u["city"],
                    u["name"],
                    u["bio"],
                    u["photo_file_id"],
                    u["search_city"],
                ),
            )
        conn.commit()
        return len(users)
    finally:
        conn.close()


def get_test_users_stats(db_path: str) -> dict:
    """Count demo users in DB (IDs 910001–910300)."""
    conn = sqlite3.connect(db_path)
    try:
        total = conn.execute(
            """SELECT COUNT(*) FROM users
               WHERE user_id BETWEEN ? AND ?""",
            (TEST_ID_START, TEST_ID_END),
        ).fetchone()[0]

        active = conn.execute(
            """SELECT COUNT(*) FROM users
               WHERE user_id BETWEEN ? AND ?
                 AND is_active = 1 AND is_banned = 0 AND is_shadow_banned = 0""",
            (TEST_ID_START, TEST_ID_END),
        ).fetchone()[0]

        with_photo = conn.execute(
            """SELECT COUNT(*) FROM users
               WHERE user_id BETWEEN ? AND ?
                 AND TRIM(COALESCE(photo_file_id, '')) != ''""",
            (TEST_ID_START, TEST_ID_END),
        ).fetchone()[0]

        by_city = {
            row[0]: row[1]
            for row in conn.execute(
                """SELECT city, COUNT(*) FROM users
                   WHERE user_id BETWEEN ? AND ?
                   GROUP BY city""",
                (TEST_ID_START, TEST_ID_END),
            ).fetchall()
        }

        by_gender = {
            row[0]: row[1]
            for row in conn.execute(
                """SELECT gender, COUNT(*) FROM users
                   WHERE user_id BETWEEN ? AND ?
                   GROUP BY gender""",
                (TEST_ID_START, TEST_ID_END),
            ).fetchall()
        }

        return {
            "total": total,
            "expected": (TEST_ID_END - TEST_ID_START + 1),
            "active": active,
            "with_photo": with_photo,
            "by_city": by_city,
            "by_gender": by_gender,
            "seed_data_dir": str(SEED_DATA_DIR),
            "photos_json": str(PHOTOS_JSON),
            "genders_json": str(GENDERS_JSON),
        }
    finally:
        conn.close()


def format_test_users_report(stats: dict) -> str:
    lines = [
        f"Демо-профили в БД: {stats['total']}/{stats['expected']}",
        f"Активных (не забанены): {stats['active']}",
        f"С photo_file_id: {stats['with_photo']}",
        f"ID: {TEST_ID_START}–{TEST_ID_END}",
    ]
    if stats["by_gender"]:
        g = stats["by_gender"]
        lines.append(f"Пол: M={g.get('M', 0)}, F={g.get('F', 0)}")
    missing_cities = [c for c in CITIES if stats["by_city"].get(c, 0) != PERSONA_COUNT]
    if missing_cities:
        lines.append(f"Города с неполным набором ({PERSONA_COUNT}/город): {', '.join(missing_cities[:5])}")
        if len(missing_cities) > 5:
            lines.append(f"… и ещё {len(missing_cities) - 5}")
    elif stats["total"] == stats["expected"]:
        lines.append(f"Все {len(CITIES)} городов по {PERSONA_COUNT} профилей ✅")
    lines.append(f"seed_data: {stats['seed_data_dir']}")
    return "\n".join(lines)


def run_seed_cli(db_path: str) -> int:
    """CLI entry point (used by seed_test_users.py or `python -m seed_logic`)."""
    result = seed_all_profiles(db_path)
    print(format_test_users_report(result["stats"]))
    print(f"\nSeeded {result['seeded']} demo users in {Path(db_path).resolve()}")
    return result["seeded"]


def count_test_users(db_path: str) -> dict:
    """Return counts and breakdown for demo users (910001–910300)."""
    stats = get_test_users_stats(db_path)
    stats["cities"] = CITIES
    return stats


def seed_all_profiles(db_path: str) -> dict:
    """Delete old demo users (900001–900030, 910001+) and insert 300 profiles."""
    if not SEED_DATA_DIR.is_dir():
        raise FileNotFoundError(f"Missing seed_data directory: {SEED_DATA_DIR}")

    genders = load_genders()
    photos = load_photos()

    conn = sqlite3.connect(db_path)
    try:
        removed = delete_all_test_users(conn)
    finally:
        conn.close()

    seeded = seed_test_users_db(db_path, photos=photos, genders=genders)
    stats = get_test_users_stats(db_path)

    return {
        "removed": removed,
        "seeded": seeded,
        "stats": stats,
        "photos_count": len(photos),
        "genders_count": len(genders),
    }


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()
    _db = os.getenv("DB_PATH", "database.db")
    run_seed_cli(_db)
