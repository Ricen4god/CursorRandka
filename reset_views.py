#!/usr/bin/env python3
"""Clear views table for testing browse flow."""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "database.db")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Clear views for browse testing")
    parser.add_argument(
        "user_id",
        nargs="?",
        type=int,
        help="Clear views only for this viewer_id (default: all views)",
    )
    args = parser.parse_args()

    db_file = Path(DB_PATH)
    if not db_file.is_file():
        raise SystemExit(f"Database not found: {db_file.resolve()}")

    conn = sqlite3.connect(DB_PATH)
    try:
        if args.user_id is not None:
            cur = conn.execute(
                "SELECT COUNT(*) FROM views WHERE viewer_id = ?", (args.user_id,)
            )
            count = cur.fetchone()[0]
            conn.execute("DELETE FROM views WHERE viewer_id = ?", (args.user_id,))
            conn.commit()
            print(f"Cleared {count} views for user {args.user_id}")
        else:
            cur = conn.execute("SELECT COUNT(*) FROM views")
            count = cur.fetchone()[0]
            conn.execute("DELETE FROM views")
            conn.commit()
            print(f"Cleared all {count} views")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
