"""Shared audit log writer. Text is redacted and shortened before it is stored."""
from trabasist_server.db import get_connection, init_db
from trabasist_server.redact import redact

_MAX_FIELD = 500


def clean_meta(tier=None, decision=None, rule=None, tag=None, change_mode=None):
    """Validate the policy fields stored with an audit row.

    Returns (tier, decision, rule, tag, change_mode) ready for the database.
    Raises ValueError for a value that is not what the classifier and inventory produce.
    """
    if tier is not None and (isinstance(tier, bool) or not isinstance(tier, int)
                             or tier not in (1, 2, 3)):
        raise ValueError("tier must be 1, 2, 3 or None")
    if change_mode is not None and not isinstance(change_mode, bool):
        raise ValueError("change_mode must be true, false or None")
    decision = None if decision is None else redact(str(decision))[:50]
    rule = None if rule is None else redact(str(rule))[:100]
    tag = None if tag is None else redact(str(tag))[:20]
    return (tier, decision, rule, tag, None if change_mode is None else int(change_mode))


def write_audit(tool, device, command, summary, *, tier=None, decision=None, rule=None,
                tag=None, change_mode=None) -> int:
    """Write one audit row and return its id.

    The keyword-only policy fields are optional, so older callers work unchanged.
    """
    extra = clean_meta(tier, decision, rule, tag, change_mode)
    tool = redact(str(tool))[:100]
    device = redact(str(device))[:100]
    command = redact(str(command))[:_MAX_FIELD]
    summary = redact(str(summary))[:_MAX_FIELD]
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO audit_log (tool, device, command, result_summary, "
            "tier, decision, rule, tag, change_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tool, device, command, summary) + extra,
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
