import subprocess
from pathlib import Path
from types import SimpleNamespace

from turtlebot3_muse.muse_sender import build_send_command, send_image


def test_build_send_command():
    assert build_send_command("musegadget", Path("/tmp/m.png"), "hi") == [
        "musegadget", "send-user-msg", "--image", "/tmp/m.png", "hi"]


def test_send_success():
    calls = []

    def runner(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0, stderr="")

    assert send_image(Path("a.png"), "m", runner=runner).sent
    assert calls[0][1]["timeout"] == 15.0 and calls[0][1]["check"] is False


def test_send_nonzero_exit():
    result = send_image(Path("a.png"), "m", runner=lambda *a, **k: SimpleNamespace(returncode=2, stderr=" denied \n"))
    assert not result.sent and result.error == "denied"


def test_send_binary_missing():
    def runner(*a, **k):
        raise FileNotFoundError

    assert send_image(Path("a.png"), "m", runner=runner).error == "musegadget not found"


def test_send_timeout():
    def runner(*a, **k):
        raise subprocess.TimeoutExpired("musegadget", 1)

    assert "timed out" in send_image(Path("a.png"), "m", timeout_s=1, runner=runner).error
