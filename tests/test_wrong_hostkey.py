import tempfile, subprocess
from pathlib import Path
from trabasist_server.tools.inventory import get_device, get_credentials
from trabasist_server.tools.ssh_conn import run_command, HostKeyRefused

dev = get_device("kali-lab")
creds = get_credentials(dev.credentials)

# A throwaway ed25519 key that is NOT Kali's key
tmp = Path(tempfile.mkdtemp())
subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(tmp / "fake")], check=True)
pub = (tmp / "fake.pub").read_text().split()
(tmp / "known_hosts").write_text(f"{dev.address} {pub[0]} {pub[1]}\n")

try:
    run_command(dev, creds, "uptime", known_hosts=tmp / "known_hosts")
    print("FAIL: connected with a wrong host key")
except HostKeyRefused as e:
    print("PASS: refused ->", e)
except Exception as e:
    print("FAIL: wrong error:", type(e).__name__, e)
