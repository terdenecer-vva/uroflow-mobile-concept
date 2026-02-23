import math

from uroflow_mobile.fusion import (
    FusionLevelConfig,
    estimate_flow_uncertainty,
    estimate_from_level_series,
    estimate_volume_curve,
    fuse_depth_and_rgb_levels,
)


def test_estimate_volume_curve_uses_baseline_and_clips_negative() -> None:
    levels = [10.0, 12.0, 9.0, 15.0]
    volume = estimate_volume_curve(levels, ml_per_mm=2.0)

    assert volume == [0.0, 4.0, 0.0, 10.0]


def test_fusion_estimation_returns_valid_status_for_clean_signal() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    levels = [0.0, 4.0, 8.0, 12.0, 16.0, 20.0]
    confidence = [0.95, 0.95, 0.95, 0.95, 0.95, 0.95]

    result = estimate_from_level_series(
        timestamps_s=timestamps,
        level_mm=levels,
        depth_confidence=confidence,
        config=FusionLevelConfig(
            ml_per_mm=10.0,
            min_voided_volume_ml=150.0,
            min_depth_confidence=0.6,
            min_depth_confidence_ratio=0.8,
            max_level_noise_mm=3.0,
        ),
    )

    assert result.quality.status == "valid"
    assert result.volume_ml[-1] == 200.0
    assert len(result.flow_ml_s) == len(levels)
    assert len(result.flow_uncertainty_ml_s) == len(levels)


def test_fusion_estimation_marks_repeat_when_volume_is_low() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0]
    levels = [0.0, 2.0, 4.0, 6.0]

    result = estimate_from_level_series(
        timestamps_s=timestamps,
        level_mm=levels,
        config=FusionLevelConfig(ml_per_mm=10.0, min_voided_volume_ml=100.0),
    )

    assert result.volume_ml[-1] == 60.0
    assert result.quality.insufficient_volume is True
    assert result.quality.status == "repeat"


def test_fusion_estimation_marks_reject_when_confidence_low_and_signal_noisy() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    levels = [0.0, 8.0, 1.0, 10.0, 2.0, 12.0]
    confidence = [0.1, 0.2, 0.1, 0.15, 0.2, 0.1]

    result = estimate_from_level_series(
        timestamps_s=timestamps,
        level_mm=levels,
        depth_confidence=confidence,
        config=FusionLevelConfig(
            ml_per_mm=20.0,
            min_voided_volume_ml=50.0,
            min_depth_confidence=0.6,
            min_depth_confidence_ratio=0.8,
            max_level_noise_mm=1.0,
        ),
    )

    assert result.quality.low_depth_confidence is True
    assert result.quality.noisy_level_signal is True
    assert result.quality.status == "reject"


def test_depth_to_rgb_fallback_used_when_confidence_is_low() -> None:
    depth_levels = [0.0, 10.0, 30.0, 40.0]
    rgb_levels = [0.0, 9.5, 19.0, 28.0]
    confidence = [0.95, 0.9, 0.2, 0.1]

    fused, used, missing = fuse_depth_and_rgb_levels(
        depth_level_mm=depth_levels,
        depth_confidence=confidence,
        min_depth_confidence=0.6,
        rgb_level_mm=rgb_levels,
    )

    assert fused == [0.0, 10.0, 19.0, 28.0]
    assert used == [False, False, True, True]
    assert missing is False


def test_fusion_status_can_be_valid_with_rgb_fallback() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0]
    depth_levels = [0.0, 6.0, 18.0, 30.0, 42.0]
    rgb_levels = [0.0, 6.0, 12.0, 18.0, 24.0]
    confidence = [0.95, 0.2, 0.2, 0.2, 0.95]

    result = estimate_from_level_series(
        timestamps_s=timestamps,
        level_mm=depth_levels,
        depth_confidence=confidence,
        rgb_level_mm=rgb_levels,
        config=FusionLevelConfig(
            ml_per_mm=10.0,
            min_voided_volume_ml=150.0,
            min_depth_confidence=0.6,
            min_depth_confidence_ratio=0.8,
            max_level_noise_mm=10.0,
        ),
    )

    assert result.quality.low_depth_confidence is True
    assert result.quality.fallback_to_rgb_used is True
    assert result.quality.status == "valid"


def test_missing_rgb_fallback_with_nonfinite_depth_marks_reject() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0]
    levels = [0.0, 5.0, math.nan, 15.0]
    confidence = [0.95, 0.95, 0.1, 0.95]

    result = estimate_from_level_series(
        timestamps_s=timestamps,
        level_mm=levels,
        depth_confidence=confidence,
        config=FusionLevelConfig(
            ml_per_mm=20.0,
            min_voided_volume_ml=50.0,
            min_depth_confidence=0.6,
            min_depth_confidence_ratio=0.8,
            max_level_noise_mm=10.0,
        ),
    )

    assert result.quality.missing_rgb_fallback is True
    assert result.quality.status == "reject"


def test_estimate_flow_uncertainty_returns_positive_values() -> None:
    timestamps = [0.0, 1.0, 2.0, 4.0]
    sigma_q = estimate_flow_uncertainty(timestamps, ml_per_mm=8.0, level_sigma_mm=1.5)

    assert len(sigma_q) == len(timestamps)
    assert all(value > 0 for value in sigma_q)
