"""Convert ROS 2 messages to ROS-independent models.

Functions are duck-typed on message attributes so they can be tested without ROS.
"""

from __future__ import annotations

import math
from typing import Any

from .geometry import quaternion_to_yaw, stamp_to_seconds
from .lidar import valid_ranges
from .models import BatterySample, OccupancyGridData, OdomSample, Pose2D, ScanSample


def header_stamp_s(header: Any) -> float | None:
    return stamp_to_seconds(header.stamp.sec, header.stamp.nanosec)


def odom_from_msg(msg: Any, received_monotonic_s: float) -> OdomSample:
    pose = msg.pose.pose
    q = pose.orientation
    twist = msg.twist.twist
    return OdomSample(
        frame_id=msg.header.frame_id,
        child_frame_id=msg.child_frame_id,
        x_m=pose.position.x,
        y_m=pose.position.y,
        yaw_rad=quaternion_to_yaw(q.x, q.y, q.z, q.w),
        linear_x_mps=twist.linear.x,
        angular_z_radps=twist.angular.z,
        stamp_s=header_stamp_s(msg.header),
        received_monotonic_s=received_monotonic_s,
    )


def scan_from_msg(msg: Any, received_monotonic_s: float) -> ScanSample:
    ranges = list(msg.ranges)
    valid = valid_ranges(ranges, msg.range_min, msg.range_max)
    return ScanSample(
        frame_id=msg.header.frame_id,
        min_distance_m=min(valid) if valid else None,
        valid_count=len(valid),
        total_count=len(ranges),
        stamp_s=header_stamp_s(msg.header),
        received_monotonic_s=received_monotonic_s,
    )


def _finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None


def battery_from_msg(msg: Any, received_monotonic_s: float) -> BatterySample:
    return BatterySample(
        voltage_v=_finite_or_none(msg.voltage),
        percentage=_finite_or_none(msg.percentage),
        stamp_s=header_stamp_s(msg.header),
        received_monotonic_s=received_monotonic_s,
    )


def pose_from_ros_pose(pose: Any) -> Pose2D:
    q = pose.orientation
    return Pose2D(pose.position.x, pose.position.y, quaternion_to_yaw(q.x, q.y, q.z, q.w))


def _grid_bytes(data: Any) -> bytes:
    if hasattr(data, "tobytes"):
        return data.tobytes()
    return bytes(v & 0xFF for v in data)


def grid_from_msg(msg: Any) -> OccupancyGridData:
    info = msg.info
    return OccupancyGridData(
        frame_id=msg.header.frame_id,
        width=info.width,
        height=info.height,
        resolution_m=info.resolution,
        origin=pose_from_ros_pose(info.origin),
        data=_grid_bytes(msg.data),
    )


def pose_from_transform(transform_stamped: Any) -> Pose2D:
    t = transform_stamped.transform
    q = t.rotation
    return Pose2D(t.translation.x, t.translation.y, quaternion_to_yaw(q.x, q.y, q.z, q.w))
