#!/usr/bin/env python3
"""Insert 300 demo profiles (20 personas × 15 Polish cities) for CursorRandka.

Requires seed_data/genders.json and seed_data/photos.json (from upload_test_photos.py).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from seed_logic import run_seed_cli

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "database.db")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    db_file = Path(DB_PATH)
    if not db_file.is_file():
        raise SystemExit(f"Database not found: {db_file.resolve()}")

    run_seed_cli(DB_PATH)


if __name__ == "__main__":
    main()
