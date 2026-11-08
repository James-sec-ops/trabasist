"""open_case tool: record a new issue as a structured case."""
import re

from trabasist_server.db import get_connection, init_db

MAX_TEXT = 2000
_CODE_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")
_DEVICE_RE = re.compile(r"^[A-Za-z0-9_.\- ]{1,100}$")


def _clean(value, field, required=False, pattern=None):
    if value is None or not str(value).strip():
        if required:
            raise ValueError(f"{field} is required")
        return None
    value = str(value).strip()
    if len(value) > MAX_TEXT:
        raise ValueError(f"{field} is too long (max {MAX_TEXT} characters)")
    if pattern and not pattern.match(value):
        raise ValueError(f"{field} contains invalid characters or is too long")
    return value


def open_case(symptom, error_code=None, device=None, environment=None) -> dict:
    symptom = _clean(symptom, "symptom", required=True)
    error_code = _clean(error_code, "error_code", pattern=_CODE_RE)
    device = _clean(device, "device", pattern=_DEVICE_RE)
    environment = _clean(environment, "environment")

    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO cases (symptom, error_code, device, environment) VALUES (?, ?, ?, ?)",
            (symptom, error_code, device, environment),
        )
        conn.commit()
        return {"case_id": cur.lastrowid, "status": "open", "symptom": symptom,
                "error_code": error_code, "device": device, "environment": environment}
    finally:
        conn.close()
