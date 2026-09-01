import threading
from datetime import timedelta

from smartdialer.models import init_db, seed_agents, seed_borrowers, set_db_path, get_conn
from smartdialer.safety_controller import SafetyController
from smartdialer.metrics import Metrics
from smartdialer.event_processor import EventProcessor
from smartdialer.util import now_iso, now_utc


def _insert_call(call_id, agent_id="agent-0", borrower_id="borrower-0", state="INITIATED"):
    conn = get_conn()
    cur = conn.cursor()
    ts = now_iso()
    cur.execute(
        "INSERT INTO calls (id, agent_id, borrower_id, state, provider, last_event_ts, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (call_id, agent_id, borrower_id, state, "ProviderA", ts, ts),
    )
    conn.commit()
    conn.close()


def test_idempotent_events():
    set_db_path("smartdialer_test_events1.db")
    init_db()
    seed_agents(1)
    seed_borrowers(1)
    safety = SafetyController()
    metrics = Metrics()
    ep = EventProcessor(safety, metrics, threading.Event())

    call_id = "test-call-1"
    _insert_call(call_id)

    for _ in range(3):
        ep.handle_event(call_id, "RINGING", now_iso())
    ep.handle_event(call_id, "ANSWERED", now_iso())
    ep.handle_event(call_id, "CONNECTED", now_iso())
    ep.handle_event(call_id, "COMPLETED", now_iso())
    ep.handle_event(call_id, "COMPLETED", now_iso())  # duplicate, should be a no-op

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state FROM calls WHERE id=?", (call_id,))
    final_state = cur.fetchone()["state"]
    conn.close()

    assert final_state == "COMPLETED"
    print(f"test_idempotent_events PASSED — final state: {final_state}")


def test_out_of_order_events():
    set_db_path("smartdialer_test_events2.db")
    init_db()
    seed_agents(1)
    seed_borrowers(1)
    safety = SafetyController()
    metrics = Metrics()
    ep = EventProcessor(safety, metrics, threading.Event())

    call_id = "test-call-2"
    _insert_call(call_id)

    t0 = now_utc()
    ts_ringing = t0.isoformat()
    ts_completed_early = (t0 - timedelta(seconds=5)).isoformat()

    ep.handle_event(call_id, "RINGING", ts_ringing)
    ep.handle_event(call_id, "COMPLETED", ts_completed_early)  # stale timestamp, should be ignored

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state FROM calls WHERE id=?", (call_id,))
    state = cur.fetchone()["state"]
    conn.close()

    assert state == "RINGING", f"expected RINGING, got {state}"
    print(f"test_out_of_order_events PASSED — stale event ignored, state stayed: {state}")


if __name__ == "__main__":
    test_idempotent_events()
    test_out_of_order_events()
