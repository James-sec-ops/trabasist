"""log_step tool: record a check or attempt and its outcome on an open case."""
from trabasist_server.db import get_connection, init_db
from trabasist_server.redact import redact

MAX_ACTION = 500
MAX_COMMAND = 1000
MAX_RESULT = 20000
OUTCOMES = ("cause", "ruled_out", "inconclusive")


def log_step(case_id, action, command=None, result=None, outcome="inconclusive") -> dict:
    if isinstance(case_id, bool) or not isinstance(case_id, int) or case_id < 1:
        raise ValueError("case_id must be a positive whole number")
    if not action or not str(action).strip():
        raise ValueError("action is required")
    action = str(action).strip()
    if len(action) > MAX_ACTION:
        raise ValueError(f"action is too long (max {MAX_ACTION} characters)")
    if outcome not in OUTCOMES:
        raise ValueError("outcome must be one of: " + ", ".join(OUTCOMES))

    command = redact(command.strip()) if command else None
    if command and len(command) > MAX_COMMAND:
        raise ValueError(f"command is too long (max {MAX_COMMAND} characters)")
    result = redact(result)
    if result and len(result) > MAX_RESULT:
        result = result[:MAX_RESULT] + "\n[truncated]"
    action = redact(action)

    init_db()
    conn = get_connection()
    try:
        row = conn.execute("SELECT status FROM cases WHERE id = ?", (case_id,)).fetchone()
        if row is None:
            raise ValueError(f"case {case_id} does not exist")
        if row["status"] != "open":
            raise ValueError(f"case {case_id} is closed")
        cur = conn.execute(
            "INSERT INTO steps (case_id, action, command, result, outcome) VALUES (?, ?, ?, ?, ?)",
            (case_id, action, command, result, outcome),
        )
        conn.commit()
        return {"step_id": cur.lastrowid, "case_id": case_id, "action": action, "outcome": outcome}
    finally:
        conn.close()
