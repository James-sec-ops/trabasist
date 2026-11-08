"""Add the starter error codes to the database. Safe to run again (adds only missing ones).

Run from the project folder:  python tests/seed_error_codes.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trabasist_server.db import db_path, init_db
from trabasist_server.tools.lookup_error_code import seed_starter_codes, lookup_error_code

src = Path(db_path())
if src.exists():
    shutil.copy2(src, str(src) + ".bak")
init_db()
print("database:", src)
print("added:", seed_starter_codes())
r = lookup_error_code("2735")
print("check 2735:", r["status"], "-", r["matches"][0]["meaning"])
