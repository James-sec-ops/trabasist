"""Step 3 tests: policy gate (pure, offline)."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trabasist_server.tools.classifier import Classification, classify  # noqa: E402
from trabasist_server.tools.policy import (  # noqa: E402
    ALLOW, NEEDS_APPROVAL, REFUSED, TAGS, Decision, decide,
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


def cls(tier):
    return Classification(tier, "test", "test")


# ---- Full matrix ----
EXPECTED = {}
for tag in TAGS:
    for cm in (True, False):
        EXPECTED[(1, tag, cm)] = ALLOW
EXPECTED[(2, "lab", False)] = REFUSED
EXPECTED[(2, "lab", True)] = ALLOW
EXPECTED[(2, "production", False)] = REFUSED
EXPECTED[(2, "production", True)] = NEEDS_APPROVAL
EXPECTED[(3, "lab", False)] = REFUSED
EXPECTED[(3, "production", False)] = REFUSED
EXPECTED[(3, "lab", True)] = NEEDS_APPROVAL
EXPECTED[(3, "production", True)] = NEEDS_APPROVAL

bad = []
for (tier, tag, cm), want in EXPECTED.items():
    d = decide(cls(tier), tag, cm)
    if not (isinstance(d, Decision) and d.action == want and d.code and d.reason):
        bad.append((tier, tag, cm, want, d))
check(f"full matrix ({len(EXPECTED)} cases)", not bad)
for b in bad:
    print("   ", b)

# ---- Tier 1 does not depend on tag or change mode ----
for tag, cm in [("bogus", None), (None, "yes"), ("Lab", 1), ("", False)]:
    check(f"Tier 1 allowed with tag={tag!r} change_mode={cm!r}",
          decide(cls(1), tag, cm).action == ALLOW)

# ---- Bad tier ----
for t in (0, 4, -1, "1", None, True, False, 1.0, 2.0, [1], 3.5):
    check(f"bad tier {t!r} refused", decide(Classification(t, "x", "x"), "lab", True).action == REFUSED)


class NoTier:
    pass


check("object without tier refused", decide(NoTier(), "lab", True).action == REFUSED)
check("None classification refused", decide(None, "lab", True).action == REFUSED)

# ---- Bad tag or change mode on change tiers ----
for tier in (2, 3):
    for tag in ("Lab", "LAB", "dev", "", None, 5, " lab", "lab "):
        check(f"Tier {tier} with bad tag {tag!r} refused", decide(cls(tier), tag, True).action == REFUSED)
    for cm in ("true", "True", 1, 0, None, "yes", []):
        check(f"Tier {tier} with bad change_mode {cm!r} refused", decide(cls(tier), "lab", cm).action == REFUSED)

# ---- Fuzz: ALLOW only for Tier 1, or Tier 2 on lab with change mode on ----
rng = random.Random(99)
TIERS = [0, 1, 2, 3, 4, True, False, None, "1", 1.0, 2.0]
TAG_VALUES = ["lab", "production", "Lab", "", None, 5, "dev"]
CMS = [True, False, 1, 0, None, "true"]
bad = []
for _ in range(4000):
    t, tag, cm = rng.choice(TIERS), rng.choice(TAG_VALUES), rng.choice(CMS)
    d = decide(Classification(t, "x", "x"), tag, cm)
    exact = isinstance(t, int) and not isinstance(t, bool)
    ok_allow = (exact and t == 1) or (exact and t == 2 and tag == "lab" and cm is True)
    if d.action == ALLOW and not ok_allow:
        bad.append(("allowed wrongly", t, tag, cm))
    if d.action == NEEDS_APPROVAL and not (exact and t in (2, 3) and tag in TAGS and cm is True):
        bad.append(("needs_approval wrongly", t, tag, cm))
check("fuzz: allow and needs_approval only where the table says", not bad)
for b in bad[:5]:
    print("   ", b)

# ---- Classifier and gate together ----
CASES = [
    ("linux", "uptime", "production", False, ALLOW),
    ("linux", "uptime", "lab", True, ALLOW),
    ("windows", "ipconfig /all", "production", False, ALLOW),
    ("linux", "systemctl restart nginx", "lab", False, REFUSED),
    ("linux", "systemctl restart nginx", "lab", True, ALLOW),
    ("linux", "systemctl restart nginx", "production", True, NEEDS_APPROVAL),
    ("linux", "systemctl restart nginx", "production", False, REFUSED),
    ("linux", "systemctl restart sshd", "lab", True, NEEDS_APPROVAL),
    ("linux", "reboot", "lab", True, NEEDS_APPROVAL),
    ("linux", "reboot", "lab", False, REFUSED),
    ("linux", "uptime; reboot", "lab", True, NEEDS_APPROVAL),
    ("linux", "uptime | sh", "lab", True, NEEDS_APPROVAL),
    ("linux", "apt-get install -y htop", "lab", True, ALLOW),
    ("linux", "ip addr add 192.0.2.5/24 dev eth0", "lab", True, ALLOW),
    ("windows", "Restart-Service -Name Spooler", "lab", True, ALLOW),
    ("windows", "Restart-Service -Name sshd", "lab", True, NEEDS_APPROVAL),
    ("windows", "Restart-Computer", "lab", True, NEEDS_APPROVAL),
    ("cisco", "show version", "lab", True, NEEDS_APPROVAL),
    ("mikrotik", "/ip address print", "lab", True, NEEDS_APPROVAL),
    ("plan9", "uptime", "lab", True, NEEDS_APPROVAL),
]
bad = []
for plat, command, tag, cm, want in CASES:
    d = decide(classify(plat, command), tag, cm)
    if d.action != want:
        bad.append((plat, command, tag, cm, want, d))
check(f"classifier and gate together ({len(CASES)} cases)", not bad)
for b in bad:
    print("   ", b)

# ---- Anything classified Tier 3 is never allowed, in any state ----
SAMPLE = [
    "reboot", "uptime; reboot", "rm -rf /", "iptables -F", "sudo uptime", "powershell -enc AAAA",
    "Restart-Computer", "systemctl restart sshd", "echo $(id)", "uptime > /etc/passwd", "",
]
bad = []
for plat in ("linux", "windows", "cisco", "mikrotik", "plan9"):
    for command in SAMPLE:
        c = classify(plat, command)
        if c.tier != 3:
            continue
        for tag in TAG_VALUES:
            for cm in CMS:
                if decide(c, tag, cm).action == ALLOW:
                    bad.append((plat, command, tag, cm))
check("a Tier 3 command is never allowed", not bad)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
