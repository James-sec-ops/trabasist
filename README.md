# Trabasist

Trabasist is an open-source [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server that lets an AI client such as Claude Desktop help an IT person diagnose and resolve issues on networks, servers and devices.

It is a resolution memory, not a ticketing system. Tracking exists to get the next problem solved faster. It does four things a plain chat cannot:

1. Records every issue as a structured case, so nothing is lost.
2. Gathers real evidence by running safe, read-only checks.
3. Searches past cases to suggest likely causes and fixes.
4. Reports on recurring problems.

> **WARNING: test on lab devices first, not production.**
> Trabasist 1.0.0 is a first public release and has had little outside testing. It only runs allowlisted, read-only commands, but it logs in to real devices over SSH. Use a read-only account, try it on lab machines, and read the output yourself before acting on it.

## What version 1 supports

| Area | Supported in v1 |
|---|---|
| Where the server runs | Windows only (ping and traceroute use the Windows `ping` and `tracert`) |
| AI client | Claude Desktop, launching the server locally |
| Device commands over SSH | Linux only, with a fixed read-only allowlist |
| Login method | Username and password (stored in `.env`) |
| Storage | A local SQLite database with full-text search, one per user |

Not in v1 (planned for later): Windows Server device commands, SSH keys, switch and firewall command sets, configuration snapshots and diffing, a shared team database, and a Linux or Mac version of the server itself.


## Install

You need Windows, Python 3.12, Git and [Claude Desktop](https://claude.ai/download).

```powershell
git clone <repo-url> trabasist
cd trabasist
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell refuses to run the activate script, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Quick start

**1. Add a device.** Use a lab machine and a read-only account. The helper asks for a name, address, platform (`linux`), username and password (typed twice, hidden), then shows the device's SSH fingerprint. Type `yes` only if you trust it.

```powershell
python -m trabasist_server.add_device
```

The password goes into `.env` and never into `devices.json` or the chat. See `.env.example` and `devices.example.json` for the file formats.

**2. Load the starter error codes.** These are written by the project and are not verified vendor data. Check them and add your own.

```powershell
python tests\seed_error_codes.py
```

**3. Optional: load sample cases** so search and reports have something to show. The loader refuses to run if you already have cases.

```powershell
python sample_data/load_sample_data.py
```

**4. Connect Claude Desktop.** Open `%APPDATA%\Claude\claude_desktop_config.json` and add this entry inside `mcpServers` (use your own folder path, with doubled backslashes):

```json
"trabasist": {
  "command": "C:\\path\\to\\trabasist\\.venv\\Scripts\\python.exe",
  "args": ["-m", "trabasist_server.server"],
  "env": { "PYTHONPATH": "C:\\path\\to\\trabasist" }
}
```

Fully quit Claude Desktop from the tray icon and reopen it. Do this again after any change to the server code or this config.

**5. Use it.** Start your prompt with "Use the trabasist tools", for example: "Use the trabasist tools. Open a case: SSH to kali-lab is refused. Check the device and tell me the likely cause." Claude Desktop asks you to approve the first call to each tool.

## How it works

Claude Desktop starts the Trabasist server on your PC. Claude calls its tools to record a case, gather evidence, search past cases and report. Everything is stored in a local SQLite file (`trabasist.db`) in the project folder. Nothing is sent anywhere by Trabasist itself.

- **Diagnostics run from your PC**, not from the affected device. `ping_host`, `traceroute_host`, `dns_lookup` and `check_port` show what your PC can see.
- **Device commands run on the device** over SSH, using the credentials in `.env`. The server logs in itself, so no password is ever typed into the chat.
- Every command and diagnostic is written to an audit log.
- Diagnostic and device steps are saved as `inconclusive`. Claude judges whether each one is a `cause` or `ruled_out` and records that with `log_step`.

## Tools

| Tool | What it does |
|---|---|
| `open_case` | Record a new issue: symptom, error code, device, environment |
| `log_step` | Record a check or attempt and its result, including what was ruled out |
| `close_case` | Record the root cause and the fix that worked |
| `find_similar_cases` | Search past cases by symptom, error code and device, with their logged steps |
| `report` | Recurring issues by device, error code and root cause, plus time to resolve |
| `ping_host`, `traceroute_host`, `dns_lookup`, `check_port` | Local diagnostics, attached to the open case |
| `run_device_command` | Run one allowlisted read-only command on a device over SSH |
| `lookup_error_code` | Look up an error code in the local table (18 starter entries) |
| `import_config` | Import a config file with passwords, SNMP strings and keys removed |

### Linux commands (allowlist)

Claude asks for a command by name. It cannot send free-form text, and anything not in this list is refused and logged.

`uptime`, `df`, `free`, `systemctl_status` (service name), `journalctl` (optional unit, 1-500 lines), `dmesg` (1-500 lines), `ip_a`, `ip_route`, `ss`, `last` (1-100 entries).

Service and unit names must match `^[A-Za-z0-9][A-Za-z0-9@._-]{0,63}$`. No other parameters are accepted.

### Importing a config

Copy the config file into the `imports` folder yourself, then ask Claude to import it by file name. Never paste configs into the chat. Only plain file names with the extensions `.txt .cfg .conf .config .log .ini` (up to 512 KB) are read from that folder, so Claude cannot be asked to read `.env` or any other path. Redaction is best effort, not a guarantee: review the stored text. It can also over-redact lines containing the word "community" (for example BGP `send-community`). That fails safe: it hides too much rather than too little.

## Adding your own error codes

For 1.0.0 you add your own entries from Python. Save this as `add_my_code.py` in the project folder, edit the values, and run `python add_my_code.py` with the virtual environment active:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trabasist_server.db import init_db
from trabasist_server.tools.lookup_error_code import add_error_code

init_db()
print(add_error_code("0x80070005", "windows", "Access denied",
                     "Missing permissions; blocked by security software", "my note"))
```

It prints the new entry's id. Adding the same code and platform twice is refused with an error. Claude can look codes up but cannot add them. The 18 starter entries are written by this project and are not verified vendor data. Check them.

## Safety

- Only allowlisted read-only commands run. There is no free-form command input, no `shell=True`, and all hostnames, ports and parameters are validated.
- SSH host keys are verified, never auto-accepted. An unknown or changed key is refused.
- Passwords live only in `.env` (`LABEL_USERNAME`, `LABEL_PASSWORD`). `devices.json` holds a label, never a password. Both files are git-ignored.
- Secrets are redacted before anything is stored. Redaction is best effort, so review stored text.
- SQL uses parameterised values only.
- Every command run and refusal is written to the audit log.
- Use read-only accounts on lab devices.
- Before release, `pip-audit` found no known vulnerabilities and `bandit` found no high-severity issues. Its remaining notes were reviewed and accepted: string-built SQL in `report.py` (joins fixed constants only, values go through parameters), `subprocess` use in `diag_common.py` (fixed argument list, validated input, no shell), and an ignored error when closing an already-dead SSH connection in `ssh_conn.py`.

## Known limits

- Device commands work on Linux only. Windows Server over OpenSSH, and switch and firewall command sets, are not in 1.0.0.
- Status `ok` means the command ran and returned text. It does not mean the device is healthy. Read the output.
- Your read-only account may not be allowed to read some logs (for example the system journal needs group membership, and `dmesg` can be restricted). The command then returns little or nothing.
- The output of `dmesg`, `ip_a`, `ip_route` and `ss` has not been checked for stray formatting characters on every system.
- The `add_device` test login is not written to the audit log.
- Search is keyword-based. Time to resolve in the sample data shows about 0 minutes because the sample cases are opened and closed instantly.
- The report groups root causes by exact wording, so differently worded causes appear separately.
- Diagnostics run from your PC, so odd things on your own network (for example an unusual TTL on ping) affect results.

## Troubleshooting

- **Claude says a tool is unavailable.** Start your prompt with "Use the trabasist tools". Fully quit Claude Desktop from the tray icon and reopen it after any config or server code change.
- **Host key refused after the device got a new IP.** Known hosts are stored per address. Run `python -m trabasist_server.add_device` again to trust the key at the new address.
- **Host key refused on a device you rebuilt.** Run `ssh-keygen -R OLD_IP`, then trust the new key again with `add_device`. A changed key is refused on purpose, so verify the device first.
- **Wrong password saved.** Edit `.env` by hand for now.
- **"imports folder does not exist".** Create a folder named `imports` in the project folder.

## Roadmap

Next: Windows Server device commands, switch and firewall command sets, SSH keys, editing and removing devices without hand-editing files, an optional web search tool, config snapshots and diffing, a shared team database, and a Linux version of the server.

## Licence

Apache License 2.0. See the `LICENSE` and `NOTICE` files.
