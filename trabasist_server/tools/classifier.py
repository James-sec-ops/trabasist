"""Command classifier. Pure functions: no I/O, nothing is run here.

Tier 1: read-only. Only the exact text of an allowlist command.
Tier 2: normal change, from a small set of strict patterns.
Tier 3: everything else. Unknown, chained, piped, redirected, encoded or non-ASCII
        input is Tier 3.

classify() never raises. It does not strip, lower-case or otherwise normalise the
command: the text that was classified is the text that would be sent.
"""
import ipaddress
import re
from functools import lru_cache
from types import MappingProxyType
from typing import NamedTuple

from trabasist_server.tools.command_allowlist import CommandRefused, PLATFORMS, build_command

MAX_LEN = 500


class Classification(NamedTuple):
    tier: int
    rule: str
    reason: str


def _t3(rule, reason):
    return Classification(3, rule, reason)


# Characters that chain, pipe, redirect, substitute or control the shell, plus all control
# characters. Anything containing one is never Tier 2, and Tier 1 only by exact match.
_META_RE = re.compile(r"[;&|<>`$\x00-\x1f\x7f]")

# Used only to label a Tier 3 result. Everything unknown is Tier 3 regardless.
_NESTED_RE = re.compile(
    r"(?<![\w-])(?:-enc\w*|frombase64string|base64|iex|invoke-expression|invoke-command|"
    r"eval|bash|sh|zsh|dash|powershell|pwsh|cmd|cmd\.exe)(?![\w-])",
    re.IGNORECASE,
)

_SVC = r"[A-Za-z0-9][A-Za-z0-9@._-]{0,63}"
_PKG = r"[a-z0-9][a-z0-9+._:-]{0,63}"
_IFACE = r"[A-Za-z0-9][A-Za-z0-9._-]{0,14}"

_LINUX_SVC_RE = re.compile(rf"systemctl (restart|start|reload) ({_SVC})", re.ASCII)
_LINUX_PKG_RE = re.compile(
    rf"(apt-get|apt|dnf|yum) install -y ({_PKG}(?: {_PKG}){{0,4}})", re.ASCII)
_LINUX_IPADD_RE = re.compile(
    rf"ip addr add (\d{{1,3}}(?:\.\d{{1,3}}){{3}}/\d{{1,2}}) dev ({_IFACE})", re.ASCII)
_WIN_SVC_RE = re.compile(
    rf"(Restart-Service|Start-Service) -Name ({_SVC})", re.ASCII | re.IGNORECASE)

_LINUX_PROTECTED = frozenset(
    {"ssh", "sshd", "networking", "network", "networkmanager", "systemd-networkd"})
_WINDOWS_PROTECTED = frozenset(
    {"sshd", "winrm", "dhcp", "dnscache", "nlasvc", "netman", "netprofm",
     "lanmanserver", "eventlog"})


@lru_cache(maxsize=None)
def _tier1_texts(platform):
    """Map exact command text to allowlist name, for commands that need no parameters."""
    found = {}
    if platform in PLATFORMS:
        for name in PLATFORMS[platform]:
            try:
                found[build_command(platform, name, {})] = name
            except CommandRefused:
                pass
    return MappingProxyType(found)


def _linux_service(m):
    verb, svc = m.group(1), m.group(2)
    base = svc.lower()
    if base.endswith(".service"):
        base = base[: -len(".service")]
    if base in _LINUX_PROTECTED:
        return _t3("tier3:protected-service",
                   f"{svc} carries the management session or the network")
    return Classification(2, f"tier2:linux:systemctl-{verb}", f"{verb} service {svc}")


def _linux_package(m):
    return Classification(2, f"tier2:linux:{m.group(1)}-install", f"install {m.group(2)}")


def _linux_ip_add(m):
    try:
        iface = ipaddress.IPv4Interface(m.group(1))
    except ValueError:
        return _t3("tier3:invalid-args", "not a valid IPv4 address with prefix")
    ip = iface.ip
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or iface.network.prefixlen < 8:
        return _t3("tier3:unsafe-address", "loopback, unspecified, multicast or prefix below /8")
    return Classification(2, "tier2:linux:ip-addr-add", f"add address {m.group(1)} on {m.group(2)}")


def _windows_service(m):
    verb, svc = m.group(1).lower(), m.group(2)
    if svc.lower() in _WINDOWS_PROTECTED:
        return _t3("tier3:protected-service",
                   f"{svc} carries the management session or the network")
    return Classification(2, f"tier2:windows:{verb}", f"{verb} {svc}")


_TIER2 = {
    "linux": [
        (_LINUX_SVC_RE, _linux_service),
        (_LINUX_PKG_RE, _linux_package),
        (_LINUX_IPADD_RE, _linux_ip_add),
    ],
    "windows": [(_WIN_SVC_RE, _windows_service)],
}

# Platforms planned for later phases. They have no rules yet, so everything is Tier 3.
_NO_RULES_YET = frozenset({"cisco", "mikrotik"})


def classify(platform, command):
    """Return Classification(tier, rule, reason) for a free-form command. Never raises."""
    if not isinstance(platform, str) or not isinstance(command, str):
        return _t3("tier3:bad-input", "platform and command must be text")

    # Tier 1: the whole string equals an allowlist command.
    tier1 = _tier1_texts(platform)
    if command in tier1:
        return Classification(1, f"tier1:allowlist:{tier1[command]}", "exact allowlist command")

    rules = _TIER2.get(platform)
    if rules is None:
        if platform in _NO_RULES_YET:
            return _t3("tier3:no-rules-yet", f"no rules for {platform} yet; only Tier 3")
        return _t3("tier3:unknown-platform", "platform is not supported")

    if not command or len(command) > MAX_LEN or not command.isascii():
        return _t3("tier3:bad-input", "empty, too long or not plain ASCII")
    if _META_RE.search(command):
        return _t3("tier3:shell-syntax",
                   "chaining, pipe, redirect, substitution or control character")

    for pattern, handler in rules:
        m = pattern.fullmatch(command)
        if m:
            return handler(m)

    if _NESTED_RE.search(command):
        return _t3("tier3:encoded-or-nested-shell", "encoded or nested shell command")
    return _t3("tier3:unknown", "not a recognised command; unknown commands are Tier 3")


def classify_named(platform, name, params=None):
    """Build an allowlist command and classify it. Raises CommandRefused like build_command.

    Returns (command_text, Classification). Every allowlist command is Tier 1.
    """
    command = build_command(platform, name, params)
    return command, Classification(1, f"tier1:allowlist:{name}", "named allowlist command")
