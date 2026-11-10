import math

import pytest

from turtlebot3_muse.geometry import quaternion_to_yaw, stamp_to_seconds
from turtlebot3_muse.lidar import min_valid_range, valid_ranges


@pytest.mark.parametrize("deg", [0.0, 45.0, 90.0, -90.0, 179.0, -135.0])
def test_quaternion_to_yaw_roundtrip(deg):
    half = math.radians(deg) / 2
    assert math.degrees(quaternion_to_yaw(0.0, 0.0, math.sin(half), math.cos(half))) == pytest.approx(deg)


def test_stamp_zero_means_unset():
    assert stamp_to_seconds(0, 0) is None
    assert stamp_to_seconds(10, 500_000_000) == pytest.approx(10.5)


def test_valid_ranges_drops_nan_inf_and_out_of_range():
    ranges = [0.0, 0.05, 0.82, math.inf, math.nan, 3.6, 3.5, 0.12]
    assert valid_ranges(ranges, 0.12, 3.5) == [0.82, 3.5, 0.12]


def test_min_valid_range_none_when_all_invalid():
    assert min_valid_range([math.nan, math.inf, 0.0], 0.12, 3.5) is None
    assert min_valid_range([], 0.12, 3.5) is None
