import threading
import time
from datetime import timedelta

from smartdialer.models import init_db, seed_agents, seed_borrowers, set_db_path, get_conn, LEASE_SECONDS
from smartdialer.lease_sweeper import LeaseSweeper
from smartdialer.util import now_utc


def test_crash_recovery():
    set_db_path("smartdialer_test_crash.db")
    init_db()
    seed_agents(3)
    seed_borrowers(3)

    conn = get_conn()
    cur = conn.cursor()
    stale_ts = (now_utc() - timedelta(seconds=LEASE_SECONDS + 5)).isoformat()
    cur.execute(
        "UPDATE agents SET state='RESERVED', reserved_by='dead-worker', reserved_at=? WHERE id='agent-0'",
        (stale_ts,),
    )
    conn.commit()
    conn.close()

    stop_event = threading.Event()
    sweeper = LeaseSweeper(stop_event)
    t = threading.Thread(target=sweeper.run, daemon=True)
    t.start()
    time.sleep(3)
    stop_event.set()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state FROM agents WHERE id='agent-0'")
    state = cur.fetchone()["state"]
    conn.close()

    assert state == "AVAILABLE", f"expected AVAILABLE after lease expiry, got {state}"
    print(f"test_crash_recovery PASSED — stale reservation auto-released, state: {state}")


if __name__ == "__main__":
    test_crash_recovery()
