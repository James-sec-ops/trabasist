import shutil
from trabasist_server.db import db_path, init_db
from trabasist_server.tools.lookup_error_code import seed_starter_codes, lookup_error_code

src = str(db_path())
shutil.copy2(src, src + ".bak")
init_db()
print("database:", src)
print("added:", seed_starter_codes())
r = lookup_error_code("2735")
print("check 2735:", r["status"], "-", r["matches"][0]["meaning"])
