import io

import pytest
from PIL import Image

from turtlebot3_muse import view_cli
from turtlebot3_muse.muse_sender import SendResult
from turtlebot3_muse.screen_capture import CaptureError


def png(color=(48, 48, 48), dot=True):
    image = Image.new("RGB", (64, 36), color)
    if dot:
        image.putpixel((10, 10), (255, 127, 163))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


class Sender:
    def __init__(self, result=SendResult(True)):
        self.calls, self.result = [], result

    def __call__(self, path, message, cfg):
        self.calls.append(message)
        return self.result


@pytest.fixture
def display_up(monkeypatch):
    monkeypatch.setattr(view_cli, "display_exists", lambda display: True)


def run(tmp_path, *extra, capturer=lambda cfg: png(), status=None, sender=None):
    args = view_cli.parse_args(["--out", str(tmp_path / "view.png"), *extra])
    status = status or {"state": "online", "warnings": []}
    return view_cli.execute(args, io.StringIO(""), capturer=capturer,
                            status_reader=lambda cfg, path: status, sender=sender or Sender())


def test_ok_saves_png_without_sending(tmp_path, display_up):
    result = run(tmp_path)
    assert result["state"] == "ok" and result["source"] == "rviz_headless"
    assert result["sent"] is False and result["warnings"] == []
    assert result["robot_state"] == "online"
    assert Image.open(result["image"]["path"]).size == (64, 36)


def test_sends_with_plain_caption_when_online(tmp_path, display_up):
    sender = Sender()
    result = run(tmp_path, "--send", sender=sender)
    assert result["sent"] is True
    assert sender.calls == [view_cli.DEFAULT_MESSAGE]


def test_caption_warns_when_robot_not_online(tmp_path, display_up):
    sender = Sender()
    result = run(tmp_path, "--send", sender=sender, status={"state": "offline", "warnings": ["no_odom"]})
    assert "robot_not_online" in result["warnings"]
    assert result["robot_warnings"] == ["no_odom"]
    assert "offline" in sender.calls[0] and "最新ではない" in sender.calls[0]


def test_viewer_unavailable_when_no_display(tmp_path, monkeypatch):
    monkeypatch.setattr(view_cli, "display_exists", lambda display: False)
    sender = Sender()
    result = run(tmp_path, "--send", sender=sender)
    assert result["state"] == "viewer_unavailable"
    assert sender.calls == [] and not (tmp_path / "view.png").exists()


def test_blank_frame_is_not_sent(tmp_path, display_up):
    sender = Sender()
    result = run(tmp_path, "--send", capturer=lambda cfg: png((0, 0, 0), dot=False), sender=sender)
    assert result["state"] == "viewer_not_ready" and result["warnings"] == ["blank_frame"]
    assert sender.calls == []


def test_capture_error_returns_error_json(tmp_path, display_up):
    def broken(cfg):
        raise CaptureError("Cannot open display :99")

    result = run(tmp_path, capturer=broken)
    assert result["state"] == "error" and result["error"]["code"] == "capture_error"


def test_send_failure_reported(tmp_path, display_up):
    result = run(tmp_path, "--send", sender=Sender(SendResult(False, "socket not found")))
    assert result["sent"] is False and "send_failed" in result["warnings"]
    assert result["send_error"] == "socket not found"


@pytest.mark.parametrize("state, expected", [("online", view_cli.DEFAULT_MESSAGE), (None, "unknown")])
def test_build_caption(state, expected):
    assert expected in view_cli.build_caption(view_cli.DEFAULT_MESSAGE, state)


def test_repo_rviz_config_is_read_only():
    """The headless RViz2 must not offer tools that publish (goals, initial pose, points)."""
    from pathlib import Path

    text = (Path(__file__).parents[1] / "config" / "rviz" / "muse_view.rviz").read_text()
    tools = text.split("  Tools:")[1].split("  Transformation:")[0]
    assert "rviz_default_plugins/Interact" in tools
    for publishing_tool in ("SetGoal", "SetInitialPose", "PublishPoint", "nav2_rviz_plugins"):
        assert publishing_tool not in text
