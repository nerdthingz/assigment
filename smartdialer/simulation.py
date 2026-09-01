import threading
import time

from . import models
from .models import get_conn, init_db, seed_agents, seed_borrowers, set_db_path
from .safety_controller import SafetyController
from .metrics import Metrics
from .event_processor import EventProcessor
from .pacing_progressive import ProgressivePacingEngine
from .lease_sweeper import LeaseSweeper
from .worker import worker_loop
from .providers import build_providers


def run_simulation(num_agents=20, num_borrowers=200, num_workers=4, duration_seconds=20,
                    providers=None, pacing=None, on_tick=None, control=None,
                    quiet=False, db_path=None):
    if db_path:
        set_db_path(db_path)
    init_db()
    seed_agents(num_agents)
    seed_borrowers(num_borrowers)

    if providers is None:
        providers = build_providers()
    if pacing is None:
        pacing = ProgressivePacingEngine()

    safety = SafetyController()
    metrics = Metrics()
    stop_event = threading.Event()
    event_processor = EventProcessor(safety, metrics, stop_event)

    sweeper = LeaseSweeper(stop_event)
    threading.Thread(target=sweeper.run, daemon=True).start()

    history = []

    def metrics_logger():
        elapsed = 0
        while not stop_event.is_set():
            metrics.log_row()
            snap = metrics.snapshot()
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) c FROM agents WHERE state='AVAILABLE'")
                avail = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) c FROM agents")
                total = cur.fetchone()["c"]
                cur.execute(
                    "SELECT COUNT(*) c FROM agents WHERE state IN "
                    "('DIALING','CONNECTED','WRAP_UP','RESERVED')"
                )
                busy = cur.fetchone()["c"]
                conn.close()
            except Exception:
                break

            row = dict(snap)
            row["t"] = elapsed
            row["agents_available"] = avail
            row["agents_total"] = total
            row["utilization"] = round(busy / total, 3) if total else 0.0
            row["provider_failure_rate"] = round(safety.provider_failure_rate(), 3)
            history.append(row)

            if on_tick:
                on_tick(elapsed, row, providers, safety)
            if not quiet:
                print(f"  t={elapsed:>3}s  initiated={row['calls_initiated']:<4} "
                      f"connected={row['calls_connected']:<4} failed={row['calls_failed']:<4} "
                      f"safety_reduced={row['safety_reduced']:<4} avail={avail:<3} "
                      f"util={row['utilization']:.0%} prov_fail_rate={row['provider_failure_rate']:.0%}")
            elapsed += 1
            time.sleep(1)

    logger_thread = threading.Thread(target=metrics_logger, daemon=True)
    logger_thread.start()

    threads = []
    for i in range(num_workers):
        t = threading.Thread(
            target=worker_loop,
            args=(f"worker-{i}", providers, safety, metrics, event_processor, stop_event, pacing),
            daemon=True,
        )
        threads.append(t)
        t.start()

    if control:
        control(stop_event, safety, metrics)
    else:
        time.sleep(duration_seconds)

    stop_event.set()
    time.sleep(6)  # drain window: lets in-flight provider/worker threads see stop_event and exit

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state, COUNT(*) c FROM agents GROUP BY state")
    agent_states = {r["state"]: r["c"] for r in cur.fetchall()}
    cur.execute("SELECT state, COUNT(*) c FROM calls GROUP BY state")
    call_states = {r["state"]: r["c"] for r in cur.fetchall()}
    conn.close()

    result = {
        "final_metrics": metrics.snapshot(),
        "agent_states": agent_states,
        "call_states": call_states,
        "history": history,
    }
    if not quiet:
        print("Final metrics:", result["final_metrics"])
        print("Agent states:", agent_states)
        print("Call states:", call_states)
    return result


def check_no_agent_double_booked():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT agent_id, COUNT(*) c FROM calls
        WHERE state IN ('INITIATED','RINGING','ANSWERED','CONNECTED')
        GROUP BY agent_id HAVING c > 1
    """)
    rows = cur.fetchall()
    conn.close()
    return len(rows) > 0
