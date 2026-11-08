import tempfile
from pathlib import Path
from trabasist_server.tools.inventory import get_device, get_credentials, Credentials, Device
from trabasist_server.tools.command_allowlist import build_command
from trabasist_server.tools.ssh_conn import run_command, HostKeyRefused, DeviceConnectionError

passed = failed = 0

def check(label, good):
    global passed, failed
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label)

dev = get_device("kali-lab")
creds = get_credentials(dev.credentials)

# 1. real command
try:
    out = run_command(dev, creds, build_command("linux", "uptime"))
    check("uptime over SSH returns output", "load average" in out)
    print("   output:", out.strip())
except Exception as e:
    check("uptime over SSH returns output", False)
    print("   error:", type(e).__name__, e)

# 2. unknown host key (empty known_hosts) must be refused
empty = Path(tempfile.mkdtemp()) / "known_hosts"
empty.write_text("")
try:
    run_command(dev, creds, "uptime", known_hosts=empty)
    check("unknown host key refused", False)
except HostKeyRefused as e:
    check("unknown host key refused", True)
    print("   message:", e)
except Exception as e:
    check("unknown host key refused", False)
    print("   wrong error:", type(e).__name__, e)

# 3. missing known_hosts file must be refused
try:
    run_command(dev, creds, "uptime", known_hosts=empty.parent / "nope")
    check("missing known_hosts refused", False)
except HostKeyRefused:
    check("missing known_hosts refused", True)

# 4. wrong password
bad = Credentials(creds.username, "wrong-password-test")
try:
    run_command(dev, bad, "uptime")
    check("wrong password fails", False)
except DeviceConnectionError as e:
    check("wrong password fails", "authentication" in str(e))
    check("password not in error text", creds.password not in str(e) and "wrong-password-test" not in str(e))

# 5. unreachable host (takes about 10 seconds)
ghost = Device("ghost", "192.0.2.1", "linux", 22, "KALI")
try:
    run_command(ghost, creds, "uptime")
    check("unreachable host fails", False)
except DeviceConnectionError as e:
    check("unreachable host fails", True)
    print("   message:", e)

print(f"\n{passed} passed, {failed} failed")
