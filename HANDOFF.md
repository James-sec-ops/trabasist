# Trabasist V2 handoff

## Phase 0 - done (17 Nov 2026)

Branch v2 was cut from main at 79b9871. Release 1.0.1 on main is the fix commit (6cd09fc) plus the notes
commit (9cc3a15). The Windows work (0c8d5fe, c086a5c) is on v2 only; v2 has merged main.

### What changed
- add_device test login is now written to the audit log (shared writer: trabasist_server/tools/audit.py).
- Clearer device-name message in device_setup.py.
- tests/test_run_device_command.py uses its own temporary database (it used to scan the real audit log, and a
  5-character password matched kernel text in an old row).
- Windows platform: allowlist table "windows" in command_allowlist.py, and a Paramiko exec path in ssh_conn.py
  (strict known_hosts, RejectPolicy). Linux still uses Netmiko.

### Windows read-only commands as run by the limited account (trabread)
- Work: uptime (tick counter, accurate to about 49 days), os_info and cpu (registry), disk, service_status,
  processes_top_cpu, processes_top_mem, ipconfig, netstat, routes, test_netconnection.
- Need more rights (skipped in tests, planned for the Administrator account in Phase 4): memory (WMI),
  services (full list), eventlog (Get-WinEvent).
- Command text has no quote, dollar, brace, backtick or semicolon, so it works from cmd or PowerShell.

### Test baseline
- Offline tests pass on v2. Windows allowlist: 58 passed.
- Live tests (need the lab VMs and correct addresses in devices.json): add_device 25, hostkey_setup 26,
  run_device_command 13, windows_live 14 passed / 3 skipped.
- Run a test: set PYTHONPATH to the project folder, then python tests\<file>.py (tests are plain scripts).

### Gotchas
- devices.json and .env are git-ignored, so they are the same on every branch. With winserver1 set to platform
  windows, the 1.0.x code on main rejects the whole inventory (unsupported platform), and tests/test_inventory.py
  fails there. Work on v2, or set winserver1 back to linux before using main.
- Device addresses change when the laptop changes network. Helper outside the repo: python $HOME\set_addr.py
  <device> <address> [linux|windows]; then run the ssh line it prints once to trust the host key
  (Ctrl+C at the password prompt).
- Windows VM: each new network starts as Public and blocks SSH. On the VM (as Administrator):
  Set-NetConnectionProfile -InterfaceAlias Ethernet -NetworkCategory Private. Keep SSH closed on Public.
- Kali login name and the Windows read-only account name come from .env; trabread is the Windows read-only account.

### Found, for Phase 1 and Phase 7
- One device with an unsupported platform makes load_inventory fail for every device. Skipping and reporting the
  bad entry would be safer.
- test_check_port depends on the network (it probes 192.0.2.1, which some networks answer).
- test_wrong_hostkey prints FAIL but exits 0.
- Tests need a proper runner (no PYTHONPATH step).
- Editing devices without hand-editing files (the address helper is a stopgap).

## Next: Phase 1
Command classifier, tiers, device tags, change mode off by default. Unknown commands become Tier 3.
Nothing in Phase 0 changed how commands are allowed: the allowlist is still the only gate.
