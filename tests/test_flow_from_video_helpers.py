from uroflow_mobile.flow_from_video import (
    moving_average,
    rescale_curve_to_volume,
    trapz_integral,
    trim_to_active_region,
)


def test_moving_average_preserves_length() -> None:
    values = [0.0, 2.0, 4.0, 2.0, 0.0]
    smoothed = moving_average(values, window=3)

    assert len(smoothed) == len(values)
    assert smoothed[0] == values[0]
    assert smoothed[2] < values[2]


def test_trim_to_active_region_normalizes_timestamps() -> None:
    timestamps = [10.0, 11.0, 12.0, 13.0, 14.0]
    flow = [0.0, 0.0, 5.0, 4.0, 0.0]

    trimmed_t, trimmed_flow = trim_to_active_region(timestamps, flow, threshold_ml_s=0.5)

    assert trimmed_t[0] == 0.0
    assert trimmed_flow == [0.0, 5.0, 4.0, 0.0]


def test_rescale_curve_to_known_volume() -> None:
    timestamps = [0.0, 1.0, 2.0]
    flow = [0.0, 10.0, 0.0]
    raw_volume = trapz_integral(timestamps, flow)
    assert raw_volume == 10.0

    scaled = rescale_curve_to_volume(timestamps, flow, known_volume_ml=20.0)
    scaled_volume = trapz_integral(timestamps, scaled)
    assert abs(scaled_volume - 20.0) < 1e-9
