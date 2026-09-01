import threading
import time
import queue

from smartdialer.models import init_db, seed_agents, seed_borrowers, set_db_path, get_conn, db_lock
from smartdialer.providers import ProviderA
from smartdialer.safety_controller import SafetyController
from smartdialer.metrics import Metrics
from smartdialer.allocator import CallAllocator


def test_no_double_booking():
    set_db_path("smartdialer_test_concurrency.db")
    init_db()
    seed_agents(5)
    seed_borrowers(100)
    safety = SafetyController()
    metrics = Metrics()
    providers = [ProviderA()]
    results = queue.Queue()
    test_guard = threading.Event()

    def worker(i):
        allocator = CallAllocator(f"tw-{i}", providers, safety, metrics, test_guard)
        for _ in range(10):
            with db_lock:
                conn = get_conn()
                agent_id = allocator.reserve_agent(conn)
                conn.close()
            if agent_id:
                results.put(agent_id)
            time.sleep(0.01)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    seen = []
    while not results.empty():
        seen.append(results.get())

    assert len(seen) == len(set(seen)), "DOUBLE BOOKING DETECTED"
    print(f"test_no_double_booking PASSED — {len(seen)} unique reservations, no duplicates")


if __name__ == "__main__":
    test_no_double_booking()
