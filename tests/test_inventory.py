import json, tempfile, os
from pathlib import Path
from trabasist_server.tools.inventory import (
    load_inventory, get_device, get_credentials, InventoryError)

passed = failed = 0

def check(label, good):
    global passed, failed
    passed, failed = (passed + 1, failed) if good else (passed, failed + 1)
    print(("PASS " if good else "FAIL ") + label)

def raises(label, fn):
    try:
        fn()
        check(label, False)
    except InventoryError:
        check(label, True)

tmp = Path(tempfile.mkdtemp())
def write(name, obj):
    p = tmp / name
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
    return p

good = {"name": "a", "address": "10.0.0.1", "platform": "linux", "port": 22, "credentials": "KALI"}

# real inventory
inv = load_inventory()
check("real inventory has kali-lab", "kali-lab" in inv)
d = get_device("kali-lab")
check("kali-lab is linux on port 22", d.platform == "linux" and d.port == 22)
c = get_credentials(d.credentials)
check("credentials loaded", bool(c.username) and bool(c.password))
check("password not in repr", c.password not in repr(c))

# bad inventories
check("valid temp inventory loads", "a" in load_inventory(write("ok.json", {"devices": [good]})))
raises("missing file", lambda: load_inventory(tmp / "nope.json"))
raises("bad JSON", lambda: load_inventory(write("bad.json", "{not json")))
raises("no devices list", lambda: load_inventory(write("nd.json", {"x": 1})))
raises("duplicate name", lambda: load_inventory(write("dup.json", {"devices": [good, good]})))
raises("bad name", lambda: load_inventory(write("n.json", {"devices": [dict(good, name="a;b")]})))
raises("bad address", lambda: load_inventory(write("ad.json", {"devices": [dict(good, address="1.2.3.4; id")]})))
raises("bad platform", lambda: load_inventory(write("pl.json", {"devices": [dict(good, platform="cisco")]})))
raises("bad port 0", lambda: load_inventory(write("p0.json", {"devices": [dict(good, port=0)]})))
raises("bad port string", lambda: load_inventory(write("ps.json", {"devices": [dict(good, port="22")]})))
raises("bad label", lambda: load_inventory(write("lb.json", {"devices": [dict(good, credentials="kali;x")]})))
raises("unknown device", lambda: get_device("nope"))
raises("device name None", lambda: get_device(None))
raises("missing credentials", lambda: get_credentials("NOSUCHLABEL"))
raises("bad credentials label", lambda: get_credentials("../x"))

print(f"\n{passed} passed, {failed} failed")
