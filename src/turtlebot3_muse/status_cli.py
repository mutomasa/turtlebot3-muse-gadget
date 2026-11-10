"""``robot.status`` Muse command: read-only TurtleBot3 status as one JSON object."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from .cli_common import ParamError, log, read_params, write_json
from .config import DEFAULT_ROBOT_NAME, AppConfig, ConfigError, load_config
from .mock_source import MOCK_SOURCE, mock_status
from .models import StatusCollection
from .status_service import build_error_status, build_status
from .stdout_guard import stdout_to_stderr

LIVE_SOURCE = "ros2_live"

StatusCollector = Callable[[AppConfig], StatusCollection]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None, help="TOML config file")
    parser.add_argument("--mock", action="store_true", help="use mock data (output is labelled source=mock)")
    return parser.parse_args(argv)


def select_collector(mock: bool) -> tuple[StatusCollector, str]:
    if mock:
        return mock_status, MOCK_SOURCE
    from .ros_adapter import collect_status

    return collect_status, LIVE_SOURCE


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ConfigError):
        return "config_error"
    if isinstance(exc, ParamError):
        return "invalid_params"
    return "collection_error"


def execute(args: argparse.Namespace, stdin: TextIO | None, collector: StatusCollector | None = None) -> dict[str, Any]:
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
        return build_status(
            collection, robot=robot, source=source,
            now_monotonic_s=time.monotonic(), now_wall_s=time.time(), cfg=cfg.status,
        )
    except Exception as exc:  # noqa: BLE001 - always answer Muse with JSON
        log(f"status failed: {type(exc).__name__}: {exc}")
        return build_error_status(robot=robot, source=source, now_wall_s=time.time(), code=_error_code(exc), message=str(exc))


def main(argv: list[str] | None = None) -> int:
    write_json(execute(parse_args(argv), sys.stdin), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
