"""Load the device inventory and credentials. Secrets are never printed or logged."""
import ipaddress
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from trabasist_server.tools.command_allowlist import PLATFORMS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_LABEL_RE = re.compile(r"^[A-Z0-9_]{1,32}$")
_HOST_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")


class InventoryError(ValueError):
    pass


@dataclass(frozen=True)
class Device:
    name: str
    address: str
    platform: str
    port: int
    credentials: str


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str = field(repr=False)


def env_path():
    return Path(os.environ.get("TRABASIST_ENV", PROJECT_ROOT / ".env"))


def inventory_path():
    return Path(os.environ.get("TRABASIST_DEVICES", PROJECT_ROOT / "devices.json"))


def _valid_address(value):
    if not isinstance(value, str):
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return bool(_HOST_RE.fullmatch(value))


def _parse_device(raw):
    if not isinstance(raw, dict):
        raise InventoryError("each device must be an object")
    name, address = raw.get("name"), raw.get("address")
    platform, label = raw.get("platform"), raw.get("credentials")
    port = raw.get("port", 22)
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise InventoryError(f"invalid device name: {name!r}")
    if not _valid_address(address):
        raise InventoryError(f"invalid address for {name}")
    if platform not in PLATFORMS:
        raise InventoryError(f"unsupported platform for {name}: {platform!r}")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise InventoryError(f"invalid port for {name}")
    if not isinstance(label, str) or not _LABEL_RE.fullmatch(label):
        raise InventoryError(f"invalid credentials label for {name}")
    return Device(name, address, platform, port, label)


def load_inventory(path=None):
    path = Path(path) if path else inventory_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise InventoryError("device inventory file not found")
    except json.JSONDecodeError:
        raise InventoryError("device inventory file is not valid JSON")
    devices = data.get("devices") if isinstance(data, dict) else None
    if not isinstance(devices, list):
        raise InventoryError("inventory must contain a 'devices' list")
    result = {}
    for raw in devices:
        dev = _parse_device(raw)
        if dev.name in result:
            raise InventoryError(f"duplicate device name: {dev.name}")
        result[dev.name] = dev
    return result


def get_device(name, path=None):
    inv = load_inventory(path)
    if not isinstance(name, str) or name not in inv:
        raise InventoryError(f"device not in inventory: {name!r}")
    return inv[name]


def get_credentials(label):
    if not isinstance(label, str) or not _LABEL_RE.fullmatch(label):
        raise InventoryError("invalid credentials label")
    file_values = dotenv_values(env_path(), interpolate=False)
    user = os.environ.get(f"{label}_USERNAME") or file_values.get(f"{label}_USERNAME")
    password = os.environ.get(f"{label}_PASSWORD") or file_values.get(f"{label}_PASSWORD")
    if not user or not password:
        raise InventoryError(f"credentials for {label} are missing from .env")
    return Credentials(user, password)
