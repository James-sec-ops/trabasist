import sys
from trabasist_server.tools.command_allowlist import build_command, list_commands, CommandRefused
from trabasist_server.tools.diag_common import validate_host

passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print("FAIL:", label)


def expect(label, name, params, expected):
    try:
        got = build_command("linux", name, params)
    except CommandRefused as exc:
        got = "REFUSED: " + str(exc)
    check(label + " expected " + repr(expected) + " got " + repr(got), got == expected)


def refuse(label, name, params):
    try:
        got = build_command("linux", name, params)
        check(label + " should be refused, got " + repr(got), False)
    except CommandRefused:
        check(label, True)


# Old commands still work, new ones are listed
check("25 linux commands", len(list_commands("linux")) == 25)
expect("uptime", "uptime", {}, "uptime")
expect("last", "last", {"count": 5}, "last -n 5")

# ping
expect("ping default", "ping", {"host": "8.8.8.8"}, "ping -n -c 4 -W 2 8.8.8.8")
expect("ping count 10", "ping", {"host": "example.com", "count": 10}, "ping -n -c 10 -W 2 example.com")
expect("ping ipv6", "ping", {"host": "2001:db8::1"}, "ping -n -c 4 -W 2 2001:db8::1")
expect("ping trims spaces", "ping", {"host": "  8.8.8.8  "}, "ping -n -c 4 -W 2 8.8.8.8")
expect("ping hostname", "ping", {"host": "My-Server.local", "count": 1}, "ping -n -c 1 -W 2 My-Server.local")
for bad in (0, 11, -1, "4", True, 2.5, None):
    refuse("ping count " + repr(bad), "ping", {"host": "8.8.8.8", "count": bad})
refuse("ping no host", "ping", {})
refuse("ping extra param", "ping", {"host": "8.8.8.8", "flood": True})

# traceroute
expect("traceroute default", "traceroute", {"host": "example.com"}, "traceroute -n -m 15 -w 1 -q 1 example.com")
expect("traceroute 30 hops", "traceroute", {"host": "8.8.8.8", "max_hops": 30}, "traceroute -n -m 30 -w 1 -q 1 8.8.8.8")
for bad in (0, 31, "5", True):
    refuse("traceroute hops " + repr(bad), "traceroute", {"host": "8.8.8.8", "max_hops": bad})
refuse("traceroute no host", "traceroute", {})

# dig
expect("dig default A", "dig", {"name": "example.com"}, "dig +time=3 +tries=1 example.com A")
expect("dig mx lower case", "dig", {"name": "example.com", "record_type": "mx"}, "dig +time=3 +tries=1 example.com MX")
expect("dig PTR ip", "dig", {"name": "8.8.8.8", "record_type": "PTR"}, "dig +time=3 +tries=1 -x 8.8.8.8")
refuse("dig PTR with a hostname", "dig", {"name": "example.com", "record_type": "PTR"})
for bad in ("ANY", "AXFR", "IXFR", "A; id", "", None, 5):
    refuse("dig type " + repr(bad), "dig", {"name": "example.com", "record_type": bad})
refuse("dig no name", "dig", {})

# fixed commands
expect("ip_link_stats", "ip_link_stats", {}, "ip -s link")
expect("ip_neigh", "ip_neigh", {}, "ip neigh")
expect("resolv_conf", "resolv_conf", {}, "cat /etc/resolv.conf")
refuse("resolv_conf with a file", "resolv_conf", {"file": "/etc/shadow"})
refuse("ip_neigh with a param", "ip_neigh", {"dev": "eth0"})

# injection attempts on every host/name field
bad_hosts = [
    "8.8.8.8; id", "8.8.8.8 && id", "$(id)", "`id`", "-c", "--help", "-8.8.8.8",
    "8.8.8.8 -f", "8.8.8.8|id", "8.8.8.8>x", "a.b\n.c", "a.b\r.c", "8.8.8.8\nid",
    "", "   ", 123, ["8.8.8.8"], "fe80::1%eth0", "a" * 300, "bad host", "ex'ample.com",
]
for bad in bad_hosts:
    refuse("ping host " + repr(bad), "ping", {"host": bad})
    refuse("traceroute host " + repr(bad), "traceroute", {"host": bad})
    refuse("dig name " + repr(bad), "dig", {"name": bad})

# Information only: does the shared validator accept a newline host?
try:
    validate_host("a.b\n.c")
    print("INFO: validate_host() accepts a host containing a newline (the bug found earlier)")
except ValueError:
    print("INFO: validate_host() refuses a host containing a newline")

print(str(passed) + " passed, " + str(failed) + " failed")
print("PASS" if failed == 0 else "FAIL")
sys.exit(1 if failed else 0)
