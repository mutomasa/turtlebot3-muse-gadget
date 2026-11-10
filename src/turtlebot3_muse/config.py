"""Load and validate the TOML configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

DEFAULT_ROBOT_NAME = "TurtleBot3 Burger"


class ConfigError(ValueError):
    """Raised when the configuration file is missing or invalid."""


def _require_positive(obj: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(obj, name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ConfigError(f"{type(obj).__name__}.{name} must be a positive number: {value!r}")


@dataclass(frozen=True)
class TopicConfig:
    odom: str = "/odom"
    scan: str = "/scan"
    battery: str = "/battery_state"
    map: str = "/map"


@dataclass(frozen=True)
class StatusConfig:
    wait_timeout_s: float = 4.0
    max_age_s: float = 2.0
    max_stamp_skew_s: float = 5.0

    def __post_init__(self) -> None:
        _require_positive(self, ("wait_timeout_s", "max_age_s", "max_stamp_skew_s"))


@dataclass(frozen=True)
class MapConfig:
    wait_timeout_s: float = 5.0
    tf_timeout_s: float = 2.0
    map_frame: str = "map"
    base_frame: str = "base_link"
    transient_local: bool = True
    max_side_px: int = 1024
    max_image_bytes: int = 2 * 1024 * 1024

    def __post_init__(self) -> None:
        _require_positive(self, ("wait_timeout_s", "tf_timeout_s", "max_side_px", "max_image_bytes"))


@dataclass(frozen=True)
class MuseConfig:
    binary: str = "musegadget"
    send_timeout_s: float = 15.0

    def __post_init__(self) -> None:
        _require_positive(self, ("send_timeout_s",))


@dataclass(frozen=True)
class BridgeConfig:
    socket_path: str = "/run/turtlebot-muse/bridge.sock"
    request_timeout_s: float = 1.0

    def __post_init__(self) -> None:
        _require_positive(self, ("request_timeout_s",))


@dataclass(frozen=True)
class ViewConfig:
    """Headless RViz2 viewer (systemd/turtlebot3-muse-rviz.service) captured by robot.view."""

    display: str = ":99"
    xauthority: str = "/run/turtlebot-muse-rviz/xauth"
    ffmpeg: str = "ffmpeg"
    capture_timeout_s: float = 5.0
    max_image_bytes: int = 2 * 1024 * 1024

    def __post_init__(self) -> None:
        _require_positive(self, ("capture_timeout_s", "max_image_bytes"))
        if not self.display.startswith(":") or not self.display[1:].split(".")[0].isdigit():
            raise ConfigError(f"ViewConfig.display must look like ':99': {self.display!r}")


@dataclass(frozen=True)
class AppConfig:
    robot_name: str = DEFAULT_ROBOT_NAME
    topics: TopicConfig = field(default_factory=TopicConfig)
    status: StatusConfig = field(default_factory=StatusConfig)
    map: MapConfig = field(default_factory=MapConfig)
    muse: MuseConfig = field(default_factory=MuseConfig)
    bridge: BridgeConfig = field(default_factory=BridgeConfig)
    view: ViewConfig = field(default_factory=ViewConfig)


_SECTIONS: dict[str, type] = {
    "topics": TopicConfig,
    "status": StatusConfig,
    "map": MapConfig,
    "muse": MuseConfig,
    "bridge": BridgeConfig,
    "view": ViewConfig,
}


def load_config(path: Path | None) -> AppConfig:
    """Load config from ``path``; ``None`` means built-in defaults."""
    if path is None:
        return AppConfig()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    return build_config(raw)


def build_config(raw: dict[str, Any]) -> AppConfig:
    unknown = set(raw) - set(_SECTIONS) - {"robot_name"}
    if unknown:
        raise ConfigError(f"unknown config keys: {sorted(unknown)}")
    sections = {name: _build_section(cls, raw.get(name, {}), name) for name, cls in _SECTIONS.items()}
    return AppConfig(robot_name=str(raw.get("robot_name", DEFAULT_ROBOT_NAME)), **sections)


def _build_section(cls: type, raw: Any, name: str) -> Any:
    if not isinstance(raw, dict):
        raise ConfigError(f"[{name}] must be a table")
    unknown = set(raw) - {f.name for f in fields(cls)}
    if unknown:
        raise ConfigError(f"unknown keys in [{name}]: {sorted(unknown)}")
    return cls(**raw)
