"""report: summarise recurring issues and time to resolve. Read-only."""
import statistics

from trabasist_server.db import get_connection

_DEVICE = "NULLIF(lower(trim(device)), '')"
_ERROR = "NULLIF(lower(trim(error_code)), '')"
_CAUSE = "NULLIF(lower(trim(root_cause)), '')"
_MINUTES = "(julianday(closed_at) - julianday(opened_at)) * 1440"


def _int_in_range(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(name + " must be a whole number")
    if value < low or value > high:
        raise ValueError(name + " must be between %d and %d" % (low, high))
    return value


def _groups(conn, expr, base_where, base_params, min_count, limit, closed_only=False):
    # expr and base_where are fixed constants from this file, never user input.
    where = base_where + " AND " + expr + " IS NOT NULL"
    if closed_only:
        where += " AND status = 'closed'"
    sql = (
        "SELECT " + expr + " AS k, COUNT(*), "
        "SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END), "
        "AVG(CASE WHEN closed_at IS NOT NULL THEN " + _MINUTES + " END) "
        "FROM cases WHERE " + where + " GROUP BY k HAVING COUNT(*) >= ? "
        "ORDER BY COUNT(*) DESC, k LIMIT ?"
    )
    rows = conn.execute(sql, list(base_params) + [min_count, limit]).fetchall()
    out = []
    for k, n, closed, avg in rows:
        out.append({
            "value": k,
            "cases": n,
            "closed": closed or 0,
            "avg_minutes_to_resolve": round(avg, 1) if avg is not None else None,
        })
    return out


def report(days=None, min_count=2, limit=10):
    """Summarise recurring issues by device, error code and root cause."""
    if days is not None:
        days = _int_in_range(days, "days", 1, 3650)
    min_count = _int_in_range(min_count, "min_count", 1, 1000)
    limit = _int_in_range(limit, "limit", 1, 50)

    if days is None:
        where, params = "1 = 1", []
        period = "all time"
    else:
        where, params = "opened_at >= datetime('now', ?)", ["-%d days" % days]
        period = "last %d days" % days

    conn = get_connection()
    try:
        total, open_n, closed_n = conn.execute(
            "SELECT COUNT(*), "
            "COALESCE(SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END), 0), "
            "COALESCE(SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END), 0) "
            "FROM cases WHERE " + where, params).fetchone()
        mins = [
            r[0] for r in conn.execute(
                "SELECT " + _MINUTES + " FROM cases WHERE " + where +
                " AND closed_at IS NOT NULL", params).fetchall()
            if r[0] is not None
        ]
        result = {
            "period": period,
            "total_cases": total,
            "open_cases": open_n,
            "closed_cases": closed_n,
            "avg_minutes_to_resolve": round(statistics.mean(mins), 1) if mins else None,
            "median_minutes_to_resolve": round(statistics.median(mins), 1) if mins else None,
            "min_count": min_count,
            "by_device": _groups(conn, _DEVICE, where, params, min_count, limit),
            "by_error_code": _groups(conn, _ERROR, where, params, min_count, limit),
            "by_root_cause": _groups(conn, _CAUSE, where, params, min_count, limit,
                                     closed_only=True),
        }
    finally:
        conn.close()

    if total == 0:
        result["message"] = "No cases in this period."
    elif not (result["by_device"] or result["by_error_code"] or result["by_root_cause"]):
        result["message"] = ("No issue appears %d or more times in this period. "
                             "Use a lower min_count to see single cases." % min_count)
    return result
