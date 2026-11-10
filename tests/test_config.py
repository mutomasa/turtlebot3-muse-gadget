from pathlib import Path

import pytest

from turtlebot3_muse.config import AppConfig, ConfigError, build_config, load_config

REPO_CONFIG = Path(__file__).parents[1] / "config" / "robot.toml"


def test_defaults_when_no_path():
    assert load_config(None) == AppConfig()


def test_repo_config_matches_defaults():
    assert load_config(REPO_CONFIG) == AppConfig()


def test_partial_override():
    cfg = build_config({"robot_name": "X", "status": {"wait_timeout_s": 1.5}})
    assert cfg.robot_name == "X"
    assert cfg.status.wait_timeout_s == 1.5
    assert cfg.status.max_age_s == 2.0


@pytest.mark.parametrize("raw", [
    {"unknown": 1},
    {"status": {"typo_s": 1}},
    {"status": {"wait_timeout_s": 0}},
    {"status": {"wait_timeout_s": "4"}},
    {"topics": "not a table"},
])
def test_invalid_config_raises(raw):
    with pytest.raises(ConfigError):
        build_config(raw)


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "missing.toml")
