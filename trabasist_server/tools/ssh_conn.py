"""SSH connection to a device through Netmiko. Host keys are verified, never auto-accepted."""
import os
import re
from pathlib import Path

import paramiko
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

DEVICE_TYPES = {"linux": "linux"}
MAX_OUTPUT = 20000
# Fixed, internal strings (never built from user input).
_PROMPT_TEXT = "TBX> "
_PROMPT_RE = r"TBX> $"
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_SET_PROMPT = "unset PROMPT_COMMAND; PS0=''; PS1='TBX> '; export SYSTEMD_COLORS=0 TERM=dumb\n"


class DeviceConnectionError(RuntimeError):
    """Connection or command failure. Messages never contain credentials."""


class HostKeyRefused(DeviceConnectionError):
    """The device's SSH host key is unknown or does not match known_hosts."""


def known_hosts_path():
    return Path(os.environ.get("TRABASIST_KNOWN_HOSTS", Path.home() / ".ssh" / "known_hosts"))


def _is_host_key_problem(exc):
    text = str(exc).lower()
    return ("known_hosts" in text or "badhostkey" in type(exc).__name__.lower()
            or "host key" in text or "does not match" in text)


_WIN_PREFIX = 'powershell.exe -NoProfile -NonInteractive -Command "'
_MAX_READ = MAX_OUTPUT * 4


def _run_windows(device, creds, command_text, kh, timeout):
    """Windows OpenSSH: one plain exec channel, no prompt handling. Host keys are verified."""
    if not kh.is_file():
        raise HostKeyRefused("known_hosts file not found; connect once with ssh to trust the host")
    if any(ch in command_text for ch in '"\r\n\x00'):
        raise DeviceConnectionError("command text is not allowed")
    client = paramiko.SSHClient()
    client.load_host_keys(str(kh))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(device.address, port=device.port, username=creds.username,
                       password=creds.password, look_for_keys=False, allow_agent=False,
                       timeout=10, auth_timeout=15, banner_timeout=15)
        stdin, stdout, stderr = client.exec_command(_WIN_PREFIX + command_text + '"', timeout=timeout)
        stdin.close()
        raw = stdout.read(_MAX_READ)
        err = stderr.read(2000)
        status = stdout.channel.recv_exit_status()
    except paramiko.AuthenticationException:
        raise DeviceConnectionError("authentication failed")
    except Exception as exc:
        if isinstance(exc, paramiko.BadHostKeyException) or _is_host_key_problem(exc):
            raise HostKeyRefused("host key not trusted or changed; verify the device, then trust it with ssh")
        if isinstance(exc, OSError):
            raise DeviceConnectionError("connection timed out or host unreachable")
        raise DeviceConnectionError(f"{type(exc).__name__} during SSH session")
    finally:
        client.close()
    text = _ANSI_RE.sub("", raw.decode("utf-8", errors="replace").replace("\r", "")).strip("\n")
    if status != 0:
        detail = err.decode("utf-8", errors="replace").replace("\r", "").strip()
        if detail.startswith("#< CLIXML"):
            detail = ""
        note = f"[exit code {status}" + (f": {detail[:300]}" if detail else "") + "]"
        text = f"{text}\n{note}" if text else note
    if len(text) > MAX_OUTPUT:
        text = text[:MAX_OUTPUT] + "\n[output truncated]"
    return text


def run_command(device, creds, command_text, known_hosts=None, timeout=30):
    """Run one already-validated command and return its raw output text."""
    if device.platform == "windows":
        return _run_windows(device, creds, command_text,
                            Path(known_hosts) if known_hosts else known_hosts_path(), timeout)
    device_type = DEVICE_TYPES.get(device.platform)
    if device_type is None:
        raise DeviceConnectionError(f"platform not supported: {device.platform!r}")
    kh = Path(known_hosts) if known_hosts else known_hosts_path()
    if not kh.is_file():
        raise HostKeyRefused("known_hosts file not found; connect once with ssh to trust the host")

    params = dict(
        device_type=device_type,
        host=device.address,
        port=device.port,
        username=creds.username,
        password=creds.password,
        ssh_strict=True,
        system_host_keys=False,
        alt_host_keys=True,
        alt_key_file=str(kh),
        use_keys=False,
        allow_agent=False,
        conn_timeout=10,
        auth_timeout=15,
        banner_timeout=15,
        timeout=timeout,
        fast_cli=False,
        session_log=None,
    )
    conn = None
    try:
        conn = ConnectHandler(**params)
        conn.write_channel(_SET_PROMPT)
        conn.read_until_pattern(_PROMPT_RE, read_timeout=15)
        out = conn.send_command(command_text, expect_string=_PROMPT_RE,
                                strip_prompt=False, read_timeout=timeout)
    except NetmikoAuthenticationException:
        raise DeviceConnectionError("authentication failed")
    except Exception as exc:
        if _is_host_key_problem(exc):
            raise HostKeyRefused("host key not trusted or changed; verify the device, then trust it with ssh")
        if isinstance(exc, NetmikoTimeoutException):
            raise DeviceConnectionError("connection timed out or host unreachable")
        raise DeviceConnectionError(f"{type(exc).__name__} during SSH session")
    finally:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass
    out = _ANSI_RE.sub("", out.replace("\r", ""))
    if out.endswith(_PROMPT_TEXT):
        out = out[: -len(_PROMPT_TEXT)]
    out = out.strip("\n")
    if len(out) > MAX_OUTPUT:
        out = out[:MAX_OUTPUT] + "\n[output truncated]"
    return out

