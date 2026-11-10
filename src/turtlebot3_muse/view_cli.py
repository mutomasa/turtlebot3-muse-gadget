"""``robot.view`` Muse command: post a snapshot of the headless RViz2 to Muse chat.

The RViz2 instance runs on its own Xvfb display (turtlebot3-muse-rviz.service)
with a read-only config, so the desktop RViz2 is never touched. Muse chat only
accepts still images, so this sends one frame per request.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from . import status_cli
from .cli_common import ParamError, log, read_params, write_atomically, write_json
from .config import DEFAULT_ROBOT_NAME, AppConfig, ConfigError, load_config
from .map_renderer import encode_png_within
from .muse_sender import SendResult, send_image
from .screen_capture import CaptureError, CaptureTarget, capture_png, display_exists, is_blank, load_image
from .status_service import STATE_ONLINE, iso_utc

VIEW_SOURCE = "rviz_headless"
DEFAULT_MESSAGE = "TurtleBot3 の RViz2 画面です。"
DEFAULT_OUT = Path(tempfile.gettempdir()) / "turtlebot_view.png"

Capturer = Callable[[AppConfig], bytes]
StatusReader = Callable[[AppConfig, Path | None], dict[str, Any]]
ImageSender = Callable[[Path, str, AppConfig], SendResult]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output PNG path")
    parser.add_argument("--send", action=argparse.BooleanOptionalAction, default=False, help="post the PNG to Muse chat")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    return parser.parse_args(argv)


def default_capturer(cfg: AppConfig) -> bytes:
    view = cfg.view
    target = CaptureTarget(view.display, view.xauthority or None)
    return capture_png(target, ffmpeg=view.ffmpeg, timeout_s=view.capture_timeout_s)


def default_status_reader(cfg: AppConfig, config_path: Path | None) -> dict[str, Any]:
    """Robot status via the bridge, falling back to a one-shot subscription."""
    argv = ["--config", str(config_path)] if config_path else []
    return status_cli.execute(status_cli.parse_args(argv), None)


def default_sender(path: Path, message: str, cfg: AppConfig) -> SendResult:
    return send_image(path, message, binary=cfg.muse.binary, timeout_s=cfg.muse.send_timeout_s)


def build_caption(message: str, robot_state: str | None) -> str:
    if robot_state == STATE_ONLINE:
        return message
    shown = robot_state or "unknown"
    return f"{message}（注意：ロボットの状態は {shown} です。表示が最新ではない可能性があります）"


def base_result(robot: str, state: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "robot": robot, "source": VIEW_SOURCE, "state": state, "observed_at": iso_utc(time.time()),
        "robot_state": None, "robot_warnings": [], "image": None, "sent": False, "warnings": warnings,
    }


def attach_robot_status(result: dict[str, Any], status: dict[str, Any]) -> None:
    result["robot_state"] = status.get("state")
    result["robot_warnings"] = list(status.get("warnings", []))
    if result["robot_state"] != STATE_ONLINE:
        result["warnings"].append("robot_not_online")


def save_snapshot(png: bytes, cfg: AppConfig, out: Path) -> dict[str, Any] | None:
    """Encode within the size limit and save. ``None`` when the frame is blank."""
    image = load_image(png)
    if is_blank(image):
        return None
    data, final = encode_png_within(image, cfg.view.max_image_bytes)
    write_atomically(out, data)
    return {"path": str(out), "width_px": final.width, "height_px": final.height, "bytes": len(data)}


def produce(args: argparse.Namespace, cfg: AppConfig, capturer: Capturer, status_reader: StatusReader,
            sender: ImageSender) -> dict[str, Any]:
    if not display_exists(cfg.view.display):
        return base_result(cfg.robot_name, "viewer_unavailable", ["viewer_unavailable"])
    image = save_snapshot(capturer(cfg), cfg, args.out)
    if image is None:
        return base_result(cfg.robot_name, "viewer_not_ready", ["blank_frame"])
    result = base_result(cfg.robot_name, "ok", [])
    result["image"] = image
    attach_robot_status(result, status_reader(cfg, args.config))
    if args.send:
        sent = sender(args.out, build_caption(args.message, result["robot_state"]), cfg)
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
    if isinstance(exc, CaptureError):
        return "capture_error"
    return "view_error"


def execute(args: argparse.Namespace, stdin: TextIO | None, *, capturer: Capturer = default_capturer,
            status_reader: StatusReader = default_status_reader, sender: ImageSender = default_sender) -> dict[str, Any]:
    robot = DEFAULT_ROBOT_NAME
    try:
        cfg = load_config(args.config)
        robot = cfg.robot_name
        read_params(stdin)
        return produce(args, cfg, capturer, status_reader, sender)
    except Exception as exc:  # noqa: BLE001 - always answer Muse with JSON
        log(f"view failed: {type(exc).__name__}: {exc}")
        result = base_result(robot, "error", [_error_code(exc)])
        result["error"] = {"code": _error_code(exc), "message": str(exc)}
        return result


def main(argv: list[str] | None = None) -> int:
    write_json(execute(parse_args(argv), sys.stdin), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
