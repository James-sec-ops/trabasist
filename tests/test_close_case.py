import os
import tempfile

tmp = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["TRABASIST_DB"] = tmp

from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.log_step import log_step
from trabasist_server.tools.close_case import close_case
from trabasist_server.db import get_connection

c = open_case("Installer fails with error 2735", "2735", "srv01")["case_id"]
log_step(c, "Checked disk space", "df -h", "40% used", "ruled_out")

r = close_case(c, "Windows Installer service was stopped", "Started the service and re-ran the installer")
print("Valid close:", "PASS" if r["status"] == "closed" and r["steps_recorded"] == 1 else "FAIL", r)

conn = get_connection()
row = conn.execute("SELECT status, closed_at, root_cause FROM cases WHERE id = ?", (c,)).fetchone()
print("Stored correctly:", "PASS" if row["status"] == "closed" and row["closed_at"] and row["root_cause"] else "FAIL")
conn.close()

def refused(label, **kw):
    try:
        close_case(**kw)
        print(label + ":", "FAIL (was accepted)")
    except ValueError:
        print(label + ":", "PASS")

refused("Already closed refused", case_id=c, root_cause="x", resolution="y")
refused("Missing case refused", case_id=999, root_cause="x", resolution="y")
c2 = open_case("Second issue")["case_id"]
refused("Empty root cause refused", case_id=c2, root_cause="  ", resolution="y")
refused("Empty resolution refused", case_id=c2, root_cause="x", resolution="")
