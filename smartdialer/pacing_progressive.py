class ProgressivePacingEngine:
    """
    Never suggests more calls than agents that are already confirmed free
    right now. Never bets on the future. This is what makes Progressive
    dialing inherently safe even without the Safety Controller - the
    Safety Controller here mainly acts as a backstop against
    provider-outage conditions, not against Progressive's own math.
    """

    name = "progressive"

    def suggest(self, agents_available, calls_in_flight, **kwargs):
        return max(0, agents_available - calls_in_flight)
