"""ping_host tool: Windows ping with a fixed argument list, logged to audit and case."""
from trabasist_server.tools.diag_common import (
    validate_host, check_case_open, run_fixed, record_diagnostic,
)

MAX_COUNT = 10
PER_REPLY_WAIT_MS = 2000


def ping_host(host, count=4, case_id=None) -> dict:
    host = validate_host(host)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_COUNT:
        raise ValueError(f"count must be a whole number from 1 to {MAX_COUNT}")
    check_case_open(case_id)

    args = ["ping", "-n", str(count), "-w", str(PER_REPLY_WAIT_MS), host]
    timeout = count * (PER_REPLY_WAIT_MS // 1000 + 1) + 5
    code, output = run_fixed(args, timeout=timeout)
    reachable = "TTL=" in output

    rec = record_diagnostic("ping_host", host, " ".join(args), output, case_id)
    return {
        "host": host,
        "reachable": reachable,
        "output": output,
        "audit_id": rec["audit_id"],
        "step_id": rec["step"]["step_id"] if rec["step"] else None,
    }
