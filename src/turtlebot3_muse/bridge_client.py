"""Query the running bridge (for operators): ``python -m turtlebot3_muse.bridge_client metrics``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .ipc import request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("op", choices=["status", "metrics", "ping"])
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--socket", type=Path, default=None)
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    try:
        response = request(args.socket or Path(cfg.bridge.socket_path), {"op": args.op}, cfg.bridge.request_timeout_s)
    except OSError as exc:
        print(f"bridge unavailable: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
