import hashlib, json, os, subprocess, tempfile
from pathlib import Path
from dotenv import dotenv_values
from trabasist_server.add_device import run_add_device
from trabasist_server.tools.hostkey_setup import _hostname_for
from trabasist_server.tools.inventory import get_device, get_credentials, env_path, inventory_path
from trabasist_server.tools.ssh_conn import known_hosts_path

passed = failed = 0

def check(label, good):
    global passed, failed
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label)

dev = get_device("kali-lab")
real = get_credentials(dev.credentials)
USER, PW, ADDR, PORT = real.username, real.password, dev.address, dev.port

REAL_FILES = [inventory_path(), env_path(), known_hosts_path()]
def digest():
    return [hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in REAL_FILES]
before = digest()

def fresh():
    d = Path(tempfile.mkdtemp())
    os.environ["TRABASIST_DEVICES"] = str(d / "devices.json")
    os.environ["TRABASIST_ENV"] = str(d / ".env")
    os.environ["TRABASIST_KNOWN_HOSTS"] = str(d / "known_hosts")
    return d

def scripted(items):
    items = list(items)
    def fn(prompt=""):
        if not items:
            raise RuntimeError("unexpected prompt: " + prompt)
        return items.pop(0)
    return fn

def run(answers, secrets):
    lines = []
    try:
        code = run_add_device(scripted(answers), scripted(secrets), lines.append)
    except RuntimeError as exc:
        code = "UNEXPECTED " + str(exc)
    return code, lines

def show(lines):
    for l in lines:
        print("   |", l)

# 1. new key, confirmed with yes
d = fresh()
code, lines = run(["kali-test", ADDR, "", "", USER, "yes"], [PW, PW])
text = "\n".join(lines)
show(lines)
check("1 happy path returns 0", code == 0)
check("1 test login reported", "Test login OK" in text)
inv = json.loads((d / "devices.json").read_text(encoding="utf-8"))
check("1 device saved with label", [x["name"] for x in inv["devices"]] == ["kali-test"]
      and inv["devices"][0]["credentials"] == "KALI_TEST")
vals = dotenv_values(d / ".env", interpolate=False)
check("1 credentials saved exactly", vals["KALI_TEST_USERNAME"] == USER and vals["KALI_TEST_PASSWORD"] == PW)
check("1 host key saved to temp known_hosts", ADDR in (d / "known_hosts").read_text(encoding="utf-8"))
check("1 password never printed", PW not in text)

# 1b. duplicate name refused, then a second device on a trusted key
inv_before = (d / "devices.json").read_text(encoding="utf-8")
code, lines = run(["kali-test"] * 3, [])
check("1b duplicate name refused", code == 1 and (d / "devices.json").read_text(encoding="utf-8") == inv_before)
code, lines = run(["kali-test2", ADDR, "", "", USER], [PW, PW])
check("1b second device on trusted key returns 0", code == 0 and "already trusted" in "\n".join(lines))
check("1b both devices stored", len(json.loads((d / "devices.json").read_text(encoding="utf-8"))["devices"]) == 2)

# 2. declined
d = fresh()
code, lines = run(["kali-test", ADDR, "", "", USER, "no"], [PW, PW])
check("2 declined returns 1", code == 1)
check("2 nothing written",
      not (d / "devices.json").exists() and not (d / ".env").exists() and not (d / "known_hosts").exists())

# 3. changed key refused (same key type, different key)
d = fresh()
subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(d / "fake")], check=True)
pub = (d / "fake.pub").read_text(encoding="utf-8").split()
kh_text = f"{_hostname_for(ADDR, PORT)} {pub[0]} {pub[1]}\n"
(d / "known_hosts").write_text(kh_text, encoding="utf-8")
code, lines = run(["kali-test", ADDR, "", "", USER], [PW, PW])
text = "\n".join(lines)
show(lines)
check("3 changed key returns 1", code == 1)
check("3 shows ssh-keygen -R steps", "ssh-keygen -R" in text)
check("3 known_hosts untouched", (d / "known_hosts").read_text(encoding="utf-8") == kh_text)
check("3 nothing else written", not (d / "devices.json").exists() and not (d / ".env").exists())

# 4. password mismatch three times
d = fresh()
code, lines = run(["kali-test", ADDR, "", "", USER], [PW, "x", PW, "y", "a", "b"])
check("4 password mismatch returns 1", code == 1)
check("4 nothing written", not (d / "devices.json").exists() and not (d / ".env").exists())

# 5. bad address three times
d = fresh()
code, lines = run(["x1", "1.2.3.4; id", "bad;host", "also bad"], [])
check("5 bad address returns 1", code == 1 and not (d / "devices.json").exists())

# 6. wrong password: saved, but test login fails and is reported
d = fresh()
code, lines = run(["kali-test", ADDR, "", "", USER, "yes"], ["wrong-pass-test", "wrong-pass-test"])
text = "\n".join(lines)
check("6 wrong password returns 1", code == 1 and "Test login failed" in text)
check("6 wrong password never printed", "wrong-pass-test" not in text)
check("6 device still saved", (d / "devices.json").exists())

# real files must be untouched
for k in ("TRABASIST_DEVICES", "TRABASIST_ENV", "TRABASIST_KNOWN_HOSTS"):
    os.environ.pop(k, None)
check("real devices.json, .env and known_hosts unchanged", digest() == before)

print(f"\n{passed} passed, {failed} failed")
