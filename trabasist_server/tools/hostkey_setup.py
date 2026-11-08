"""Host key helpers for add_device: fetch a server's key, compare with known_hosts, trust it."""
import base64
import hashlib
import re
import socket
from pathlib import Path

import paramiko

from trabasist_server.tools.inventory import _valid_address


class HostKeyError(RuntimeError):
    """A host key could not be fetched, checked or saved. No credentials are involved."""


_TYPE_RE = re.compile(r"^[a-z0-9@.-]{1,64}$")


def _hostname_for(address, port):
    return address if port == 22 else f"[{address}]:{port}"


def _check_target(address, port):
    if not _valid_address(address):
        raise HostKeyError("invalid address")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise HostKeyError("invalid port")


def fingerprint(key):
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def fetch_host_key(address, port=22, timeout=10, key_types=None):
    """Connect, read the server's host key and disconnect. Never logs in."""
    _check_target(address, port)
    try:
        sock = socket.create_connection((address, port), timeout=timeout)
    except OSError:
        raise HostKeyError("could not connect to the device (unreachable or port closed)") from None
    transport = paramiko.Transport(sock)
    try:
        if key_types:
            opts = transport.get_security_options()
            wanted = [k for k in key_types if k in opts.key_types]
            if not wanted:
                raise HostKeyError("none of the saved key types can be checked on this PC")
            opts.key_types = wanted
        transport.start_client(timeout=timeout)
        key = transport.get_remote_server_key()
    except (paramiko.SSHException, OSError, EOFError):
        if key_types:
            raise HostKeyError("the device did not offer a host key of the type already saved") from None
        raise HostKeyError("the SSH handshake with the device failed") from None
    finally:
        transport.close()
    return key


def _load(path):
    path = Path(path)
    hk = paramiko.HostKeys()
    if path.is_file():
        try:
            hk.load(str(path))
        except (OSError, UnicodeDecodeError):
            raise HostKeyError("known_hosts could not be read") from None
    return hk


def saved_key_types(path, address, port=22):
    """Key types already saved for this address (empty list if none)."""
    _check_target(address, port)
    entries = _load(path).lookup(_hostname_for(address, port))
    return list(entries.keys()) if entries else []


def known_hosts_status(path, address, port, key):
    """Return 'unknown' (no entry), 'trusted' (same key saved) or 'changed' (different key saved)."""
    _check_target(address, port)
    entries = _load(path).lookup(_hostname_for(address, port))
    if not entries:
        return "unknown"
    saved = entries.get(key.get_name())
    if saved is not None and saved.asbytes() == key.asbytes():
        return "trusted"
    return "changed"


def trust_host_key(path, address, port, key):
    """Append the key to known_hosts. Returns True if saved, False if it was already trusted.
    A different key for the same address is refused and never overwritten."""
    status = known_hosts_status(path, address, port, key)
    if status == "changed":
        raise HostKeyError("a different key is already saved for this address and is never overwritten")
    if status == "trusted":
        return False
    name = key.get_name()
    if not _TYPE_RE.fullmatch(name):
        raise HostKeyError("unexpected host key type")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{prefix}{_hostname_for(address, port)} {name} {key.get_base64()}\n")
    return True
