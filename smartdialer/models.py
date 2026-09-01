import sqlite3
import threading

AGENT_STATES = ["OFFLINE", "AVAILABLE", "RESERVED", "DIALING", "CONNECTED", "WRAP_UP", "PAUSED"]
CALL_STATES = ["QUEUED", "RESERVED", "INITIATED", "RINGING", "ANSWERED", "CONNECTED", "COMPLETED", "FAILED", "CANCELLED"]

CALL_TRANSITIONS = {
    "QUEUED": {"RESERVED", "CANCELLED"},
    "RESERVED": {"INITIATED", "CANCELLED", "FAILED"},
    "INITIATED": {"RINGING", "FAILED"},
    "RINGING": {"ANSWERED", "FAILED", "CANCELLED"},
    "ANSWERED": {"CONNECTED", "FAILED", "COMPLETED"},
    "CONNECTED": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

LEASE_SECONDS = 15

db_lock = threading.Lock()
DB_PATH = "smartdialer.db"


def set_db_path(path):
    global DB_PATH
    DB_PATH = path


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    DROP TABLE IF EXISTS agents;
    DROP TABLE IF EXISTS borrowers;
    DROP TABLE IF EXISTS calls;
    DROP TABLE IF EXISTS processed_events;
    DROP TABLE IF EXISTS metrics_log;

    CREATE TABLE agents (
        id TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        reserved_by TEXT,
        reserved_at TEXT,
        current_call_id TEXT
    );

    CREATE TABLE borrowers (
        id TEXT PRIMARY KEY,
        phone TEXT,
        state TEXT NOT NULL,
        claimed_by TEXT
    );

    CREATE TABLE calls (
        id TEXT PRIMARY KEY,
        agent_id TEXT,
        borrower_id TEXT,
        state TEXT NOT NULL,
        provider TEXT,
        last_event_ts TEXT,
        created_at TEXT
    );

    CREATE TABLE processed_events (
        event_id TEXT PRIMARY KEY,
        call_id TEXT,
        event_type TEXT,
        event_ts TEXT,
        processed_at TEXT
    );

    CREATE TABLE metrics_log (
        ts TEXT,
        calls_initiated INTEGER,
        calls_connected INTEGER,
        calls_failed INTEGER,
        agents_available INTEGER,
        safety_reduced INTEGER
    );
    """)
    conn.commit()
    conn.close()


def seed_agents(n):
    conn = get_conn()
    cur = conn.cursor()
    for i in range(n):
        cur.execute(
            "INSERT INTO agents (id, state, reserved_by, reserved_at, current_call_id) VALUES (?,?,?,?,?)",
            (f"agent-{i}", "AVAILABLE", None, None, None),
        )
    conn.commit()
    conn.close()


def seed_borrowers(n):
    conn = get_conn()
    cur = conn.cursor()
    for i in range(n):
        cur.execute(
            "INSERT INTO borrowers (id, phone, state, claimed_by) VALUES (?,?,?,?)",
            (f"borrower-{i}", f"+91900000{i:04d}", "PENDING", None),
        )
    conn.commit()
    conn.close()
