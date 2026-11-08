import os
import tempfile

tmp = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["TRABASIST_DB"] = tmp

from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.log_step import log_step
from trabasist_server.db import get_connection

c = open_case("Installer fails with error 2735", "2735", "srv01")["case_id"]

r = log_step(c, "Checked disk space", "df -h", "/ 40% used", "ruled_out")
print("Valid step:", "PASS" if r["step_id"] == 1 else "FAIL", r)

def refused(label, **kw):
    try:
        log_step(**kw)
        print(label + ":", "FAIL (was accepted)")
    except ValueError:
        print(label + ":", "PASS")

refused("Bad outcome refused", case_id=c, action="x", outcome="maybe")
refused("Missing case refused", case_id=999, action="x")
refused("Empty action refused", case_id=c, action="  ")

log_step(c, "Read config", "show run", "login ok password=Hunter2 token: abc123", "inconclusive")
conn = get_connection()
stored = conn.execute("SELECT result FROM steps WHERE id = 2").fetchone()["result"]
print("Secrets redacted:", "PASS" if ("Hunter2" not in stored and "abc123" not in stored) else "FAIL", "->", stored)

conn.execute("UPDATE cases SET status='closed' WHERE id = ?", (c,))
conn.commit()
conn.close()
refused("Closed case refused", case_id=c, action="x")
