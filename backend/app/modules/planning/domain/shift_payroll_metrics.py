"""Calcul pur des métriques paie par poste (nuit, pause payée)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _time_to_minutes(value: str) -> int:
    parts = str(value or "00:00")[:8].split(":")
    h = int(parts[0]) if parts else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    return h * 60 + m


def _shift_segments(start_min: int, end_min: int) -> list[tuple[int, int]]:
    if end_min <= start_min:
        return [(start_min, 24 * 60), (0, end_min)]
    return [(start_min, end_min)]


def _window_segments(window_start: int, window_end: int) -> list[tuple[int, int]]:
    if window_end <= window_start:
        return [(window_start, 24 * 60), (0, window_end)]
    return [(window_start, window_end)]


@dataclass
class NightHoursResult:
    hours: float
    weighted_rate_hours: float

    @property
    def average_rate(self) -> float:
        if self.hours <= 0:
            return 0.0
        return self.weighted_rate_hours / self.hours


def compute_night_hours(
    start_time: str,
    end_time: str,
    windows: list[dict[str, Any]] | None,
) -> NightHoursResult:
    if not windows:
        return NightHoursResult(0.0, 0.0)

    start_min = _time_to_minutes(start_time)
    end_min = _time_to_minutes(end_time)
    shift_segs = _shift_segments(start_min, end_min)

    # Union des minutes de nuit (évite le double comptage si plages chevauchantes)
    covered: dict[int, float] = {}
    for window in windows:
        w_start = _time_to_minutes(str(window.get("start") or "22:00"))
        w_end = _time_to_minutes(str(window.get("end") or "06:00"))
        rate = float(window.get("rate") or 0.0)
        if rate <= 0:
            continue
        for s0, s1 in shift_segs:
            for w0, w1 in _window_segments(w_start, w_end):
                overlap_start = max(s0, w0)
                overlap_end = min(s1, w1)
                for minute in range(overlap_start, overlap_end):
                    covered[minute] = max(covered.get(minute, 0.0), rate)

    if not covered:
        return NightHoursResult(0.0, 0.0)

    hours = round(len(covered) / 60.0, 4)
    weighted = round(sum(covered.values()) / 60.0, 4)
    return NightHoursResult(hours=hours, weighted_rate_hours=weighted)


def compute_paid_break_hours(paid_break_minutes: int | None) -> float:
    if not paid_break_minutes or paid_break_minutes <= 0:
        return 0.0
    return round(paid_break_minutes / 60.0, 4)


__all__ = [
    "NightHoursResult",
    "compute_night_hours",
    "compute_paid_break_hours",
]
