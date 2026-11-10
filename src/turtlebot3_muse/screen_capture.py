"""Grab one frame from an X display (the headless RViz2 Xvfb) with ffmpeg."""

from __future__ import annotations

import io
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

X11_SOCKET_DIR = Path("/tmp/.X11-unix")
MAX_ERROR_CHARS = 300
BLANK_TOLERANCE = 2  # max per-channel spread (0-255) still treated as a blank frame


class CaptureError(RuntimeError):
    """Screen capture failed."""


@dataclass(frozen=True)
class CaptureTarget:
    display: str
    xauthority: str | None


def display_number(display: str) -> int:
    return int(display.lstrip(":").split(".")[0])


def display_exists(display: str, socket_dir: Path = X11_SOCKET_DIR) -> bool:
    """True when an X server is listening on ``display`` (local Unix socket)."""
    return (socket_dir / f"X{display_number(display)}").exists()


def build_capture_command(ffmpeg: str, display: str) -> list[str]:
    return [
        ffmpeg, "-loglevel", "error", "-nostdin",
        "-f", "x11grab", "-draw_mouse", "0", "-i", display,
        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-",
    ]


def capture_env(target: CaptureTarget, base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env["DISPLAY"] = target.display
    if target.xauthority:
        env["XAUTHORITY"] = target.xauthority
    return env


def capture_png(
    target: CaptureTarget,
    *,
    ffmpeg: str = "ffmpeg",
    timeout_s: float = 5.0,
    runner: Callable[..., Any] = subprocess.run,
) -> bytes:
    """Return the whole screen of ``target.display`` as PNG bytes."""
    command = build_capture_command(ffmpeg, target.display)
    try:
        completed = runner(command, capture_output=True, timeout=timeout_s, check=False, env=capture_env(target))
    except FileNotFoundError as exc:
        raise CaptureError(f"{ffmpeg} not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise CaptureError(f"{ffmpeg} timed out after {timeout_s}s") from exc
    if completed.returncode != 0 or not completed.stdout:
        detail = (completed.stderr or b"").decode("utf-8", "replace").strip()[:MAX_ERROR_CHARS]
        raise CaptureError(detail or f"{ffmpeg} exited with {completed.returncode}")
    return completed.stdout


def load_image(png: bytes) -> Any:
    from PIL import Image

    image = Image.open(io.BytesIO(png))
    image.load()
    return image.convert("RGB")


def is_blank(image: Any, tolerance: int = BLANK_TOLERANCE) -> bool:
    """A frame with (almost) a single color means RViz2 has not drawn anything yet."""
    return all(high - low <= tolerance for low, high in image.getextrema())
