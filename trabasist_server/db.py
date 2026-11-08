"""Trabasist database: schema and connection helper."""
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "trabasist.db"


def db_path() -> Path:
    return Path(os.environ.get("TRABASIST_DB", str(DEFAULT_DB)))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT,
    platform TEXT,
    connection_type TEXT,
    tags TEXT
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opened_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT,
    symptom TEXT NOT NULL,
    error_code TEXT,
    device TEXT,
    environment TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    root_cause TEXT,
    resolution TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    action TEXT NOT NULL,
    command TEXT,
    result TEXT,
    outcome TEXT NOT NULL DEFAULT 'inconclusive'
        CHECK (outcome IN ('cause', 'ruled_out', 'inconclusive'))
);

CREATE TABLE IF NOT EXISTS configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device TEXT,
    case_id INTEGER REFERENCES cases(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    content_redacted TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS error_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    platform TEXT,
    meaning TEXT,
    likely_causes TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    tool TEXT NOT NULL,
    device TEXT,
    command TEXT,
    result_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_steps_case ON steps(case_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);

CREATE VIRTUAL TABLE IF NOT EXISTS cases_fts USING fts5(
    symptom, error_code, device, root_cause, resolution,
    content='cases', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS cases_ai AFTER INSERT ON cases BEGIN
    INSERT INTO cases_fts(rowid, symptom, error_code, device, root_cause, resolution)
    VALUES (new.id, new.symptom, new.error_code, new.device, new.root_cause, new.resolution);
END;

CREATE TRIGGER IF NOT EXISTS cases_ad AFTER DELETE ON cases BEGIN
    INSERT INTO cases_fts(cases_fts, rowid, symptom, error_code, device, root_cause, resolution)
    VALUES ('delete', old.id, old.symptom, old.error_code, old.device, old.root_cause, old.resolution);
END;

CREATE TRIGGER IF NOT EXISTS cases_au AFTER UPDATE ON cases BEGIN
    INSERT INTO cases_fts(cases_fts, rowid, symptom, error_code, device, root_cause, resolution)
    VALUES ('delete', old.id, old.symptom, old.error_code, old.device, old.root_cause, old.resolution);
    INSERT INTO cases_fts(rowid, symptom, error_code, device, root_cause, resolution)
    VALUES (new.id, new.symptom, new.error_code, new.device, new.root_cause, new.resolution);
END;
"""


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    conn = get_connection()
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'cases_fts_%' ORDER BY name")]
    print("DB file:", db_path())
    print("Tables:", ", ".join(tables))
    # Search smoke test, rolled back so nothing is kept
    conn.execute("INSERT INTO cases (symptom, error_code, device) VALUES (?, ?, ?)",
                 ("Installer fails on Windows server", "2735", "srv01"))
    hits = conn.execute(
        "SELECT c.id FROM cases_fts f JOIN cases c ON c.id = f.rowid WHERE cases_fts MATCH ?",
        ("2735",)).fetchall()
    conn.rollback()
    print("FTS test:", "PASS" if len(hits) == 1 else "FAIL")
    conn.close()
