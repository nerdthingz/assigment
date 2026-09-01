class SafetyController:
    """
    The only component allowed to authorize real dials.
    Pacing engines (progressive or predictive) may only suggest a number.
    This class can approve, reduce, reject, or force a fallback.
    There is no bypass path: every worker loop must call approve() before
    the CallAllocator is invoked.
    """

    def __init__(self, max_history=20, failure_rate_throttle=0.4):
        self.recent_provider_results = []
        self.max_history = max_history
        self.failure_rate_throttle = failure_rate_throttle

    def record_provider_result(self, success):
        self.recent_provider_results.append(success)
        if len(self.recent_provider_results) > self.max_history:
            self.recent_provider_results.pop(0)

    def provider_failure_rate(self):
        if not self.recent_provider_results:
            return 0.0
        fails = sum(1 for r in self.recent_provider_results if not r)
        return fails / len(self.recent_provider_results)

    def approve(self, requested, agents_available, calls_in_flight):
        hard_cap = max(0, agents_available - calls_in_flight)
        allowed = min(requested, hard_cap)

        if self.provider_failure_rate() > self.failure_rate_throttle:
            allowed = min(allowed, 1)

        return allowed
