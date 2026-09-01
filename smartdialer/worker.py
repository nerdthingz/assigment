import random
import time

from .models import get_conn
from .allocator import CallAllocator
from .util import RunEnded, safe_db_call


def worker_loop(worker_id, providers, safety, metrics, event_processor, stop_event, pacing):
    allocator = CallAllocator(worker_id, providers, safety, metrics, stop_event)
    while not stop_event.is_set():
        try:
            conn = safe_db_call(get_conn)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) c FROM agents WHERE state='AVAILABLE'")
            available = cur.fetchone()["c"]
            cur.execute(
                "SELECT COUNT(*) c FROM calls WHERE state IN "
                "('INITIATED','RINGING','ANSWERED','CONNECTED')"
            )
            in_flight = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) c FROM agents WHERE state='WRAP_UP'")
            about_to_free = cur.fetchone()["c"]
            conn.close()
        except RunEnded:
            return

        if stop_event.is_set():
            return

        suggested = pacing.suggest(
            agents_available=available,
            calls_in_flight=in_flight,
            agents_about_to_free=about_to_free,
        )
        approved = safety.approve(suggested, available, in_flight)
        if approved < suggested:
            metrics.incr("safety_reduced")

        for _ in range(approved):
            if stop_event.is_set():
                break
            call_id = allocator.start_call(event_processor.handle_event)
            if not call_id:
                break

        time.sleep(random.uniform(0.3, 0.7))
