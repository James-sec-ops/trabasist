"""Tests for traceroute_host (uses a temp database)."""
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["TRABASIST_DB"] = os.path.join(tmp, "test.db")

from trabasist_server.db import get_connection, init_db
from trabasist_server.tools.traceroute_host import traceroute_host
from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.close_case import close_case

failures = []


def check(name, ok):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        failures.append(name)


def refuses(**kw):
    try:
        traceroute_host(**kw)
        return False
    except ValueError:
        return True


init_db()
cid = open_case(symptom="traceroute test", device="local")["case_id"]

r = traceroute_host(host="127.0.0.1", max_hops=5, case_id=cid)
print("      hops:", r["hops_seen"], "completed:", r["completed"])
check("localhost trace completes", r["completed"] is True and r["hops_seen"] >= 1)
check("step attached to case", r["step_id"] is not None)

r = traceroute_host(host="127.0.0.1", max_hops=5)
check("works without a case", r["step_id"] is None)

for bad in ["", "a;b", "-h 99", "x y", "host&calc"]:
    check(f"refuses host {bad!r}", refuses(host=bad))
for bad in [0, 31, -1, "5", True]:
    check(f"refuses max_hops {bad!r}", refuses(host="127.0.0.1", max_hops=bad))
check("refuses missing case", refuses(host="127.0.0.1", case_id=999))

conn = get_connection()
n_audit = conn.execute("SELECT COUNT(*) AS n FROM audit_log WHERE tool='traceroute_host'").fetchone()["n"]
n_steps = conn.execute("SELECT COUNT(*) AS n FROM steps WHERE case_id=?", (cid,)).fetchone()["n"]
conn.close()
check(f"every trace audited (2 runs, found {n_audit})", n_audit == 2)
check("only the case trace created a step", n_steps == 1)

close_case(case_id=cid, root_cause="test", resolution="test")
check("refuses closed case", refuses(host="127.0.0.1", case_id=cid))

print()
print("ALL PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)

