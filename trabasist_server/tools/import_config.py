"""import_config: read a config file from the imports folder, strip secrets, store it."""
import os
import re
from pathlib import Path

from trabasist_server.db import get_connection
from trabasist_server.redact import redact
from trabasist_server.tools.diag_common import check_case_open

MAX_BYTES = 512 * 1024
RETURN_CHARS = 8000
ALLOWED_EXT = {".txt", ".cfg", ".conf", ".config", ".log", ".ini"}
_DEVICE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,100}$")

_KEYWORDS = (r"(?:password|passwd|passphrase|secret|psksecret|pre-shared-key|psk|wpa-psk|"
             r"authentication-key|auth-key|key-string|privacy-key|encrypted-password|"
             r"community|token|api[_-]?key|private-key|shared-secret)")

_RULES = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[REDACTED PRIVATE KEY]"),
    (re.compile(r"(?i)((?<![\w-])" + _KEYWORDS + r"(?![\w-])(?:[ \t]*[=:][ \t]*|[ \t]+))"
                r"((?:ENC[ \t]+|\d[ \t]+)?)(\"[^\"\n]*\"|\S+)"),
     r"\1\2[REDACTED]"),
    (re.compile(r"\bENC[ \t]+\S+"), "ENC [REDACTED]"),
    (re.compile(r"\$[0-9A-Za-z]{1,3}\$[^\s]{6,}"), "[REDACTED HASH]"),
    (re.compile(r"(?i)(message-digest-key[ \t]+\d+[ \t]+(?:md5|sha\S*)[ \t]+(?:\d[ \t]+)?)(\S+)"),
     r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:tacacs|radius)[^\n]*?(?<![\w-])key[ \t]+)(?:\d[ \t]+)?(\S+)"),
     r"\1[REDACTED]"),
    (re.compile(r"(?i)(snmp-server[ \t]+host[ \t]+\S+[ \t]+(?:version[ \t]+\S+[ \t]+)?"
                r"(?:(?:traps|informs)[ \t]+)?)(\S+)"),
     r"\1[REDACTED]"),
]


def import_dir():
    env = os.environ.get("TRABASIST_IMPORTS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "imports"


def redact_config(text):
    """Return (redacted_text, number_of_redactions)."""
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    text = redact(text)
    return text, text.count("[REDACTED")


def _read_file(filename):
    if not isinstance(filename, str):
        raise ValueError("filename must be text")
    name = filename.strip()
    if not _NAME_RE.match(name) or ".." in name:
        raise ValueError("filename must be a plain file name inside the imports folder (no paths)")
    if Path(name).suffix.lower() not in ALLOWED_EXT:
        raise ValueError("file type not allowed; use one of: " + ", ".join(sorted(ALLOWED_EXT)))
    folder = import_dir()
    if not folder.is_dir():
        raise ValueError("imports folder does not exist: " + str(folder))
    path = (folder / name).resolve()
    if path.parent != folder.resolve():
        raise ValueError("file must be directly inside the imports folder")
    if not path.is_file():
        raise ValueError("file not found in the imports folder")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("file is too large (max 512 KB)")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("file looks binary; only text configs are accepted")
    return name, raw.decode("utf-8", errors="replace")


def import_config(filename, device=None, case_id=None):
    """Read a config from the imports folder, redact secrets, store it."""
    name, text = _read_file(filename)

    dev = None
    if device is not None:
        if not isinstance(device, str) or not _DEVICE_RE.match(device.strip()):
            raise ValueError("device must be a plain name (letters, digits, . _ -)")
        dev = device.strip()
    if case_id is not None:
        if isinstance(case_id, bool) or not isinstance(case_id, int):
            raise ValueError("case_id must be a whole number")
        check_case_open(case_id)
    if dev is None and case_id is None:
        raise ValueError("give a device, a case_id, or both")

    redacted, count = redact_config(text)

    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO configs (device, case_id, content_redacted) VALUES (?, ?, ?)",
            (dev, case_id, redacted))
        config_id = cur.lastrowid
        conn.execute(
            "INSERT INTO audit_log (tool, device, command, result_summary) VALUES (?, ?, ?, ?)",
            ("import_config", dev, "import " + name,
             "config %d stored, %d redactions, %d characters" % (config_id, count, len(redacted))))
        conn.commit()
    finally:
        conn.close()

    shown = redacted[:RETURN_CHARS]
    return {
        "status": "ok",
        "config_id": config_id,
        "device": dev,
        "case_id": case_id,
        "file": name,
        "redactions": count,
        "characters": len(redacted),
        "truncated": len(redacted) > RETURN_CHARS,
        "content_redacted": shown,
        "note": ("Secrets were removed on a best-effort basis. Review the text before "
                 "sharing it, and never ask for the original values."),
    }
