"""rclpy one-shot collectors. rclpy is imported lazily so the rest of the
package (and the unit tests) work without a ROS 2 environment.

This module only subscribes; it never publishes (in particular never /cmd_vel).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from .config import AppConfig, MapConfig
from .models import MapCollection, Pose2D, StatusCollection
from .msg_convert import (
    battery_from_msg,
    grid_from_msg,
    header_stamp_s,
    odom_from_msg,
    pose_from_transform,
    scan_from_msg,
)

SPIN_STEP_S = 0.1


class LatestMessageStore:
    """Keeps the latest converted message per key, so freshness reflects the last receipt."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._items: dict[str, Any] = {}
        self._clock = clock

    def callback(self, key: str, convert: Callable[[Any, float], Any]) -> Callable[[Any], None]:
        def _on_message(msg: Any) -> None:
            self._items[key] = convert(msg, self._clock())

        return _on_message

    def has(self, *keys: str) -> bool:
        return all(k in self._items for k in keys)

    def get(self, key: str) -> Any:
        return self._items.get(key)


@contextmanager
def ros_node(name: str) -> Iterator[Any]:
    import rclpy

    rclpy.init()
    node = rclpy.create_node(name)
    try:
        yield node
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


def spin_until(node: Any, done: Callable[[], bool], timeout_s: float) -> bool:
    """Spin ``node`` until ``done()`` or timeout. Returns whether ``done()`` became true."""
    import rclpy

    deadline = time.monotonic() + timeout_s
    while not done():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        rclpy.spin_once(node, timeout_sec=min(SPIN_STEP_S, remaining))
    return True


def collect_status(cfg: AppConfig) -> StatusCollection:
    from nav_msgs.msg import Odometry
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import BatteryState, LaserScan

    # Best Effort subscribers are compatible with both Reliable and Best Effort publishers.
    store = LatestMessageStore()
    with ros_node("turtlebot3_muse_status") as node:
        node.create_subscription(Odometry, cfg.topics.odom, store.callback("odom", odom_from_msg), qos_profile_sensor_data)
        node.create_subscription(LaserScan, cfg.topics.scan, store.callback("scan", scan_from_msg), qos_profile_sensor_data)
        node.create_subscription(
            BatteryState, cfg.topics.battery, store.callback("battery", battery_from_msg), qos_profile_sensor_data
        )
        spin_until(node, lambda: store.has("odom", "scan", "battery"), cfg.status.wait_timeout_s)
    return StatusCollection(
        odom=store.get("odom"),
        scan=store.get("scan"),
        battery=store.get("battery"),
        timed_out=not store.has("odom", "scan"),
    )


def map_qos(transient_local: bool) -> Any:
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

    durability = DurabilityPolicy.TRANSIENT_LOCAL if transient_local else DurabilityPolicy.VOLATILE
    return QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=durability)


def _wait_for_pose(node: Any, buffer: Any, mcfg: MapConfig) -> tuple[Pose2D | None, float | None]:
    from rclpy.time import Time

    def available() -> bool:
        return buffer.can_transform(mcfg.map_frame, mcfg.base_frame, Time())

    if not spin_until(node, available, mcfg.tf_timeout_s):
        return None, None
    transform = buffer.lookup_transform(mcfg.map_frame, mcfg.base_frame, Time())
    return pose_from_transform(transform), header_stamp_s(transform.header)


def collect_map(cfg: AppConfig) -> MapCollection:
    from nav_msgs.msg import OccupancyGrid
    from tf2_ros import Buffer, TransformListener

    store = LatestMessageStore()
    with ros_node("turtlebot3_muse_map") as node:
        buffer = Buffer()
        _listener = TransformListener(buffer, node)  # keep a reference while spinning
        node.create_subscription(
            OccupancyGrid, cfg.topics.map, store.callback("map", lambda m, _t: grid_from_msg(m)),
            map_qos(cfg.map.transient_local),
        )
        got_map = spin_until(node, lambda: store.has("map"), cfg.map.wait_timeout_s)
        pose, stamp = _wait_for_pose(node, buffer, cfg.map) if got_map else (None, None)
    return MapCollection(grid=store.get("map"), robot_pose=pose, pose_stamp_s=stamp, timed_out=not got_map)
