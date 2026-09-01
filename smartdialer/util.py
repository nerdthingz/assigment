import sqlite3
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def now_utc():
    return datetime.now(timezone.utc)


class RunEnded(Exception):
    pass


def safe_db_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except sqlite3.OperationalError as e:
        if "no such table" in str(e) or "database is locked" in str(e):
            raise RunEnded(str(e))
        raise
