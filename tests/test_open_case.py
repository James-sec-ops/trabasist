import os
import tempfile

# Use a throwaway database so the real one stays clean
tmp = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["TRABASIST_DB"] = tmp

from trabasist_server.tools.open_case import open_case
from trabasist_server.db import get_connection

r = open_case("Installer fails with error 2735", "2735", "srv01", "Windows Server lab")
print("Valid case:", "PASS" if r["case_id"] == 1 and r["status"] == "open" else "FAIL", r)

for label, kwargs in [
    ("Empty symptom refused", dict(symptom="  ")),
    ("Bad error code refused", dict(symptom="x", error_code="2735; DROP TABLE cases")),
    ("Bad device refused", dict(symptom="x", device="srv01 && whoami")),
]:
    try:
        open_case(**kwargs)
        print(label + ":", "FAIL (was accepted)")
    except ValueError as e:
        print(label + ":", "PASS")

conn = get_connection()
n = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
conn.close()
print("Rows stored:", "PASS" if n == 1 else f"FAIL ({n})")
