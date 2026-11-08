import json, tempfile
from pathlib import Path
from dotenv import dotenv_values
from trabasist_server.tools.inventory import load_inventory
from trabasist_server.tools.device_setup import (
    label_from_name, add_device_entry, add_credentials, SetupError)

passed = failed = 0

def check(label, good):
    global passed, failed
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label)

def refused(label, fn):
    try:
        fn()
        check(label, False)
    except SetupError:
        check(label, True)

tmp = Path(tempfile.mkdtemp())
inv = tmp / "devices.json"
env = tmp / ".env"

# labels
check("label kali-lab", label_from_name("kali-lab") == "KALI_LAB")
check("label web.srv-01", label_from_name("web.srv-01") == "WEB_SRV_01")
refused("label too long", lambda: label_from_name("a" * 33))
refused("label bad name", lambda: label_from_name("a;b"))
refused("label empty", lambda: label_from_name(""))
refused("label None", lambda: label_from_name(None))

# inventory
check("add first device", add_device_entry(inv, "kali-lab", "10.0.0.5", "linux", 22) == "KALI_LAB")
check("no backup for a new file", not (tmp / "devices.json.bak").exists())
add_device_entry(inv, "web-01", "web01.lab.local", "linux", 2222)
data = json.loads(inv.read_text(encoding="utf-8"))
check("two devices stored in order", [d["name"] for d in data["devices"]] == ["kali-lab", "web-01"])
check("port stored", data["devices"][1]["port"] == 2222)
check("backup made on second add", (tmp / "devices.json.bak").exists())
check("real loader accepts the file", set(load_inventory(inv)) == {"kali-lab", "web-01"})
before = inv.read_text(encoding="utf-8")
refused("duplicate name", lambda: add_device_entry(inv, "kali-lab", "10.0.0.9", "linux", 22))
refused("label collision", lambda: add_device_entry(inv, "kali.lab", "10.0.0.9", "linux", 22))
refused("bad address", lambda: add_device_entry(inv, "x1", "1.2.3.4; id", "linux", 22))
refused("bad platform", lambda: add_device_entry(inv, "x2", "10.0.0.9", "cisco", 22))
refused("bad port", lambda: add_device_entry(inv, "x3", "10.0.0.9", "linux", "22"))
refused("bad name", lambda: add_device_entry(inv, "x;4", "10.0.0.9", "linux", 22))
check("refused adds changed nothing", inv.read_text(encoding="utf-8") == before)
broken = tmp / "broken.json"
broken.write_text("{not json", encoding="utf-8")
refused("corrupt inventory refused", lambda: add_device_entry(broken, "x5", "10.0.0.9", "linux", 22))

# credentials
tricky = "p#ss w'rd\\\"$x ${HOME} end\\"
add_credentials(env, "KALI_LAB", "testuser", tricky)
vals = dotenv_values(env, interpolate=False)
check("username round trip", vals["KALI_LAB_USERNAME"] == "testuser")
check("tricky password round trip", vals["KALI_LAB_PASSWORD"] == tricky)
check("password not in inventory file", tricky not in inv.read_text(encoding="utf-8"))
env_before = env.read_text(encoding="utf-8")
refused("duplicate credentials", lambda: add_credentials(env, "KALI_LAB", "x", "y"))
refused("newline in password", lambda: add_credentials(env, "WEB_01", "u", "a\nb"))
refused("empty password", lambda: add_credentials(env, "WEB_01", "u", ""))
refused("empty username", lambda: add_credentials(env, "WEB_01", "", "pw"))
refused("bad label", lambda: add_credentials(env, "web;01", "u", "pw"))
check("refused credentials changed nothing", env.read_text(encoding="utf-8") == env_before)

env2 = tmp / "env2"
env2.write_text("OTHER=keep", encoding="utf-8")
add_credentials(env2, "WEB_01", "u", "pw")
v2 = dotenv_values(env2, interpolate=False)
check("existing line kept", v2["OTHER"] == "keep" and v2["WEB_01_PASSWORD"] == "pw")
check("env backup made", (tmp / "env2.bak").exists())

print(f"\n{passed} passed, {failed} failed")
