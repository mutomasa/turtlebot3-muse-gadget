import io
from pathlib import Path

from PIL import Image

from turtlebot3_muse import map_cli
from turtlebot3_muse.mock_source import mock_grid
from turtlebot3_muse.models import MapCollection
from turtlebot3_muse.muse_sender import SendResult


def args(tmp_path: Path, *extra):
    return map_cli.parse_args(["--out", str(tmp_path / "map.png"), *extra])


class RecordingSender:
    def __init__(self, result=SendResult(True)):
        self.calls, self.result = [], result

    def __call__(self, path, message, cfg):
        self.calls.append((path, message))
        return self.result


def test_mock_map_renders_png(tmp_path):
    result = map_cli.execute(args(tmp_path, "--mock"), io.StringIO(""))
    assert result["state"] == "ok" and result["source"] == "mock"
    assert result["sent"] is False
    image = Image.open(result["image"]["path"])
    assert image.format == "PNG"
    assert result["image"]["bytes"] <= 2 * 1024 * 1024
    assert result["robot_pose"]["frame_id"] == "map"


def test_no_map_produces_no_image(tmp_path):
    sender = RecordingSender()
    result = map_cli.execute(args(tmp_path, "--send"), io.StringIO(""),
                             collector=lambda _c: MapCollection(None, timed_out=True), sender=sender)
    assert result["state"] == "no_map"
    assert result["warnings"] == ["no_map", "timeout"]
    assert result["image"] is None
    assert not (tmp_path / "map.png").exists()
    assert sender.calls == []


def test_missing_pose_warns_and_caption_says_so(tmp_path):
    sender = RecordingSender()
    result = map_cli.execute(args(tmp_path, "--send"), io.StringIO(""),
                             collector=lambda _c: MapCollection(mock_grid()), sender=sender)
    assert "robot_pose_unavailable" in result["warnings"]
    assert result["sent"] is True
    assert "ロボット位置は取得できませんでした" in sender.calls[0][1]


def test_mock_caption_is_marked(tmp_path):
    sender = RecordingSender()
    map_cli.execute(args(tmp_path, "--mock", "--send"), io.StringIO(""), sender=sender)
    assert sender.calls[0][1].startswith("[MOCK]")


def test_send_failure_is_reported(tmp_path):
    sender = RecordingSender(SendResult(False, "socket not found"))
    result = map_cli.execute(args(tmp_path, "--mock", "--send"), io.StringIO(""), sender=sender)
    assert result["sent"] is False
    assert "send_failed" in result["warnings"]
    assert result["send_error"] == "socket not found"


def test_collector_error_returns_error_json(tmp_path):
    def broken(_cfg):
        raise RuntimeError("boom")

    result = map_cli.execute(args(tmp_path), io.StringIO(""), collector=broken)
    assert result["state"] == "error" and result["error"]["code"] == "map_error"
