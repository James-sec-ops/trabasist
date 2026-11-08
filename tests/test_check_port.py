"""Tests for check_port (uses a temp database and a local listener)."""
import os
import socket
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["TRABASIST_DB"] = os.path.join(tmp, "test.db")

from trabasist_server.db import get_connection, init_db
from trabasist_server.tools.check_port import check_port
from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.close_case import close_case

failures = []


def check(name, ok):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        failures.append(name)


def refuses(**kw):
    try:
        check_port(**kw)
        return False
    except ValueError:
        return True


init_db()
cid = open_case(symptom="port test", device="local")["case_id"]

listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(5)
open_port = listener.getsockname()[1]

spare = socket.socket()
spare.bind(("127.0.0.1", 0))
closed_port = spare.getsockname()[1]
spare.close()

r = check_port(host="127.0.0.1", port=open_port, timeout=5, case_id=cid)
check("open port detected", r["state"] == "open")
check("step attached to case", r["step_id"] is not None)

r = check_port(host="127.0.0.1", port=closed_port, timeout=5)
check("closed port detected", r["state"] == "closed")
check("works without a case", r["step_id"] is None)

r = check_port(host="192.0.2.1", port=80, timeout=2)
check("unreachable address is not open", r["state"] in ("timeout", "error"))

for bad in ["", "a;b", "-n 5", "x y"]:
    check(f"refuses host {bad!r}", refuses(host=bad, port=80))
for bad in [0, 65536, "80", True, None]:
    check(f"refuses port {bad!r}", refuses(host="127.0.0.1", port=bad))
for bad in [0, 11, "3", True]:
    check(f"refuses timeout {bad!r}", refuses(host="127.0.0.1", port=80, timeout=bad))
check("refuses missing case", refuses(host="127.0.0.1", port=80, case_id=999))

conn = get_connection()
n_audit = conn.execute("SELECT COUNT(*) AS n FROM audit_log WHERE tool='check_port'").fetchone()["n"]
n_steps = conn.execute("SELECT COUNT(*) AS n FROM steps WHERE case_id=?", (cid,)).fetchone()["n"]
conn.close()
check(f"every check audited (3 runs, found {n_audit})", n_audit == 3)
check("only the case check created a step", n_steps == 1)

close_case(case_id=cid, root_cause="test", resolution="test")
check("refuses closed case", refuses(host="127.0.0.1", port=open_port, case_id=cid))

listener.close()
print()
print("ALL PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)

