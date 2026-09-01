from smartdialer.tests.test_concurrency import test_no_double_booking
from smartdialer.tests.test_events import test_idempotent_events, test_out_of_order_events
from smartdialer.tests.test_crash_recovery import test_crash_recovery
from smartdialer.tests.test_safety_controller import (
    test_safety_controller_caps_calls,
    test_safety_controller_throttles_on_high_failure_rate,
    test_safety_controller_never_exceeds_available_agents,
)
from smartdialer.tests.test_state_machine import (
    test_valid_transitions_exist,
    test_terminal_states_have_no_outgoing_transitions,
    test_illegal_skip_transition_rejected,
)
from smartdialer.tests.test_predictive_pacing import (
    test_predictive_suggests_more_than_progressive_when_answer_rate_low,
    test_predictive_suggests_fewer_when_answer_rate_high,
    test_predictive_never_negative,
)

from smartdialer.scenarios import (
    run_scenario_matrix,
    run_provider_outage_scenario,
    run_sudden_agent_drop_scenario,
    run_load_test,
    run_predictive_vs_progressive,
)

if __name__ == "__main__":
    print("=== Running tests ===")
    test_valid_transitions_exist()
    test_terminal_states_have_no_outgoing_transitions()
    test_illegal_skip_transition_rejected()
    test_no_double_booking()
    test_idempotent_events()
    test_out_of_order_events()
    test_crash_recovery()
    test_safety_controller_caps_calls()
    test_safety_controller_throttles_on_high_failure_rate()
    test_safety_controller_never_exceeds_available_agents()
    test_predictive_suggests_more_than_progressive_when_answer_rate_low()
    test_predictive_suggests_fewer_when_answer_rate_high()
    test_predictive_never_negative()

    print("\n=== Running scenario matrix (A/B/C/D) — Progressive pacing ===")
    run_scenario_matrix()

    print("\n=== Running provider outage scenario ===")
    run_provider_outage_scenario()

    print("\n=== Running sudden agent drop scenario ===")
    run_sudden_agent_drop_scenario()

    print("\n=== Running load test ===")
    run_load_test()

    print("\n=== Running Predictive vs Progressive comparison ===")
    run_predictive_vs_progressive()

    print("\nAll done.")
