"""Step 4 tests: classifier and gate wired into run_device_command (offline, fake SSH)."""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TMP = Path(tempfile.mkdtemp())
os.environ["TRABASIST_DB"] = str(TMP / "old.db")
os.environ["TRABASIST_DEVICES"] = str(TMP / "devices.json")

from trabasist_server.db import get_connection, init_db  # noqa: E402
from trabasist_server.tools.audit import write_audit  # noqa: E402
import trabasist_server.tools.run_device_command as rdc  # noqa: E402
from trabasist_server.tools.ssh_conn import DeviceConnectionError  # noqa: E402

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name)


def columns():
    c = get_connection()
    try:
        return {r["name"] for r in c.execute("PRAGMA table_info(audit_log)")}
    finally:
        c.close()


def rows(tool):
    init_db()
    c = get_connection()
    try:
        return [dict(r) for r in c.execute("SELECT * FROM audit_log WHERE tool=? ORDER BY id", (tool,))]
    finally:
        c.close()


NEW_COLS = {"tier", "decision", "rule", "tag", "change_mode"}

# ---- Migration of an old-style database ----
old = sqlite3.connect(TMP / "old.db")
old.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "created_at TEXT NOT NULL DEFAULT (datetime('now')), tool TEXT NOT NULL, "
            "device TEXT, command TEXT, result_summary TEXT)")
old.execute("INSERT INTO audit_log (tool, device, command, result_summary) VALUES ('t','d','c','s')")
old.commit()
old.close()
init_db()
check("migration adds the five columns", NEW_COLS <= columns())
r = rows("t")
check("old row survives with empty policy fields",
      len(r) == 1 and r[0]["command"] == "c" and r[0]["tier"] is None and r[0]["decision"] is None)
init_db()
init_db()
check("migration is idempotent", NEW_COLS <= columns())

# ---- Fresh database from here on ----
os.environ["TRABASIST_DB"] = str(TMP / "new.db")
init_db()
check("fresh database has the columns", NEW_COLS <= columns())

# ---- write_audit ----
write_audit("w", "dev", "cmd", "sum")
r = rows("w")[-1]
check("old call style still works", r["tier"] is None and r["tag"] is None and r["change_mode"] is None)
write_audit("w", "dev", "cmd", "sum", tier=2, decision="allow", rule="r", tag="lab", change_mode=True)
r = rows("w")[-1]
check("policy fields stored",
      (r["tier"], r["decision"], r["rule"], r["tag"], r["change_mode"]) == (2, "allow", "r", "lab", 1))
before = len(rows("w"))
for label, kw in [("tier True", {"tier": True}), ("tier 0", {"tier": 0}), ("tier 4", {"tier": 4}),
                  ("tier '1'", {"tier": "1"}), ("change_mode 'yes'", {"change_mode": "yes"}),
                  ("change_mode 1", {"change_mode": 1})]:
    try:
        write_audit("w", "dev", "cmd", "sum", **kw)
        check(f"write_audit rejects {label}", False)
    except ValueError:
        check(f"write_audit rejects {label}", True)
check("rejected values wrote nothing", len(rows("w")) == before)

# ---- Inventory and fakes ----
def entry(name, platform="linux", **extra):
    d = {"name": name, "address": "192.0.2.10", "platform": platform, "credentials": "KALI"}
    d.update(extra)
    return d


(TMP / "devices.json").write_text(json.dumps({"devices": [
    entry("lab-on", tag="lab", change_mode=True),
    entry("lab-off", tag="lab", change_mode=False),
    entry("prod-on", tag="production", change_mode=True),
    entry("old-style"),
    entry("win-lab", platform="windows", tag="lab", change_mode=True),
    entry("bad-tag", tag="dev"),
]}), encoding="utf-8")

STATE = {"calls": 0, "mode": "ok"}


def fake_run_command(dev, creds, command_text, *a, **k):
    STATE["calls"] += 1
    if STATE["mode"] == "fail":
        raise DeviceConnectionError("connection timed out or host unreachable")
    return "up 1 day, load average: 0.00"


rdc.run_command = fake_run_command
rdc.get_credentials = lambda label: object()

TAGS = {"lab-on": ("lab", 1), "lab-off": ("lab", 0), "prod-on": ("production", 1),
        "old-style": ("production", 0), "win-lab": ("lab", 1)}

# ---- check_device_command ----
CASES = [
    ("lab-on", "systemctl restart nginx", "allow", 2),
    ("lab-on", "systemctl restart sshd", "needs_approval", 3),
    ("lab-on", "reboot", "needs_approval", 3),
    ("lab-on", "uptime; reboot", "needs_approval", 3),
    ("lab-on", "uptime | sh", "needs_approval", 3),
    ("lab-on", "uptime", "allow", 1),
    ("lab-off", "systemctl restart nginx", "refused", 2),
    ("lab-off", "reboot", "refused", 3),
    ("lab-off", "uptime", "allow", 1),
    ("prod-on", "systemctl restart nginx", "needs_approval", 2),
    ("prod-on", "reboot", "needs_approval", 3),
    ("old-style", "systemctl restart nginx", "refused", 2),
    ("old-style", "uptime", "allow", 1),
    ("win-lab", "Restart-Service -Name Spooler", "allow", 2),
    ("win-lab", "Restart-Service -Name sshd", "needs_approval", 3),
    ("win-lab", "Restart-Computer", "needs_approval", 3),
    ("win-lab", "ipconfig /all", "allow", 1),
]
calls_before = STATE["calls"]
bad = []
for dev, cmd, want, tier in CASES:
    n = len(rows("check_device_command"))
    r = rdc.check_device_command(dev, cmd)
    new = rows("check_device_command")[n:]
    tag, cm = TAGS[dev]
    ok = (r["status"] == "checked" and r["decision"] == want and r["tier"] == tier
          and r["executed"] is False and len(new) == 1
          and (new[0]["tier"], new[0]["decision"], new[0]["tag"], new[0]["change_mode"]) == (tier, want, tag, cm)
          and new[0]["result_summary"].endswith("not executed"))
    if not ok:
        bad.append((dev, cmd, want, tier, r))
check(f"check_device_command decisions and audit rows ({len(CASES)} cases)", not bad)
for b in bad[:5]:
    print("   ", b)
check("check_device_command never runs anything", STATE["calls"] == calls_before)

r = rdc.check_device_command("lab-on", 123)
check("non-text command is not allowed", r["status"] == "checked" and r["decision"] != "allow" and r["tier"] == 3)
r = rdc.check_device_command("bad-tag", "uptime")
check("skipped device reports its real reason",
      r["status"] == "refused" and "skipped" in r["reason"] and "tag" in r["reason"])
r = rdc.check_device_command("no-such-device", "uptime")
check("unknown device refused", r["status"] == "refused" and "not in inventory" in r["reason"])
r = rdc.check_device_command(None, "uptime")
check("device None refused", r["status"] == "refused")
check("a bad entry does not hide good devices", rdc.check_device_command("lab-on", "uptime")["status"] == "checked")

# ---- run_device_command: named path ----
STATE["calls"] = 0
n = len(rows("run_device_command"))
r = rdc.run_device_command("lab-on", "uptime")
row = rows("run_device_command")[n:]
check("named command runs", r["status"] == "ok" and STATE["calls"] == 1 and "load average" in r["output"])
check("named command audited with tier, rule, decision, tag, change mode",
      len(row) == 1 and (row[0]["tier"], row[0]["decision"], row[0]["rule"], row[0]["tag"], row[0]["change_mode"])
      == (1, "allow", "tier1:allowlist:uptime", "lab", 1))

n = len(rows("run_device_command"))
r = rdc.run_device_command("old-style", "uptime")
row = rows("run_device_command")[n:]
check("old-style device runs read-only command", r["status"] == "ok")
check("old-style device audited as production, change mode off",
      len(row) == 1 and row[0]["tag"] == "production" and row[0]["change_mode"] == 0)

n = len(rows("run_device_command"))
r = rdc.run_device_command("win-lab", "ipconfig")
row = rows("run_device_command")[n:]
check("windows named command is Tier 1", r["status"] == "ok" and row[0]["tier"] == 1 and row[0]["tag"] == "lab")

STATE["calls"] = 0
n = len(rows("run_device_command"))
r = rdc.run_device_command("lab-on", "rm -rf /")
row = rows("run_device_command")[n:]
check("free-form text as a name is refused and not run", r["status"] == "refused" and STATE["calls"] == 0)
check("refusal audited with decision, tag and no tier",
      len(row) == 1 and row[0]["decision"] == "refused" and row[0]["tag"] == "lab"
      and row[0]["tier"] is None and row[0]["result_summary"].startswith("REFUSED"))

r = rdc.run_device_command("lab-on", "systemctl_status", {"service": "ssh; id"})
check("injection in a parameter refused", r["status"] == "refused" and STATE["calls"] == 0)
r = rdc.run_device_command("bad-tag", "uptime")
check("skipped device refused with its reason", r["status"] == "refused" and "skipped" in r["reason"] and STATE["calls"] == 0)
r = rdc.run_device_command("no-such-device", "uptime")
check("unknown device refused", r["status"] == "refused" and STATE["calls"] == 0)

STATE["mode"] = "fail"
n = len(rows("run_device_command"))
r = rdc.run_device_command("lab-on", "uptime")
row = rows("run_device_command")[n:]
check("connection failure audited with tier and decision",
      r["status"] == "failed" and len(row) == 1 and row[0]["tier"] == 1
      and row[0]["decision"] == "allow" and row[0]["result_summary"].startswith("FAILED"))
STATE["mode"] = "ok"

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
