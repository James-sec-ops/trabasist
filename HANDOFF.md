# Trabasist V2 handoff

Last updated: 17 Nov 2026, end of Phase 0. Read this first in every new phase chat, together with the scope
(Trabasist_V2_Scope.md v0.2 in the V2 project).

## Where things stand
- main = Trabasist 1.0.1: Linux only, read-only. Released, pushed to GitHub (9cc3a15). Nothing for V2 goes onto main
  until 2.0.0 is ready, except small 1.0.x fixes.
- v2 = work toward 2.0.0. It has merged main. Windows read-only support already exists here.
- Working copy: C:\Users\xtranet\trabasist, on branch v2. Claude Desktop is connected to this copy, so it runs the
  v2 code. After any change to server code, fully quit Claude Desktop from the tray icon and reopen it.
- Repo: github.com/James-sec-ops/trabasist. Both branches are pushed.

## Phase 0 - done
Commits: 6cd09fc (fixes, on main), 0c8d5fe and c086a5c (Windows, v2 only), 9cc3a15 (1.0.1 notes, on main),
b6aef6b (main merged into v2), then the handoff commits.

What changed:
- add_device test login is now written to the audit log. Shared writer: trabasist_server/tools/audit.py
  (write_audit). run_device_command uses it too, keeping its old _audit name as a wrapper.
- Clearer device-name message in device_setup.py (label_from_name).
- tests/test_run_device_command.py uses its own temporary database. Before, it scanned the real audit log, and a short
  password matched kernel text in an old row.
- Windows platform: a "windows" table in command_allowlist.py (PLATFORMS = linux + windows) and a Paramiko exec path
  in ssh_conn.py (_run_windows: strict known_hosts, RejectPolicy, one exec channel). Linux still uses Netmiko.
- Windows command text has no double quote, dollar, brace, backtick or semicolon, so it behaves the same whether the
  default SSH shell is cmd or PowerShell. Keep that rule for any new Windows command.

Windows read-only commands as run by the limited account trabread:
- Work: uptime (tick counter, accurate to about 49 days after a reboot), os_info and cpu (registry), disk,
  service_status (a named service such as EventLog), processes_top_cpu, processes_top_mem, ipconfig, netstat, routes,
  test_netconnection.
- Need more rights, so they are SKIPped in the live test and planned for the Administrator account in Phase 4:
  memory (WMI is denied), services (full list), eventlog (Get-WinEvent). WMI, performance counters and net statistics
  are all denied to trabread. Granting Event Log Readers would allow eventlog but also exposes the Security log.

## Test baseline (17 Nov 2026)
- Tests are plain scripts. Set PYTHONPATH to the project folder, then run python tests\<file>.py.
- Offline tests pass on v2. Windows allowlist: 58 passed.
- Live tests need the lab VMs and correct addresses in devices.json: add_device 25 passed, hostkey_setup 26,
  run_device_command 13, windows_live 14 passed and 3 skipped.
- Fresh-install test done: cloned main (1.0.1) into a new folder, new venv, README followed, add_device against Kali
  worked (host key trusted, test login OK), seed_error_codes and the sample data loaded. The Claude Desktop step
  was skipped on purpose. The test clone was deleted.

## Gotchas
- devices.json and .env are git-ignored, so they are shared by every branch. With winserver1 set to platform
  windows, the 1.0.x code on main rejects the whole inventory and tests/test_inventory.py fails there. Work on v2.
- Addresses change whenever the laptop changes network (Kali and the Windows VM are bridged). Check reachability, then
  use the helper outside the repo: python $HOME\set_addr.py <device> <address> [linux|windows]. It refuses if port
  22 does not answer, backs up devices.json, and prints the ssh line to run once (Ctrl+C at the password prompt) so the
  host key at the new address is trusted. Trabasist stores host keys per address.
- Windows VM: each new network starts as Public and blocks SSH. On the VM, as Administrator:
  Set-NetConnectionProfile -InterfaceAlias Ethernet -NetworkCategory Private. Do not open SSH on Public networks.
- Kali account name and the Windows read-only account name (trabread) come from .env. The Kali password is short:
  use a longer one before the sudo work in Phase 3, because that account gets elevated rights.
- Patch scripts: files differ in line endings (some CRLF, some LF) and tests/test_run_device_command.py starts with a
  byte-order mark. Edit scripts must read bytes, normalise line endings, match each replacement exactly once, write
  nothing unless all match, and write back in the file's own style.
- Do not chain a commit onto the same command block as the tests that gate it. Run the tests, read them, then commit.

## Found, for Phase 1 and Phase 7
- load_inventory fails for every device if one entry is bad (for example an unsupported platform). Skipping and
  reporting the bad entry would be safer.
- 1.0.x add_device only offers linux. Saving a Windows server as linux makes the test login time out. Say plainly in
  the README and at the prompt that 1.0.x cannot manage Windows devices. Goes away when 2.0.0 ships.
- A user who runs git clone from inside an existing folder ends up with a nested folder. Consider a README note.
- add_device's test login runs uptime, which now exists for both linux and windows. Other platforms (MikroTik, Cisco)
  need their own check.
- test_check_port depends on the network (it probes 192.0.2.1, which some networks answer).
- test_wrong_hostkey prints FAIL but exits 0.
- Tests need a proper runner (no PYTHONPATH step).
- Editing devices without hand-editing files (the address helper is a stopgap).

## Helpers outside the repo (in C:\Users\xtranet)
- set_addr.py: device address helper described above.
- win_probe.py: scratch probe of what the Windows read-only account may run. Safe to delete.

## Next: Phase 1 - command classifier, tiers, device tags, change mode off by default
Scope section 5.1. Tier 1 read-only, Tier 2 normal changes (automatic on lab devices, approval on production),
Tier 3 critical (always needs the owner's approval). Unknown or ambiguous commands are Tier 3, never Tier 1. Chaining,
pipes to a shell, overwriting redirects and encoded commands are Tier 3 at least. Devices get a lab or production tag.
Change mode is off for every device and turned on per device. Every command goes through the classifier and the
audit log records the tier.
- Today the allowlist is the only gate and everything in it is read-only. Phase 1 must not weaken that.
- Open design questions: where the tag and the change-mode switch live in devices.json, how the classifier sits in
  front of the allowlist, how free-form commands are tiered per platform (Linux, Windows PowerShell and cmd, Cisco IOS,
  MikroTik RouterOS), and how existing 1.0.x inventories keep loading (new fields need safe defaults: change mode off).
- Approval (Phase 2) is outside the chat and cannot be given through the MCP server.
