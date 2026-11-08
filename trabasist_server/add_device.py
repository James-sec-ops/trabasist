"""add_device: interactive setup for one device.

Run from PowerShell:  python -m trabasist_server.add_device

Command-line tool only. It is NOT an MCP tool and is never registered in server.py,
so an AI client cannot call it. The password is typed hidden and goes only into .env.
"""
import getpass
import sys

from dotenv import dotenv_values

from trabasist_server.tools.command_allowlist import PLATFORMS, build_command
from trabasist_server.tools.device_setup import (
    SetupError, _check_value, add_credentials, add_device_entry, label_from_name)
from trabasist_server.tools.hostkey_setup import (
    HostKeyError, fetch_host_key, fingerprint, known_hosts_status,
    saved_key_types, trust_host_key)
from trabasist_server.tools.inventory import (
    Credentials, Device, InventoryError, _parse_device, _valid_address,
    env_path, inventory_path, load_inventory)
from trabasist_server.tools.ssh_conn import DeviceConnectionError, known_hosts_path, run_command


def _existing_devices():
    path = inventory_path()
    return load_inventory(path) if path.exists() else {}


def _ask_valid(ask, prompt, convert, out, tries=3):
    for _ in range(tries):
        try:
            return convert(ask(prompt).strip())
        except ValueError as exc:
            out(f"  {exc}")
    raise SetupError("too many invalid answers")


def _name(value):
    label = label_from_name(value)
    existing = _existing_devices()
    if value in existing:
        raise SetupError(f"device already exists: {value}")
    if any(d.credentials == label for d in existing.values()):
        raise SetupError(f"credentials label {label} is already used by another device")
    return value


def _address(value):
    if not _valid_address(value):
        raise ValueError("enter a valid IP address or hostname")
    return value


def _platform_converter(default):
    def convert(value):
        value = (value or default).lower()
        if value not in PLATFORMS:
            raise ValueError(f"choose one of: {', '.join(PLATFORMS)}")
        return value
    return convert


def _port(value):
    if not value:
        return 22
    if not (value.isascii() and value.isdigit()) or not 1 <= int(value) <= 65535:
        raise ValueError("port must be a number from 1 to 65535")
    return int(value)


def _username(value):
    _check_value("username", value)
    return value


def _ask_password(ask_secret, out, tries=3):
    for _ in range(tries):
        first = ask_secret("Password (hidden): ")
        second = ask_secret("Repeat password: ")
        if first != second:
            out("  passwords do not match")
            continue
        try:
            _check_value("password", first)
        except SetupError as exc:
            out(f"  {exc}")
            continue
        return first
    raise SetupError("password was not set")


def _precheck(name, address, platform, port):
    label = label_from_name(name)
    _parse_device({"name": name, "address": address, "platform": platform,
                   "port": port, "credentials": label})
    env_file = env_path()
    if env_file.exists():
        vals = dotenv_values(env_file, interpolate=False)
        if f"{label}_USERNAME" in vals or f"{label}_PASSWORD" in vals:
            raise SetupError(f"credentials for {label} already exist in .env")
    return label


def _confirm_host_key(address, port, ask, out):
    """Return (key, needs_saving). Refuses a changed key. Needs a typed 'yes' for a new one."""
    kh = known_hosts_path()
    types = saved_key_types(kh, address, port)
    key = fetch_host_key(address, port, key_types=types or None)
    status = known_hosts_status(kh, address, port, key)
    out(f"Server host key: {key.get_name()} {fingerprint(key)}")
    if status == "trusted":
        out("This key is already trusted on this PC.")
        return key, False
    if status == "changed":
        target = address if port == 22 else f"[{address}]:{port}"
        out("The key this device is showing is DIFFERENT from the one saved on this PC.")
        out("This can mean the device was rebuilt, or that something is pretending to be it.")
        out("If you are sure it was rebuilt, remove the old key and run this command again:")
        out(f"    ssh-keygen -R {target}")
        raise HostKeyError("host key changed; nothing was saved")
    answer = ask("Is this the right server? Type yes to trust it: ").strip().lower()
    if answer != "yes":
        raise SetupError("host key not confirmed; nothing was saved")
    return key, True


def _flow(ask, ask_secret, out):
    out("Add a device to Trabasist. Use lab devices first, not production.")
    out("The password is typed hidden and saved only in .env. It is never shown or sent to the AI.")
    name = _ask_valid(ask, "Device name (for example kali-lab): ", _name, out)
    address = _ask_valid(ask, "IP address or hostname: ", _address, out)
    default = "linux" if "linux" in PLATFORMS else next(iter(PLATFORMS))
    platform = _ask_valid(ask, f"Platform ({', '.join(PLATFORMS)}) [{default}]: ",
                          _platform_converter(default), out)
    port = _ask_valid(ask, "SSH port [22]: ", _port, out)
    username = _ask_valid(ask, "Username (a read-only account): ", _username, out)
    password = _ask_password(ask_secret, out)
    label = _precheck(name, address, platform, port)

    out("Reading the device's SSH host key (no login yet)...")
    key, needs_saving = _confirm_host_key(address, port, ask, out)
    if needs_saving:
        trust_host_key(known_hosts_path(), address, port, key)
        out("Host key saved.")
    add_device_entry(inventory_path(), name, address, platform, port)
    add_credentials(env_path(), label, username, password)
    out(f"Saved device {name}. Its login is stored in .env under {label}_USERNAME and {label}_PASSWORD.")

    device = Device(name, address, platform, port, label)
    try:
        output = run_command(device, Credentials(username, password), build_command(platform, "uptime"))
    except DeviceConnectionError as exc:
        out(f"Test login failed: {exc}")
        out(f"The device is saved. Check the {label}_ lines in .env, or the device itself, and try again.")
        return 1
    out("Test login OK: " + (output.splitlines()[0] if output else "(no output)"))
    return 0


def run_add_device(ask=input, ask_secret=getpass.getpass, out=print) -> int:
    try:
        return _flow(ask, ask_secret, out)
    except (SetupError, HostKeyError, InventoryError) as exc:
        out(f"Stopped: {exc}")
        return 1
    except (KeyboardInterrupt, EOFError):
        out("Cancelled.")
        return 1


def main() -> None:
    sys.exit(run_add_device())


if __name__ == "__main__":
    main()
