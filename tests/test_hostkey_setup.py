import tempfile
from pathlib import Path
import paramiko
from trabasist_server.tools.hostkey_setup import (
    fetch_host_key, fingerprint, known_hosts_status, saved_key_types,
    trust_host_key, HostKeyError)
from trabasist_server.tools.inventory import get_device
from trabasist_server.tools.ssh_conn import known_hosts_path

passed = failed = 0

def check(label, good):
    global passed, failed
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label)

def raises(label, fn):
    try:
        fn()
        check(label, False)
    except HostKeyError:
        check(label, True)

# ---- no network ----
k1 = paramiko.ECDSAKey.generate()
k2 = paramiko.ECDSAKey.generate()
fp = fingerprint(k1)
check("fingerprint format", fp.startswith("SHA256:") and "=" not in fp and len(fp) == 50)
check("different keys differ", fp != fingerprint(k2))

tmp = Path(tempfile.mkdtemp())
kh = tmp / "known_hosts"
A = "10.0.0.5"
check("missing file is unknown", known_hosts_status(kh, A, 22, k1) == "unknown")
kh.write_text("")
check("empty file is unknown", known_hosts_status(kh, A, 22, k1) == "unknown")
check("trust saves", trust_host_key(kh, A, 22, k1) is True)
check("then trusted", known_hosts_status(kh, A, 22, k1) == "trusted")
check("trust again is a no-op", trust_host_key(kh, A, 22, k1) is False)
check("other key is changed", known_hosts_status(kh, A, 22, k2) == "changed")
before = kh.read_text()
raises("changed key refused", lambda: trust_host_key(kh, A, 22, k2))
check("refusal changed nothing", kh.read_text() == before)
check("saved key types", saved_key_types(kh, A, 22) == [k1.get_name()])
check("no saved types for new address", saved_key_types(kh, "10.0.0.6", 22) == [])

check("port 2222 starts unknown", known_hosts_status(kh, A, 2222, k2) == "unknown")
trust_host_key(kh, A, 2222, k2)
check("non-22 port uses [host]:port", f"[{A}]:2222 " in kh.read_text())
check("port 22 entry unaffected", known_hosts_status(kh, A, 22, k1) == "trusted")
check("port 2222 trusted", known_hosts_status(kh, A, 2222, k2) == "trusted")

kh2 = tmp / "no_newline"
kh2.write_text(f"10.0.0.9 {k2.get_name()} {k2.get_base64()}")
trust_host_key(kh2, "10.0.0.7", 22, k1)
check("no-newline file keeps both entries",
      known_hosts_status(kh2, "10.0.0.9", 22, k2) == "trusted"
      and known_hosts_status(kh2, "10.0.0.7", 22, k1) == "trusted")

raises("bad address", lambda: fetch_host_key("1.2.3.4; id", 22))
raises("bad port type", lambda: fetch_host_key("10.0.0.5", "22"))
raises("bad port range", lambda: known_hosts_status(kh, A, 0, k1))

# ---- real Kali (read-only on your real known_hosts) ----
dev = get_device("kali-lab")
real = known_hosts_path()
real_before = real.read_bytes()
key = fetch_host_key(dev.address, dev.port)
print("   kali fingerprint:", fingerprint(key), "| type:", key.get_name())
check("kali key is already trusted in real known_hosts",
      known_hosts_status(real, dev.address, dev.port, key) == "trusted")
key2 = fetch_host_key(dev.address, dev.port, key_types=[key.get_name()])
check("restricted fetch gives the same key", fingerprint(key2) == fingerprint(key))
raises("unsupported key type refused", lambda: fetch_host_key(dev.address, dev.port, key_types=["ssh-dss"]))
raises("closed port fails cleanly", lambda: fetch_host_key("127.0.0.1", 1, timeout=3))
raises("unreachable host fails cleanly", lambda: fetch_host_key("192.0.2.1", 22, timeout=4))
check("real known_hosts unchanged", real.read_bytes() == real_before)

print(f"\n{passed} passed, {failed} failed")
