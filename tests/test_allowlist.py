from trabasist_server.tools.command_allowlist import build_command, list_commands, CommandRefused

passed = failed = 0

def ok(label, platform, name, params=None, expect=None):
    global passed, failed
    try:
        got = build_command(platform, name, params)
        good = expect is None or got == expect
    except CommandRefused:
        good, got = False, "refused"
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label + ("" if good else f"  got: {got}"))

def refused(label, platform, name, params=None):
    global passed, failed
    try:
        got = build_command(platform, name, params)
        good = False
    except CommandRefused:
        good, got = True, "refused"
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label + ("" if good else f"  RAN: {got}"))

# allowed
ok("uptime", "linux", "uptime", expect="uptime")
ok("df", "linux", "df", expect="df -h")
ok("systemctl ssh", "linux", "systemctl_status", {"service": "ssh"}, "systemctl status ssh --no-pager -l")
ok("systemctl templated unit", "linux", "systemctl_status", {"service": "getty@tty1.service"})
ok("journalctl default", "linux", "journalctl", expect="journalctl -n 50 --no-pager")
ok("journalctl unit+lines", "linux", "journalctl", {"unit": "ssh", "lines": 20}, "journalctl -n 20 --no-pager -u ssh")
ok("dmesg", "linux", "dmesg", expect="dmesg | tail -n 100")
ok("last", "linux", "last", {"count": 5}, "last -n 5")
ok("ss", "linux", "ss", expect="ss -tuln")
ok("ip_a", "linux", "ip_a", expect="ip a")
ok("ip_route", "linux", "ip_route", expect="ip route")
ok("free", "linux", "free", expect="free -h")

# refused: names and platforms
refused("free-form command", "linux", "rm -rf /")
refused("shell name", "linux", "bash")
refused("empty name", "linux", "")
refused("name is None", "linux", None)
refused("name is list", "linux", ["uptime"])
refused("unknown platform", "windows-x", "uptime")
refused("platform None", None, "uptime")
refused("uptime with args string", "linux", "uptime; id")

# refused: parameters
refused("extra param", "linux", "uptime", {"foo": "bar"})
refused("service missing", "linux", "systemctl_status", {})
refused("service semicolon", "linux", "systemctl_status", {"service": "ssh; id"})
refused("service subshell", "linux", "systemctl_status", {"service": "$(id)"})
refused("service backtick", "linux", "systemctl_status", {"service": "`id`"})
refused("service pipe", "linux", "systemctl_status", {"service": "ssh|cat"})
refused("service space", "linux", "systemctl_status", {"service": "ssh id"})
refused("service newline", "linux", "systemctl_status", {"service": "ssh\nid"})
refused("service leading dash", "linux", "systemctl_status", {"service": "-x"})
refused("service too long", "linux", "systemctl_status", {"service": "a" * 65})
refused("service not string", "linux", "systemctl_status", {"service": 5})
refused("unit injection", "linux", "journalctl", {"unit": "ssh;id"})
refused("lines zero", "linux", "journalctl", {"lines": 0})
refused("lines too big", "linux", "journalctl", {"lines": 501})
refused("lines string", "linux", "journalctl", {"lines": "5"})
refused("lines injection", "linux", "dmesg", {"lines": "5; id"})
refused("lines bool", "linux", "dmesg", {"lines": True})
refused("count too big", "linux", "last", {"count": 101})
refused("params not dict", "linux", "uptime", "x")

print("linux commands:", sorted(list_commands("linux")))
print(f"\n{passed} passed, {failed} failed")
