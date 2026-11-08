import os
import tempfile

tmp = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["TRABASIST_DB"] = tmp

from trabasist_server.tools.open_case import open_case
from trabasist_server.tools.close_case import close_case
from trabasist_server.tools.find_similar_cases import find_similar_cases

a = open_case("Installer fails with error 2735", "2735", "srv01")["case_id"]
close_case(a, "Windows Installer service was stopped", "Started the service and re-ran the installer")
b = open_case("Switch port flapping", "LINK-FLAP", "sw-core")["case_id"]
close_case(b, "Bad patch cable", "Replaced the cable")
c = open_case("Website slow on Monday mornings", None, "web01")["case_id"]

r = find_similar_cases(error_code="2735")
print("Error code match:", "PASS" if r and r[0]["case_id"] == a and r[0]["resolution"] else "FAIL", r[:1])

r = find_similar_cases(symptom="installer keeps failing on the server")
print("Symptom match:", "PASS" if r and r[0]["case_id"] == a else "FAIL")

r = find_similar_cases(symptom="port flapping", device="sw-core")
print("Device + symptom match:", "PASS" if r and r[0]["case_id"] == b else "FAIL")

r = find_similar_cases(symptom="completely unrelated printer jam")
print("No match returns empty:", "PASS" if r == [] else "FAIL")

r = find_similar_cases(symptom='tricky "quotes" AND OR NOT * ( ) input')
print("Odd characters safe:", "PASS" if isinstance(r, list) else "FAIL")

def refused(label, **kw):
    try:
        find_similar_cases(**kw)
        print(label + ":", "FAIL (was accepted)")
    except ValueError:
        print(label + ":", "PASS")

refused("Empty search refused", symptom="  ")
refused("Bad error code refused", error_code="2735; DROP TABLE cases")
refused("Bad limit refused", symptom="x", limit=500)
