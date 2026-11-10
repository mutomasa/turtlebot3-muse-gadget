"""Shared helpers for Muse command entry points."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO


class ParamError(ValueError):
    """Invalid command parameters received on stdin."""


def read_params(stream: TextIO | None) -> dict[str, Any]:
    """Read Muse command parameters (a JSON object) from stdin. Empty input means ``{}``."""
    if stream is None or stream.isatty():
        return {}
    text = stream.read()
    if not text.strip():
        return {}
    try:
        params = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParamError(f"stdin is not valid JSON: {exc}") from exc
    if not isinstance(params, dict):
        raise ParamError("stdin JSON must be an object")
    return params


def write_json(result: dict[str, Any], stream: TextIO) -> None:
    stream.write(json.dumps(result, ensure_ascii=False) + "\n")
    stream.flush()


def log(message: str) -> None:
    print(f"[turtlebot3_muse] {message}", file=sys.stderr)
