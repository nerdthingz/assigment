class PredictivePacingEngine:
    """
    Rule-based, not ML. Estimates how many calls can be started right now
    by betting that not everyone answers, and that some currently-busy
    agents will free up before the calls in flight connect.

    Formula:
        effective_capacity = agents_available + agents_about_to_free * soon_free_weight
        target_in_flight    = effective_capacity / max(recent_answer_rate, floor)
        suggested           = target_in_flight - calls_already_in_flight

    This number is only ever a *suggestion*. It has no access to the
    telecom provider or the call allocator - the Safety Controller is the
    only component that can turn this into a real dial, and it always
    re-clamps against agents_available, independent of this formula.
    """

    name = "predictive"

    def __init__(self, min_answer_rate_floor=0.05, soon_free_weight=0.5, history_size=30):
        self.min_answer_rate_floor = min_answer_rate_floor
        self.soon_free_weight = soon_free_weight
        self.history = []
        self.history_size = history_size

    def record_outcome(self, answered: bool):
        self.history.append(answered)
        if len(self.history) > self.history_size:
            self.history.pop(0)

    def recent_answer_rate(self):
        if not self.history:
            return 0.5
        return sum(1 for a in self.history if a) / len(self.history)

    def suggest(self, agents_available, calls_in_flight, agents_about_to_free=0, **kwargs):
        answer_rate = max(self.recent_answer_rate(), self.min_answer_rate_floor)
        effective_capacity = agents_available + agents_about_to_free * self.soon_free_weight
        target_in_flight = effective_capacity / answer_rate
        suggested = target_in_flight - calls_in_flight
        return max(0, round(suggested))
