import time

from .models import get_conn
from .providers import build_providers
from .pacing_progressive import ProgressivePacingEngine
from .pacing_predictive import PredictivePacingEngine
from .simulation import run_simulation, check_no_agent_double_booked

SCENARIOS = {
    "A": {"answer_rate": 0.20, "talk_time": 120},
    "B": {"answer_rate": 0.50, "talk_time": 90},
    "C": {"answer_rate": 0.70, "talk_time": 180},
}


def run_scenario_matrix(num_agents=20, num_borrowers=300, num_workers=4, duration_seconds=15,
                         pacing_factory=None):
    """
    pacing_factory: callable() -> pacing engine instance. Defaults to Progressive.
    Runs scenarios A, B, C (fixed conditions) and D (changing conditions mid-run).
    """
    if pacing_factory is None:
        pacing_factory = ProgressivePacingEngine

    results = {}

    for name, cfg in SCENARIOS.items():
        print(f"\n=== Scenario {name}  (answer_rate={cfg['answer_rate']:.0%}, talk_time={cfg['talk_time']}s) ===")
        providers = build_providers(answer_rate=cfg["answer_rate"], talk_time=cfg["talk_time"])
        res = run_simulation(
            num_agents=num_agents, num_borrowers=num_borrowers,
            num_workers=num_workers, duration_seconds=duration_seconds,
            providers=providers, pacing=pacing_factory(),
            db_path=f"smartdialer_scenario_{name}.db",
        )
        results["Scenario_" + name] = res

    print("\n=== Scenario D (changing conditions mid-run) ===")
    providers_d = build_providers(answer_rate=0.20, talk_time=60)

    def changing_control(stop_event, safety, metrics):
        phases = [(5, 0.20, 60), (5, 0.70, 200), (5, 0.35, 100)]
        for seconds, rate, talk in phases:
            for p in providers_d:
                p.answer_rate = rate
                p.talk_time = talk
            time.sleep(seconds)

    res_d = run_simulation(
        num_agents=num_agents, num_borrowers=num_borrowers,
        num_workers=num_workers, duration_seconds=15,
        providers=providers_d, pacing=pacing_factory(),
        control=changing_control, db_path="smartdialer_scenario_D.db",
    )
    results["Scenario_D"] = res_d

    print("\n=== Scenario Matrix Summary ===")
    for name, res in results.items():
        fm = res["final_metrics"]
        print(f"{name:14s} initiated={fm['calls_initiated']:<4} connected={fm['calls_connected']:<4} "
              f"failed={fm['calls_failed']:<4} safety_reduced={fm['safety_reduced']:<4}")
    return results


def run_load_test(num_agents=200, num_borrowers=3000, num_workers=12, duration_seconds=20,
                   pacing=None):
    print(f"\n=== Load test: {num_agents} agents, {num_workers} workers, {num_borrowers} borrowers ===")
    start = time.time()
    providers = build_providers(answer_rate=0.4, talk_time=60)
    res = run_simulation(
        num_agents=num_agents, num_borrowers=num_borrowers,
        num_workers=num_workers, duration_seconds=duration_seconds,
        providers=providers, pacing=pacing or ProgressivePacingEngine(),
        quiet=True, db_path="smartdialer_loadtest.db",
    )
    elapsed = time.time() - start
    fm = res["final_metrics"]
    throughput = fm["calls_initiated"] / elapsed if elapsed else 0
    print(f"wall_time={elapsed:.1f}s  calls_initiated={fm['calls_initiated']}  "
          f"throughput={throughput:.1f} calls/sec  safety_reduced={fm['safety_reduced']}")
    double_booked = check_no_agent_double_booked()
    print(f"double_booking_detected={double_booked}")
    return res


def run_provider_outage_scenario(num_agents=20, num_borrowers=200, num_workers=4, pacing=None):
    print("\n=== Provider outage scenario ===")
    providers = build_providers(answer_rate=0.5, talk_time=30)

    def outage_control(stop_event, safety, metrics):
        print("  phase 1: normal operation (5s)")
        time.sleep(5)
        print("  phase 2: provider outage begins (8s)")
        for p in providers:
            p.set_outage(True)
        time.sleep(8)
        print("  phase 3: provider recovers (7s)")
        for p in providers:
            p.set_outage(False)
        time.sleep(7)

    res = run_simulation(
        num_agents=num_agents, num_borrowers=num_borrowers, num_workers=num_workers,
        providers=providers, pacing=pacing or ProgressivePacingEngine(),
        control=outage_control, db_path="smartdialer_outage.db",
    )
    return res


def run_sudden_agent_drop_scenario(num_agents=100, num_borrowers=500, num_workers=6, pacing=None):
    print("\n=== Sudden agent drop scenario (100 agents, 40 drop at t=5s) ===")
    providers = build_providers(answer_rate=0.4, talk_time=60)
    drop_recorded = {}

    def drop_control(stop_event, safety, metrics):
        time.sleep(5)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM agents WHERE state='AVAILABLE' LIMIT 40")
        ids = [r["id"] for r in cur.fetchall()]
        for aid in ids:
            cur.execute("UPDATE agents SET state='OFFLINE' WHERE id=?", (aid,))
        conn.commit()
        conn.close()
        drop_recorded["dropped_at_t"] = 5
        drop_recorded["count"] = len(ids)
        print(f"  dropped {len(ids)} agents to OFFLINE at t=5s")
        time.sleep(10)

    res = run_simulation(
        num_agents=num_agents, num_borrowers=num_borrowers, num_workers=num_workers,
        duration_seconds=15, providers=providers, pacing=pacing or ProgressivePacingEngine(),
        control=drop_control, db_path="smartdialer_agentdrop.db",
    )
    if len(res["history"]) > 6:
        before = res["history"][4]["agents_available"]
        after = res["history"][6]["agents_available"]
        print(f"  agents_available before drop (t=4): {before}, two ticks after drop (t=6): {after}")
    return res


def run_predictive_vs_progressive(num_agents=20, num_borrowers=200, num_workers=4, duration_seconds=15):
    """
    Runs the same scenario under both pacing engines so the difference in
    utilization vs safety-reduced behavior can be directly compared.
    """
    print("\n=== Progressive pacing ===")
    providers_p = build_providers(answer_rate=0.5, talk_time=90)
    res_prog = run_simulation(
        num_agents=num_agents, num_borrowers=num_borrowers, num_workers=num_workers,
        duration_seconds=duration_seconds, providers=providers_p,
        pacing=ProgressivePacingEngine(), db_path="smartdialer_progressive.db",
    )

    print("\n=== Predictive pacing (same conditions) ===")
    providers_pred = build_providers(answer_rate=0.5, talk_time=90)
    pred_engine = PredictivePacingEngine()

    def on_tick(elapsed, row, providers, safety):
        recent = row.get("calls_connected", 0)
        pred_engine.record_outcome(recent > 0)

    res_pred = run_simulation(
        num_agents=num_agents, num_borrowers=num_borrowers, num_workers=num_workers,
        duration_seconds=duration_seconds, providers=providers_pred,
        pacing=pred_engine, on_tick=on_tick, db_path="smartdialer_predictive.db",
    )

    print("\n=== Comparison ===")
    fp, fpred = res_prog["final_metrics"], res_pred["final_metrics"]
    print(f"Progressive: initiated={fp['calls_initiated']:<4} connected={fp['calls_connected']:<4} "
          f"safety_reduced={fp['safety_reduced']}")
    print(f"Predictive:  initiated={fpred['calls_initiated']:<4} connected={fpred['calls_connected']:<4} "
          f"safety_reduced={fpred['safety_reduced']}")
    return {"progressive": res_prog, "predictive": res_pred}
