import math

import pytest
from PIL import Image

from turtlebot3_muse.map_renderer import (
    FREE_GRAY,
    OCCUPIED_GRAY,
    UNKNOWN_GRAY,
    ImageTooLargeError,
    encode_png_within,
    grid_to_image,
    occupancy_to_gray,
    render_map,
    scale_factor,
    world_to_pixel,
)
from turtlebot3_muse.mock_source import mock_grid
from turtlebot3_muse.models import OccupancyGridData, Pose2D


def grid(width=4, height=3, data=None, origin=Pose2D(0.0, 0.0, 0.0), res=1.0):
    data = data if data is not None else bytes(width * height)
    return OccupancyGridData("map", width, height, res, origin, data)


@pytest.mark.parametrize("value, gray", [(-1, UNKNOWN_GRAY), (0, FREE_GRAY), (25, FREE_GRAY),
                                         (65, OCCUPIED_GRAY), (100, OCCUPIED_GRAY), (101, UNKNOWN_GRAY)])
def test_occupancy_to_gray(value, gray):
    assert occupancy_to_gray(value) == gray


def test_intermediate_probability_is_gray():
    assert OCCUPIED_GRAY < occupancy_to_gray(50) < FREE_GRAY


def test_grid_row_zero_is_bottom_of_image():
    data = bytes([100, 0, 0, 0,  0, 0, 0, 0,  0xFF, 0, 0, 0])  # row0: occupied at col0, row2: unknown at col0
    image = grid_to_image(grid(data=data))
    assert image.getpixel((0, 2)) == OCCUPIED_GRAY
    assert image.getpixel((0, 0)) == UNKNOWN_GRAY


def test_grid_size_mismatch_raises():
    with pytest.raises(ValueError):
        grid_to_image(grid(data=bytes(5)))


def test_world_to_pixel_with_offset_origin():
    g = grid(origin=Pose2D(-2.0, -1.0, 0.0), res=0.5)
    assert world_to_pixel(g, -2.0, -1.0) == pytest.approx((0.0, 3.0))
    assert world_to_pixel(g, -1.0, -0.5) == pytest.approx((2.0, 2.0))


def test_world_to_pixel_with_rotated_origin():
    g = grid(origin=Pose2D(0.0, 0.0, math.pi / 2))
    # map +y lies along the grid's +x axis when the origin is rotated by 90 deg
    assert world_to_pixel(g, 0.0, 2.0) == pytest.approx((2.0, 3.0))


@pytest.mark.parametrize("w, h, max_side, expected", [(60, 40, 1024, 8.0), (300, 200, 1024, 3.0),
                                                      (2048, 1000, 1024, 0.5)])
def test_scale_factor(w, h, max_side, expected):
    assert scale_factor(w, h, max_side) == expected


def test_render_without_pose_has_no_marker():
    rendered = render_map(mock_grid(), None, 512)
    assert not rendered.marker_drawn and rendered.robot_inside_map is None
    assert rendered.image.mode == "RGB"


def test_render_with_pose_draws_red_marker():
    g = mock_grid()
    rendered = render_map(g, Pose2D(0.0, 0.0, 0.0), 480)
    assert rendered.marker_drawn and rendered.robot_inside_map
    colors = rendered.image.getcolors(maxcolors=1 << 16)
    assert any(r > 200 and gr < 60 and b < 60 for _count, (r, gr, b) in colors)


def test_render_pose_outside_map():
    assert render_map(mock_grid(), Pose2D(100.0, 100.0, 0.0), 480).robot_inside_map is False


def test_encode_png_within_limit_shrinks():
    noisy = Image.effect_noise((800, 800), 100).convert("RGB")
    data, final = encode_png_within(noisy, 200_000)
    assert len(data) <= 200_000
    assert final.width < 800


def test_encode_png_raises_when_impossible():
    with pytest.raises(ImageTooLargeError):
        encode_png_within(Image.new("RGB", (64, 64)), 10)
