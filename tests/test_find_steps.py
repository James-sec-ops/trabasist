import os
import tempfile

tmp = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["TRABASIST_DB"] = tmp

from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.log_step import log_step
from trabasist_server.tools.close_case import close_case
from trabasist_server.tools.find_similar_cases import find_similar_cases

c = open_case("Installer fails with error 2735", "2735", "srv01")["case_id"]
log_step(c, "Checked disk space", "df -h", "40% used", "ruled_out")
log_step(c, "Checked Installer service", "Get-Service msiserver", "x" * 1000, "cause")
close_case(c, "Installer service was stopped", "1. Start the service. 2. Re-run the installer.")
open_case("Unrelated open case with no steps", "9999")

r = find_similar_cases(error_code="2735")
steps = r[0]["steps"]
print("Steps returned:", "PASS" if len(steps) == 2 else "FAIL", len(steps))
print("Outcomes shown:", "PASS" if [s["outcome"] for s in steps] == ["ruled_out", "cause"] else "FAIL")
print("Long result trimmed:", "PASS" if len(steps[1]["result"]) < 400 and steps[1]["result"].endswith("...") else "FAIL")

r = find_similar_cases(error_code="9999")
print("Case with no steps gives empty list:", "PASS" if r and r[0]["steps"] == [] else "FAIL")
