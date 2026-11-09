"""Trabasist MCP server: exposes the case tools to an MCP client such as Claude Desktop."""
from mcp.server.mcpserver import MCPServer

from trabasist_server.tools.open_case import open_case as _open_case
from trabasist_server.tools.log_step import log_step as _log_step
from trabasist_server.tools.close_case import close_case as _close_case
from trabasist_server.tools.find_similar_cases import find_similar_cases as _find_similar_cases
from trabasist_server.tools.ping_host import ping_host as _ping_host
from trabasist_server.tools.traceroute_host import traceroute_host as _traceroute_host
from trabasist_server.tools.dns_lookup import dns_lookup as _dns_lookup
from trabasist_server.tools.check_port import check_port as _check_port
from trabasist_server.tools.run_device_command import run_device_command as _run_device_command
from trabasist_server.tools.lookup_error_code import lookup_error_code as _lookup_error_code
from trabasist_server.tools.report import report as _report
from trabasist_server.tools.import_config import import_config as _import_config

INSTRUCTIONS = (
    "Trabasist is a troubleshooting memory. Work every issue in this order. "
    "1) Search past cases with find_similar_cases (try the error code alone and the "
    "symptom alone). Each past case lists the steps that were tried, what was ruled out "
    "and what worked. "
    "If an error code is involved, also use lookup_error_code for its meaning and likely "
    "causes; if there is no local entry, say so and continue. "
    "2) Open a case with open_case. "
    "3) Give the person clear numbered step-by-step guidance they can follow without "
    "expert knowledge: say exactly what to click, type or run, and what result to expect "
    "at each step. Base it on matching past cases first, then on a web search for common "
    "solutions if you have web search, and say which source each step comes from. Do not "
    "present web knowledge as a recorded fix. "
    "4) Gather evidence with the local diagnostics ping_host, traceroute_host, dns_lookup "
    "and check_port. Always pass the open case_id so each result is attached to the case "
    "automatically. These run from the PC where Trabasist is installed, not from the "
    "affected device. To test what the device itself can reach (its gateway, a server, "
    "the internet, its DNS), use run_device_command with ping, traceroute or dig. "
    "To look inside a device, use run_device_command with the device name from the "
    "inventory and a command NAME from its list (never a free-form command line). Pass "
    "case_id. A refused command is not an error to work around: tell the person it is "
    "not allowed and pick an allowed command instead. "
    "5) Record each manual check with log_step as the person reports the result, including "
    "what was ruled out. Do not log_step a diagnostic or device command result again; it "
    "is already saved. "
    "6) Finish with close_case: the root cause, and the resolution written as numbered "
    "steps that someone else could repeat. "
    "When asked about recurring problems, trends or time to resolve, use report. "
    "To store a device configuration, ask the person to copy the file into the imports "
    "folder of the Trabasist project, then call import_config with the file name. "
    "Never ask the person to paste a configuration into the chat. "
    "Never put passwords or keys in any field."
)

mcp = MCPServer("trabasist", instructions=INSTRUCTIONS, version="1.0.0")


@mcp.tool()
def open_case(symptom: str, error_code: str | None = None,
              device: str | None = None, environment: str | None = None) -> dict:
    """Record a new issue as a case. Returns the case_id to use in later calls."""
    return _open_case(symptom, error_code, device, environment)


@mcp.tool()
def log_step(case_id: int, action: str, command: str | None = None,
             result: str | None = None, outcome: str = "inconclusive") -> dict:
    """Record a check or attempt on an open case. outcome is one of: cause, ruled_out, inconclusive."""
    return _log_step(case_id, action, command, result, outcome)


@mcp.tool()
def close_case(case_id: int, root_cause: str, resolution: str) -> dict:
    """Close a case. Give the root cause and the resolution as numbered steps."""
    return _close_case(case_id, root_cause, resolution)


@mcp.tool()
def find_similar_cases(symptom: str | None = None, error_code: str | None = None,
                       device: str | None = None, limit: int = 5) -> list:
    """Search past cases by symptom, error code and device. Best matches first, each with its logged steps."""
    return _find_similar_cases(symptom, error_code, device, limit)


@mcp.tool()
def ping_host(host: str, count: int = 4, case_id: int | None = None) -> dict:
    """Ping a host from this PC (1-10 packets). Pass case_id to attach the result to an open case."""
    return _ping_host(host, count, case_id)


@mcp.tool()
def traceroute_host(host: str, max_hops: int = 15, case_id: int | None = None) -> dict:
    """Trace the network path to a host from this PC (1-30 hops). Pass case_id to attach the result to an open case."""
    return _traceroute_host(host, max_hops, case_id)


@mcp.tool()
def dns_lookup(name: str, record_type: str = "A", server: str | None = None,
               case_id: int | None = None) -> dict:
    """Look up a DNS record (A, AAAA, MX, NS, TXT, CNAME, SOA, PTR). Optional server must be an IP. Pass case_id to attach the result to an open case."""
    return _dns_lookup(name, record_type, server, case_id)


@mcp.tool()
def check_port(host: str, port: int, timeout: int = 3, case_id: int | None = None) -> dict:
    """Test whether a TCP port is open on a host, from this PC. Pass case_id to attach the result to an open case."""
    return _check_port(host, port, timeout, case_id)


@mcp.tool()
def run_device_command(device: str, command: str, params: dict | None = None,
                       case_id: int | None = None) -> dict:
    """Run one read-only allowlisted command on a device over SSH. device is the name from the
    device inventory (for example kali-lab). command is a command NAME, not a command line.
    Linux commands with no parameters: uptime, df, free, ip_a, ip_route, ss, ip_link_stats,
    ip_neigh, resolv_conf, uname, os_release, timedatectl, systemctl_failed, ps_top_cpu,
    ps_top_mem, lsblk, df_inodes, who.
    Linux commands with parameters: systemctl_status (service), journalctl (unit, lines 1-500),
    dmesg (lines 1-500), last (count 1-100), ping (host, count 1-10),
    traceroute (host, max_hops 1-30), dig (name, record_type one of A AAAA MX NS TXT CNAME SOA PTR; PTR needs an IP).
    ping, traceroute and dig run ON the device, so they show what the device itself can reach,
    unlike ping_host, traceroute_host and dns_lookup, which run from the PC.
    Anything else is refused and logged. status ok means the command ran and returned output, not that the device is healthy: read the output (for example 'could not be found') to judge the result. Pass case_id to attach the result to an open case."""
    return _run_device_command(device, command, params, case_id)


@mcp.tool()
def lookup_error_code(code: str, platform: str | None = None) -> dict:
    """Look up an error code in the local table (meaning and likely causes). platform is optional, for example windows or linux. Read-only. If status is not_found, there is no local entry: use find_similar_cases and web search instead."""
    return _lookup_error_code(code, platform)


@mcp.tool()
def report(days: int | None = None, min_count: int = 2, limit: int = 10) -> dict:
    """Summarise recurring issues by device, error code and root cause, plus time to resolve. days limits it to the last N days (omit for all time). min_count is how many cases make an issue recurring (default 2). Read-only. Root causes are grouped by exact wording, so differently worded causes appear separately."""
    return _report(days, min_count, limit)


@mcp.tool()
def import_config(filename: str, device: str | None = None, case_id: int | None = None) -> dict:
    """Store a device configuration with passwords, SNMP strings and keys removed. filename is a plain file name (.txt .cfg .conf .config .log .ini, max 512 KB) of a file the person has copied into the imports folder of the Trabasist project; paths are refused. Give a device name, a case_id, or both. Redaction is best-effort: review the returned text and never ask for the original secrets."""
    return _import_config(filename, device, case_id)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
