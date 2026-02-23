from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FusionLevelConfig:
    """Configuration for level-based fusion estimation."""

    ml_per_mm: float = 1.0
    level_sigma_mm: float = 1.0
    flow_smoothing_window: int = 5
    min_depth_confidence: float = 0.6
    min_depth_confidence_ratio: float = 0.8
    min_voided_volume_ml: float = 150.0
    max_level_noise_mm: float = 2.5


@dataclass(frozen=True)
class FusionQualityFlags:
    """Quality evaluation for a fused measurement session."""

    low_depth_confidence: bool
    insufficient_volume: bool
    noisy_level_signal: bool
    depth_confidence_ratio: float
    level_noise_mm: float
    status: str


@dataclass(frozen=True)
class FusionEstimationResult:
    """Estimated signals and quality metadata from level/depth series."""

    timestamps_s: list[float]
    level_mm: list[float]
    depth_confidence: list[float]
    volume_ml: list[float]
    flow_ml_s: list[float]
    flow_uncertainty_ml_s: list[float]
    quality: FusionQualityFlags


def _validate_timestamps(timestamps_s: Sequence[float]) -> None:
    if len(timestamps_s) < 2:
        raise ValueError("at least two timestamps are required")
    previous_t = timestamps_s[0]
    for index, current_t in enumerate(timestamps_s[1:], start=1):
        if current_t <= previous_t:
            raise ValueError(f"timestamps must be strictly increasing (index {index})")
        previous_t = current_t


def _validate_confidence(depth_confidence: Sequence[float]) -> None:
    for index, value in enumerate(depth_confidence):
        if value < 0.0 or value > 1.0:
            raise ValueError(f"depth confidence must be in [0, 1] (index {index})")


def _moving_average(values: Sequence[float], window: int) -> list[float]:
    if window <= 1:
        return list(values)

    smoothed: list[float] = []
    for index in range(len(values)):
        start = max(0, index - window + 1)
        segment = values[start : index + 1]
        smoothed.append(sum(segment) / len(segment))
    return smoothed


def estimate_volume_curve(level_mm: Sequence[float], ml_per_mm: float) -> list[float]:
    """Convert level series into cumulative volume relative to baseline."""

    if not level_mm:
        raise ValueError("level_mm is empty")
    if ml_per_mm <= 0:
        raise ValueError("ml_per_mm must be positive")

    baseline_level = level_mm[0]
    volume_ml: list[float] = []
    for level in level_mm:
        delta_level = level - baseline_level
        volume_ml.append(max(delta_level * ml_per_mm, 0.0))
    return volume_ml


def estimate_flow_curve(
    timestamps_s: Sequence[float], volume_ml: Sequence[float], smoothing_window: int = 5
) -> list[float]:
    """Differentiate V(t) and smooth to estimate Q(t)."""

    if len(timestamps_s) != len(volume_ml):
        raise ValueError("timestamps_s and volume_ml must have equal length")
    _validate_timestamps(timestamps_s)

    flow_raw: list[float] = []
    for index in range(len(volume_ml)):
        if index == 0:
            dv = volume_ml[1] - volume_ml[0]
            dt = timestamps_s[1] - timestamps_s[0]
        elif index == len(volume_ml) - 1:
            dv = volume_ml[-1] - volume_ml[-2]
            dt = timestamps_s[-1] - timestamps_s[-2]
        else:
            dv = volume_ml[index + 1] - volume_ml[index - 1]
            dt = timestamps_s[index + 1] - timestamps_s[index - 1]
        flow_raw.append(max(dv / dt, 0.0))

    return _moving_average(flow_raw, smoothing_window)


def estimate_flow_uncertainty(
    timestamps_s: Sequence[float], ml_per_mm: float, level_sigma_mm: float
) -> list[float]:
    """Approximate sigma(Q) from constant sigma(h) and finite differences."""

    if ml_per_mm <= 0:
        raise ValueError("ml_per_mm must be positive")
    if level_sigma_mm <= 0:
        raise ValueError("level_sigma_mm must be positive")
    _validate_timestamps(timestamps_s)

    sigma_v = ml_per_mm * level_sigma_mm
    sigma_q: list[float] = []
    for index in range(len(timestamps_s)):
        if index == 0:
            dt = timestamps_s[1] - timestamps_s[0]
        elif index == len(timestamps_s) - 1:
            dt = timestamps_s[-1] - timestamps_s[-2]
        else:
            dt = timestamps_s[index + 1] - timestamps_s[index - 1]
        sigma_q.append((math.sqrt(2.0) * sigma_v) / dt)
    return sigma_q


def _estimate_level_noise_mm(level_mm: Sequence[float]) -> float:
    smoothed_level = _moving_average(level_mm, window=5)
    residual = [raw - smooth for raw, smooth in zip(level_mm, smoothed_level, strict=True)]
    return statistics.pstdev(residual) if len(residual) > 1 else 0.0


def evaluate_fusion_quality(
    depth_confidence: Sequence[float],
    volume_ml: Sequence[float],
    level_mm: Sequence[float],
    config: FusionLevelConfig,
) -> FusionQualityFlags:
    if len(depth_confidence) != len(level_mm):
        raise ValueError("depth_confidence and level_mm must have equal length")
    _validate_confidence(depth_confidence)
    if not volume_ml:
        raise ValueError("volume_ml is empty")

    above_threshold = sum(value >= config.min_depth_confidence for value in depth_confidence)
    confidence_ratio = above_threshold / len(depth_confidence)
    level_noise_mm = _estimate_level_noise_mm(level_mm)

    low_depth_confidence = confidence_ratio < config.min_depth_confidence_ratio
    insufficient_volume = volume_ml[-1] < config.min_voided_volume_ml
    noisy_level_signal = level_noise_mm > config.max_level_noise_mm

    if low_depth_confidence and noisy_level_signal:
        status = "reject"
    elif low_depth_confidence or insufficient_volume or noisy_level_signal:
        status = "repeat"
    else:
        status = "valid"

    return FusionQualityFlags(
        low_depth_confidence=low_depth_confidence,
        insufficient_volume=insufficient_volume,
        noisy_level_signal=noisy_level_signal,
        depth_confidence_ratio=confidence_ratio,
        level_noise_mm=level_noise_mm,
        status=status,
    )


def estimate_from_level_series(
    timestamps_s: Sequence[float],
    level_mm: Sequence[float],
    depth_confidence: Sequence[float] | None = None,
    config: FusionLevelConfig | None = None,
) -> FusionEstimationResult:
    cfg = config or FusionLevelConfig()
    if len(timestamps_s) != len(level_mm):
        raise ValueError("timestamps_s and level_mm must have equal length")
    if not level_mm:
        raise ValueError("level_mm is empty")

    _validate_timestamps(timestamps_s)

    if depth_confidence is None:
        confidence = [1.0 for _ in range(len(level_mm))]
    else:
        confidence = list(depth_confidence)
    if len(confidence) != len(level_mm):
        raise ValueError("depth_confidence and level_mm must have equal length")
    _validate_confidence(confidence)

    volume_ml = estimate_volume_curve(level_mm, ml_per_mm=cfg.ml_per_mm)
    flow_ml_s = estimate_flow_curve(
        timestamps_s=timestamps_s,
        volume_ml=volume_ml,
        smoothing_window=cfg.flow_smoothing_window,
    )
    flow_uncertainty_ml_s = estimate_flow_uncertainty(
        timestamps_s=timestamps_s,
        ml_per_mm=cfg.ml_per_mm,
        level_sigma_mm=cfg.level_sigma_mm,
    )
    quality = evaluate_fusion_quality(
        depth_confidence=confidence,
        volume_ml=volume_ml,
        level_mm=level_mm,
        config=cfg,
    )

    return FusionEstimationResult(
        timestamps_s=list(timestamps_s),
        level_mm=list(level_mm),
        depth_confidence=confidence,
        volume_ml=volume_ml,
        flow_ml_s=flow_ml_s,
        flow_uncertainty_ml_s=flow_uncertainty_ml_s,
        quality=quality,
    )
