"""Live test of the Windows platform against winserver1. Needs the lab VM running."""
import os, sys, tempfile
os.environ["TRABASIST_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
from trabasist_server.db import init_db
init_db()
from trabasist_server.tools.inventory import get_device, get_credentials
from trabasist_server.tools.run_device_command import run_device_command

passed = failed = 0


def check(label, good):
    global passed, failed
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label)


dev = get_device("winserver1")
check("winserver1 is registered as windows", dev.platform == "windows")
print("   login account:", get_credentials(dev.credentials).username)

CASES = [
    ("uptime", None), ("os_info", None), ("cpu", None), ("memory", None), ("disk", None),
    ("services", None), ("service_status", {"service": "sshd"}),
    ("processes_top_cpu", None), ("processes_top_mem", None),
    ("eventlog", {"log": "System", "lines": 3}),
    ("ipconfig", None), ("netstat", None), ("routes", None),
    ("test_netconnection", {"host": dev.address, "port": 22}),
]
for name, params in CASES:
    r = run_device_command("winserver1", name, params)
    out = r.get("output") or ""
    check(f"{name} ok with output", r["status"] == "ok" and bool(out.strip()))
    if r["status"] != "ok":
        print("   ->", r["status"], r.get("reason"))
    elif name in ("uptime", "service_status"):
        for line in out.strip().splitlines()[:6]:
            print("   |", line)

r = run_device_command("winserver1", "Get-Process")
check("free-form command refused", r["status"] == "refused")
r = run_device_command("winserver1", "service_status", {"service": "sshd; whoami"})
check("service injection refused", r["status"] == "refused")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
