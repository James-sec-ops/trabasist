"""Redaction helper: strip secrets from text before it is stored."""
import re

_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[REDACTED PRIVATE KEY]"),
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|apikey|community)"
                r"(\s*[=:]\s*|\s+)(?:[0-9]\s+)?(\S+)"),
     r"\1\2[REDACTED]"),
]


def redact(text):
    if text is None:
        return None
    text = str(text)
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text
