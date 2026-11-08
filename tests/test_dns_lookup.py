"""Tests for dns_lookup (temp database). Live checks need internet access."""
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["TRABASIST_DB"] = os.path.join(tmp, "test.db")

from trabasist_server.db import get_connection, init_db
from trabasist_server.tools.dns_lookup import dns_lookup
from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.close_case import close_case

failures = []


def check(name, ok):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        failures.append(name)


def refuses(**kw):
    try:
        dns_lookup(**kw)
        return False
    except ValueError:
        return True


init_db()
cid = open_case(symptom="dns test", device="local")["case_id"]

r = dns_lookup(name="example.com", record_type="A", case_id=cid)
print("      example.com ->", r["state"], r["answers"], "via", r["resolver"])
check("live A lookup works (needs internet)", r["state"] == "ok" and len(r["answers"]) >= 1)
check("step attached to case", r["step_id"] is not None)

r = dns_lookup(name="no-such-name-xyz.invalid", record_type="a")
check("invalid name gives nxdomain (or timeout offline)", r["state"] in ("nxdomain", "timeout", "error"))
check("works without a case", r["step_id"] is None)

r = dns_lookup(name="example.com", record_type="A", server="1.1.1.1")
print("      via 1.1.1.1 ->", r["state"], r["answers"])
check("custom server is used", r["resolver"] == "1.1.1.1")

for bad in ["", "a;b", "-n 5", "x y", "host&calc"]:
    check(f"refuses name {bad!r}", refuses(name=bad))
for bad in ["ANY", "AXFR", "", None, 5]:
    check(f"refuses record type {bad!r}", refuses(name="example.com", record_type=bad))
check("refuses PTR on a hostname", refuses(name="example.com", record_type="PTR"))
check("refuses A on an IP", refuses(name="8.8.8.8", record_type="A"))
check("refuses server hostname", refuses(name="example.com", server="dns.google"))
check("refuses bad server", refuses(name="example.com", server="1.1.1.1;ls"))
check("refuses missing case", refuses(name="example.com", case_id=999))

conn = get_connection()
n_audit = conn.execute("SELECT COUNT(*) AS n FROM audit_log WHERE tool='dns_lookup'").fetchone()["n"]
n_steps = conn.execute("SELECT COUNT(*) AS n FROM steps WHERE case_id=?", (cid,)).fetchone()["n"]
conn.close()
check(f"every lookup audited (3 runs, found {n_audit})", n_audit == 3)
check("only the case lookup created a step", n_steps == 1)

close_case(case_id=cid, root_cause="test", resolution="test")
check("refuses closed case", refuses(name="example.com", case_id=cid))

print()
print("ALL PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)
