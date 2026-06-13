#!/usr/bin/env python3
"""Remove test users (user_id 900001–900030) and related data."""

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "database.db")

TEST_ID_START = 900001
TEST_ID_END = 900030
TEST_IDS = list(range(TEST_ID_START, TEST_ID_END + 1))


def delete_user(conn: sqlite3.Connection, user_id: int):
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


def main():
    db_file = Path(DB_PATH)
    if not db_file.is_file():
        raise SystemExit(f"Database not found: {db_file.resolve()}")

    conn = sqlite3.connect(DB_PATH)
    try:
        before = conn.execute(
            f"SELECT COUNT(*) FROM users WHERE user_id BETWEEN {TEST_ID_START} AND {TEST_ID_END}"
        ).fetchone()[0]

        for user_id in TEST_IDS:
            delete_user(conn, user_id)
        conn.commit()

        after = conn.execute(
            f"SELECT COUNT(*) FROM users WHERE user_id BETWEEN {TEST_ID_START} AND {TEST_ID_END}"
        ).fetchone()[0]

        print(f"Removed {before - after} test users from {db_file.resolve()}")
        print(f"Remaining test users: {after}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
