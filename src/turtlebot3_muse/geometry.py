"""Small geometry helpers."""

from __future__ import annotations

import math


def quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
    """Yaw (rotation about Z) in radians, in [-pi, pi]."""
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def stamp_to_seconds(sec: int, nanosec: int) -> float | None:
    """Convert a ROS stamp to seconds; an all-zero stamp means "unset"."""
    if sec == 0 and nanosec == 0:
        return None
    return sec + nanosec * 1e-9
