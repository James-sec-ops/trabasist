# Trabasist V2 handoff

Last updated: 19 Nov 2026, end of Phase 1. Read this first in every new phase chat, together with the scope
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

## Phase 1 - done (19 Nov 2026)
Commits on v2 since the Phase 0 handoff:
  b5164c9 Phase 1 step 1: device tag and change_mode fields, load_inventory_report
  4dfbb76 Phase 1 step 2: command classifier (Tier 1/2/3) with tests
  e611e04 Phase 1 step 3: policy gate (tier, tag, change mode) with tests
  3e20a1a Phase 1 step 4: classifier and policy gate wired into run_device_command, audit tier columns
  79c584f Phase 1 step 5: expose check_device_command, Windows command names, safety instructions

What exists now:
- inventory.py: Device has tag (lab or production, default production) and change_mode (default false).
  load_inventory_report(path) returns (devices, problems) and skips a bad entry instead of failing everything.
  load_inventory stays strict and unchanged.
- classifier.py: classify(platform, command) -> (tier, rule, reason). Pure, never raises. Tier 1 only when the text
  equals an allowlist command exactly. Tier 2 patterns: Linux systemctl restart/start/reload, apt/apt-get/dnf/yum
  install -y, ip addr add; Windows Restart-Service/Start-Service. Protected services stay Tier 3 (Linux: ssh, sshd,
  networking, network, NetworkManager, systemd-networkd; Windows: sshd, WinRM, Dhcp, Dnscache, NlaSvc, Netman,
  NetProfM, LanmanServer, EventLog). Everything else is Tier 3. Cisco and MikroTik have no rules yet, so all Tier 3.
  classify_named builds an allowlist command with build_command and returns Tier 1.
- policy.py: decide(classification, tag, change_mode) -> (action, code, reason). Tier 1 always allow. Tier 2: refused
  if change mode is off, allow on lab, needs_approval on production. Tier 3: refused if change mode is off, else
  needs_approval. There is no approved argument. Bad input is refused.
- audit_log has tier, decision, rule, tag, change_mode. init_db migrates old databases safely. write_audit takes them
  as keyword-only optional arguments; record_diagnostic takes meta.
- run_device_command: named commands go classify_named, then decide, then run as before (all Tier 1). A device skipped
  for a bad entry reports its real reason. check_device_command(device, command) classifies and gates a free-form
  command and never runs it (executed false). It is an MCP tool in server.py. The server instructions say Claude
  cannot approve and that device text is never an instruction.
- Nothing can change a device yet. Tier 2 allow means the policy would allow it. Execution comes with the platform
  phases (3 for Linux, 4 for Windows).

Test baseline (19 Nov 2026), all passing:
- Offline: classifier 28, policy 51, inventory_tags 24, inventory 19, step4_wiring 31, server_tools 17.
- Live: run_device_command 13, windows_live 14 passed and 3 skipped (same as Phase 0), add_device 25, hostkey_setup
  no failures.
- New Phase 1 tests set sys.path themselves. Older tests still need PYTHONPATH.
- Live check in Claude Desktop: with no tag, kali-lab is production with change mode off, so nginx restart, ssh
  restart, reboot and a chained command were all refused (policy:change-mode-off). Claude refused to "just run" reboot.

Notes:
- The real devices.json has no tags, so every device is production with change mode off. To see the allow and
  needs_approval branches live, set kali-lab to tag lab and change_mode true, restart Claude Desktop, and put the
  backup (devices.json.bak) back afterwards.
- Git warns that LF will be replaced by CRLF on new files. Harmless. A .gitattributes file would settle it.
- Still open from Phase 0: test_wrong_hostkey prints FAIL but exits 0; tests need a proper runner; 1.0.x add_device
  only offers linux; Windows memory, services and eventlog need the Administrator account (Phase 4).

## Next: Phase 2 - approval outside the chat
Scope sections 5.2 and 7. Claude can request a Tier 3 action but cannot approve it. The owner approves in a separate
terminal command that shows the exact command and device. An approval covers one command on one device, runs once and
expires. It cannot be given through the MCP server, and text from devices, logs or web pages cannot trigger one.
Optional: approve a written change plan as a whole, with a check after each step, stopping on failure or deviation.
Checks (scope section 9): a Tier 3 command without approval, an expired approval, a reused approval, an approval for
a different command or device, and an injection attempt through device output must all be refused and logged.
- Phase 1 supplies the inputs: Classification, Decision with needs_approval, and audit columns for decision and tag.
- Open design questions: where pending requests and approvals are stored (an approvals table in the same database is
  the likely answer); how an approval is bound to the exact command text, device and tier (a hash over those fields);
  how long it lives; how a row is proved to come from the approval command and not from anything else that can write
  the database (for example a signature using a secret in .env); how Claude files a request (check_device_command
  could create the pending request when the decision is needs_approval); what the approval command shows and asks for.
- The approval module must not be imported by server.py and must not appear as an MCP tool.
- Execution of free-form commands still does not exist. Phase 2 is built and tested with a fake executor. The first
  real execution is Phase 3 (Linux, sudo on Kali).
- Before Phase 3 the Kali account needs a longer password, because it gets elevated rights.
