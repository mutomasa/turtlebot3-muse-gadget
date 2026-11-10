import pytest

from turtlebot3_muse.topic_monitor import TopicMonitor


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def test_keeps_latest_message_with_receive_time():
    clock = FakeClock(1.0)
    monitor = TopicMonitor(clock=clock)
    cb = monitor.callback("odom", lambda msg, t: (msg, t))
    cb("a")
    clock.t = 2.0
    cb("b")
    assert monitor.get("odom") == ("b", 2.0)
    assert monitor.has("odom") and not monitor.has("odom", "scan")


def test_metrics_count_age_and_rate():
    clock = FakeClock(0.0)
    monitor = TopicMonitor(clock=clock)
    monitor.watch("odom", "scan")
    cb = monitor.callback("odom", lambda msg, t: msg)
    for t in (10.0, 10.1, 10.2, 10.3):
        clock.t = t
        cb("m")
    clock.t = 11.3
    metrics = monitor.metrics()
    assert metrics["uptime_s"] == 11.3
    odom = metrics["topics"]["odom"]
    assert odom["count"] == 4
    assert odom["age_s"] == pytest.approx(1.0)
    assert odom["rate_hz"] == pytest.approx(10.0, rel=0.01)
    assert metrics["topics"]["scan"] == {"count": 0, "age_s": None, "rate_hz": None}
