import os
import tempfile
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["TRABASIST_DB"] = os.path.join(tmp, "test.db")
imp = Path(tmp) / "imports"
imp.mkdir()
os.environ["TRABASIST_IMPORTS"] = str(imp)

from trabasist_server.db import init_db, get_connection
from trabasist_server.tools.import_config import import_config, redact_config, MAX_BYTES

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


CONFIG = "\n".join([
    "hostname core-sw1",
    "interface GigabitEthernet0/1",
    " ip address 10.0.0.1 255.255.255.0",
    "enable secret 5 $1$abcd$xyz",
    "username admin password MySecretPass1",
    "snmp-server community s3cr3tRW RW",
    "snmp-server host 10.1.1.1 version 2c trapcomm",
    "set psksecret ENC AbCdEfGh123==",
    "ip ospf message-digest-key 1 md5 7 MyOspfKey",
    "tacacs-server host 10.0.0.5 key 7 0822455D0A16",
    "-----BEGIN RSA PRIVATE KEY-----",
    "MIIFAKEKEYDATA",
    "-----END RSA PRIVATE KEY-----",
    "root:$6$abcdefgh$HASHVALUEHASHVALUE:19000",
    "",
])
SECRETS = ["abcd$xyz", "MySecretPass1", "s3cr3tRW", "trapcomm", "AbCdEfGh123",
           "MyOspfKey", "0822455D0A16", "MIIFAKEKEYDATA", "HASHVALUEHASHVALUE"]
(imp / "core-sw1.cfg").write_text(CONFIG, encoding="utf-8")

# Direct redaction checks
text, n = redact_config(CONFIG)
for s in SECRETS:
    check("redact removes " + s, s not in text)
check("redactions counted", n >= 8)
check("hostname kept", "hostname core-sw1" in text)
check("ip address kept", "ip address 10.0.0.1 255.255.255.0" in text)
check("username kept", "username admin" in text)
text, n = redact_config("hostname core-sw1\ninterface Gi0/1\n")
check("clean text unchanged", text == "hostname core-sw1\ninterface Gi0/1\n" and n == 0)
text, n = redact_config("snmp-server host 10.1.1.1 trapcomm2")
check("snmp host without version", "trapcomm2" not in text)
text, n = redact_config('set password "my pass phrase"')
check("quoted password", "my pass phrase" not in text)

# Real import with a case
conn = get_connection()
cid = conn.execute("INSERT INTO cases (symptom) VALUES ('config test')").lastrowid
conn.commit()
conn.close()

r = import_config("core-sw1.cfg", device="core-sw1", case_id=cid)
check("status ok", r["status"] == "ok")
check("device linked", r["device"] == "core-sw1")
check("case linked", r["case_id"] == cid)
check("not truncated", r["truncated"] is False)
for s in SECRETS:
    check("returned text has no " + s, s not in r["content_redacted"])

conn = get_connection()
stored = conn.execute("SELECT device, case_id, content_redacted FROM configs WHERE id = ?",
                      (r["config_id"],)).fetchone()
audit = conn.execute("SELECT tool, device, command, result_summary FROM audit_log "
                     "WHERE tool = 'import_config'").fetchall()
conn.close()
check("db device", stored[0] == "core-sw1")
check("db case", stored[1] == cid)
for s in SECRETS:
    check("db has no " + s, s not in stored[2])
check("one audit row", len(audit) == 1)
check("audit mentions file", "core-sw1.cfg" in audit[0][2])
check("audit has no secrets", not any(s in " ".join(str(x) for x in audit[0]) for s in SECRETS))

# Device only and case only
check("device only ok", import_config("core-sw1.cfg", device="core-sw1")["status"] == "ok")
check("case only ok", import_config("core-sw1.cfg", case_id=cid)["status"] == "ok")

# Truncation: stored in full, returned in part
(imp / "long.txt").write_text("hostname x\n" * 2000, encoding="utf-8")
r2 = import_config("long.txt", device="long-test")
check("long truncated", r2["truncated"] is True)
conn = get_connection()
ln = conn.execute("SELECT length(content_redacted) FROM configs WHERE id = ?",
                  (r2["config_id"],)).fetchone()[0]
conn.close()
check("long stored in full", ln == r2["characters"])

# Refusals
check("no device or case refused", raises(import_config, "core-sw1.cfg"))
check("bad device refused", raises(import_config, "core-sw1.cfg", device="bad name!"))
check("device semicolon refused", raises(import_config, "core-sw1.cfg", device="x;y"))
check("unknown case refused", raises(import_config, "core-sw1.cfg", case_id=9999))
check("bool case refused", raises(import_config, "core-sw1.cfg", case_id=True))
check("text case refused", raises(import_config, "core-sw1.cfg", case_id="1"))
check("dotdot slash refused", raises(import_config, "../x.txt", device="d"))
check("dotdot backslash refused", raises(import_config, "..\\x.txt", device="d"))
check("absolute path refused", raises(import_config, "C:\\Windows\\win.ini", device="d"))
check(".env refused", raises(import_config, ".env", device="d"))
check("exe refused", raises(import_config, "evil.exe", device="d"))
check("missing file refused", raises(import_config, "nothere.cfg", device="d"))
check("non-text name refused", raises(import_config, 123, device="d"))
(imp / "bin.cfg").write_bytes(b"abc\x00def")
check("binary refused", raises(import_config, "bin.cfg", device="d"))
(imp / "big.txt").write_text("a" * (MAX_BYTES + 10), encoding="utf-8")
check("oversize refused", raises(import_config, "big.txt", device="d"))

# Refused imports stored nothing extra
conn = get_connection()
count = conn.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
conn.close()
check("only successful imports stored", count == 4)

print("passed", passed, "failed", failed)
print("PASS" if failed == 0 else "FAILED")
