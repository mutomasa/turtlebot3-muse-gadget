"""Send images to Muse chat through the ``musegadget send-user-msg`` CLI."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_ERROR_CHARS = 500


@dataclass(frozen=True)
class SendResult:
    sent: bool
    error: str | None = None


def build_send_command(binary: str, image: Path, message: str) -> list[str]:
    return [binary, "send-user-msg", "--image", str(image), message]


def send_image(
    image: Path,
    message: str,
    *,
    binary: str = "musegadget",
    timeout_s: float = 15.0,
    runner: Callable[..., Any] = subprocess.run,
) -> SendResult:
    command = build_send_command(binary, image, message)
    try:
        completed = runner(command, capture_output=True, text=True, timeout=timeout_s, check=False)
    except FileNotFoundError:
        return SendResult(False, f"{binary} not found")
    except subprocess.TimeoutExpired:
        return SendResult(False, f"{binary} timed out after {timeout_s}s")
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()[:MAX_ERROR_CHARS]
        return SendResult(False, detail or f"{binary} exited with {completed.returncode}")
    return SendResult(True)
