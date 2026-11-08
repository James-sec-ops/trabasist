"""check_port tool: TCP connect test with a timeout, logged to audit and case."""
import socket

from trabasist_server.tools.diag_common import (
    validate_host, validate_port, check_case_open, record_diagnostic,
)

MAX_TIMEOUT = 10


def check_port(host, port, timeout=3, case_id=None) -> dict:
    host = validate_host(host)
    port = validate_port(port)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= MAX_TIMEOUT:
        raise ValueError(f"timeout must be a whole number from 1 to {MAX_TIMEOUT} seconds")
    check_case_open(case_id)

    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        state = "open"
        detail = f"TCP connection to {host}:{port} succeeded"
    except ConnectionRefusedError:
        state = "closed"
        detail = f"{host}:{port} refused the connection (host is up, nothing listening)"
    except socket.timeout:
        state = "timeout"
        detail = f"No answer from {host}:{port} within {timeout}s (firewall drop or host down)"
    except socket.gaierror as exc:
        state = "error"
        detail = f"Could not resolve {host}: {exc}"
    except OSError as exc:
        state = "error"
        detail = f"Connection error to {host}:{port}: {exc}"

    command = f"tcp connect {host}:{port} timeout={timeout}s"
    rec = record_diagnostic("check_port", host, command, f"state={state}; {detail}", case_id)
    return {
        "host": host,
        "port": port,
        "state": state,
        "detail": detail,
        "audit_id": rec["audit_id"],
        "step_id": rec["step"]["step_id"] if rec["step"] else None,
    }
