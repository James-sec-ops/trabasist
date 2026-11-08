"""dns_lookup tool: DNS query via dnspython, logged to audit and case."""
import ipaddress

import dns.exception
import dns.resolver
import dns.reversename

from trabasist_server.tools.diag_common import (
    validate_host, check_case_open, record_diagnostic,
)

RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "PTR")
LIFETIME_SECONDS = 5


def _is_ip(text) -> bool:
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False


def dns_lookup(name, record_type="A", server=None, case_id=None) -> dict:
    name = validate_host(name)
    if not isinstance(record_type, str) or record_type.upper() not in RECORD_TYPES:
        raise ValueError("record_type must be one of: " + ", ".join(RECORD_TYPES))
    rtype = record_type.upper()
    if rtype == "PTR" and not _is_ip(name):
        raise ValueError("PTR lookups need an IP address")
    if rtype != "PTR" and _is_ip(name):
        raise ValueError(f"{rtype} lookups need a hostname, not an IP address")
    if server is not None:
        server = validate_host(server)
        if not _is_ip(server):
            raise ValueError("server must be an IP address")
    check_case_open(case_id)

    resolver = dns.resolver.Resolver()
    if server:
        resolver.nameservers = [server]
    used = ", ".join(resolver.nameservers)
    query_name = dns.reversename.from_address(name) if rtype == "PTR" else name

    answers = []
    try:
        result = resolver.resolve(query_name, rtype, lifetime=LIFETIME_SECONDS)
        answers = [r.to_text() for r in result]
        state = "ok"
    except dns.resolver.NXDOMAIN:
        state = "nxdomain"
    except dns.resolver.NoAnswer:
        state = "no_answer"
    except dns.resolver.NoNameservers:
        state = "error"
    except dns.exception.Timeout:
        state = "timeout"
    except dns.exception.DNSException as exc:
        state = "error"
        answers = [f"{type(exc).__name__}"]

    command = f"dns {rtype} {name} via {used}"
    output = f"state={state}; answers=" + (" | ".join(answers) if answers else "none")
    rec = record_diagnostic("dns_lookup", name, command, output, case_id)
    return {
        "name": name,
        "record_type": rtype,
        "resolver": used,
        "state": state,
        "answers": answers,
        "audit_id": rec["audit_id"],
        "step_id": rec["step"]["step_id"] if rec["step"] else None,
    }
