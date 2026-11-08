"""Tests for ping_host (uses a temp database)."""
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["TRABASIST_DB"] = os.path.join(tmp, "test.db")

from trabasist_server.db import get_connection, init_db
from trabasist_server.tools.ping_host import ping_host
from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.close_case import close_case

failures = []


def check(name, ok):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        failures.append(name)


def refuses(**kw):
    try:
        ping_host(**kw)
        return False
    except ValueError:
        return True


init_db()
cid = open_case(symptom="ping test", device="local")["case_id"]

r = ping_host(host="127.0.0.1", count=2, case_id=cid)
check("localhost is reachable", r["reachable"] is True)
check("step attached to case", r["step_id"] is not None)

r = ping_host(host="127.0.0.1", count=1)
check("works without a case", r["reachable"] and r["step_id"] is None)

r = ping_host(host="192.0.2.1", count=1)
check("unreachable address reported as not reachable", r["reachable"] is False)

for bad in ["", "a;b", "-n 5", "host&calc", "x y"]:
    check(f"refuses host {bad!r}", refuses(host=bad))
for bad in [0, 11, -1, "4", True]:
    check(f"refuses count {bad!r}", refuses(host="127.0.0.1", count=bad))
check("refuses missing case", refuses(host="127.0.0.1", case_id=999))

conn = get_connection()
n_audit = conn.execute("SELECT COUNT(*) AS n FROM audit_log WHERE tool='ping_host'").fetchone()["n"]
n_steps = conn.execute("SELECT COUNT(*) AS n FROM steps WHERE case_id=?", (cid,)).fetchone()["n"]
conn.close()
check("every ping audited (3 runs)", n_audit == 3)
check("only the case ping created a step", n_steps == 1)

close_case(case_id=cid, root_cause="test", resolution="test")
check("refuses closed case", refuses(host="127.0.0.1", case_id=cid))

print()
print("ALL PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)
