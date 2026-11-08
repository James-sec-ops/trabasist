import os
import tempfile

tmp = tempfile.mkdtemp()
os.environ["TRABASIST_DB"] = os.path.join(tmp, "test.db")

from trabasist_server.db import init_db
from trabasist_server.tools.lookup_error_code import (
    lookup_error_code, add_error_code, seed_starter_codes, STARTER_CODES)

init_db()
passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print("FAIL:", name)


def raises(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ValueError:
        return True
    return False


check("seed adds all", seed_starter_codes() == len(STARTER_CODES))
check("seed twice adds none", seed_starter_codes() == 0)

r = lookup_error_code("2735")
check("2735 found", r["status"] == "found" and len(r["matches"]) == 1)
check("2735 platform", r["matches"][0]["platform"] == "windows")
check("case-insensitive", lookup_error_code("0X80070005")["status"] == "found")
check("code with space", lookup_error_code("errno 13")["status"] == "found")
check("platform filter hit", lookup_error_code("127", "linux")["status"] == "found")
check("platform filter miss", lookup_error_code("127", "windows")["status"] == "not_found")
check("platform case", lookup_error_code("127", "LINUX")["status"] == "found")
check("not found", lookup_error_code("99999")["status"] == "not_found")
check("not found message", "find_similar_cases" in lookup_error_code("99999")["message"])

check("empty code refused", raises(lookup_error_code, ""))
check("quote refused", raises(lookup_error_code, "x' OR '1'='1"))
check("semicolon refused", raises(lookup_error_code, "1; DROP TABLE error_codes"))
check("long code refused", raises(lookup_error_code, "a" * 100))
check("non-text refused", raises(lookup_error_code, 123))
check("bad platform refused", raises(lookup_error_code, "127", "li nux'; --"))
check("table survives", lookup_error_code("127")["status"] == "found")

new_id = add_error_code("1722", "windows", "RPC server unavailable.",
                        "RPC service stopped; firewall blocking; DNS problem.", "own note")
check("add returns id", isinstance(new_id, int))
check("added entry found", lookup_error_code("1722")["status"] == "found")
check("duplicate refused", raises(add_error_code, "1722", "windows", "again", ""))
check("same code other platform ok",
      isinstance(add_error_code("1722", "linux", "other meaning", ""), int))
check("meaning required", raises(add_error_code, "5555", "linux", "", ""))
check("meaning too long", raises(add_error_code, "5556", "linux", "x" * 1001, ""))
check("bad code on add", raises(add_error_code, "bad'code", "linux", "m", ""))

print("passed", passed, "failed", failed)
print("PASS" if failed == 0 else "FAILED")
