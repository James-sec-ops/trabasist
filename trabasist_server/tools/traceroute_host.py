"""traceroute_host tool: Windows tracert with a fixed argument list, logged to audit and case."""
import re

from trabasist_server.tools.diag_common import (
    validate_host, check_case_open, run_fixed, record_diagnostic,
)

MAX_HOPS_LIMIT = 30
HOP_WAIT_MS = 1000
OVERALL_TIMEOUT = 60
_HOP_LINE = re.compile(r"^\s*\d+\s")


def traceroute_host(host, max_hops=15, case_id=None) -> dict:
    host = validate_host(host)
    if isinstance(max_hops, bool) or not isinstance(max_hops, int) or not 1 <= max_hops <= MAX_HOPS_LIMIT:
        raise ValueError(f"max_hops must be a whole number from 1 to {MAX_HOPS_LIMIT}")
    check_case_open(case_id)

    args = ["tracert", "-d", "-h", str(max_hops), "-w", str(HOP_WAIT_MS), host]
    code, output = run_fixed(args, timeout=OVERALL_TIMEOUT)
    hops = sum(1 for line in output.splitlines() if _HOP_LINE.match(line))
    completed = "Trace complete" in output

    rec = record_diagnostic("traceroute_host", host, " ".join(args), output, case_id)
    return {
        "host": host,
        "completed": completed,
        "hops_seen": hops,
        "output": output,
        "audit_id": rec["audit_id"],
        "step_id": rec["step"]["step_id"] if rec["step"] else None,
    }

