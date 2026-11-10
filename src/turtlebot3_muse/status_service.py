"""Turn collected samples into the ``robot.status`` response JSON.

State rules (never report "online" on missing or old data):
- online:   odom and scan received, fresh, and scan has valid ranges
- degraded: something received, but not everything is healthy
- offline:  nothing received within the wait timeout
- unknown:  collection itself failed (see ``build_error_status``)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .config import StatusConfig
from .models import BatterySample, OdomSample, ScanSample, StatusCollection

STATE_ONLINE = "online"
STATE_DEGRADED = "degraded"
STATE_OFFLINE = "offline"
STATE_UNKNOWN = "unknown"

ODOM_FRAME_NOTE = "Position is in the odom frame (dead reckoning), not an absolute map position."


@dataclass(frozen=True)
class Freshness:
    fresh: bool
    age_s: float
    warnings: tuple[str, ...]


def assess_freshness(
    name: str,
    received_monotonic_s: float,
    stamp_s: float | None,
    now_monotonic_s: float,
    now_wall_s: float,
    cfg: StatusConfig,
) -> Freshness:
    """Freshness from receive age; header stamp skew only produces a warning."""
    age = max(0.0, now_monotonic_s - received_monotonic_s)
    warnings: list[str] = []
    fresh = age <= cfg.max_age_s
    if not fresh:
        warnings.append(f"stale_{name}")
    if stamp_s is not None and abs(now_wall_s - stamp_s) > cfg.max_stamp_skew_s:
        warnings.append(f"{name}_stamp_skew")
    return Freshness(fresh, age, tuple(warnings))


def classify_state(odom_ok: bool, scan_ok: bool, any_received: bool) -> str:
    if odom_ok and scan_ok:
        return STATE_ONLINE
    if any_received:
        return STATE_DEGRADED
    return STATE_OFFLINE


def iso_utc(wall_s: float) -> str:
    return datetime.fromtimestamp(wall_s, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _round(value: float | None, digits: int) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def odom_section(sample: OdomSample | None, fresh: Freshness | None) -> dict[str, Any]:
    if sample is None or fresh is None:
        return {
            "received": False, "frame_id": None, "child_frame_id": None,
            "x_m": None, "y_m": None, "yaw_deg": None,
            "linear_x_mps": None, "angular_z_radps": None,
            "age_s": None, "fresh": False,
        }
    return {
        "received": True,
        "frame_id": sample.frame_id,
        "child_frame_id": sample.child_frame_id,
        "x_m": _round(sample.x_m, 3),
        "y_m": _round(sample.y_m, 3),
        "yaw_deg": _round(math.degrees(sample.yaw_rad), 1),
        "linear_x_mps": _round(sample.linear_x_mps, 3),
        "angular_z_radps": _round(sample.angular_z_radps, 3),
        "age_s": _round(fresh.age_s, 2),
        "fresh": fresh.fresh,
        "note": ODOM_FRAME_NOTE,
    }


def lidar_section(sample: ScanSample | None, fresh: Freshness | None) -> dict[str, Any]:
    if sample is None or fresh is None:
        return {
            "received": False, "frame_id": None, "min_distance_m": None,
            "valid_points": None, "total_points": None, "age_s": None, "fresh": False,
        }
    return {
        "received": True,
        "frame_id": sample.frame_id,
        "min_distance_m": _round(sample.min_distance_m, 3),
        "valid_points": sample.valid_count,
        "total_points": sample.total_count,
        "age_s": _round(fresh.age_s, 2),
        "fresh": fresh.fresh,
    }


def battery_section(sample: BatterySample | None, fresh: Freshness | None) -> dict[str, Any]:
    if sample is None or fresh is None:
        return {"received": False, "voltage_v": None, "percentage_raw": None, "age_s": None, "fresh": False}
    return {
        "received": True,
        "voltage_v": _round(sample.voltage_v, 2),
        "percentage_raw": _round(sample.percentage, 3),
        "age_s": _round(fresh.age_s, 2),
        "fresh": fresh.fresh,
    }


def _assess(name: str, sample: Any, now_mono: float, now_wall: float, cfg: StatusConfig) -> Freshness | None:
    if sample is None:
        return None
    return assess_freshness(name, sample.received_monotonic_s, sample.stamp_s, now_mono, now_wall, cfg)


def collect_warnings(collection: StatusCollection, assessments: list[Freshness | None]) -> list[str]:
    warnings: list[str] = []
    if collection.timed_out:
        warnings.append("timeout")
    if collection.odom is None:
        warnings.append("no_odom")
    if collection.scan is None:
        warnings.append("no_scan")
    elif collection.scan.min_distance_m is None:
        warnings.append("no_valid_scan_ranges")
    if collection.battery is None:
        warnings.append("no_battery")
    for item in assessments:
        if item is not None:
            warnings.extend(item.warnings)
    return warnings


def build_status(
    collection: StatusCollection,
    *,
    robot: str,
    source: str,
    now_monotonic_s: float,
    now_wall_s: float,
    cfg: StatusConfig,
) -> dict[str, Any]:
    odom_f = _assess("odom", collection.odom, now_monotonic_s, now_wall_s, cfg)
    scan_f = _assess("scan", collection.scan, now_monotonic_s, now_wall_s, cfg)
    battery_f = _assess("battery", collection.battery, now_monotonic_s, now_wall_s, cfg)

    odom_ok = odom_f is not None and odom_f.fresh
    scan_ok = scan_f is not None and scan_f.fresh and collection.scan.min_distance_m is not None
    any_received = collection.odom is not None or collection.scan is not None
    return {
        "robot": robot,
        "source": source,
        "state": classify_state(odom_ok, scan_ok, any_received),
        "observed_at": iso_utc(now_wall_s),
        "odom": odom_section(collection.odom, odom_f),
        "lidar": lidar_section(collection.scan, scan_f),
        "battery": battery_section(collection.battery, battery_f),
        "warnings": collect_warnings(collection, [odom_f, scan_f, battery_f]),
    }


def build_error_status(*, robot: str, source: str, now_wall_s: float, code: str, message: str) -> dict[str, Any]:
    return {
        "robot": robot,
        "source": source,
        "state": STATE_UNKNOWN,
        "observed_at": iso_utc(now_wall_s),
        "odom": odom_section(None, None),
        "lidar": lidar_section(None, None),
        "battery": battery_section(None, None),
        "warnings": [code],
        "error": {"code": code, "message": message},
    }
