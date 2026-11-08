"""File logic for the add_device helper: updates devices.json and .env. No network, no prompts."""
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from dotenv import dotenv_values

from trabasist_server.tools.inventory import (
    InventoryError, _LABEL_RE, _NAME_RE, _parse_device, load_inventory)


class SetupError(ValueError):
    """A device or credentials could not be added. Messages never contain passwords."""


def label_from_name(name):
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise SetupError("invalid device name")
    label = re.sub(r"[^A-Za-z0-9]+", "_", name).upper().strip("_")
    if not _LABEL_RE.fullmatch(label):
        raise SetupError("device name is too long to make a credentials label (max 32 characters)")
    return label


def _backup(path):
    shutil.copy2(path, path.with_name(path.name + ".bak"))


def _write_atomic(path, text):
    # Temp file ends in .bak so a leftover after a crash is ignored by .gitignore.
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".bak")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def add_device_entry(path, name, address, platform, port=22):
    """Add one device to the inventory file. Returns its credentials label."""
    path = Path(path)
    label = label_from_name(name)
    raw = {"name": name, "address": address, "platform": platform,
           "port": port, "credentials": label}
    try:
        _parse_device(raw)
        existing = load_inventory(path) if path.exists() else {}
    except InventoryError as exc:
        raise SetupError(str(exc)) from None
    if name in existing:
        raise SetupError(f"device already exists: {name}")
    if any(d.credentials == label for d in existing.values()):
        raise SetupError(f"credentials label {label} is already used by another device")
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        _backup(path)
    else:
        data = {"devices": []}
    data["devices"].append(raw)
    _write_atomic(path, json.dumps(data, indent=2) + "\n")
    return label


def _check_value(kind, value):
    if not isinstance(value, str) or not value:
        raise SetupError(f"{kind} is required")
    if any(ch in value for ch in "\r\n\x00"):
        raise SetupError(f"{kind} must not contain line breaks")


def _quote(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def add_credentials(path, label, username, password):
    """Add LABEL_USERNAME and LABEL_PASSWORD to the .env file."""
    path = Path(path)
    if not isinstance(label, str) or not _LABEL_RE.fullmatch(label):
        raise SetupError("invalid credentials label")
    _check_value("username", username)
    _check_value("password", password)
    text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    existing = dotenv_values(path, interpolate=False) if path.exists() else {}
    if f"{label}_USERNAME" in existing or f"{label}_PASSWORD" in existing:
        raise SetupError(f"credentials for {label} already exist in .env")
    if text and not text.endswith("\n"):
        text += "\n"
    text += f"{label}_USERNAME={_quote(username)}\n{label}_PASSWORD={_quote(password)}\n"
    if path.exists():
        _backup(path)
    _write_atomic(path, text)
