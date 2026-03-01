"""In-memory latency metrics for TUI actions."""

from __future__ import annotations

from statistics import median
from typing import Dict, List


class LatencyMetrics:
    """Tracks latency samples and computes p50/p95 summaries."""

    def __init__(self) -> None:
        self._samples: Dict[str, List[float]] = {}

    def record(self, action: str, duration_ms: float) -> None:
        bucket = self._samples.setdefault(action, [])
        bucket.append(max(0.0, float(duration_ms)))
        if len(bucket) > 500:
            del bucket[: len(bucket) - 500]

    def summary(self) -> Dict[str, Dict[str, float]]:
        result: Dict[str, Dict[str, float]] = {}
        for action, values in self._samples.items():
            if not values:
                continue
            ordered = sorted(values)
            p50 = median(ordered)
            idx_95 = max(0, int(round((len(ordered) - 1) * 0.95)))
            p95 = ordered[idx_95]
            result[action] = {
                "count": float(len(ordered)),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
            }
        return result


latency_metrics = LatencyMetrics()
