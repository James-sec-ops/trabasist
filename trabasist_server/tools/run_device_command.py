"""run_device_command tool: allowlisted, read-only commands over SSH. Everything is audited."""
from trabasist_server.db import get_connection, init_db
from trabasist_server.redact import redact
from trabasist_server.tools.command_allowlist import build_command, CommandRefused
from trabasist_server.tools.diag_common import check_case_open, record_diagnostic
from trabasist_server.tools.inventory import get_device, get_credentials, InventoryError
from trabasist_server.tools.ssh_conn import run_command, DeviceConnectionError

TOOL = "run_device_command"
_MAX_FIELD = 500


def _audit(device, command, summary) -> int:
    """Write one audit row. Text is redacted and shortened first."""
    device = redact(str(device))[:100]
    command = redact(str(command))[:_MAX_FIELD]
    summary = redact(str(summary))[:_MAX_FIELD]
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO audit_log (tool, device, command, result_summary) VALUES (?, ?, ?, ?)",
            (TOOL, device, command, summary),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _problem(status, device, command, reason, tried):
    audit_id = _audit(device, tried, f"{status.upper()}: {reason}")
    return {"status": status, "device": str(device)[:100], "reason": reason,
            "audit_id": audit_id, "step_id": None}


def run_device_command(device, command, params=None, case_id=None) -> dict:
    check_case_open(case_id)
    tried = f"{command} {params}" if params else f"{command}"

    try:
        dev = get_device(device)
    except InventoryError as exc:
        return _problem("refused", device, tried, str(exc), tried)

    try:
        command_text = build_command(dev.platform, command, params)
    except CommandRefused as exc:
        return _problem("refused", dev.name, tried, str(exc), tried)

    try:
        creds = get_credentials(dev.credentials)
        output = run_command(dev, creds, command_text)
    except (InventoryError, DeviceConnectionError) as exc:
        return _problem("failed", dev.name, command_text, str(exc), command_text)

    output = redact(output) or ""
    rec = record_diagnostic(TOOL, dev.name, command_text, output, case_id)
    return {
        "status": "ok",
        "device": dev.name,
        "command": command_text,
        "output": output,
        "audit_id": rec["audit_id"],
        "step_id": rec["step"]["step_id"] if rec["step"] else None,
    }
