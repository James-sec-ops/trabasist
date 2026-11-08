import json, os, tempfile
from pathlib import Path
from trabasist_server.db import get_connection, init_db
from trabasist_server.tools.run_device_command import run_device_command
from trabasist_server.tools.inventory import get_device, get_credentials

passed = failed = 0

def check(label, good):
    global passed, failed
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label)

def audit_rows():
    init_db()
    c = get_connection()
    try:
        return [dict(r) for r in c.execute(
            "SELECT * FROM audit_log WHERE tool='run_device_command' ORDER BY id")]
    finally:
        c.close()

def new_rows(before):
    return audit_rows()[before:]

# 1. allowed command
n = len(audit_rows())
r = run_device_command("kali-lab", "uptime")
check("uptime ok", r["status"] == "ok" and "load average" in r["output"])
rows = new_rows(n)
check("uptime audited once", len(rows) == 1 and rows[0]["command"] == "uptime")
print("   output:", r.get("output", r.get("reason")))

# 2. allowed command with parameter
r = run_device_command("kali-lab", "journalctl", {"lines": 5})
check("journalctl with lines ok", r["status"] == "ok")
check("no TBX prompt in output", "TBX>" not in r.get("output", ""))

# 3. refused: not in allowlist
n = len(audit_rows())
r = run_device_command("kali-lab", "rm -rf /")
rows = new_rows(n)
check("free-form command refused", r["status"] == "refused")
check("refusal audited with command", len(rows) == 1 and "rm -rf /" in rows[0]["command"]
      and rows[0]["result_summary"].startswith("REFUSED"))

# 4. refused: injection in parameter
n = len(audit_rows())
r = run_device_command("kali-lab", "systemctl_status", {"service": "ssh; id"})
check("injection refused", r["status"] == "refused" and len(new_rows(n)) == 1)

# 5. refused: unknown device
n = len(audit_rows())
r = run_device_command("no-such-device", "uptime")
check("unknown device refused", r["status"] == "refused" and len(new_rows(n)) == 1)

# 6. bad case id: input error, not audited
n = len(audit_rows())
try:
    run_device_command("kali-lab", "uptime", case_id=99999)
    check("missing case rejected", False)
except ValueError:
    check("missing case rejected", True)
check("missing case not audited", len(new_rows(n)) == 0)

# 7. connection failure is audited
tmp = Path(tempfile.mkdtemp()) / "devices.json"
tmp.write_text(json.dumps({"devices": [{"name": "ghost", "address": "192.0.2.1",
    "platform": "linux", "port": 22, "credentials": "KALI"}]}))
os.environ["TRABASIST_DEVICES"] = str(tmp)
n = len(audit_rows())
r = run_device_command("ghost", "uptime")
del os.environ["TRABASIST_DEVICES"]
rows = new_rows(n)
check("unreachable device failed", r["status"] == "failed")
check("failure audited", len(rows) == 1 and rows[0]["result_summary"].startswith("FAILED"))

# 8. password never in the audit log
pw = get_credentials(get_device("kali-lab").credentials).password
check("password not in audit rows", all(pw not in json.dumps(x) for x in audit_rows()))

print(f"\n{passed} passed, {failed} failed")
