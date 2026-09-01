from smartdialer.models import CALL_TRANSITIONS


def test_valid_transitions_exist():
    assert "RINGING" in CALL_TRANSITIONS["INITIATED"]
    assert "ANSWERED" in CALL_TRANSITIONS["RINGING"]
    assert "CONNECTED" in CALL_TRANSITIONS["ANSWERED"]
    assert "COMPLETED" in CALL_TRANSITIONS["CONNECTED"]
    print("test_valid_transitions_exist PASSED")


def test_terminal_states_have_no_outgoing_transitions():
    for terminal in ("COMPLETED", "FAILED", "CANCELLED"):
        assert CALL_TRANSITIONS[terminal] == set(), f"{terminal} should be terminal"
    print("test_terminal_states_have_no_outgoing_transitions PASSED")


def test_illegal_skip_transition_rejected():
    # QUEUED should never be allowed to jump straight to CONNECTED
    assert "CONNECTED" not in CALL_TRANSITIONS["QUEUED"]
    print("test_illegal_skip_transition_rejected PASSED")


if __name__ == "__main__":
    test_valid_transitions_exist()
    test_terminal_states_have_no_outgoing_transitions()
    test_illegal_skip_transition_rejected()
