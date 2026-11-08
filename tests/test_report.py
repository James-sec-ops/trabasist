import os
import tempfile

tmp = tempfile.mkdtemp()
os.environ["TRABASIST_DB"] = os.path.join(tmp, "test.db")

from trabasist_server.db import init_db, get_connection
from trabasist_server.tools.report import report

init_db()
passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print("FAIL:", name)


def raises(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ValueError:
        return True
    return False


def find(groups, value):
    for g in groups:
        if g["value"] == value:
            return g
    return None


# Empty database
r = report()
check("empty total", r["total_cases"] == 0)
check("empty message", "No cases" in r.get("message", ""))
check("empty avg none", r["avg_minutes_to_resolve"] is None)

# Made-up cases (old dates, except the last one which is "now")
rows = [
    ("2020-01-01 10:00:00", "2020-01-01 11:00:00", "disk full", "2735", "kali-lab", "closed", "Missing .NET"),
    ("2020-01-02 12:00:00", "2020-01-02 12:30:00", "disk full again", "2735", "KALI-LAB", "closed", "missing .net "),
    ("2020-01-03 09:00:00", None, "slow", None, "kali-lab", "open", None),
    ("2020-01-03 10:00:00", "2020-01-03 11:30:00", "not found", "127", "sw-1", "closed", "Service stopped"),
    ("2020-01-04 10:00:00", None, "blank fields", "", "", "open", None),
]
conn = get_connection()
for opened, closed, symptom, code, dev, status, cause in rows:
    conn.execute(
        "INSERT INTO cases (opened_at, closed_at, symptom, error_code, device, status, root_cause, resolution) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (opened, closed, symptom, code, dev, status, cause, None))
conn.execute(
    "INSERT INTO cases (symptom, device, status) VALUES (?, ?, ?)",
    ("new issue", "kali-lab", "open"))
conn.commit()
conn.close()

r = report()
check("total 6", r["total_cases"] == 6)
check("open 3", r["open_cases"] == 3)
check("closed 3", r["closed_cases"] == 3)
check("avg 60", r["avg_minutes_to_resolve"] == 60.0)
check("median 60", r["median_minutes_to_resolve"] == 60.0)
d = find(r["by_device"], "kali-lab")
check("kali-lab found, case-insensitive", d is not None and d["cases"] == 4)
check("kali-lab closed 2", d is not None and d["closed"] == 2)
check("kali-lab avg 45", d is not None and d["avg_minutes_to_resolve"] == 45.0)
check("sw-1 hidden at min 2", find(r["by_device"], "sw-1") is None)
check("blank values ignored", all(g["value"] for g in r["by_device"] + r["by_error_code"]))
e = find(r["by_error_code"], "2735")
check("2735 cases 2", e is not None and e["cases"] == 2)
check("2735 avg 45", e is not None and e["avg_minutes_to_resolve"] == 45.0)
check("127 hidden at min 2", find(r["by_error_code"], "127") is None)
c = find(r["by_root_cause"], "missing .net")
check("root cause merged", c is not None and c["cases"] == 2)

r1 = report(min_count=1)
check("service stopped at min 1", find(r1["by_root_cause"], "service stopped") is not None)
check("two devices at min 1", len(r1["by_device"]) == 2)
check("two error codes at min 1", len(r1["by_error_code"]) == 2)
check("limit 1", len(report(min_count=1, limit=1)["by_device"]) == 1)

r = report(days=1)
check("days=1 total", r["total_cases"] == 1)
check("days=1 open", r["open_cases"] == 1)
check("days=1 closed", r["closed_cases"] == 0)
check("days=1 message", "No issue" in r.get("message", ""))
check("days=1 period", r["period"] == "last 1 days")
check("days=7 total", report(days=7)["total_cases"] == 1)

r = report(min_count=5)
check("min 5 empty groups", not (r["by_device"] or r["by_error_code"] or r["by_root_cause"]))
check("min 5 message", "No issue" in r.get("message", ""))

check("days=0 refused", raises(report, days=0))
check("days=True refused", raises(report, days=True))
check("days text refused", raises(report, days="7"))
check("days huge refused", raises(report, days=100000))
check("min_count=0 refused", raises(report, min_count=0))
check("limit=51 refused", raises(report, limit=51))
check("limit=0 refused", raises(report, limit=0))

print("passed", passed, "failed", failed)
print("PASS" if failed == 0 else "FAILED")
