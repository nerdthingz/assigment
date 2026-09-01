from smartdialer.safety_controller import SafetyController


def test_safety_controller_caps_calls():
    safety = SafetyController()
    allowed = safety.approve(requested=15, agents_available=10, calls_in_flight=3)
    assert allowed <= 7, f"safety controller allowed {allowed}, expected <=7"
    print(f"test_safety_controller_caps_calls PASSED — requested 15, approved {allowed}")


def test_safety_controller_throttles_on_high_failure_rate():
    safety = SafetyController()
    for _ in range(15):
        safety.record_provider_result(False)
    allowed = safety.approve(requested=10, agents_available=10, calls_in_flight=0)
    assert allowed <= 1, f"expected throttling under high failure rate, got {allowed}"
    print(f"test_safety_controller_throttles_on_high_failure_rate PASSED — throttled to {allowed}")


def test_safety_controller_never_exceeds_available_agents():
    safety = SafetyController()
    for requested in [0, 1, 5, 50, 1000]:
        allowed = safety.approve(requested=requested, agents_available=10, calls_in_flight=2)
        assert allowed <= 8, f"safety controller exceeded hard cap: requested={requested} allowed={allowed}"
    print("test_safety_controller_never_exceeds_available_agents PASSED")


if __name__ == "__main__":
    test_safety_controller_caps_calls()
    test_safety_controller_throttles_on_high_failure_rate()
    test_safety_controller_never_exceeds_available_agents()
