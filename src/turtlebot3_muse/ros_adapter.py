"""rclpy one-shot collectors. rclpy is imported lazily so the rest of the
package (and the unit tests) work without a ROS 2 environment.

This module only subscribes; it never publishes (in particular never /cmd_vel).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from .config import AppConfig, MapConfig, TopicConfig
from .models import MapCollection, Pose2D, StatusCollection
from .msg_convert import (
    battery_from_msg,
    grid_from_msg,
    header_stamp_s,
    odom_from_msg,
    pose_from_transform,
    scan_from_msg,
)

from .topic_monitor import TopicMonitor

SPIN_STEP_S = 0.1
STATUS_KEYS = ("odom", "scan", "battery")


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


def subscribe_status_topics(node: Any, topics: TopicConfig, monitor: TopicMonitor) -> None:
    """Subscribe /odom, /scan and /battery_state into ``monitor`` (shared by one-shot and bridge)."""
    from nav_msgs.msg import Odometry
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import BatteryState, LaserScan

    # Best Effort subscribers are compatible with both Reliable and Best Effort publishers.
    monitor.watch(*STATUS_KEYS)
    for msg_type, topic, key, convert in (
        (Odometry, topics.odom, "odom", odom_from_msg),
        (LaserScan, topics.scan, "scan", scan_from_msg),
        (BatteryState, topics.battery, "battery", battery_from_msg),
    ):
        node.create_subscription(msg_type, topic, monitor.callback(key, convert), qos_profile_sensor_data)


def status_collection(monitor: TopicMonitor, timed_out: bool = False) -> StatusCollection:
    return StatusCollection(
        odom=monitor.get("odom"), scan=monitor.get("scan"), battery=monitor.get("battery"), timed_out=timed_out
    )


def collect_status(cfg: AppConfig) -> StatusCollection:
    monitor = TopicMonitor()
    with ros_node("turtlebot3_muse_status") as node:
        subscribe_status_topics(node, cfg.topics, monitor)
        spin_until(node, lambda: monitor.has(*STATUS_KEYS), cfg.status.wait_timeout_s)
    return status_collection(monitor, timed_out=not monitor.has("odom", "scan"))


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

    store = TopicMonitor()
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
