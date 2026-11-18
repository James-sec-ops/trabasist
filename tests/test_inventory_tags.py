"""Step 1 tests: device tag and change_mode fields, defaults, validation, skip-and-report."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trabasist_server.tools.inventory import (  # noqa: E402
    Device, InventoryError, load_inventory, load_inventory_report,
)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name)


def write(tmp, devices):
    p = Path(tmp) / "devices.json"
    p.write_text(json.dumps({"devices": devices}), encoding="utf-8")
    return p


def dev(name="d1", **extra):
    d = {"name": name, "address": "192.0.2.10", "platform": "linux", "credentials": "KALI"}
    d.update(extra)
    return d


with tempfile.TemporaryDirectory() as tmp:
    # Old-style inventory: no new fields. Must load, production, change mode off.
    p = write(tmp, [dev()])
    inv, problems = load_inventory_report(p)
    check("old-style entry loads", "d1" in inv and not problems)
    check("default tag is production", inv["d1"].tag == "production")
    check("default change_mode is False", inv["d1"].change_mode is False)
    check("strict load_inventory also loads old-style", "d1" in load_inventory(p))

    # Valid new fields.
    inv, problems = load_inventory_report(write(tmp, [dev(tag="lab", change_mode=True)]))
    check("lab tag accepted", inv["d1"].tag == "lab")
    check("change_mode true accepted", inv["d1"].change_mode is True)
    inv, _ = load_inventory_report(write(tmp, [dev(tag="production", change_mode=False)]))
    check("explicit production accepted", inv["d1"].tag == "production")

    # Invalid values are skipped and reported, never defaulted.
    for label, extra in [
        ("tag dev", {"tag": "dev"}),
        ("tag Lab (case)", {"tag": "Lab"}),
        ("tag empty", {"tag": ""}),
        ("tag number", {"tag": 5}),
        ("tag null", {"tag": None}),
        ("change_mode string", {"change_mode": "true"}),
        ("change_mode number 1", {"change_mode": 1}),
        ("change_mode null", {"change_mode": None}),
    ]:
        inv, problems = load_inventory_report(write(tmp, [dev(**extra)]))
        check(f"{label} skipped and reported", "d1" not in inv and len(problems) == 1)

    # One bad entry must not block the good ones.
    inv, problems = load_inventory_report(write(tmp, [
        dev("good1"), dev("bad", tag="dev"), dev("good2", tag="lab"),
        dev("badplat", platform="plan9"), "not an object",
    ]))
    check("good devices still load", set(inv) == {"good1", "good2"})
    check("each bad entry reported", len(problems) == 3)
    check("problem names the entry number", any(m.startswith("entry 2:") for m in problems))

    # Duplicate names: first wins, second reported.
    inv, problems = load_inventory_report(write(tmp, [dev("x", tag="lab"), dev("x")]))
    check("duplicate keeps first", inv["x"].tag == "lab")
    check("duplicate reported", len(problems) == 1)

    # Strict loader keeps its old behaviour.
    try:
        load_inventory(write(tmp, [dev(tag="dev")]))
        check("strict load_inventory raises on bad tag", False)
    except InventoryError:
        check("strict load_inventory raises on bad tag", True)

    # File-level errors still raise.
    try:
        load_inventory_report(Path(tmp) / "missing.json")
        check("missing file raises", False)
    except InventoryError:
        check("missing file raises", True)

# Dataclass behaviour.
d = Device("a", "192.0.2.1", "linux", 22, "KALI")
check("5-argument Device still works with safe defaults", d.tag == "production" and d.change_mode is False)
try:
    d.change_mode = True
    check("Device is frozen", False)
except Exception:
    check("Device is frozen", True)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
