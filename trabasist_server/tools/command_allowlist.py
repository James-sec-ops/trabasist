"""Read-only command allowlist. Only commands listed here can ever run."""
import re

class CommandRefused(ValueError):
    """Raised when a command name, platform or parameter is not allowed."""

_SERVICE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9@._-]{0,63}$")


def _int(params, key, default, lo, hi):
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CommandRefused(f"{key} must be a whole number")
    if not lo <= value <= hi:
        raise CommandRefused(f"{key} must be between {lo} and {hi}")
    return value


def _service(params, key, required):
    value = params.get(key)
    if value is None:
        if required:
            raise CommandRefused(f"{key} is required")
        return None
    if not isinstance(value, str) or not _SERVICE_RE.fullmatch(value):
        raise CommandRefused(f"{key} has invalid characters or length")
    return value


def _journalctl(p):
    lines = _int(p, "lines", 50, 1, 500)
    unit = _service(p, "unit", required=False)
    cmd = f"journalctl -n {lines} --no-pager"
    return f"{cmd} -u {unit}" if unit else cmd


# name -> (allowed parameter names, function that builds the command text)
LINUX = {
    "uptime": (set(), lambda p: "uptime"),
    "df": (set(), lambda p: "df -h"),
    "free": (set(), lambda p: "free -h"),
    "systemctl_status": (
        {"service"},
        lambda p: f"systemctl status {_service(p, 'service', True)} --no-pager -l",
    ),
    "journalctl": ({"unit", "lines"}, _journalctl),
    "dmesg": ({"lines"}, lambda p: f"dmesg | tail -n {_int(p, 'lines', 100, 1, 500)}"),
    "ip_a": (set(), lambda p: "ip a"),
    "ip_route": (set(), lambda p: "ip route"),
    "ss": (set(), lambda p: "ss -tuln"),
    "last": ({"count"}, lambda p: f"last -n {_int(p, 'count', 20, 1, 100)}"),
}

PLATFORMS = {"linux": LINUX}


def list_commands(platform):
    table = PLATFORMS.get(platform)
    if table is None:
        raise CommandRefused(f"platform not supported: {platform!r}")
    return {name: sorted(spec[0]) for name, spec in table.items()}


def build_command(platform, name, params=None):
    """Return the exact command text to run, or raise CommandRefused."""
    params = params or {}
    table = PLATFORMS.get(platform) if isinstance(platform, str) else None
    if table is None:
        raise CommandRefused(f"platform not supported: {platform!r}")
    if not isinstance(name, str) or name not in table:
        raise CommandRefused(f"command not in allowlist: {name!r}")
    if not isinstance(params, dict):
        raise CommandRefused("params must be a dictionary")
    allowed, builder = table[name]
    extra = set(params) - allowed
    if extra:
        raise CommandRefused(f"parameters not allowed for {name}: {sorted(extra)}")
    return builder(params)
