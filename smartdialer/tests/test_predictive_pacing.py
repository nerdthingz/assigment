from smartdialer.pacing_predictive import PredictivePacingEngine


def test_predictive_suggests_more_than_progressive_when_answer_rate_low():
    engine = PredictivePacingEngine()
    for _ in range(20):
        engine.record_outcome(False)  # low answer rate history

    suggested = engine.suggest(agents_available=10, calls_in_flight=0, agents_about_to_free=0)
    # with a very low answer rate, predictive should suggest starting many more
    # calls than the number of agents available, betting most will not answer
    assert suggested > 10, f"expected predictive to over-suggest under low answer rate, got {suggested}"
    print(f"test_predictive_suggests_more_than_progressive_when_answer_rate_low PASSED — suggested {suggested}")


def test_predictive_suggests_fewer_when_answer_rate_high():
    engine = PredictivePacingEngine()
    for _ in range(20):
        engine.record_outcome(True)  # high answer rate history

    suggested = engine.suggest(agents_available=10, calls_in_flight=0, agents_about_to_free=0)
    assert suggested <= 12, f"expected conservative suggestion under high answer rate, got {suggested}"
    print(f"test_predictive_suggests_fewer_when_answer_rate_high PASSED — suggested {suggested}")


def test_predictive_never_negative():
    engine = PredictivePacingEngine()
    suggested = engine.suggest(agents_available=0, calls_in_flight=50, agents_about_to_free=0)
    assert suggested >= 0
    print("test_predictive_never_negative PASSED")


if __name__ == "__main__":
    test_predictive_suggests_more_than_progressive_when_answer_rate_low()
    test_predictive_suggests_fewer_when_answer_rate_high()
    test_predictive_never_negative()
