import threading

from .models import get_conn
from .util import now_iso, RunEnded, safe_db_call


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.counters = {
            "calls_initiated": 0,
            "calls_connected": 0,
            "calls_failed": 0,
            "safety_reduced": 0,
        }

    def incr(self, key, n=1):
        with self.lock:
            self.counters[key] += n

    def snapshot(self):
        with self.lock:
            return dict(self.counters)

    def log_row(self):
        try:
            conn = safe_db_call(get_conn)
            cur = conn.cursor()
            snap = self.snapshot()
            cur.execute("SELECT COUNT(*) c FROM agents WHERE state='AVAILABLE'")
            avail = cur.fetchone()["c"]
            cur.execute(
                "INSERT INTO metrics_log (ts, calls_initiated, calls_connected, calls_failed, "
                "agents_available, safety_reduced) VALUES (?,?,?,?,?,?)",
                (now_iso(), snap["calls_initiated"], snap["calls_connected"],
                 snap["calls_failed"], avail, snap["safety_reduced"]),
            )
            conn.commit()
            conn.close()
        except RunEnded:
            return
