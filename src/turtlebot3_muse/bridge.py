"""Long-running read-only bridge: keeps subscribing to status topics and
answers ``status`` / ``metrics`` / ``ping`` over a Unix domain socket.

It is independent of the Muse connection, so it keeps monitoring ROS 2 even
while Muse is disconnected. It never publishes to ROS 2.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .cli_common import log
from .config import AppConfig, load_config
from .ipc import create_server
from .ros_adapter import status_collection
from .status_service import build_status
from .topic_monitor import TopicMonitor

BRIDGE_SOURCE = "ros2_bridge"


class BridgeApp:
    """IPC request handler. ROS-independent so it can be unit tested."""

    def __init__(
        self,
        cfg: AppConfig,
        monitor: TopicMonitor,
        *,
        mono_clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._cfg = cfg
        self._monitor = monitor
        self._mono = mono_clock
        self._wall = wall_clock
        self._lock = threading.Lock()
        self._requests: Counter[str] = Counter()
        self._handlers: dict[str, Callable[[], dict[str, Any]]] = {
            "status": self.status,
            "metrics": self.metrics,
            "ping": lambda: {"pong": True},
        }

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        op = request.get("op")
        self._count(str(op))
        handler = self._handlers.get(op) if isinstance(op, str) else None
        if handler is None:
            raise ValueError(f"unknown op: {op!r}")
        return handler()

    def _count(self, op: str) -> None:
        with self._lock:
            self._requests[op] += 1

    def status(self) -> dict[str, Any]:
        return build_status(
            status_collection(self._monitor),
            robot=self._cfg.robot_name,
            source=BRIDGE_SOURCE,
            now_monotonic_s=self._mono(),
            now_wall_s=self._wall(),
            cfg=self._cfg.status,
        )

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            requests = dict(self._requests)
        return {**self._monitor.metrics(), "requests": requests}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--socket", type=Path, default=None, help="override bridge.socket_path")
    return parser.parse_args(argv)


def run_bridge(cfg: AppConfig, socket_path: Path) -> None:
    import rclpy
    from rclpy.executors import ExternalShutdownException

    from .ros_adapter import subscribe_status_topics

    monitor = TopicMonitor()
    rclpy.init()
    node = rclpy.create_node("turtlebot3_muse_bridge")
    server = None
    try:
        subscribe_status_topics(node, cfg.topics, monitor)
        server = create_server(socket_path, BridgeApp(cfg, monitor))
        threading.Thread(target=server.serve_forever, name="ipc", daemon=True).start()
        log(f"bridge listening on {socket_path}")
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
            socket_path.unlink(missing_ok=True)
        node.destroy_node()
        rclpy.try_shutdown()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    run_bridge(cfg, args.socket or Path(cfg.bridge.socket_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
