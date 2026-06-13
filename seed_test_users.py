#!/usr/bin/env python3
"""Insert 30 Polish test profiles in Opole for CursorRandka bot testing.

NOTE: photo_file_id is empty — browse/profile flows fall back to text when missing
(handlers/swipe.py, handlers/profile.py).
"""

import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "database.db")

TEST_ID_START = 900001
TEST_ID_END = 900030

FEMALE_NAMES = [
    "Anna", "Kasia", "Zuzanna", "Ola", "Marta", "Weronika",
    "Natalia", "Julia", "Agnieszka", "Magda", "Paulina", "Dominika",
    "Aleksandra", "Karolina", "Monika",
]

MALE_NAMES = [
    "Michał", "Piotr", "Jakub", "Kacper", "Adam", "Szymon",
    "Bartek", "Mateusz", "Filip", "Dawid", "Kamil", "Maciej",
    "Łukasz", "Tomek", "Wiktor",
]

FEMALE_BIOS = [
    "Uczennica LO w Opolu, kocham kawę i spacery nad Odrą ☕",
    "Lubię książki i koncerty w Centrum 🎵",
    "Szukam kogoś do rozmów i wspólnych wypadów po mieście 💕",
    "Fanatka seriali i dobrego jedzenia 🍕",
    "Gram w siatkówkę w szkole, zawsze pozytywna 🏐",
    "Uwielbiam fotografię i zachody słońca 📷",
    "Studentka, weekendy spędzam z przyjaciółkami ✨",
    "Kocham zwierzęta i długie rozmowy do późna 🐱",
    "Lubię rower i odkrywać nowe miejsca w Opolu 🚲",
    "Miłośniczka muzyki pop i karaoke 🎤",
    "Szukam szczerych ludzi i dobrego humoru 😊",
    "Planuję studia, na razie cieszę się wakacjami 🌞",
    "Uwielbiam tańczyć i chodzić na festiwale 💃",
    "Kawa rano, muzyka wieczorem — idealny dzień ☕🎧",
    "Szukam kogoś z podobnymi zainteresowaniami 💫",
]

MALE_BIOS = [
    "Uczeń technikum, gram w piłkę po szkole ⚽",
    "Lubię gry, muzykę i spotkania z ekipą 🎮",
    "Szukam miłej osoby do rozmów i spacerów 💬",
    "Fan motoryzacji i dobrego kebaba 🚗",
    "Gram na gitarze, czasem gram na scenie 🎸",
    "Kocham sport i aktywny wypoczynek 🏃",
    "Student, weekendy na Rynku z przyjaciółmi 🍻",
    "Lubię filmy akcji i planszówki 🎬",
    "Jeżdżę na deskorolce po Opolu 🛹",
    "Szukam kogoś pozytywnego i otwartego 😄",
    "Fan koszykówki i NBA 🏀",
    "Programuję po lekcjach, lubię nowe technologie 💻",
    "Uwielbiam wędkowanie i naturę nad Odrą 🎣",
    "Gram w zespole szkolnym, kocham muzykę 🥁",
    "Szukam szczerej relacji i dobrego kontaktu ❤️",
]


def _build_test_users() -> list[dict]:
    users = []
    female_idx = 0
    male_idx = 0

    for i in range(30):
        user_id = TEST_ID_START + i
        age = 16 + (i // 6)

        if i % 2 == 0:
            gender = "F"
            looking_for = "M"
            name = FEMALE_NAMES[female_idx]
            bio = FEMALE_BIOS[female_idx]
            username = f"test_{name.lower().replace('ł', 'l')}_{user_id}"
            female_idx += 1
        else:
            gender = "M"
            looking_for = "F"
            name = MALE_NAMES[male_idx]
            bio = MALE_BIOS[male_idx]
            username = f"test_{name.lower().replace('ł', 'l')}_{user_id}"
            male_idx += 1

        users.append(
            {
                "user_id": user_id,
                "username": username,
                "name": name,
                "age": age,
                "gender": gender,
                "looking_for": looking_for,
                "city": "Opole",
                "search_city": "Opole",
                "bio": bio,
            }
        )

    return users


TEST_USERS = _build_test_users()

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


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    db_file = Path(DB_PATH)
    if not db_file.is_file():
        raise SystemExit(f"Database not found: {db_file.resolve()}")

    conn = sqlite3.connect(DB_PATH)
    try:
        for u in TEST_USERS:
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
                    "",
                    u["search_city"],
                ),
            )
        conn.commit()

        cur = conn.execute(
            f"""SELECT user_id, name, age, gender, looking_for, city, search_city, is_active
               FROM users WHERE user_id BETWEEN {TEST_ID_START} AND {TEST_ID_END}
               ORDER BY user_id"""
        )
        rows = cur.fetchall()
        print(f"Seeded {len(rows)} test users in {db_file.resolve()}:\n")
        for row in rows:
            print(
                f"  {row[0]} | {row[1]}, {row[2]} | {row[3]}->{row[4]} | "
                f"city={row[5]} search={row[6]} active={row[7]}"
            )

        count = conn.execute(
            f"""SELECT COUNT(*) FROM users
               WHERE city = 'Opole'
                 AND age BETWEEN 16 AND 20
                 AND user_id BETWEEN {TEST_ID_START} AND {TEST_ID_END}"""
        ).fetchone()[0]
        print(f"\nVerification: {count} Opole profiles aged 16-20")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
