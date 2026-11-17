"""Offline checks for the Windows allowlist. No device needed."""
import sys
from trabasist_server.tools.command_allowlist import CommandRefused, build_command, list_commands

passed = failed = 0


def check(label, good):
    global passed, failed
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label)


def refused(label, name, params=None):
    try:
        build_command("windows", name, params)
    except CommandRefused:
        check(label, True)
    else:
        check(label, False)


SAMPLES = {
    "service_status": {"service": "W32Time"},
    "eventlog": {"log": "System", "lines": 20},
    "test_netconnection": {"host": "192.168.88.1", "port": 22},
}
for name in sorted(list_commands("windows")):
    text = build_command("windows", name, SAMPLES.get(name))
    check(f"{name} builds", bool(text))
    check(f"{name} has no shell-special characters", not any(c in text for c in '"$`{};\r\n'))

refused("free-form PowerShell refused", "Get-Process")
refused("unknown command refused", "whoami")
refused("uptime takes no params", "uptime", {"x": 1})
refused("params not dict", "uptime", "x")
refused("service missing", "service_status", {})
for bad in ("W32Time; whoami", "a b", "-Force", "x|y", "$env", '"a"', "a`b", ""):
    refused(f"service {bad!r} refused", "service_status", {"service": bad})
refused("log Security refused", "eventlog", {"log": "Security"})
refused("log injection refused", "eventlog", {"log": "System; whoami"})
for bad in (0, 101, True, "5"):
    refused(f"eventlog lines {bad!r} refused", "eventlog", {"lines": bad})
for bad in ("1.2.3.4; id", "$(whoami)", "-Force", "a b", ""):
    refused(f"host {bad!r} refused", "test_netconnection", {"host": bad, "port": 22})
refused("port missing refused", "test_netconnection", {"host": "192.168.88.1"})
for bad in (0, 70000, "22", True, None):
    refused(f"port {bad!r} refused", "test_netconnection", {"host": "192.168.88.1", "port": bad})

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
