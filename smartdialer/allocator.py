import random
import uuid

from .models import get_conn, db_lock
from .util import now_iso, RunEnded, safe_db_call


class CallAllocator:
    def __init__(self, worker_id, providers, safety, metrics, run_guard):
        self.worker_id = worker_id
        self.providers = providers
        self.safety = safety
        self.metrics = metrics
        self.run_guard = run_guard

    def reserve_agent(self, conn):
        cur = conn.cursor()
        cur.execute("SELECT id FROM agents WHERE state='AVAILABLE' LIMIT 5")
        candidates = [r["id"] for r in cur.fetchall()]
        random.shuffle(candidates)
        for agent_id in candidates:
            cur.execute(
                "UPDATE agents SET state='RESERVED', reserved_by=?, reserved_at=? "
                "WHERE id=? AND state='AVAILABLE'",
                (self.worker_id, now_iso(), agent_id),
            )
            if cur.rowcount == 1:
                conn.commit()
                return agent_id
        return None

    def claim_borrower(self, conn):
        cur = conn.cursor()
        cur.execute("SELECT id FROM borrowers WHERE state='PENDING' LIMIT 5")
        candidates = [r["id"] for r in cur.fetchall()]
        random.shuffle(candidates)
        for borrower_id in candidates:
            cur.execute(
                "UPDATE borrowers SET state='CLAIMED', claimed_by=? WHERE id=? AND state='PENDING'",
                (self.worker_id, borrower_id),
            )
            if cur.rowcount == 1:
                conn.commit()
                return borrower_id
        return None

    def start_call(self, on_event):
        if self.run_guard.is_set():
            return None
        try:
            with db_lock:
                conn = safe_db_call(get_conn)
                agent_id = safe_db_call(self.reserve_agent, conn)
                if not agent_id:
                    conn.close()
                    return None
                borrower_id = safe_db_call(self.claim_borrower, conn)
                if not borrower_id:
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE agents SET state='AVAILABLE', reserved_by=NULL, reserved_at=NULL WHERE id=?",
                        (agent_id,),
                    )
                    conn.commit()
                    conn.close()
                    return None

                call_id = str(uuid.uuid4())
                provider = random.choice(self.providers)
                ts = now_iso()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO calls (id, agent_id, borrower_id, state, provider, last_event_ts, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (call_id, agent_id, borrower_id, "RESERVED", provider.name, ts, ts),
                )
                cur.execute("UPDATE agents SET state='DIALING', current_call_id=? WHERE id=?", (call_id, agent_id))
                cur.execute(
                    "UPDATE calls SET state='INITIATED', last_event_ts=? WHERE id=?",
                    (now_iso(), call_id),
                )
                conn.commit()
                conn.close()
        except RunEnded:
            return None

        self.metrics.incr("calls_initiated")
        provider.place_call(call_id, on_event, self.run_guard)
        return call_id
