"""lookup_error_code: a local, extensible table of error codes."""
import re

from trabasist_server.db import get_connection

_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:/\-]{0,63}$")
_PLATFORM_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,31}$")
_MAX_TEXT = 1000


def _clean_code(code):
    if not isinstance(code, str):
        raise ValueError("error code must be text")
    c = code.strip()
    if not _CODE_RE.match(c):
        raise ValueError("error code has invalid characters or is too long")
    return c


def _clean_platform(platform):
    if platform is None:
        return None
    if not isinstance(platform, str):
        raise ValueError("platform must be text")
    p = platform.strip().lower()
    if not p:
        return None
    if not _PLATFORM_RE.match(p):
        raise ValueError("platform must be letters, digits, - or _ (max 32)")
    return p


def _clean_text(value, name, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(name + " must be text")
    v = value.strip()
    if required and not v:
        raise ValueError(name + " is required")
    if len(v) > _MAX_TEXT:
        raise ValueError(name + " is too long (max 1000 characters)")
    return v


def lookup_error_code(code, platform=None):
    """Look up an error code. Returns a dict; never changes anything."""
    c = _clean_code(code)
    p = _clean_platform(platform)
    sql = ("SELECT id, code, platform, meaning, likely_causes, notes "
           "FROM error_codes WHERE lower(code) = lower(?)")
    params = [c]
    if p:
        sql += " AND (lower(platform) = ? OR platform IS NULL)"
        params.append(p)
    sql += " ORDER BY id"
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    matches = [
        {"id": r[0], "code": r[1], "platform": r[2], "meaning": r[3],
         "likely_causes": r[4], "notes": r[5]}
        for r in rows
    ]
    if matches:
        return {"status": "found", "code": c, "matches": matches}
    return {
        "status": "not_found",
        "code": c,
        "matches": [],
        "message": ("No local entry for this code. Try find_similar_cases "
                    "for past cases, then a web search using the evidence "
                    "gathered so far."),
    }


def add_error_code(code, platform, meaning, likely_causes, notes=None):
    """Add a user entry. Refuses duplicates of the same code and platform."""
    c = _clean_code(code)
    p = _clean_platform(platform)
    m = _clean_text(meaning, "meaning", required=True)
    lc = _clean_text(likely_causes, "likely_causes")
    n = _clean_text(notes, "notes")
    conn = get_connection()
    try:
        dup = conn.execute(
            "SELECT id FROM error_codes WHERE lower(code) = lower(?) "
            "AND coalesce(lower(platform), '') = ?",
            (c, p or ""),
        ).fetchone()
        if dup:
            raise ValueError("an entry for this code and platform already exists")
        cur = conn.execute(
            "INSERT INTO error_codes (code, platform, meaning, likely_causes, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (c, p, m, lc, n),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# Starter entries, written for this project. Verify before relying on them.
STARTER_CODES = [
    ("2735", "windows", "Windows Installer: a custom action that uses a .NET assembly failed.",
     "Missing or damaged .NET Framework; installer cannot register the assembly; leftover files from an earlier install.", None),
    ("0x80070005", "windows", "Access denied.",
     "Not running as administrator; folder or registry permissions; security software blocking the action.", None),
    ("0x80070057", "windows", "The parameter is incorrect.",
     "Bad value passed to an operation; damaged update cache; disk or partition problem.", None),
    ("0x80070002", "windows", "The system cannot find the file specified.",
     "Missing or moved file; damaged update components; wrong path in a setting.", None),
    ("0x80004005", "windows", "Unspecified error.",
     "Generic failure; check permissions, security software, damaged files; look for a more specific event nearby.", None),
    ("4625", "windows", "Event ID 4625: an account failed to log on.",
     "Wrong password; locked or disabled account; wrong logon type; brute-force attempts.", "Check the logon type and source address in the event."),
    ("7034", "windows", "Event ID 7034: a service terminated unexpectedly.",
     "Service crash; missing dependency; resource shortage; bad update or configuration.", None),
    ("41", "windows", "Event ID 41 (Kernel-Power): the system restarted without a clean shutdown.",
     "Power loss; crash or blue screen; overheating; hardware or driver fault.", None),
    ("126", "linux", "Exit code 126: command found but cannot be run.",
     "File is not executable; no permission; wrong architecture.", None),
    ("127", "linux", "Exit code 127: command not found.",
     "Typo; program not installed; not in PATH.", None),
    ("137", "linux", "Exit code 137: process was killed (SIGKILL).",
     "Out-of-memory killer; killed manually; container memory limit.", "Check dmesg or the journal for out-of-memory messages."),
    ("255", "linux", "Exit code 255: often an SSH connection or login failure.",
     "Host unreachable; wrong credentials; host key problem; connection refused.", None),
    ("errno 13", "linux", "Permission denied.",
     "Wrong file or directory permissions; not the owner; needs elevated rights; SELinux or AppArmor.", None),
    ("errno 28", "linux", "No space left on device.",
     "Disk full; inodes used up; large logs or temp files.", "Compare df -h with df -i."),
    ("errno 98", "linux", "Address already in use.",
     "Another process is on that port; a previous instance is still running.", "ss -tuln shows what is listening."),
    ("errno 111", "linux", "Connection refused.",
     "Service not running; wrong port; firewall rejecting the connection.", None),
    ("errno 110", "linux", "Connection timed out.",
     "Host down; firewall dropping packets; routing problem.", None),
    ("errno 2", "linux", "No such file or directory.",
     "Wrong path; file deleted or not yet created; typo.", None),
]


def seed_starter_codes():
    """Add the starter entries that are missing. Returns how many were added."""
    added = 0
    for code, platform, meaning, causes, notes in STARTER_CODES:
        try:
            add_error_code(code, platform, meaning, causes, notes)
            added += 1
        except ValueError:
            pass
    return added
