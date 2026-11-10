import io
import re
import json
from pathlib import Path

import pytest

from turtlebot3_muse import status_cli
from turtlebot3_muse.cli_common import ParamError, read_params
from turtlebot3_muse.models import StatusCollection

COMMANDS = Path(__file__).parents[1] / "commands"
REQUIRED_KEYS = {"robot", "source", "state", "observed_at", "odom", "lidar", "battery", "warnings"}


def args(*argv):
    # --no-bridge keeps tests independent of a bridge running on this machine
    return status_cli.parse_args(["--no-bridge", *argv])


@pytest.mark.parametrize("text, expected", [("", {}), ("  \n", {}), ('{"a": 1}', {"a": 1})])
def test_read_params(text, expected):
    assert read_params(io.StringIO(text)) == expected


@pytest.mark.parametrize("text", ["{bad", "[1, 2]"])
def test_read_params_rejects_invalid(text):
    with pytest.raises(ParamError):
        read_params(io.StringIO(text))


def test_mock_status_is_labelled_mock():
    result = status_cli.execute(args("--mock"), io.StringIO(""))
    assert result["source"] == "mock"
    assert result["state"] == "online"
    assert REQUIRED_KEYS <= result.keys()


def test_invalid_stdin_returns_unknown():
    result = status_cli.execute(args("--mock"), io.StringIO("{bad"))
    assert result["state"] == "unknown"
    assert result["error"]["code"] == "invalid_params"


def test_collector_exception_returns_unknown_not_sample_values():
    def broken(_cfg):
        raise RuntimeError("rclpy init failed")

    result = status_cli.execute(args(), io.StringIO(""), collector=broken)
    assert result["state"] == "unknown"
    assert result["source"] == "ros2_live"
    assert result["error"]["code"] == "collection_error"
    assert result["odom"]["x_m"] is None


def test_timeout_collection_reports_offline():
    result = status_cli.execute(args(), io.StringIO(""),
                                collector=lambda _c: StatusCollection(None, None, None, timed_out=True))
    assert result["state"] == "offline"
    assert "timeout" in result["warnings"]


def test_bad_config_returns_unknown(tmp_path):
    bad = tmp_path / "robot.toml"
    bad.write_text("[status]\nwait_timeout_s = -1\n")
    result = status_cli.execute(args("--mock", "--config", str(bad)), io.StringIO(""))
    assert result["error"]["code"] == "config_error"


def test_stdout_is_single_json_object_even_if_collector_prints(capfd, monkeypatch):
    def noisy(_cfg):
        print("noise from python")
        import os
        os.write(1, b"noise from native code\n")
        return StatusCollection(None, None, None, timed_out=True)

    monkeypatch.setattr(status_cli, "select_collector", lambda mock: (noisy, "ros2_live"))
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert status_cli.main(["--no-bridge"]) == 0
    out, err = capfd.readouterr()
    assert json.loads(out)["state"] == "offline"
    assert "noise from python" in err and "noise from native code" in err


@pytest.mark.parametrize("name", ["robot.status.json", "robot.map.json"])
def test_command_definitions(name):
    spec = json.loads((COMMANDS / name).read_text())
    assert set(spec) == {"description", "exec", "required", "optional", "timeout_ms"}
    assert spec["exec"][0].startswith("/usr/local/bin/turtlebot-muse-")
    assert re.search(r"without moving|not move", spec["description"])
