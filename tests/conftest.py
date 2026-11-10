import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _to_namespace(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_to_namespace(v) for v in value]
    if value in ("inf", "nan"):
        return math.inf if value == "inf" else math.nan
    return value


def load_msg(name: str):
    return _to_namespace(json.loads((FIXTURES / name).read_text()))


@pytest.fixture
def odom_msg():
    return load_msg("odom.json")


@pytest.fixture
def scan_msg():
    return load_msg("scan.json")
