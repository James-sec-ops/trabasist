"""Shared audit log writer. Text is redacted and shortened before it is stored."""
from trabasist_server.db import get_connection, init_db
from trabasist_server.redact import redact

_MAX_FIELD = 500


def write_audit(tool, device, command, summary) -> int:
    """Write one audit row and return its id."""
    tool = redact(str(tool))[:100]
    device = redact(str(device))[:100]
    command = redact(str(command))[:_MAX_FIELD]
    summary = redact(str(summary))[:_MAX_FIELD]
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO audit_log (tool, device, command, result_summary) VALUES (?, ?, ?, ?)",
            (tool, device, command, summary),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
