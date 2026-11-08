"""Tests for diag_common: validators, safe runner, audit and case logging."""
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["TRABASIST_DB"] = os.path.join(tmp, "test.db")

from trabasist_server.db import get_connection, init_db
from trabasist_server.tools.diag_common import (
    validate_host, validate_port, check_case_open, run_fixed, record_diagnostic,
)
from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.close_case import close_case

failures = []


def check(name, ok):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        failures.append(name)


def refuses(fn, *args):
    try:
        fn(*args)
        return False
    except ValueError:
        return True


init_db()

# Host validation
check("accepts IPv4", validate_host("192.168.1.10") == "192.168.1.10")
check("accepts hostname", validate_host("srv01.example.com") == "srv01.example.com")
check("accepts IPv6", validate_host("::1") == "::1")
for bad in ["", "  ", "a b", "host;rm -rf", "host&calc", "-n 100", "a|b", "$(x)", "host`x`", "fe80::1%eth0", "a" * 300, "-bad.com", "bad-.com"]:
    check(f"refuses host {bad[:20]!r}", refuses(validate_host, bad))
check("refuses non-text host", refuses(validate_host, 123))

# Port validation
check("accepts port 443", validate_port(443) == 443)
for bad in [0, 65536, -1, "80", True, None, 80.5]:
    check(f"refuses port {bad!r}", refuses(validate_port, bad))

# Safe runner
code, out = run_fixed([sys.executable, "-c", "print('hello')"])
check("run_fixed runs a fixed command", code == 0 and "hello" in out)
code, out = run_fixed(["no_such_program_xyz"])
check("run_fixed handles missing program", code == -1 and "not found" in out)
code, out = run_fixed([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
check("run_fixed times out", code == -1 and "timed out" in out)

# Case checks
check("case_id None is allowed", check_case_open(None) is None)
check("refuses missing case", refuses(check_case_open, 999))
check("refuses bad case id", refuses(check_case_open, "1"))

case = open_case(symptom="Test symptom", device="srv01")
cid = case["case_id"]
check("open case passes check", check_case_open(cid) is None)

# Audit only (no case)
r = record_diagnostic("ping_host", "10.0.0.1", "ping -n 2 10.0.0.1", "Reply from 10.0.0.1", None)
check("audit written without case", r["audit_id"] >= 1 and r["step"] is None)

# Audit plus case step, with redaction
r = record_diagnostic("ping_host", "10.0.0.1", "ping -n 2 10.0.0.1",
                      "password=SuperSecret123 reply ok", cid)
check("step created on case", r["step"] is not None and r["step"]["case_id"] == cid)
conn = get_connection()
audit = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
step = conn.execute("SELECT * FROM steps WHERE case_id = ?", (cid,)).fetchone()
conn.close()
check("audit row has tool and device", audit["tool"] == "ping_host" and audit["device"] == "10.0.0.1")
check("secret removed from audit", "SuperSecret123" not in (audit["result_summary"] or ""))
check("secret removed from step", "SuperSecret123" not in (step["result"] or ""))

# Closed case refused
close_case(case_id=cid, root_cause="test", resolution="test")
check("refuses closed case", refuses(check_case_open, cid))

print()
print("ALL PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)
