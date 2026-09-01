import time
from datetime import timedelta

from .models import get_conn, db_lock, LEASE_SECONDS
from .util import now_utc, RunEnded, safe_db_call


class LeaseSweeper:
    """
    Recovers agents left RESERVED by a worker that crashed between
    reserving the agent and initiating the call. No crash detection is
    needed: every reservation has a timestamp, and any reservation older
    than LEASE_SECONDS with no progress is simply released back to the pool.
    """

    def __init__(self, stop_event, lease_seconds=LEASE_SECONDS, poll_interval=2):
        self.stop_event = stop_event
        self.lease_seconds = lease_seconds
        self.poll_interval = poll_interval

    def run(self):
        while not self.stop_event.is_set():
            try:
                with db_lock:
                    if self.stop_event.is_set():
                        return
                    conn = safe_db_call(get_conn)
                    cur = conn.cursor()
                    cutoff = (now_utc() - timedelta(seconds=self.lease_seconds)).isoformat()
                    cur.execute(
                        "UPDATE agents SET state='AVAILABLE', reserved_by=NULL, reserved_at=NULL "
                        "WHERE state='RESERVED' AND reserved_at < ?",
                        (cutoff,),
                    )
                    conn.commit()
                    conn.close()
            except RunEnded:
                return
            time.sleep(self.poll_interval)
