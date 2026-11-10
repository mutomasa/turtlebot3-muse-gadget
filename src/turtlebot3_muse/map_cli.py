"""``robot.map`` Muse command: render /map to PNG and post it to Muse chat.

Never fabricates a map: if /map is not received, no image is produced.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from .cli_common import ParamError, log, read_params, write_json
from .config import DEFAULT_ROBOT_NAME, AppConfig, ConfigError, load_config
from .map_renderer import encode_png_within, render_map
from .mock_source import MOCK_SOURCE, mock_map
from .models import MapCollection, OccupancyGridData
from .muse_sender import SendResult, send_image
from .status_service import iso_utc
from .stdout_guard import stdout_to_stderr

LIVE_SOURCE = "ros2_live"
DEFAULT_MESSAGE = "TurtleBot3の2D地図です。"
DEFAULT_OUT = Path(tempfile.gettempdir()) / "turtlebot_map.png"

MapCollector = Callable[[AppConfig], MapCollection]
ImageSender = Callable[[Path, str, AppConfig], SendResult]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output PNG path")
    parser.add_argument("--send", action=argparse.BooleanOptionalAction, default=False, help="post the PNG to Muse chat")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--mock", action="store_true", help="use a mock map (labelled source=mock)")
    return parser.parse_args(argv)


def select_collector(mock: bool) -> tuple[MapCollector, str]:
    if mock:
        return mock_map, MOCK_SOURCE
    from .ros_adapter import collect_map

    return collect_map, LIVE_SOURCE


def default_sender(path: Path, message: str, cfg: AppConfig) -> SendResult:
    return send_image(path, message, binary=cfg.muse.binary, timeout_s=cfg.muse.send_timeout_s)


def write_atomically(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".turtlebot_map_", suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def map_info(grid: OccupancyGridData) -> dict[str, Any]:
    return {
        "frame_id": grid.frame_id,
        "width_cells": grid.width,
        "height_cells": grid.height,
        "resolution_m": grid.resolution_m,
        "origin": {"x_m": grid.origin.x_m, "y_m": grid.origin.y_m, "yaw_rad": grid.origin.yaw_rad},
    }


def pose_warnings(collection: MapCollection, rendered_inside: bool | None, now_wall: float, max_skew_s: float) -> list[str]:
    if collection.robot_pose is None:
        return ["robot_pose_unavailable"]
    warnings = []
    if rendered_inside is False:
        warnings.append("robot_outside_map")
    if collection.pose_stamp_s is not None and now_wall - collection.pose_stamp_s > max_skew_s:
        warnings.append("robot_pose_old")
    return warnings


def build_caption(message: str, source: str, pose_known: bool) -> str:
    caption = message if pose_known else f"{message}（ロボット位置は取得できませんでした）"
    return f"[MOCK] {caption}" if source == MOCK_SOURCE else caption


def base_result(robot: str, source: str, state: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "robot": robot, "source": source, "state": state, "observed_at": iso_utc(time.time()),
        "map": None, "robot_pose": None, "image": None, "sent": False, "warnings": warnings,
    }


def render_and_save(collection: MapCollection, cfg: AppConfig, out: Path) -> tuple[dict[str, Any], list[str]]:
    rendered = render_map(collection.grid, collection.robot_pose, cfg.map.max_side_px)
    png, final = encode_png_within(rendered.image, cfg.map.max_image_bytes)
    write_atomically(out, png)
    image = {"path": str(out), "width_px": final.width, "height_px": final.height, "bytes": len(png)}
    warnings = pose_warnings(collection, rendered.robot_inside_map, time.time(), cfg.status.max_stamp_skew_s)
    return image, warnings


def pose_dict(collection: MapCollection, frame: str) -> dict[str, Any] | None:
    pose = collection.robot_pose
    if pose is None:
        return None
    return {"frame_id": frame, "x_m": round(pose.x_m, 3), "y_m": round(pose.y_m, 3),
            "yaw_deg": round(math.degrees(pose.yaw_rad), 1)}


def produce(args: argparse.Namespace, cfg: AppConfig, collection: MapCollection, source: str,
            sender: ImageSender) -> dict[str, Any]:
    if collection.grid is None:
        warnings = ["no_map"] + (["timeout"] if collection.timed_out else [])
        return base_result(cfg.robot_name, source, "no_map", warnings)
    image, warnings = render_and_save(collection, cfg, args.out)
    result = base_result(cfg.robot_name, source, "ok", warnings)
    result.update(map=map_info(collection.grid), robot_pose=pose_dict(collection, cfg.map.map_frame), image=image)
    if args.send:
        sent = sender(args.out, build_caption(args.message, source, collection.robot_pose is not None), cfg)
        result["sent"] = sent.sent
        if not sent.sent:
            result["warnings"].append("send_failed")
            result["send_error"] = sent.error
    return result


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ConfigError):
        return "config_error"
    if isinstance(exc, ParamError):
        return "invalid_params"
    return "map_error"


def execute(args: argparse.Namespace, stdin: TextIO | None, collector: MapCollector | None = None,
            sender: ImageSender = default_sender) -> dict[str, Any]:
    source = MOCK_SOURCE if args.mock else LIVE_SOURCE
    robot = DEFAULT_ROBOT_NAME
    try:
        cfg = load_config(args.config)
        robot = cfg.robot_name
        read_params(stdin)
        if collector is None:
            collector, source = select_collector(args.mock)
        with stdout_to_stderr():
            collection = collector(cfg)
        return produce(args, cfg, collection, source, sender)
    except Exception as exc:  # noqa: BLE001 - always answer Muse with JSON
        log(f"map failed: {type(exc).__name__}: {exc}")
        result = base_result(robot, source, "error", [_error_code(exc)])
        result["error"] = {"code": _error_code(exc), "message": str(exc)}
        return result


def main(argv: list[str] | None = None) -> int:
    write_json(execute(parse_args(argv), sys.stdin), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
