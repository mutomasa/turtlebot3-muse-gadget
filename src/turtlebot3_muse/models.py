"""ROS-independent data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OdomSample:
    frame_id: str
    child_frame_id: str
    x_m: float
    y_m: float
    yaw_rad: float
    linear_x_mps: float
    angular_z_radps: float
    stamp_s: float | None
    received_monotonic_s: float


@dataclass(frozen=True)
class ScanSample:
    frame_id: str
    min_distance_m: float | None
    valid_count: int
    total_count: int
    stamp_s: float | None
    received_monotonic_s: float


@dataclass(frozen=True)
class BatterySample:
    voltage_v: float | None
    percentage: float | None
    stamp_s: float | None
    received_monotonic_s: float


@dataclass(frozen=True)
class StatusCollection:
    """Result of one status collection attempt."""

    odom: OdomSample | None
    scan: ScanSample | None
    battery: BatterySample | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class Pose2D:
    x_m: float
    y_m: float
    yaw_rad: float


@dataclass(frozen=True)
class OccupancyGridData:
    """OccupancyGrid with ``data`` as raw int8 bytes (row-major, row 0 at origin)."""

    frame_id: str
    width: int
    height: int
    resolution_m: float
    origin: Pose2D
    data: bytes


@dataclass(frozen=True)
class MapCollection:
    grid: OccupancyGridData | None
    robot_pose: Pose2D | None = None
    pose_stamp_s: float | None = None
    timed_out: bool = False
