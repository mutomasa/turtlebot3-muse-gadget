import io
import threading

import pytest

from turtlebot3_muse import status_cli
from turtlebot3_muse.bridge import BRIDGE_SOURCE, BridgeApp
from turtlebot3_muse.config import AppConfig, BridgeConfig
from turtlebot3_muse.ipc import create_server
from turtlebot3_muse.models import OdomSample, ScanSample, StatusCollection
from turtlebot3_muse.topic_monitor import TopicMonitor

NOW = 100.0


def make_app(odom_at=None, scan_at=None, cfg=None):
    monitor = TopicMonitor(clock=lambda: NOW)
    if odom_at is not None:
        monitor.record("odom", OdomSample("odom", "base_footprint", 1.0, 2.0, 0.0, 0.0, 0.0, None, odom_at), odom_at)
    if scan_at is not None:
        monitor.record("scan", ScanSample("base_scan", 0.5, 10, 400, None, scan_at), scan_at)
    return BridgeApp(cfg or AppConfig(), monitor, mono_clock=lambda: NOW, wall_clock=lambda: 1_762_732_800.0)


def test_status_online_from_cache():
    result = make_app(odom_at=99.9, scan_at=99.9)({"op": "status"})
    assert result["source"] == BRIDGE_SOURCE
    assert result["state"] == "online"
    assert "timeout" not in result["warnings"]


def test_status_offline_when_cache_is_stale():
    result = make_app(odom_at=10.0, scan_at=10.0)({"op": "status"})
    assert result["state"] == "offline"
    assert "stale_odom" in result["warnings"]


def test_status_offline_when_nothing_received():
    result = make_app()({"op": "status"})
    assert result["state"] == "offline"
    assert {"no_odom", "no_scan"} <= set(result["warnings"])


def test_metrics_counts_requests():
    app = make_app(odom_at=99.0)
    app({"op": "status"})
    app({"op": "ping"})
    metrics = app({"op": "metrics"})
    assert metrics["requests"] == {"status": 1, "ping": 1, "metrics": 1}
    assert metrics["topics"]["odom"]["count"] == 1


@pytest.mark.parametrize("request_", [{}, {"op": "move"}, {"op": 1}])
def test_unknown_op_raises(request_):
    with pytest.raises(ValueError):
        make_app()(request_)


@pytest.fixture
def running_bridge():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="tbm-") as d:
        path = Path(d) / "bridge.sock"
        cfg = AppConfig(bridge=BridgeConfig(socket_path=str(path), request_timeout_s=1.0))
        server = create_server(path, make_app(odom_at=99.9, scan_at=99.9, cfg=cfg))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield cfg
        server.shutdown()
        server.server_close()


def test_status_cli_prefers_bridge(running_bridge):
    result = status_cli.bridge_status(running_bridge)
    assert result["source"] == BRIDGE_SOURCE and result["state"] == "online"


def test_status_cli_bridge_missing_returns_none(tmp_path):
    cfg = AppConfig(bridge=BridgeConfig(socket_path=str(tmp_path / "none.sock")))
    assert status_cli.bridge_status(cfg) is None


def test_status_cli_falls_back_when_bridge_errors(monkeypatch, tmp_path):
    sock = tmp_path / "b.sock"
    sock.touch()
    monkeypatch.setattr(status_cli, "request", lambda *a, **k: {"ok": False, "error": "boom"})
    cfg = AppConfig(bridge=BridgeConfig(socket_path=str(sock)))
    assert status_cli.bridge_status(cfg) is None


def test_execute_uses_bridge_then_one_shot(monkeypatch):
    calls = []
    monkeypatch.setattr(status_cli, "bridge_status", lambda cfg: None)
    monkeypatch.setattr(status_cli, "select_collector",
                        lambda mock: (lambda cfg: calls.append("live") or StatusCollection(None, None), "ros2_live"))
    result = status_cli.execute(status_cli.parse_args([]), io.StringIO(""))
    assert calls == ["live"] and result["source"] == "ros2_live"


def test_execute_returns_bridge_result(monkeypatch):
    monkeypatch.setattr(status_cli, "bridge_status", lambda cfg: {"state": "online", "source": BRIDGE_SOURCE})
    monkeypatch.setattr(status_cli, "select_collector", lambda mock: pytest.fail("should not subscribe"))
    assert status_cli.execute(status_cli.parse_args([]), io.StringIO(""))["source"] == BRIDGE_SOURCE
