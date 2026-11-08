"""find_similar_cases tool: search past cases and rank them by match."""
import re

from trabasist_server.db import get_connection, init_db

_WORD_RE = re.compile(r"[A-Za-z0-9_.\-]{2,}")
_CODE_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")
_DEVICE_RE = re.compile(r"^[A-Za-z0-9_.\- ]{1,100}$")
MAX_QUERY = 2000
MAX_STEPS_PER_CASE = 20
MAX_STEP_RESULT = 300


def _fts_query(text):
    words = _WORD_RE.findall(text or "")[:30]
    if not words:
        return None
    return " OR ".join('"' + w.replace('"', "") + '"' for w in words)


def find_similar_cases(symptom=None, error_code=None, device=None, limit=5) -> list:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("limit must be a whole number from 1 to 20")
    symptom = str(symptom).strip() if symptom else None
    error_code = str(error_code).strip() if error_code else None
    device = str(device).strip() if device else None
    if not (symptom or error_code or device):
        raise ValueError("give at least one of: symptom, error_code, device")
    if symptom and len(symptom) > MAX_QUERY:
        raise ValueError(f"symptom is too long (max {MAX_QUERY} characters)")
    if error_code and not _CODE_RE.match(error_code):
        raise ValueError("error_code contains invalid characters or is too long")
    if device and not _DEVICE_RE.match(device):
        raise ValueError("device contains invalid characters or is too long")

    terms = " ".join(t for t in (symptom, error_code, device) if t)
    fts = _fts_query(terms)
    if fts is None:
        raise ValueError("nothing searchable in the input")

    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT c.id, c.status, c.symptom, c.error_code, c.device, c.root_cause, "
            "c.resolution, c.opened_at, c.closed_at, bm25(cases_fts) AS rank "
            "FROM cases_fts JOIN cases c ON c.id = cases_fts.rowid "
            "WHERE cases_fts MATCH ? LIMIT 100",
            (fts,),
        ).fetchall()

        results = []
        for r in rows:
            score = -r["rank"]  # bm25 is lower-is-better; flip so higher is better
            reasons = []
            if error_code and r["error_code"] and r["error_code"].lower() == error_code.lower():
                score += 10
                reasons.append("same error code")
            if device and r["device"] and r["device"].lower() == device.lower():
                score += 3
                reasons.append("same device")
            if r["status"] == "closed" and r["resolution"]:
                score += 1
                reasons.append("has recorded fix")
            results.append({
                "case_id": r["id"], "score": round(score, 2), "status": r["status"],
                "symptom": r["symptom"], "error_code": r["error_code"], "device": r["device"],
                "root_cause": r["root_cause"], "resolution": r["resolution"],
                "opened_at": r["opened_at"], "closed_at": r["closed_at"],
                "match_reasons": reasons,
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        top = results[:limit]

        for item in top:
            step_rows = conn.execute(
                "SELECT action, outcome, result FROM steps WHERE case_id = ? "
                "ORDER BY id LIMIT ?",
                (item["case_id"], MAX_STEPS_PER_CASE),
            ).fetchall()
            item["steps"] = [
                {"action": s["action"], "outcome": s["outcome"],
                 "result": (s["result"][:MAX_STEP_RESULT] + "...")
                           if s["result"] and len(s["result"]) > MAX_STEP_RESULT
                           else s["result"]}
                for s in step_rows
            ]
        return top
    finally:
        conn.close()
