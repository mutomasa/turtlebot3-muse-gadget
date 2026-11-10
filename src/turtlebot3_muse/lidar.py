"""LaserScan range filtering."""

from __future__ import annotations

import math
from collections.abc import Iterable


def valid_ranges(ranges: Iterable[float], range_min: float, range_max: float) -> list[float]:
    """Finite ranges within ``[range_min, range_max]``."""
    return [r for r in ranges if math.isfinite(r) and range_min <= r <= range_max]


def min_valid_range(ranges: Iterable[float], range_min: float, range_max: float) -> float | None:
    valid = valid_ranges(ranges, range_min, range_max)
    return min(valid) if valid else None
