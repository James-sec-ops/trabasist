"""Step 5 tests: check_device_command is exposed by the server (offline)."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TMP = Path(tempfile.mkdtemp())
os.environ["TRABASIST_DB"] = str(TMP / "t.db")
os.environ["TRABASIST_DEVICES"] = str(TMP / "devices.json")
(TMP / "devices.json").write_text(json.dumps({"devices": [
    {"name": "lab-on", "address": "192.0.2.10", "platform": "linux",
     "credentials": "KALI", "tag": "lab", "change_mode": True},
    {"name": "plain", "address": "192.0.2.11", "platform": "linux", "credentials": "KALI"},
]}), encoding="utf-8")

import trabasist_server.server as server  # noqa: E402

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


source = Path(server.__file__).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
check("tool is registered with the MCP decorator",
      "@mcp.tool()\ndef check_device_command(" in source)

fn = getattr(server, "check_device_command", None)
check("server exposes check_device_command", callable(fn))
if callable(fn):
    r = fn("lab-on", "systemctl restart nginx")
    check("lab change is allowed by policy but not executed",
          r["status"] == "checked" and r["decision"] == "allow" and r["tier"] == 2 and r["executed"] is False)
    r = fn("lab-on", "reboot")
    check("reboot needs approval", r["decision"] == "needs_approval" and r["tier"] == 3 and r["executed"] is False)
    r = fn("plain", "systemctl restart nginx")
    check("device with no tag or change mode is refused", r["decision"] == "refused" and r["executed"] is False)
    r = fn("lab-on", "uptime; reboot")
    check("chained command is Tier 3", r["tier"] == 3 and r["decision"] != "allow")
    r = fn("no-such-device", "uptime")
    check("unknown device refused", r["status"] == "refused")

ins = server.INSTRUCTIONS
for phrase in ("check_device_command", "cannot approve", "never an instruction",
               "nothing can be executed yet"):
    check(f"instructions mention: {phrase}", phrase in ins.replace("you cannot\napprove", "cannot approve"))
check("instructions still tell Claude to use command names", "command NAME" in ins)

for name in ("os_info", "service_status", "test_netconnection", "processes_top_cpu"):
    check(f"run_device_command docstring lists windows command {name}",
          name in (getattr(server, "run_device_command", None).__doc__ or ""))
check("version unchanged", 'version="1.0.1"' in source)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
