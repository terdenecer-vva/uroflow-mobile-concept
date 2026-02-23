from __future__ import annotations

from uroflow_mobile.synthetic import (
    SyntheticBenchConfig,
    generate_flow_profile,
    generate_synthetic_bench_series,
    generate_timestamps,
    series_to_level_payload,
)


def _trapz(timestamps_s: list[float], values: list[float]) -> float:
    area = 0.0
    for index in range(1, len(timestamps_s)):
        dt = timestamps_s[index] - timestamps_s[index - 1]
        area += 0.5 * (values[index] + values[index - 1]) * dt
    return area


def test_generate_flow_profile_matches_target_volume() -> None:
    timestamps_s = generate_timestamps(duration_s=12.0, sample_rate_hz=10.0)
    flow_ml_s = generate_flow_profile(
        timestamps_s=timestamps_s,
        profile="bell",
        target_volume_ml=280.0,
    )

    volume_ml = _trapz(timestamps_s, flow_ml_s)
    assert abs(volume_ml - 280.0) < 1e-6


def test_generate_synthetic_bench_series_has_consistent_lengths() -> None:
    series = generate_synthetic_bench_series(
        SyntheticBenchConfig(
            profile="intermittent",
            scenario="reflective_bowl",
            duration_s=16.0,
            sample_rate_hz=8.0,
            target_volume_ml=300.0,
            ml_per_mm=7.5,
            seed=7,
        )
    )

    expected_length = len(series.timestamps_s)

    assert expected_length > 2
    assert len(series.true_flow_ml_s) == expected_length
    assert len(series.true_volume_ml) == expected_length
    assert len(series.true_level_mm) == expected_length
    assert len(series.depth_level_mm) == expected_length
    assert len(series.rgb_level_mm) == expected_length
    assert len(series.depth_confidence) == expected_length
    assert any(confidence < 0.6 for confidence in series.depth_confidence)
    assert abs(series.true_volume_ml[-1] - 300.0) < 1e-6


def test_series_to_level_payload_contains_fusion_keys() -> None:
    series = generate_synthetic_bench_series(SyntheticBenchConfig(seed=13))
    payload = series_to_level_payload(series)

    assert set(payload) == {
        "timestamps_s",
        "depth_level_mm",
        "rgb_level_mm",
        "depth_confidence",
    }
