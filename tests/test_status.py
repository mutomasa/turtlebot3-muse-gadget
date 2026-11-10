import pytest

from turtlebot3_muse.config import StatusConfig
from turtlebot3_muse.models import BatterySample, OdomSample, ScanSample, StatusCollection
from turtlebot3_muse.status_service import (
    assess_freshness,
    build_error_status,
    build_status,
    classify_state,
)

NOW_MONO = 100.0
NOW_WALL = 1_762_732_800.0
CFG = StatusConfig(max_age_s=2.0, max_stamp_skew_s=5.0)


def odom(received=NOW_MONO, stamp=None):
    return OdomSample("odom", "base_footprint", 1.0, 2.0, 0.0, 0.0, 0.0, stamp, received)


def scan(min_d=0.5, received=NOW_MONO):
    return ScanSample("base_scan", min_d, 10 if min_d else 0, 400, None, received)


def battery():
    return BatterySample(11.9, None, None, NOW_MONO)


def status(collection):
    return build_status(collection, robot="R", source="ros2_live",
                        now_monotonic_s=NOW_MONO, now_wall_s=NOW_WALL, cfg=CFG)


@pytest.mark.parametrize("odom_ok, scan_ok, any_fresh, expected", [
    (True, True, True, "online"),
    (True, False, True, "degraded"),
    (False, True, True, "degraded"),
    (False, False, True, "degraded"),
    (False, False, False, "offline"),
])
def test_classify_state(odom_ok, scan_ok, any_fresh, expected):
    assert classify_state(odom_ok, scan_ok, any_fresh) == expected


def test_freshness_uses_receive_age():
    assert assess_freshness("odom", 99.0, None, NOW_MONO, NOW_WALL, CFG).fresh
    stale = assess_freshness("odom", 97.0, None, NOW_MONO, NOW_WALL, CFG)
    assert not stale.fresh and "stale_odom" in stale.warnings


def test_stamp_skew_warns_but_does_not_mark_stale():
    result = assess_freshness("odom", NOW_MONO, NOW_WALL - 100, NOW_MONO, NOW_WALL, CFG)
    assert result.fresh
    assert result.warnings == ("odom_stamp_skew",)


def test_online_when_everything_fresh():
    result = status(StatusCollection(odom(), scan(), battery()))
    assert result["state"] == "online"
    assert result["warnings"] == []
    assert result["odom"]["frame_id"] == "odom"
    assert "odom frame" in result["odom"]["note"]
    assert result["lidar"]["min_distance_m"] == 0.5
    assert result["battery"]["voltage_v"] == 11.9
    assert result["observed_at"] == "2025-11-10T00:00:00Z"


def test_offline_when_nothing_received():
    result = status(StatusCollection(None, None, None, timed_out=True))
    assert result["state"] == "offline"
    assert result["warnings"] == ["timeout", "no_odom", "no_scan", "no_battery"]
    assert result["odom"]["x_m"] is None and result["odom"]["received"] is False
    assert result["lidar"]["min_distance_m"] is None


def test_degraded_when_scan_missing():
    result = status(StatusCollection(odom(), None, battery(), timed_out=True))
    assert result["state"] == "degraded"
    assert "no_scan" in result["warnings"]
    assert result["odom"]["received"] is True


def test_degraded_when_scan_has_no_valid_ranges():
    result = status(StatusCollection(odom(), scan(min_d=None), battery()))
    assert result["state"] == "degraded"
    assert "no_valid_scan_ranges" in result["warnings"]


def test_degraded_when_odom_stale():
    result = status(StatusCollection(odom(received=90.0), scan(), battery()))
    assert result["state"] == "degraded"
    assert result["odom"]["fresh"] is False
    assert "stale_odom" in result["warnings"]


def test_missing_battery_does_not_affect_state():
    result = status(StatusCollection(odom(), scan(), None))
    assert result["state"] == "online"
    assert result["warnings"] == ["no_battery"]


def test_error_status_is_unknown_with_no_values():
    result = build_error_status(robot="R", source="ros2_live", now_wall_s=NOW_WALL, code="collection_error", message="x")
    assert result["state"] == "unknown"
    assert result["error"] == {"code": "collection_error", "message": "x"}
    assert result["odom"]["received"] is False


def test_offline_when_everything_received_is_stale():
    result = status(StatusCollection(odom(received=10.0), scan(received=10.0), battery()))
    assert result["state"] == "offline"
    assert {"stale_odom", "stale_scan"} <= set(result["warnings"])
    assert result["odom"]["fresh"] is False and result["odom"]["age_s"] == 90.0
