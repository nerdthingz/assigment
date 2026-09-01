import threading
import time
import random

from .util import now_iso


class ProviderInterface:
    name = "base"

    def place_call(self, call_id, on_event, run_guard):
        raise NotImplementedError

    def set_outage(self, active):
        raise NotImplementedError


class ProviderA(ProviderInterface):
    """Fast, reliable, low failure rate, clean sequential events."""

    name = "ProviderA"

    def __init__(self, answer_rate=0.5, talk_time=2.0, setup_time=0.15, pre_fail_rate=0.02):
        self.answer_rate = answer_rate
        self.talk_time = talk_time
        self.setup_time = setup_time
        self.pre_fail_rate = pre_fail_rate
        self.outage = False

    def set_outage(self, active):
        self.outage = active

    def place_call(self, call_id, on_event, run_guard):
        def emit(event_type, ts):
            if run_guard.is_set():
                return
            on_event(call_id, event_type, ts)

        def run():
            time.sleep(random.uniform(self.setup_time * 0.5, self.setup_time))
            if run_guard.is_set():
                return
            if self.outage:
                time.sleep(random.uniform(1.0, 2.0))
                emit("FAILED", now_iso())
                return
            if random.random() < self.pre_fail_rate:
                emit("FAILED", now_iso())
                return
            emit("RINGING", now_iso())
            time.sleep(random.uniform(0.1, 0.4))
            if run_guard.is_set():
                return
            if random.random() < self.answer_rate:
                emit("ANSWERED", now_iso())
                time.sleep(random.uniform(0.05, 0.1))
                emit("CONNECTED", now_iso())
                time.sleep(min(self.talk_time, 3.0) * random.uniform(0.15, 0.3))
                emit("COMPLETED", now_iso())
            else:
                emit("FAILED", now_iso())

        threading.Thread(target=run, daemon=True).start()


class ProviderB(ProviderInterface):
    """Slower, occasional timeouts, duplicate events, out-of-order events."""

    name = "ProviderB"

    def __init__(self, answer_rate=0.5, talk_time=2.0, setup_time=0.5, pre_fail_rate=0.15):
        self.answer_rate = answer_rate
        self.talk_time = talk_time
        self.setup_time = setup_time
        self.pre_fail_rate = pre_fail_rate
        self.outage = False

    def set_outage(self, active):
        self.outage = active

    def place_call(self, call_id, on_event, run_guard):
        def emit(event_type, ts):
            if run_guard.is_set():
                return
            on_event(call_id, event_type, ts)

        def run():
            time.sleep(random.uniform(self.setup_time * 0.5, self.setup_time))
            if run_guard.is_set():
                return
            if self.outage:
                time.sleep(random.uniform(2.0, 4.0))
                emit("FAILED", now_iso())
                return
            if random.random() < self.pre_fail_rate:
                emit("FAILED", now_iso())
                return
            emit("RINGING", now_iso())
            if random.random() < 0.3:
                emit("RINGING", now_iso())  # duplicate event
            time.sleep(random.uniform(0.3, 0.9))
            if run_guard.is_set():
                return
            if random.random() < self.answer_rate:
                ts1 = now_iso()
                if random.random() < 0.3:
                    # out-of-order: CONNECTED emitted before ANSWERED
                    time.sleep(random.uniform(0.05, 0.15))
                    emit("CONNECTED", now_iso())
                    emit("ANSWERED", ts1)
                else:
                    emit("ANSWERED", ts1)
                    time.sleep(random.uniform(0.05, 0.15))
                    emit("CONNECTED", now_iso())
                time.sleep(min(self.talk_time, 3.0) * random.uniform(0.15, 0.3))
                emit("COMPLETED", now_iso())
                if random.random() < 0.2:
                    emit("COMPLETED", now_iso())  # duplicate event
            else:
                emit("FAILED", now_iso())

        threading.Thread(target=run, daemon=True).start()


def build_providers(answer_rate=0.5, talk_time=2.0):
    return [
        ProviderA(answer_rate=answer_rate, talk_time=talk_time),
        ProviderB(answer_rate=answer_rate, talk_time=talk_time),
    ]
