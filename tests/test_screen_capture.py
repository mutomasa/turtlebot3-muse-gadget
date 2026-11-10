import io
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image

from turtlebot3_muse.screen_capture import (
    CaptureError,
    CaptureTarget,
    build_capture_command,
    capture_env,
    capture_png,
    display_exists,
    display_number,
    is_blank,
    load_image,
)

TARGET = CaptureTarget(":99", "/run/x/xauth")


def png_bytes(image):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("display, num", [(":99", 99), (":0", 0), (":12.0", 12)])
def test_display_number(display, num):
    assert display_number(display) == num


def test_display_exists(tmp_path):
    (tmp_path / "X99").touch()
    assert display_exists(":99", tmp_path)
    assert not display_exists(":98", tmp_path)


def test_capture_command_hides_mouse_and_grabs_one_frame():
    cmd = build_capture_command("ffmpeg", ":99")
    assert cmd[cmd.index("-draw_mouse") + 1] == "0"
    assert cmd[cmd.index("-frames:v") + 1] == "1"
    assert cmd[cmd.index("-i") + 1] == ":99"
    assert cmd[-1] == "-"


def test_capture_env_sets_display_and_xauthority():
    env = capture_env(TARGET, {"PATH": "/usr/bin", "XAUTHORITY": "/home/u/.Xauthority"})
    assert env == {"PATH": "/usr/bin", "DISPLAY": ":99", "XAUTHORITY": "/run/x/xauth"}


def test_capture_png_success():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(returncode=0, stdout=b"PNGDATA", stderr=b"")

    assert capture_png(TARGET, runner=runner, timeout_s=3) == b"PNGDATA"
    assert calls[0]["timeout"] == 3 and calls[0]["env"]["DISPLAY"] == ":99"


@pytest.mark.parametrize("completed, message", [
    (SimpleNamespace(returncode=1, stdout=b"", stderr=b"Cannot open display :99\n"), "Cannot open display"),
    (SimpleNamespace(returncode=0, stdout=b"", stderr=b""), "exited with 0"),
])
def test_capture_png_failures(completed, message):
    with pytest.raises(CaptureError, match=message):
        capture_png(TARGET, runner=lambda *a, **k: completed)


def test_capture_png_timeout_and_missing_binary():
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("ffmpeg", 1)

    def missing(*a, **k):
        raise FileNotFoundError

    with pytest.raises(CaptureError, match="timed out"):
        capture_png(TARGET, runner=timeout)
    with pytest.raises(CaptureError, match="not found"):
        capture_png(TARGET, runner=missing)


def test_is_blank():
    assert is_blank(load_image(png_bytes(Image.new("RGB", (20, 20), (0, 0, 0)))))
    drawn = Image.new("RGB", (20, 20), (48, 48, 48))
    drawn.putpixel((5, 5), (255, 127, 163))
    assert not is_blank(load_image(png_bytes(drawn)))
