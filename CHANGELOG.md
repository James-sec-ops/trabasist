# Changelog

## 1.0.0 - first public release

- Case tools: open_case, log_step, close_case, find_similar_cases, report.
- Local diagnostics: ping_host, traceroute_host, dns_lookup, check_port.
- run_device_command over SSH for Linux with a read-only allowlist of 25 commands (including ping, traceroute and dig run on the device), host key verification and an audit log.
- import_config with redaction of passwords, SNMP strings and keys.
- lookup_error_code with 18 starter entries (written by the project, not verified vendor data).
- add_device helper, sample data loader and a README.
- Not included: Windows Server device commands, switch and firewall command sets, optional web search tool (see the Roadmap in the README).
