import sys
from trabasist_server.tools.command_allowlist import build_command, list_commands, CommandRefused

passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print("FAIL:", label)


EXPECTED = {
    "uname": "uname -a",
    "os_release": "cat /etc/os-release",
    "timedatectl": "timedatectl",
    "systemctl_failed": "systemctl --failed --no-pager",
    "ps_top_cpu": "ps -eo pid,user,%cpu,%mem,stat,etime,comm --sort=-%cpu | head -n 11",
    "ps_top_mem": "ps -eo pid,user,%cpu,%mem,stat,etime,comm --sort=-%mem | head -n 11",
    "lsblk": "lsblk",
    "df_inodes": "df -i",
    "who": "who",
}

check("25 linux commands", len(list_commands("linux")) == 25)
for name, expected in EXPECTED.items():
    check(name + " builds", build_command("linux", name) == expected)
    for extra in ({"x": 1}, {"lines": 5}, {"file": "/etc/shadow"}):
        try:
            build_command("linux", name, extra)
            check(name + " refuses " + repr(extra), False)
        except CommandRefused:
            check(name + " refuses " + repr(extra), True)
for name in ("ps_top_cpu", "ps_top_mem"):
    cmd = build_command("linux", name)
    check(name + " has no full command line", " aux" not in cmd and "args" not in cmd and "cmd" not in cmd)

print(str(passed) + " passed, " + str(failed) + " failed")
print("PASS" if failed == 0 else "FAIL")
sys.exit(1 if failed else 0)
