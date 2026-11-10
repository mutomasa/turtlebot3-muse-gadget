"""Deterministic mock data for development and CI. Output is always labelled ``source: mock``."""

from __future__ import annotations

import math
import time

from .config import AppConfig
from .models import BatterySample, MapCollection, OccupancyGridData, OdomSample, Pose2D, ScanSample, StatusCollection

MOCK_SOURCE = "mock"


def mock_status(_cfg: AppConfig) -> StatusCollection:
    now = time.monotonic()
    return StatusCollection(
        odom=OdomSample("odom", "base_footprint", 1.23, 0.45, math.radians(90.0), 0.0, 0.0, None, now),
        scan=ScanSample("base_scan", 0.82, 380, 400, None, now),
        battery=BatterySample(11.9, None, None, now),
    )


def mock_grid(width: int = 60, height: int = 40) -> OccupancyGridData:
    cells = bytearray(width * height)  # 0 = free
    for row in range(height):
        for col in range(width):
            if row in (0, height - 1) or col in (0, width - 1):
                cells[row * width + col] = 100
            elif 25 <= col <= 30 and 10 <= row <= 15:
                cells[row * width + col] = 100
            elif col >= 45 and row >= 25:
                cells[row * width + col] = 0xFF  # -1 unknown
    return OccupancyGridData("map", width, height, 0.05, Pose2D(-1.5, -1.0, 0.0), bytes(cells))


def mock_map(_cfg: AppConfig) -> MapCollection:
    return MapCollection(grid=mock_grid(), robot_pose=Pose2D(0.2, 0.1, math.radians(30.0)), pose_stamp_s=None)
