import array
from types import SimpleNamespace as NS

import pytest

from turtlebot3_muse.msg_convert import grid_from_msg, odom_from_msg, pose_from_transform, scan_from_msg


def test_odom_from_msg(odom_msg):
    sample = odom_from_msg(odom_msg, 42.0)
    assert sample.frame_id == "odom"
    assert sample.child_frame_id == "base_footprint"
    assert (sample.x_m, sample.y_m) == (1.23, 0.45)
    assert sample.yaw_rad == pytest.approx(1.5707963, rel=1e-6)
    assert sample.linear_x_mps == 0.1 and sample.angular_z_radps == -0.2
    assert sample.stamp_s == pytest.approx(1762732800.5)
    assert sample.received_monotonic_s == 42.0


def test_scan_from_msg_counts_only_valid(scan_msg):
    sample = scan_from_msg(scan_msg, 1.0)
    assert sample.frame_id == "base_scan"
    assert sample.min_distance_m == 0.82
    assert (sample.valid_count, sample.total_count) == (3, 8)


def _quat_identity():
    return NS(x=0.0, y=0.0, z=0.0, w=1.0)


def test_grid_from_msg_accepts_int8_array():
    msg = NS(
        header=NS(frame_id="map"),
        info=NS(width=2, height=1, resolution=0.05,
                origin=NS(position=NS(x=-1.0, y=2.0, z=0.0), orientation=_quat_identity())),
        data=array.array("b", [-1, 100]),
    )
    grid = grid_from_msg(msg)
    assert grid.data == bytes([0xFF, 100])
    assert (grid.origin.x_m, grid.origin.y_m) == (-1.0, 2.0)


def test_grid_from_msg_accepts_list():
    msg = NS(header=NS(frame_id="map"),
             info=NS(width=2, height=1, resolution=0.1,
                     origin=NS(position=NS(x=0.0, y=0.0, z=0.0), orientation=_quat_identity())),
             data=[0, -1])
    assert grid_from_msg(msg).data == bytes([0, 0xFF])


def test_pose_from_transform():
    tf = NS(transform=NS(translation=NS(x=1.0, y=2.0, z=0.0), rotation=_quat_identity()))
    pose = pose_from_transform(tf)
    assert (pose.x_m, pose.y_m, pose.yaw_rad) == (1.0, 2.0, 0.0)
