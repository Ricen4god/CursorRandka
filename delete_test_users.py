#!/usr/bin/env python3
"""Remove demo/test users (900001–900030 and 910001–910300) and related data."""

import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

from seed_logic import delete_all_test_users

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "database.db")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    db_file = Path(DB_PATH)
    if not db_file.is_file():
        raise SystemExit(f"Database not found: {db_file.resolve()}")

    conn = sqlite3.connect(DB_PATH)
    try:
        removed = delete_all_test_users(conn)
        after = conn.execute(
            """SELECT COUNT(*) FROM users
               WHERE user_id BETWEEN 900001 AND 900030
                  OR user_id BETWEEN 910001 AND 910300
                  OR user_id >= 910000"""
        ).fetchone()[0]
        print(f"Removed {removed} test users from {db_file.resolve()}")
        print(f"Remaining test users: {after}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
