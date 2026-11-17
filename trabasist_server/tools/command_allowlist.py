"""Read-only command allowlist. Only commands listed here can ever run."""
import ipaddress
import re

from trabasist_server.tools.diag_common import validate_host

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


_DNS_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "PTR")
_HOST_CHARS = re.compile(r"^[A-Za-z0-9:.-]+\Z")


def _host(params, key):
    value = params.get(key)
    if value is None:
        raise CommandRefused(f"{key} is required")
    try:
        host = validate_host(value)
    except ValueError:
        raise CommandRefused(f"{key} is not a valid host") from None
    if host.startswith("-") or not _HOST_CHARS.match(host):
        raise CommandRefused(f"{key} contains characters that are not allowed")
    return host


def _ping(p):
    count = _int(p, "count", 4, 1, 10)
    return f"ping -n -c {count} -W 2 {_host(p, 'host')}"


def _traceroute(p):
    hops = _int(p, "max_hops", 15, 1, 30)
    return f"traceroute -n -m {hops} -w 1 -q 1 {_host(p, 'host')}"


def _dig(p):
    kind = p.get("record_type", "A")
    if not isinstance(kind, str) or kind.upper() not in _DNS_TYPES:
        raise CommandRefused("record_type must be one of: " + ", ".join(_DNS_TYPES))
    kind = kind.upper()
    name = _host(p, "name")
    base = "dig +time=3 +tries=1"
    if kind == "PTR":
        try:
            ipaddress.ip_address(name)
        except ValueError:
            raise CommandRefused("PTR lookups need an IP address") from None
        return f"{base} -x {name}"
    return f"{base} {name} {kind}"


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
    "ping": ({"host", "count"}, _ping),
    "traceroute": ({"host", "max_hops"}, _traceroute),
    "dig": ({"name", "record_type"}, _dig),
    "ip_link_stats": (set(), lambda p: "ip -s link"),
    "ip_neigh": (set(), lambda p: "ip neigh"),
    "resolv_conf": (set(), lambda p: "cat /etc/resolv.conf"),
    "uname": (set(), lambda p: "uname -a"),
    "os_release": (set(), lambda p: "cat /etc/os-release"),
    "timedatectl": (set(), lambda p: "timedatectl"),
    "systemctl_failed": (set(), lambda p: "systemctl --failed --no-pager"),
    "ps_top_cpu": (set(), lambda p: "ps -eo pid,user,%cpu,%mem,stat,etime,comm --sort=-%cpu | head -n 11"),
    "ps_top_mem": (set(), lambda p: "ps -eo pid,user,%cpu,%mem,stat,etime,comm --sort=-%mem | head -n 11"),
    "lsblk": (set(), lambda p: "lsblk"),
    "df_inodes": (set(), lambda p: "df -i"),
    "who": (set(), lambda p: "who"),
}

# ---- Windows (PowerShell over OpenSSH) ----
# Command text must contain no double quote, dollar sign, brace, backtick or semicolon, so it
# behaves the same whether cmd.exe or PowerShell is the default SSH shell.
_LIST = " | Format-List | Out-String -Width 200"
_TABLE = " | Format-Table -AutoSize | Out-String -Width 200"
_EVENT_LOGS = ("System", "Application")


def _choice(params, key, choices, default):
    value = params.get(key, default)
    if not isinstance(value, str) or value not in choices:
        raise CommandRefused(f"{key} must be one of: " + ", ".join(choices))
    return value


def _cim(cls, props):
    return f"Get-CimInstance {cls} | Select-Object {props}" + _LIST


def _eventlog(p):
    log = _choice(p, "log", _EVENT_LOGS, "System")
    lines = _int(p, "lines", 20, 1, 100)
    return (f"Get-WinEvent -LogName {log} -MaxEvents {lines} | "
            "Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message" + _LIST)


def _test_netconnection(p):
    host = _host(p, "host")
    if "port" not in p:
        raise CommandRefused("port is required")
    port = _int(p, "port", 0, 1, 65535)
    return (f"Test-NetConnection -ComputerName {host} -Port {port} -WarningAction SilentlyContinue | "
            "Select-Object ComputerName,RemoteAddress,RemotePort,InterfaceAlias,SourceAddress,"
            "TcpTestSucceeded" + _LIST)


WINDOWS = {
    "uptime": (set(), lambda p: "New-TimeSpan -Seconds (([Environment]::TickCount -band 4294967295) / 1000) | Select-Object Days,Hours,Minutes,Seconds" + _LIST),
    "os_info": (set(), lambda p: r"Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' | Select-Object ProductName,DisplayVersion,CurrentBuild,UBR" + _LIST),
    "cpu": (set(), lambda p: r"Get-ChildItem -Path 'HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor' | Get-ItemProperty | Select-Object PSChildName,ProcessorNameString" + _TABLE),
    "memory": (set(), lambda p: _cim("Win32_OperatingSystem", "TotalVisibleMemorySize,FreePhysicalMemory")),
    "disk": (set(), lambda p: "[System.IO.DriveInfo]::GetDrives() | Where-Object IsReady | Select-Object Name,DriveType,TotalSize,AvailableFreeSpace" + _TABLE),
    "services": (set(), lambda p: "Get-Service | Sort-Object Status,Name | Select-Object Name,Status,StartType" + _TABLE),
    "service_status": (
        {"service"},
        lambda p: (f"Get-Service -Name {_service(p, 'service', True)} | "
                   "Select-Object Name,DisplayName,Status,StartType" + _LIST),
    ),
    "processes_top_cpu": (set(), lambda p: "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Id,ProcessName,CPU,WorkingSet" + _TABLE),
    "processes_top_mem": (set(), lambda p: "Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10 Id,ProcessName,CPU,WorkingSet" + _TABLE),
    "eventlog": ({"log", "lines"}, _eventlog),
    "ipconfig": (set(), lambda p: "ipconfig /all"),
    "netstat": (set(), lambda p: "netstat -an"),
    "routes": (set(), lambda p: "route print"),
    "test_netconnection": ({"host", "port"}, _test_netconnection),
}

PLATFORMS = {"linux": LINUX, "windows": WINDOWS}


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
