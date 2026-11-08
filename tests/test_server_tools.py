import asyncio
import sys

from trabasist_server.server import mcp

tools = asyncio.run(mcp.list_tools())
names = sorted(t.name for t in tools)
print("Tools:", names)
expected = sorted([
    "check_port", "close_case", "dns_lookup", "find_similar_cases", "import_config", "lookup_error_code",
    "log_step", "open_case", "ping_host", "report", "run_device_command",
    "traceroute_host",
])
ok = names == expected
print("All twelve tools registered:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
