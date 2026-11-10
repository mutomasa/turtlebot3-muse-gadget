"""Shared helpers for Muse command entry points."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
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


def write_atomically(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` via a temp file + rename, so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}_", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
