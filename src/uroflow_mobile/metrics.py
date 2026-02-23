from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class UroflowSummary:
    """Summary metrics derived from flow curve Q(t), where Q is in ml/s."""

    start_time_s: float
    end_time_s: float
    voiding_time_s: float
    flow_time_s: float
    voided_volume_ml: float
    q_max_ml_s: float
    q_avg_ml_s: float
    time_to_qmax_s: float
    interruptions_count: int


def _validate_series(timestamps_s: Sequence[float], flow_ml_s: Sequence[float]) -> None:
    if len(timestamps_s) != len(flow_ml_s):
        raise ValueError("timestamps_s and flow_ml_s must have equal length")
    if len(timestamps_s) < 2:
        raise ValueError("at least two points are required")

    previous_t = timestamps_s[0]
    for index, current_t in enumerate(timestamps_s[1:], start=1):
        if current_t <= previous_t:
            raise ValueError(f"timestamps must be strictly increasing (index {index})")
        previous_t = current_t

    for index, flow in enumerate(flow_ml_s):
        if flow < 0:
            raise ValueError(f"flow cannot be negative (index {index})")


def _trapz_integral(timestamps_s: Sequence[float], flow_ml_s: Sequence[float]) -> float:
    area = 0.0
    for i in range(1, len(timestamps_s)):
        dt = timestamps_s[i] - timestamps_s[i - 1]
        area += 0.5 * (flow_ml_s[i] + flow_ml_s[i - 1]) * dt
    return area


def _compute_flow_time(
    timestamps_s: Sequence[float], flow_ml_s: Sequence[float], threshold_ml_s: float
) -> float:
    total = 0.0
    for i in range(1, len(timestamps_s)):
        dt = timestamps_s[i] - timestamps_s[i - 1]
        mid_flow = 0.5 * (flow_ml_s[i] + flow_ml_s[i - 1])
        if mid_flow >= threshold_ml_s:
            total += dt
    return total


def _count_interruptions(
    timestamps_s: Sequence[float],
    flow_ml_s: Sequence[float],
    threshold_ml_s: float,
    min_pause_s: float,
) -> int:
    in_pause = False
    pause_start = 0.0
    pauses = 0

    for i in range(1, len(timestamps_s)):
        mid_flow = 0.5 * (flow_ml_s[i] + flow_ml_s[i - 1])
        current_t = timestamps_s[i]

        if mid_flow < threshold_ml_s and not in_pause:
            in_pause = True
            pause_start = timestamps_s[i - 1]
        elif mid_flow >= threshold_ml_s and in_pause:
            if current_t - pause_start >= min_pause_s:
                pauses += 1
            in_pause = False

    if in_pause and (timestamps_s[-1] - pause_start >= min_pause_s):
        pauses += 1

    # End pauses that occur after stream termination are not counted as interruptions.
    return max(pauses - 1, 0)


def calculate_uroflow_summary(
    timestamps_s: Sequence[float],
    flow_ml_s: Sequence[float],
    threshold_ml_s: float = 0.2,
    min_pause_s: float = 0.5,
) -> UroflowSummary:
    """Calculate standard uroflow metrics from Q(t)."""

    _validate_series(timestamps_s, flow_ml_s)

    start_time = timestamps_s[0]
    end_time = timestamps_s[-1]
    voiding_time = end_time - start_time

    volume_ml = _trapz_integral(timestamps_s, flow_ml_s)
    flow_time = _compute_flow_time(timestamps_s, flow_ml_s, threshold_ml_s)

    q_max = max(flow_ml_s)
    max_index = flow_ml_s.index(q_max)
    time_to_qmax = timestamps_s[max_index] - start_time

    q_avg = volume_ml / flow_time if flow_time > 0 else 0.0
    interruptions = _count_interruptions(
        timestamps_s, flow_ml_s, threshold_ml_s=threshold_ml_s, min_pause_s=min_pause_s
    )

    return UroflowSummary(
        start_time_s=start_time,
        end_time_s=end_time,
        voiding_time_s=voiding_time,
        flow_time_s=flow_time,
        voided_volume_ml=volume_ml,
        q_max_ml_s=q_max,
        q_avg_ml_s=q_avg,
        time_to_qmax_s=time_to_qmax,
        interruptions_count=interruptions,
    )
