"""Shared helpers for local diagnostics: validation, safe runner, logging."""
import ipaddress
import re
import subprocess

from trabasist_server.db import get_connection, init_db
from trabasist_server.redact import redact
from trabasist_server.tools.log_step import log_step

_LABEL = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
MAX_AUDIT_SUMMARY = 500


def validate_host(host) -> str:
    """Accept an IPv4/IPv6 address or a plain hostname. Reject everything else."""
    if not isinstance(host, str):
        raise ValueError("host must be text")
    host = host.strip()
    if not host or len(host) > 253:
        raise ValueError("host is empty or too long")
    if "%" in host:
        raise ValueError("host must not contain a scope id")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    host = host.rstrip(".")
    if not host or not all(_LABEL.fullmatch(part) for part in host.split(".")):
        raise ValueError("host is not a valid IP address or hostname")
    return host


def validate_port(port) -> int:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be a whole number from 1 to 65535")
    return port


def check_case_open(case_id) -> None:
    """Fail early, before any check runs, if the case cannot take a step."""
    if case_id is None:
        return
    if isinstance(case_id, bool) or not isinstance(case_id, int) or case_id < 1:
        raise ValueError("case_id must be a positive whole number")
    init_db()
    conn = get_connection()
    try:
        row = conn.execute("SELECT status FROM cases WHERE id = ?", (case_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"case {case_id} does not exist")
    if row["status"] != "open":
        raise ValueError(f"case {case_id} is closed")


def run_fixed(args: list, timeout: int = 30):
    """Run a fixed argument list. Never uses a shell. Returns (exit_code, output)."""
    try:
        done = subprocess.run(
            args, capture_output=True, text=True, errors="replace",
            timeout=timeout, shell=False,
        )
        return done.returncode, (done.stdout + done.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {timeout} seconds"
    except FileNotFoundError:
        return -1, f"program not found: {args[0]}"


def record_diagnostic(tool, device, command, output, case_id=None, outcome="inconclusive") -> dict:
    """Write to the audit log, and to the case if one is given. Output is redacted."""
    command = redact(command)
    output = redact(output) or ""
    summary = output[:MAX_AUDIT_SUMMARY]
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO audit_log (tool, device, command, result_summary) VALUES (?, ?, ?, ?)",
            (tool, device, command, summary),
        )
        conn.commit()
        audit_id = cur.lastrowid
    finally:
        conn.close()
    step = None
    if case_id is not None:
        step = log_step(case_id, f"{tool}: {device}", command, output, outcome)
    return {"audit_id": audit_id, "step": step}
