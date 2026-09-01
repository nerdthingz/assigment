import threading
import time
import uuid
import sqlite3

from .models import get_conn, db_lock, CALL_TRANSITIONS
from .util import now_iso, RunEnded, safe_db_call


class EventProcessor:
    def __init__(self, safety, metrics, run_guard):
        self.safety = safety
        self.metrics = metrics
        self.run_guard = run_guard

    def handle_event(self, call_id, event_type, event_ts):
        if self.run_guard.is_set():
            return
        event_id = f"{uuid.uuid4()}-{call_id}-{event_type}-{event_ts}"
        try:
            with db_lock:
                if self.run_guard.is_set():
                    return
                conn = safe_db_call(get_conn)
                cur = conn.cursor()

                try:
                    cur.execute(
                        "INSERT INTO processed_events (event_id, call_id, event_type, event_ts, processed_at) "
                        "VALUES (?,?,?,?,?)",
                        (event_id, call_id, event_type, event_ts, now_iso()),
                    )
                except sqlite3.IntegrityError:
                    conn.close()
                    return  # duplicate event, already processed - no-op

                cur.execute("SELECT * FROM calls WHERE id=?", (call_id,))
                call = cur.fetchone()
                if not call:
                    conn.close()
                    return

                if call["last_event_ts"] and event_ts < call["last_event_ts"]:
                    conn.close()
                    return  # stale / out-of-order event, ignore

                current_state = call["state"]
                target_state = event_type
                if target_state not in CALL_TRANSITIONS.get(current_state, set()):
                    conn.close()
                    return  # illegal transition for current state, ignore

                cur.execute(
                    "UPDATE calls SET state=?, last_event_ts=? WHERE id=?",
                    (target_state, event_ts, call_id),
                )

                agent_id = call["agent_id"]
                if target_state == "RINGING":
                    cur.execute("UPDATE agents SET state='DIALING' WHERE id=?", (agent_id,))
                elif target_state == "CONNECTED":
                    cur.execute("UPDATE agents SET state='CONNECTED' WHERE id=?", (agent_id,))
                    self.metrics.incr("calls_connected")
                elif target_state == "COMPLETED":
                    cur.execute(
                        "UPDATE agents SET state='WRAP_UP', current_call_id=NULL WHERE id=?", (agent_id,)
                    )
                    cur.execute("UPDATE borrowers SET state='DONE' WHERE id=?", (call["borrower_id"],))
                    self.safety.record_provider_result(True)
                    self._schedule_wrapup_release(agent_id)
                elif target_state == "FAILED":
                    cur.execute(
                        "UPDATE agents SET state='AVAILABLE', current_call_id=NULL WHERE id=?", (agent_id,)
                    )
                    cur.execute(
                        "UPDATE borrowers SET state='PENDING', claimed_by=NULL WHERE id=?",
                        (call["borrower_id"],),
                    )
                    self.safety.record_provider_result(False)
                    self.metrics.incr("calls_failed")
                elif target_state == "CANCELLED":
                    cur.execute(
                        "UPDATE agents SET state='AVAILABLE', current_call_id=NULL WHERE id=?", (agent_id,)
                    )

                conn.commit()
                conn.close()
        except RunEnded:
            return

    def _schedule_wrapup_release(self, agent_id):
        def release():
            time.sleep(1.0)
            if self.run_guard.is_set():
                return
            try:
                with db_lock:
                    if self.run_guard.is_set():
                        return
                    conn = safe_db_call(get_conn)
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE agents SET state='AVAILABLE' WHERE id=? AND state='WRAP_UP'",
                        (agent_id,),
                    )
                    conn.commit()
                    conn.close()
            except RunEnded:
                return

        threading.Thread(target=release, daemon=True).start()
