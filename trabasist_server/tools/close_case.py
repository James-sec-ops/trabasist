"""close_case tool: record root cause and the fix that worked, then close the case."""
from trabasist_server.db import get_connection, init_db
from trabasist_server.redact import redact

MAX_TEXT = 2000


def _required(value, field):
    if value is None or not str(value).strip():
        raise ValueError(f"{field} is required")
    value = redact(str(value).strip())
    if len(value) > MAX_TEXT:
        raise ValueError(f"{field} is too long (max {MAX_TEXT} characters)")
    return value


def close_case(case_id, root_cause, resolution) -> dict:
    if isinstance(case_id, bool) or not isinstance(case_id, int) or case_id < 1:
        raise ValueError("case_id must be a positive whole number")
    root_cause = _required(root_cause, "root_cause")
    resolution = _required(resolution, "resolution")

    init_db()
    conn = get_connection()
    try:
        row = conn.execute("SELECT status FROM cases WHERE id = ?", (case_id,)).fetchone()
        if row is None:
            raise ValueError(f"case {case_id} does not exist")
        if row["status"] != "open":
            raise ValueError(f"case {case_id} is already closed")
        conn.execute(
            "UPDATE cases SET status = 'closed', closed_at = datetime('now'), "
            "root_cause = ?, resolution = ? WHERE id = ?",
            (root_cause, resolution, case_id),
        )
        conn.commit()
        steps = conn.execute("SELECT COUNT(*) FROM steps WHERE case_id = ?", (case_id,)).fetchone()[0]
        return {"case_id": case_id, "status": "closed", "root_cause": root_cause,
                "resolution": resolution, "steps_recorded": steps}
    finally:
        conn.close()
