from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .capture_contract import (
    CaptureValidationReport,
    capture_to_level_payload,
    validate_capture_payload,
)
from .events import (
    EventDetectionConfig,
    EventDetectionResult,
    detect_voiding_interval,
    slice_indices_for_interval,
)
from .fusion import FusionEstimationResult, FusionLevelConfig, estimate_from_level_series
from .metrics import UroflowSummary, calculate_uroflow_summary


@dataclass(frozen=True)
class CaptureSessionConfig:
    """Configuration for end-to-end capture-session analysis."""

    ml_per_mm_override: float | None = None
    level_sigma_mm: float = 1.0
    flow_smoothing_window: int = 5
    min_depth_confidence: float = 0.6
    min_depth_confidence_ratio: float = 0.8
    min_voided_volume_ml: float = 150.0
    max_level_noise_mm: float = 2.5

    flow_threshold_ml_s: float = 0.2
    min_pause_s: float = 0.5

    event_flow_threshold_ml_s: float = 0.2
    event_min_audio_delta_db: float = 6.0
    event_audio_noise_percentile: float = 20.0
    event_min_active_duration_s: float = 0.4
    event_max_gap_s: float = 0.3
    event_padding_s: float = 0.2
    event_min_duration_s: float = 1.0

    min_roi_valid_ratio: float = 0.85
    max_low_depth_confidence_ratio: float = 0.25
    high_motion_threshold: float = 0.2
    max_high_motion_ratio: float = 0.15
    audio_clip_dbfs: float = -3.0
    max_audio_clipping_ratio: float = 0.05
    min_representative_volume_ml: float = 150.0
    min_event_confidence: float = 0.5

    valid_quality_score: float = 75.0
    reject_quality_score: float = 40.0


@dataclass(frozen=True)
class CaptureSessionQuality:
    """Quality envelope for a capture session."""

    score: float
    status: str
    reasons: tuple[str, ...]
    roi_valid_ratio: float
    low_depth_confidence_ratio: float
    high_motion_ratio: float
    motion_coverage_ratio: float
    audio_clipping_ratio: float
    audio_coverage_ratio: float


@dataclass(frozen=True)
class CaptureSessionAnalysis:
    """Final analysis artifacts for a validated capture payload."""

    session_id: str
    sync_id: str | None
    mode: str
    ml_per_mm: float
    summary: UroflowSummary
    fusion: FusionEstimationResult
    validation: CaptureValidationReport
    event_detection: EventDetectionResult
    quality: CaptureSessionQuality


def _coerce_optional_numeric_series(values: list[object], field: str) -> list[float]:
    coerced: list[float] = []
    for index, value in enumerate(values):
        if value is None:
            coerced.append(math.nan)
            continue
        try:
            coerced.append(float(value))
        except (TypeError, ValueError) as error:
            raise ValueError(f"{field}[{index}] must be numeric or null") from error
    return coerced


def _extract_optional_series(samples: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for sample in samples:
        value = sample.get(field)
        if value is None:
            continue
        values.append(float(value))
    return values


def _extract_audio_series(samples: list[dict[str, Any]]) -> list[float] | None:
    has_any_audio = any(sample.get("audio_rms_dbfs") is not None for sample in samples)
    if not has_any_audio:
        return None

    audio_series: list[float] = []
    for sample in samples:
        value = sample.get("audio_rms_dbfs")
        if value is None:
            audio_series.append(math.nan)
        else:
            audio_series.append(float(value))
    return audio_series


def _ratio_above(values: list[float], threshold: float) -> float:
    if not values:
        return 0.0
    count = sum(1 for value in values if value > threshold)
    return count / len(values)


def _ratio(total: int, part: int) -> float:
    if total <= 0:
        return 0.0
    return part / total


def _resolve_ml_per_mm(payload: dict[str, Any], config: CaptureSessionConfig) -> float:
    if config.ml_per_mm_override is not None:
        if config.ml_per_mm_override <= 0:
            raise ValueError("ml_per_mm_override must be positive")
        return float(config.ml_per_mm_override)

    calibration = payload["session"]["calibration"]
    return float(calibration["ml_per_mm"])


def _resolve_min_depth_confidence(payload: dict[str, Any], default_value: float) -> float:
    calibration = payload["session"].get("calibration", {})
    calibration_value = calibration.get("min_depth_confidence")

    if calibration_value is None:
        return default_value

    try:
        candidate = float(calibration_value)
    except (TypeError, ValueError):
        return default_value

    if candidate <= 0.0 or candidate > 1.0:
        return default_value

    return candidate


def _slice_fusion_result(
    fusion_result: FusionEstimationResult,
    indices: list[int],
) -> FusionEstimationResult:
    if len(indices) < 2:
        return fusion_result

    base_index = indices[0]
    base_time = fusion_result.timestamps_s[base_index]
    base_volume = fusion_result.volume_ml[base_index]

    rgb_series: list[float] | None = None
    if fusion_result.rgb_level_mm is not None:
        rgb_series = [fusion_result.rgb_level_mm[index] for index in indices]

    return FusionEstimationResult(
        timestamps_s=[fusion_result.timestamps_s[index] - base_time for index in indices],
        level_mm=[fusion_result.level_mm[index] for index in indices],
        depth_level_mm=[fusion_result.depth_level_mm[index] for index in indices],
        depth_confidence=[fusion_result.depth_confidence[index] for index in indices],
        rgb_level_mm=rgb_series,
        used_rgb_fallback=[fusion_result.used_rgb_fallback[index] for index in indices],
        volume_ml=[
            max(fusion_result.volume_ml[index] - base_volume, 0.0)
            for index in indices
        ],
        flow_ml_s=[fusion_result.flow_ml_s[index] for index in indices],
        level_uncertainty_mm=[
            fusion_result.level_uncertainty_mm[index] for index in indices
        ],
        volume_uncertainty_ml=[
            fusion_result.volume_uncertainty_ml[index] for index in indices
        ],
        flow_uncertainty_ml_s=[
            fusion_result.flow_uncertainty_ml_s[index] for index in indices
        ],
        quality=fusion_result.quality,
    )


def _compute_quality(
    summary: UroflowSummary,
    fusion: FusionEstimationResult,
    event_detection: EventDetectionResult,
    validation: CaptureValidationReport,
    samples: list[dict[str, Any]],
    config: CaptureSessionConfig,
) -> CaptureSessionQuality:
    if config.reject_quality_score >= config.valid_quality_score:
        raise ValueError("reject_quality_score must be lower than valid_quality_score")

    motion_values = _extract_optional_series(samples, "motion_norm")
    audio_values = _extract_optional_series(samples, "audio_rms_dbfs")

    high_motion_ratio = _ratio_above(motion_values, config.high_motion_threshold)
    audio_clipping_ratio = _ratio_above(audio_values, config.audio_clip_dbfs)

    motion_coverage_ratio = _ratio(len(samples), len(motion_values))
    audio_coverage_ratio = _ratio(len(samples), len(audio_values))

    score = 100.0
    reasons: list[str] = []

    if validation.roi_valid_ratio < config.min_roi_valid_ratio:
        deficit = (
            config.min_roi_valid_ratio - validation.roi_valid_ratio
        ) / config.min_roi_valid_ratio
        score -= min(25.0, 25.0 * max(deficit, 0.0))
        reasons.append(
            "roi_valid_ratio_below_threshold"
            f"({validation.roi_valid_ratio:.3f} < {config.min_roi_valid_ratio:.3f})"
        )

    if validation.low_depth_confidence_ratio > config.max_low_depth_confidence_ratio:
        excess = (
            validation.low_depth_confidence_ratio - config.max_low_depth_confidence_ratio
        ) / max(1e-9, 1.0 - config.max_low_depth_confidence_ratio)
        score -= min(15.0, 15.0 * max(excess, 0.0))
        reasons.append(
            "low_depth_confidence_ratio_above_threshold"
            f"({validation.low_depth_confidence_ratio:.3f} > "
            f"{config.max_low_depth_confidence_ratio:.3f})"
        )

    if high_motion_ratio > config.max_high_motion_ratio:
        excess = (high_motion_ratio - config.max_high_motion_ratio) / max(
            1e-9, 1.0 - config.max_high_motion_ratio
        )
        score -= min(20.0, 20.0 * max(excess, 0.0))
        reasons.append(
            "high_motion_ratio_above_threshold"
            f"({high_motion_ratio:.3f} > {config.max_high_motion_ratio:.3f})"
        )

    if audio_clipping_ratio > config.max_audio_clipping_ratio:
        excess = (audio_clipping_ratio - config.max_audio_clipping_ratio) / max(
            1e-9, 1.0 - config.max_audio_clipping_ratio
        )
        score -= min(10.0, 10.0 * max(excess, 0.0))
        reasons.append(
            "audio_clipping_ratio_above_threshold"
            f"({audio_clipping_ratio:.3f} > {config.max_audio_clipping_ratio:.3f})"
        )

    if summary.voided_volume_ml < config.min_representative_volume_ml:
        deficit = (
            config.min_representative_volume_ml - summary.voided_volume_ml
        ) / config.min_representative_volume_ml
        score -= min(20.0, 20.0 * max(deficit, 0.0))
        reasons.append(
            "volume_below_representative_threshold"
            f"({summary.voided_volume_ml:.1f} < {config.min_representative_volume_ml:.1f})"
        )

    if not event_detection.detected:
        score -= 20.0
        reasons.append("event_not_detected")
    elif event_detection.confidence < config.min_event_confidence:
        deficit = (
            config.min_event_confidence - event_detection.confidence
        ) / max(config.min_event_confidence, 1e-9)
        score -= min(10.0, 10.0 * max(deficit, 0.0))
        reasons.append(
            "event_confidence_below_threshold"
            f"({event_detection.confidence:.3f} < {config.min_event_confidence:.3f})"
        )

    if fusion.quality.fallback_to_rgb_used:
        score -= 5.0
        reasons.append("rgb_fallback_used")

    if fusion.quality.noisy_level_signal:
        score -= 10.0
        reasons.append("noisy_level_signal")

    if fusion.quality.missing_rgb_fallback:
        score -= 20.0
        reasons.append("missing_rgb_fallback")

    if fusion.quality.status == "repeat":
        score -= 10.0
        reasons.append("fusion_quality_repeat")
    elif fusion.quality.status == "reject":
        score -= 30.0
        reasons.append("fusion_quality_reject")

    score = max(0.0, min(100.0, score))

    if fusion.quality.status == "reject" or score < config.reject_quality_score:
        status = "reject"
    elif fusion.quality.status == "repeat" or score < config.valid_quality_score:
        status = "repeat"
    else:
        status = "valid"

    if not event_detection.detected and status == "valid":
        status = "repeat"

    if not reasons:
        reasons.append("quality_within_limits")

    return CaptureSessionQuality(
        score=score,
        status=status,
        reasons=tuple(reasons),
        roi_valid_ratio=validation.roi_valid_ratio,
        low_depth_confidence_ratio=validation.low_depth_confidence_ratio,
        high_motion_ratio=high_motion_ratio,
        motion_coverage_ratio=motion_coverage_ratio,
        audio_clipping_ratio=audio_clipping_ratio,
        audio_coverage_ratio=audio_coverage_ratio,
    )


def analyze_capture_session(
    payload: dict[str, Any],
    config: CaptureSessionConfig | None = None,
) -> CaptureSessionAnalysis:
    """Run full capture-session analysis from iOS payload to uroflow summary."""

    cfg = config or CaptureSessionConfig()

    validation = validate_capture_payload(payload)
    if not validation.valid:
        raise ValueError("invalid capture payload: " + "; ".join(validation.errors))

    level_payload = capture_to_level_payload(payload)

    timestamps_s = [float(value) for value in level_payload["timestamps_s"]]
    depth_level_mm = _coerce_optional_numeric_series(
        level_payload["depth_level_mm"], field="depth_level_mm"
    )
    depth_confidence = [float(value) for value in level_payload["depth_confidence"]]

    rgb_level_mm_raw = level_payload.get("rgb_level_mm")
    rgb_level_mm: list[float] | None = None
    if isinstance(rgb_level_mm_raw, list):
        rgb_level_mm = _coerce_optional_numeric_series(
            rgb_level_mm_raw,
            field="rgb_level_mm",
        )

    ml_per_mm = _resolve_ml_per_mm(payload, cfg)
    min_depth_confidence = _resolve_min_depth_confidence(payload, cfg.min_depth_confidence)

    fusion_config = FusionLevelConfig(
        ml_per_mm=ml_per_mm,
        level_sigma_mm=cfg.level_sigma_mm,
        flow_smoothing_window=cfg.flow_smoothing_window,
        min_depth_confidence=min_depth_confidence,
        min_depth_confidence_ratio=cfg.min_depth_confidence_ratio,
        min_voided_volume_ml=cfg.min_voided_volume_ml,
        max_level_noise_mm=cfg.max_level_noise_mm,
    )

    fusion_result = estimate_from_level_series(
        timestamps_s=timestamps_s,
        level_mm=depth_level_mm,
        depth_confidence=depth_confidence,
        rgb_level_mm=rgb_level_mm,
        config=fusion_config,
    )

    samples = payload.get("samples", [])
    if not isinstance(samples, list):
        raise ValueError("samples must be an array")

    roi_valid = [bool(sample["roi_valid"]) for sample in samples]
    audio_rms_dbfs = _extract_audio_series(samples)

    event_config = EventDetectionConfig(
        flow_threshold_ml_s=cfg.event_flow_threshold_ml_s,
        min_audio_delta_db=cfg.event_min_audio_delta_db,
        audio_noise_percentile=cfg.event_audio_noise_percentile,
        min_active_duration_s=cfg.event_min_active_duration_s,
        max_gap_s=cfg.event_max_gap_s,
        padding_s=cfg.event_padding_s,
        min_event_duration_s=cfg.event_min_duration_s,
    )
    event_detection = detect_voiding_interval(
        timestamps_s=fusion_result.timestamps_s,
        flow_ml_s=fusion_result.flow_ml_s,
        roi_valid=roi_valid,
        audio_rms_dbfs=audio_rms_dbfs,
        config=event_config,
    )

    if event_detection.detected:
        interval_indices = slice_indices_for_interval(
            fusion_result.timestamps_s,
            start_time_s=event_detection.start_time_s,
            end_time_s=event_detection.end_time_s,
        )
        fusion_for_summary = _slice_fusion_result(fusion_result, interval_indices)
    else:
        fusion_for_summary = fusion_result

    summary = calculate_uroflow_summary(
        timestamps_s=fusion_for_summary.timestamps_s,
        flow_ml_s=fusion_for_summary.flow_ml_s,
        threshold_ml_s=cfg.flow_threshold_ml_s,
        min_pause_s=cfg.min_pause_s,
    )

    quality = _compute_quality(
        summary=summary,
        fusion=fusion_for_summary,
        event_detection=event_detection,
        validation=validation,
        samples=samples,
        config=cfg,
    )

    session = payload["session"]
    return CaptureSessionAnalysis(
        session_id=str(session["session_id"]),
        sync_id=str(session["sync_id"]) if session.get("sync_id") is not None else None,
        mode=str(session["mode"]),
        ml_per_mm=ml_per_mm,
        summary=summary,
        fusion=fusion_for_summary,
        validation=validation,
        event_detection=event_detection,
        quality=quality,
    )
