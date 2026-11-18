"""Policy gate. Pure function: decides what may happen to a classified command.

It runs nothing. It returns one of:
  allow           the command may run now
  needs_approval  only the owner's one-time approval (Phase 2) can let it run
  refused         it may not run

There is deliberately no "approved" argument. Phase 2 adds the approval path.
Any input that is not exactly what the inventory and classifier produce is refused.
"""
from typing import NamedTuple

ALLOW = "allow"
NEEDS_APPROVAL = "needs_approval"
REFUSED = "refused"
TAGS = ("lab", "production")


class Decision(NamedTuple):
    action: str
    code: str
    reason: str


def _refuse(code, reason):
    return Decision(REFUSED, code, reason)


def decide(classification, tag, change_mode):
    """Return Decision(action, code, reason). Never raises."""
    tier = getattr(classification, "tier", None)
    if isinstance(tier, bool) or not isinstance(tier, int) or tier not in (1, 2, 3):
        return _refuse("policy:bad-input", "command has no valid tier")

    # Read-only commands do not depend on the tag or change mode.
    if tier == 1:
        return Decision(ALLOW, "policy:read-only", "read-only command")

    if not isinstance(tag, str) or tag not in TAGS:
        return _refuse("policy:bad-input", "device tag must be 'lab' or 'production'")
    if not isinstance(change_mode, bool):
        return _refuse("policy:bad-input", "change mode must be true or false")

    if not change_mode:
        return _refuse("policy:change-mode-off", "change mode is off for this device")

    if tier == 3:
        return Decision(NEEDS_APPROVAL, "policy:tier3-needs-approval",
                        "critical command: needs the owner's one-time approval")

    if tag == "lab":
        return Decision(ALLOW, "policy:lab-change-allowed",
                        "normal change on a lab device with change mode on")
    return Decision(NEEDS_APPROVAL, "policy:production-needs-approval",
                    "change on a production device needs the owner's approval")
