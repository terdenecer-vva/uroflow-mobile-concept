from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class EventDetectionConfig:
    """Configuration for capture-event detection."""

    flow_threshold_ml_s: float = 0.2
    min_audio_delta_db: float = 6.0
    audio_noise_percentile: float = 20.0
    min_active_duration_s: float = 0.4
    max_gap_s: float = 0.3
    padding_s: float = 0.2
    min_event_duration_s: float = 1.0


@dataclass(frozen=True)
class EventDetectionResult:
    """Detected active interval for voiding event."""

    detected: bool
    start_time_s: float
    end_time_s: float
    duration_s: float
    method: str
    confidence: float
    active_ratio: float
    flow_active_ratio: float
    roi_valid_ratio: float
    audio_coverage_ratio: float
    audio_active_ratio: float
    audio_threshold_dbfs: float | None


def _validate_lengths(
    timestamps_s: Sequence[float],
    flow_ml_s: Sequence[float],
    roi_valid: Sequence[bool],
    audio_rms_dbfs: Sequence[float] | None,
) -> None:
    n = len(timestamps_s)
    if n < 2:
        raise ValueError("at least two samples are required")
    if len(flow_ml_s) != n:
        raise ValueError("timestamps_s and flow_ml_s must have equal length")
    if len(roi_valid) != n:
        raise ValueError("timestamps_s and roi_valid must have equal length")
    if audio_rms_dbfs is not None and len(audio_rms_dbfs) != n:
        raise ValueError("timestamps_s and audio_rms_dbfs must have equal length")

    previous_t = timestamps_s[0]
    for index, current_t in enumerate(timestamps_s[1:], start=1):
        if current_t <= previous_t:
            raise ValueError(f"timestamps must be strictly increasing (index {index})")
        previous_t = current_t


def _sample_dt(timestamps_s: Sequence[float]) -> float:
    diffs = [
        timestamps_s[index] - timestamps_s[index - 1]
        for index in range(1, len(timestamps_s))
    ]
    return statistics.median(diffs)


def _to_bool_mask(values: Sequence[bool]) -> list[bool]:
    return [bool(value) for value in values]


def _find_true_runs(mask: Sequence[bool]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start = None
    for index, value in enumerate(mask):
        if value and start is None:
            start = index
        elif not value and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def _fill_short_gaps(mask: list[bool], max_gap_samples: int) -> list[bool]:
    if max_gap_samples <= 0:
        return mask

    runs = _find_true_runs(mask)
    if len(runs) < 2:
        return mask

    filled = list(mask)
    for current, nxt in zip(runs, runs[1:], strict=True):
        gap_start = current[1] + 1
        gap_end = nxt[0] - 1
        gap_len = gap_end - gap_start + 1
        if gap_len <= max_gap_samples:
            for index in range(gap_start, gap_end + 1):
                filled[index] = True
    return filled


def _remove_short_true_runs(mask: list[bool], min_run_samples: int) -> list[bool]:
    if min_run_samples <= 1:
        return mask

    filtered = list(mask)
    for start, end in _find_true_runs(mask):
        run_len = end - start + 1
        if run_len < min_run_samples:
            for index in range(start, end + 1):
                filtered[index] = False
    return filtered


def _select_primary_run(
    runs: list[tuple[int, int]],
    flow_ml_s: Sequence[float],
) -> tuple[int, int]:
    if not runs:
        raise ValueError("runs is empty")

    best_run = runs[0]
    best_score = -1.0
    for start, end in runs:
        score = sum(flow_ml_s[start : end + 1])
        if score > best_score:
            best_score = score
            best_run = (start, end)
    return best_run


def _nan_percentile(values: Sequence[float], percentile: float) -> float:
    finite_values = sorted(value for value in values if math.isfinite(value))
    if not finite_values:
        raise ValueError("no finite values for percentile")

    if percentile <= 0:
        return finite_values[0]
    if percentile >= 100:
        return finite_values[-1]

    position = (percentile / 100.0) * (len(finite_values) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return finite_values[low]

    weight = position - low
    return finite_values[low] * (1.0 - weight) + finite_values[high] * weight


def _derive_audio_mask(
    audio_rms_dbfs: Sequence[float] | None,
    config: EventDetectionConfig,
) -> tuple[list[bool] | None, float | None, float, float]:
    if audio_rms_dbfs is None:
        return None, None, 0.0, 0.0

    finite_count = sum(1 for value in audio_rms_dbfs if math.isfinite(value))
    coverage = finite_count / len(audio_rms_dbfs)
    if finite_count == 0:
        return None, None, coverage, 0.0

    noise_floor_dbfs = _nan_percentile(audio_rms_dbfs, config.audio_noise_percentile)
    threshold_dbfs = noise_floor_dbfs + config.min_audio_delta_db

    mask: list[bool] = []
    active = 0
    for value in audio_rms_dbfs:
        is_active = math.isfinite(value) and value >= threshold_dbfs
        mask.append(is_active)
        if is_active:
            active += 1

    active_ratio = active / len(mask)
    return mask, threshold_dbfs, coverage, active_ratio


def _ratio_true(mask: Sequence[bool]) -> float:
    if not mask:
        return 0.0
    return sum(1 for value in mask if value) / len(mask)


def _bounded_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))


def detect_voiding_interval(
    timestamps_s: Sequence[float],
    flow_ml_s: Sequence[float],
    roi_valid: Sequence[bool],
    audio_rms_dbfs: Sequence[float] | None = None,
    config: EventDetectionConfig | None = None,
) -> EventDetectionResult:
    """Detect active voiding interval using ROI validity + audio + flow."""

    cfg = config or EventDetectionConfig()
    _validate_lengths(timestamps_s, flow_ml_s, roi_valid, audio_rms_dbfs)

    if cfg.flow_threshold_ml_s < 0:
        raise ValueError("flow_threshold_ml_s must be >= 0")

    dt = _sample_dt(timestamps_s)
    min_run_samples = max(1, int(math.ceil(cfg.min_active_duration_s / dt)))
    max_gap_samples = max(0, int(math.floor(cfg.max_gap_s / dt)))
    padding_samples = max(0, int(math.ceil(cfg.padding_s / dt)))

    roi_mask = _to_bool_mask(roi_valid)
    flow_mask = [value >= cfg.flow_threshold_ml_s for value in flow_ml_s]
    audio_mask, audio_threshold_dbfs, audio_coverage, audio_active_ratio = _derive_audio_mask(
        audio_rms_dbfs, cfg
    )

    if audio_mask is None:
        method = "roi_flow_fallback"
        combined = [roi and flow for roi, flow in zip(roi_mask, flow_mask, strict=True)]
    else:
        method = "audio_roi_flow_fusion"
        combined = [
            roi and (flow or audio)
            for roi, flow, audio in zip(roi_mask, flow_mask, audio_mask, strict=True)
        ]

    combined = _fill_short_gaps(combined, max_gap_samples=max_gap_samples)
    combined = _remove_short_true_runs(combined, min_run_samples=min_run_samples)

    runs = _find_true_runs(combined)
    if not runs:
        return EventDetectionResult(
            detected=False,
            start_time_s=timestamps_s[0],
            end_time_s=timestamps_s[-1],
            duration_s=timestamps_s[-1] - timestamps_s[0],
            method=method,
            confidence=0.0,
            active_ratio=0.0,
            flow_active_ratio=_ratio_true(flow_mask),
            roi_valid_ratio=_ratio_true(roi_mask),
            audio_coverage_ratio=audio_coverage,
            audio_active_ratio=audio_active_ratio,
            audio_threshold_dbfs=audio_threshold_dbfs,
        )

    start, end = _select_primary_run(runs, flow_ml_s=flow_ml_s)
    start = max(0, start - padding_samples)
    end = min(len(timestamps_s) - 1, end + padding_samples)

    start_time_s = timestamps_s[start]
    end_time_s = timestamps_s[end]
    duration_s = end_time_s - start_time_s

    flow_strength = max(flow_ml_s[start : end + 1])
    norm_flow_strength = _bounded_confidence(
        flow_strength / max(cfg.flow_threshold_ml_s * 3.0, 1e-6)
    )

    roi_ratio_run = _ratio_true(roi_mask[start : end + 1])
    if audio_mask is None:
        agreement = _ratio_true(flow_mask[start : end + 1])
        confidence = 0.5 * roi_ratio_run + 0.5 * norm_flow_strength
    else:
        overlap = [
            flow and audio
            for flow, audio in zip(
                flow_mask[start : end + 1],
                audio_mask[start : end + 1],
                strict=True,
            )
        ]
        agreement = _ratio_true(overlap)
        confidence = (
            0.35 * roi_ratio_run
            + 0.35 * agreement
            + 0.30 * norm_flow_strength
        )

    confidence = _bounded_confidence(confidence)
    detected = duration_s >= cfg.min_event_duration_s

    return EventDetectionResult(
        detected=detected,
        start_time_s=start_time_s,
        end_time_s=end_time_s,
        duration_s=duration_s,
        method=method,
        confidence=confidence,
        active_ratio=_ratio_true(combined),
        flow_active_ratio=_ratio_true(flow_mask),
        roi_valid_ratio=_ratio_true(roi_mask),
        audio_coverage_ratio=audio_coverage,
        audio_active_ratio=audio_active_ratio,
        audio_threshold_dbfs=audio_threshold_dbfs,
    )


def slice_indices_for_interval(
    timestamps_s: Sequence[float],
    start_time_s: float,
    end_time_s: float,
) -> list[int]:
    """Return indices within [start_time_s, end_time_s]."""

    if start_time_s > end_time_s:
        raise ValueError("start_time_s must be <= end_time_s")

    indices = [
        index
        for index, timestamp in enumerate(timestamps_s)
        if timestamp >= start_time_s and timestamp <= end_time_s
    ]
    return indices
