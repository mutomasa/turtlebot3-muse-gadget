"""Render an OccupancyGrid to a PNG, optionally with a robot marker.

The image is drawn in grid coordinates: +x of the grid points right, +y up
(row 0 of the grid, at the origin, is the bottom row of the image).
Pillow is imported lazily so the status command does not depend on it.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Any

from .models import OccupancyGridData, Pose2D

UNKNOWN_GRAY = 205
FREE_GRAY = 254
OCCUPIED_GRAY = 0
FREE_THRESHOLD = 25
OCCUPIED_THRESHOLD = 65
MAX_UPSCALE = 8
ROBOT_RADIUS_M = 0.105  # TurtleBot3 Burger footprint radius
MIN_MARKER_RADIUS_PX = 4
MARKER_RGB = (220, 30, 30)
SHRINK_STEP = 0.75
MAX_SHRINK_ATTEMPTS = 8


class ImageTooLargeError(RuntimeError):
    """PNG could not be brought under the size limit."""


def occupancy_to_gray(value: int) -> int:
    """Gray level for a signed occupancy value (-1 unknown, 0..100 probability)."""
    if value < 0 or value > 100:
        return UNKNOWN_GRAY
    if value >= OCCUPIED_THRESHOLD:
        return OCCUPIED_GRAY
    if value <= FREE_THRESHOLD:
        return FREE_GRAY
    return round(FREE_GRAY * (1.0 - value / 100.0))


_GRAY_TABLE = bytes(occupancy_to_gray(b - 256 if b > 127 else b) for b in range(256))


def validate_grid(grid: OccupancyGridData) -> None:
    if grid.width <= 0 or grid.height <= 0:
        raise ValueError(f"empty map: {grid.width}x{grid.height}")
    if len(grid.data) != grid.width * grid.height:
        raise ValueError(f"map data length {len(grid.data)} != {grid.width}x{grid.height}")
    if not grid.resolution_m > 0:
        raise ValueError(f"invalid resolution: {grid.resolution_m}")


def grid_to_image(grid: OccupancyGridData) -> Any:
    from PIL import Image

    validate_grid(grid)
    gray = grid.data.translate(_GRAY_TABLE)
    return Image.frombytes("L", (grid.width, grid.height), gray).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def world_to_pixel(grid: OccupancyGridData, x_m: float, y_m: float) -> tuple[float, float]:
    """Map-frame point to continuous pixel coordinates of the unscaled image."""
    dx, dy = x_m - grid.origin.x_m, y_m - grid.origin.y_m
    c, s = math.cos(-grid.origin.yaw_rad), math.sin(-grid.origin.yaw_rad)
    col = (c * dx - s * dy) / grid.resolution_m
    row = (s * dx + c * dy) / grid.resolution_m
    return col, grid.height - row


def scale_factor(width: int, height: int, max_side_px: int) -> float:
    longest = max(width, height)
    if longest <= max_side_px:
        return float(max(1, min(MAX_UPSCALE, max_side_px // longest)))
    return max_side_px / longest


def resize(image: Any, factor: float) -> Any:
    from PIL import Image

    if factor == 1.0:
        return image
    size = (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
    method = Image.Resampling.NEAREST if factor > 1 else Image.Resampling.BOX
    return image.resize(size, method)


def pose_in_image(grid: OccupancyGridData, pose: Pose2D, factor: float) -> tuple[float, float, float]:
    """Pixel position (scaled) and heading angle in image coordinates."""
    px, py = world_to_pixel(grid, pose.x_m, pose.y_m)
    return px * factor, py * factor, pose.yaw_rad - grid.origin.yaw_rad


def is_inside(image: Any, x: float, y: float) -> bool:
    return 0 <= x <= image.width and 0 <= y <= image.height


def draw_robot(image: Any, x: float, y: float, heading: float, radius: float) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=MARKER_RGB, width=2)
    tip = (x + 2 * radius * math.cos(heading), y - 2 * radius * math.sin(heading))
    draw.line((x, y, *tip), fill=MARKER_RGB, width=3)


@dataclass(frozen=True)
class RenderedMap:
    image: Any
    marker_drawn: bool
    robot_inside_map: bool | None


def render_map(grid: OccupancyGridData, pose: Pose2D | None, max_side_px: int) -> RenderedMap:
    factor = scale_factor(grid.width, grid.height, max_side_px)
    image = resize(grid_to_image(grid), factor).convert("RGB")
    if pose is None:
        return RenderedMap(image, marker_drawn=False, robot_inside_map=None)
    x, y, heading = pose_in_image(grid, pose, factor)
    radius = max(MIN_MARKER_RADIUS_PX, ROBOT_RADIUS_M / grid.resolution_m * factor)
    draw_robot(image, x, y, heading, radius)
    return RenderedMap(image, marker_drawn=True, robot_inside_map=is_inside(image, x, y))


def _png_bytes(image: Any) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def encode_png_within(image: Any, max_bytes: int) -> tuple[bytes, Any]:
    """Encode as PNG, shrinking until it fits ``max_bytes``. Returns (png, final_image)."""
    for _ in range(MAX_SHRINK_ATTEMPTS):
        data = _png_bytes(image)
        if len(data) <= max_bytes:
            return data, image
        image = resize(image, SHRINK_STEP)
    raise ImageTooLargeError(f"PNG still exceeds {max_bytes} bytes after shrinking")
