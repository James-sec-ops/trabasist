"""Run a named allowlist command, or check a free-form one. Everything is audited.

Phase 1: every command is classified and passed through the policy gate. Named allowlist
commands are Tier 1 and run as before. check_device_command classifies and gates a
free-form command but never runs it.
"""
import re

from trabasist_server.redact import redact
from trabasist_server.tools.audit import write_audit
from trabasist_server.tools.classifier import classify, classify_named
from trabasist_server.tools.command_allowlist import CommandRefused
from trabasist_server.tools.diag_common import check_case_open, record_diagnostic
from trabasist_server.tools.inventory import get_credentials, load_inventory_report, InventoryError
from trabasist_server.tools.policy import ALLOW, decide
from trabasist_server.tools.ssh_conn import run_command, DeviceConnectionError

TOOL = "run_device_command"
CHECK_TOOL = "check_device_command"
_MAX_FIELD = 500


def _audit(device, command, summary, **meta) -> int:
    """Write one audit row (shared writer in audit.py)."""
    return write_audit(TOOL, device, command, summary, **meta)


def _meta(dev, cls=None, decision=None) -> dict:
    meta = {}
    if dev is not None:
        meta["tag"] = dev.tag
        meta["change_mode"] = dev.change_mode
    if cls is not None:
        meta["tier"] = cls.tier
        meta["rule"] = cls.rule
    if decision is not None:
        meta["decision"] = decision.action
    return meta


def _problem(status, device, command, reason, tried, *, tool=TOOL, **meta):
    meta = dict(meta)
    if status == "refused":
        meta.setdefault("decision", "refused")
    audit_id = write_audit(tool, device, tried, f"{status.upper()}: {reason}", **meta)
    return {"status": status, "device": str(device)[:100], "reason": reason,
            "audit_id": audit_id, "step_id": None}


def _find_device(name):
    """Return the Device. A device skipped for a bad entry is reported with its real reason."""
    if not isinstance(name, str):
        raise InventoryError(f"device not in inventory: {name!r}")
    devices, problems = load_inventory_report()
    if name in devices:
        return devices[name]
    pattern = re.compile(r"(?:for |name: )" + re.escape(name) + r"(?![A-Za-z0-9._-])")
    for problem in problems:
        if pattern.search(problem):
            detail = problem.split(": ", 1)[1] if ": " in problem else problem
            raise InventoryError(f"device {name} is in the inventory but was skipped: {detail}")
    raise InventoryError(f"device not in inventory: {name!r}")


def run_device_command(device, command, params=None, case_id=None) -> dict:
    check_case_open(case_id)
    tried = f"{command} {params}" if params else f"{command}"

    try:
        dev = _find_device(device)
    except InventoryError as exc:
        return _problem("refused", device, tried, str(exc), tried)

    try:
        command_text, cls = classify_named(dev.platform, command, params)
    except CommandRefused as exc:
        return _problem("refused", dev.name, tried, str(exc), tried, **_meta(dev))

    decision = decide(cls, dev.tag, dev.change_mode)
    meta = _meta(dev, cls, decision)
    if decision.action != ALLOW:  # cannot happen for a named command; checked anyway
        return _problem("refused", dev.name, command_text, decision.reason, command_text, **meta)

    try:
        creds = get_credentials(dev.credentials)
        output = run_command(dev, creds, command_text)
    except (InventoryError, DeviceConnectionError) as exc:
        return _problem("failed", dev.name, command_text, str(exc), command_text, **meta)

    output = redact(output) or ""
    rec = record_diagnostic(TOOL, dev.name, command_text, output, case_id, meta=meta)
    return {
        "status": "ok",
        "device": dev.name,
        "command": command_text,
        "output": output,
        "audit_id": rec["audit_id"],
        "step_id": rec["step"]["step_id"] if rec["step"] else None,
    }


def check_device_command(device, command) -> dict:
    """Classify a free-form command and apply the policy gate. Runs nothing, ever."""
    tried = str(command)
    try:
        dev = _find_device(device)
    except InventoryError as exc:
        return _problem("refused", device, tried, str(exc), tried, tool=CHECK_TOOL)

    cls = classify(dev.platform, command)
    decision = decide(cls, dev.tag, dev.change_mode)
    summary = (f"{decision.action.upper()}: {decision.reason} "
               f"(tier {cls.tier}, {cls.rule}); not executed")
    audit_id = write_audit(CHECK_TOOL, dev.name, tried, summary, **_meta(dev, cls, decision))
    return {
        "status": "checked",
        "device": dev.name,
        "command": redact(tried)[:_MAX_FIELD],
        "tier": cls.tier,
        "rule": cls.rule,
        "tier_reason": cls.reason,
        "decision": decision.action,
        "decision_code": decision.code,
        "reason": decision.reason,
        "executed": False,
        "note": ("Nothing was executed. Free-form execution is not available yet. "
                 "For read-only checks use run_device_command with a command name."),
        "audit_id": audit_id,
        "step_id": None,
    }
