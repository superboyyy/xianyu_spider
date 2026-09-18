"""价格解析与样本统计。"""

from __future__ import annotations

import re
import statistics
from typing import Any, Optional


_PRICE_RE = re.compile(r"(\d+(?:\.\d+)?)")


def parse_price(value: Any) -> Optional[float]:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    if "万" in text:
        match = _PRICE_RE.search(text)
        if not match:
            return None
        return float(match.group(1)) * 10000
    match = _PRICE_RE.search(text)
    if not match:
        return None
    return float(match.group(1))


def summarize_prices(values: list[float]) -> dict[str, Any]:
    nums = sorted(v for v in values if v is not None and v >= 0)
    if not nums:
        return {
            "sample_n": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "p25": None,
            "p75": None,
        }
    return {
        "sample_n": len(nums),
        "min": round(nums[0], 2),
        "max": round(nums[-1], 2),
        "mean": round(statistics.fmean(nums), 2),
        "median": round(statistics.median(nums), 2),
        "p25": round(_percentile(nums, 0.25), 2),
        "p75": round(_percentile(nums, 0.75), 2),
    }


def _percentile(sorted_vals: list[float], q: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    low = int(pos)
    high = min(low + 1, len(sorted_vals) - 1)
    frac = pos - low
    return sorted_vals[low] * (1 - frac) + sorted_vals[high] * frac
