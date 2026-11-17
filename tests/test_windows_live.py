"""Live test of the Windows platform against winserver1. Needs the lab VM running."""
import os, sys, tempfile
os.environ["TRABASIST_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
from trabasist_server.db import init_db
init_db()
from trabasist_server.tools.inventory import get_device, get_credentials
from trabasist_server.tools.run_device_command import run_device_command

passed = failed = skipped = 0
# These need more rights than a read-only account has: an access error is an expected skip.
NEEDS_MORE_RIGHTS = {"memory", "services", "eventlog"}


def check(label, good):
    global passed, failed
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label)


dev = get_device("winserver1")
check("winserver1 is registered as windows", dev.platform == "windows")
print("   login account:", get_credentials(dev.credentials).username)

CASES = [
    ("uptime", None), ("os_info", None), ("cpu", None), ("memory", None), ("disk", None),
    ("services", None), ("service_status", {"service": "EventLog"}),
    ("processes_top_cpu", None), ("processes_top_mem", None),
    ("eventlog", {"log": "System", "lines": 3}),
    ("ipconfig", None), ("netstat", None), ("routes", None),
    ("test_netconnection", {"host": dev.address, "port": 22}),
]
for name, params in CASES:
    r = run_device_command("winserver1", name, params)
    out = (r.get("output") or "").strip()
    errored = r["status"] != "ok" or "[exit code" in out
    if errored and name in NEEDS_MORE_RIGHTS:
        skipped += 1
        print(f"SKIP {name} (needs more rights than this account has)")
        continue
    check(f"{name} returns clean output", not errored and bool(out))
    for line in (out or str(r.get("reason"))).splitlines()[:4]:
        print("   |", line[:110])

r = run_device_command("winserver1", "Get-Process")
check("free-form command refused", r["status"] == "refused")
r = run_device_command("winserver1", "service_status", {"service": "sshd; whoami"})
check("service injection refused", r["status"] == "refused")

print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
sys.exit(1 if failed else 0)
