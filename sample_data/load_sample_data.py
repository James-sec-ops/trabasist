"""Load a few example cases so a new install has something to search and report on.

Run from the project folder:  python sample_data/load_sample_data.py
Refuses to run if the database already contains cases. All data is fictional.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trabasist_server.db import init_db, get_connection, db_path
from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.log_step import log_step
from trabasist_server.tools.close_case import close_case

CASES = [
    {
        "symptom": "[SAMPLE] Installer fails with error 2735 on a Windows server",
        "error_code": "2735", "device": "demo-win1", "environment": "lab",
        "steps": [
            ("Checked that the server is reachable", "ping_host", "Replies received", "ruled_out"),
            ("Checked Windows Installer log", "Event log query", "Custom action failed to register a component", "cause"),
        ],
        "close": ("Damaged .NET component registration", "Repaired the .NET component and re-ran the installer"),
    },
    {
        "symptom": "[SAMPLE] SSH connection refused to Linux server",
        "error_code": None, "device": "demo-linux1", "environment": "lab",
        "steps": [
            ("Checked basic reachability", "ping_host", "Replies received", "ruled_out"),
            ("Checked whether port 22 is open", "check_port 22", "Port closed", "inconclusive"),
            ("Checked SSH service state", "systemctl_status ssh", "Service inactive (dead)", "cause"),
        ],
        "close": ("SSH service was stopped", "Started the ssh service and enabled it at boot"),
    },
    {
        "symptom": "[SAMPLE] SSH connection refused again after reboot",
        "error_code": None, "device": "demo-linux1", "environment": "lab",
        "steps": [
            ("Checked SSH service state", "systemctl_status ssh", "Service inactive (dead)", "cause"),
        ],
        "close": ("SSH service was stopped", "Enabled the ssh service at boot so it survives reboots"),
    },
    {
        "symptom": "[SAMPLE] Slow file transfers through access switch",
        "error_code": None, "device": "demo-sw1", "environment": "lab",
        "steps": [
            ("Looked at interface error counters", "show interfaces counters errors", "CRC errors rising on one port", "inconclusive"),
        ],
        "close": None,
    },
]


def _id(result):
    for key in ("case_id", "id"):
        if isinstance(result, dict) and key in result:
            return result[key]
    raise SystemExit("open_case returned an unexpected result: %r" % (result,))


def main():
    init_db()
    conn = get_connection()
    try:
        n = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    finally:
        conn.close()
    print("Database:", db_path())
    if n:
        raise SystemExit("Database already has %d case(s). Nothing loaded." % n)

    for c in CASES:
        cid = _id(open_case(c["symptom"], c["error_code"], c["device"], c["environment"]))
        for action, command, result, outcome in c["steps"]:
            log_step(cid, action, command, result, outcome)
        if c["close"]:
            close_case(cid, c["close"][0], c["close"][1])
        print("Loaded case", cid, "-", c["symptom"])
    print("Done.")


if __name__ == "__main__":
    main()
