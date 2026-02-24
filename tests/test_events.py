from __future__ import annotations

import math

from uroflow_mobile.events import (
    EventDetectionConfig,
    detect_voiding_interval,
    slice_indices_for_interval,
)


def test_detect_voiding_interval_with_audio_roi_flow_fusion() -> None:
    timestamps = [float(index) for index in range(10)]
    flow = [0.0, 0.0, 0.1, 1.8, 2.0, 1.9, 1.5, 0.2, 0.0, 0.0]
    roi = [True for _ in timestamps]
    audio = [-50.0, -49.0, -47.0, -34.0, -31.0, -30.0, -32.0, -40.0, -49.0, -50.0]

    result = detect_voiding_interval(
        timestamps_s=timestamps,
        flow_ml_s=flow,
        roi_valid=roi,
        audio_rms_dbfs=audio,
        config=EventDetectionConfig(
            flow_threshold_ml_s=0.25,
            min_audio_delta_db=8.0,
            min_active_duration_s=1.0,
            max_gap_s=0.5,
            padding_s=0.0,
            min_event_duration_s=1.0,
        ),
    )

    assert result.detected is True
    assert result.method == "audio_roi_flow_fusion"
    assert math.isclose(result.start_time_s, 3.0)
    assert math.isclose(result.end_time_s, 7.0)
    assert result.confidence > 0.5


def test_detect_voiding_interval_falls_back_to_roi_flow_when_audio_missing() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0]
    flow = [0.0, 1.0, 1.2, 0.9, 0.0]
    roi = [True, True, True, True, True]

    result = detect_voiding_interval(
        timestamps_s=timestamps,
        flow_ml_s=flow,
        roi_valid=roi,
        audio_rms_dbfs=None,
        config=EventDetectionConfig(
            flow_threshold_ml_s=0.2,
            min_active_duration_s=1.0,
            max_gap_s=0.0,
            padding_s=0.0,
            min_event_duration_s=1.0,
        ),
    )

    assert result.detected is True
    assert result.method == "roi_flow_fallback"
    assert result.audio_coverage_ratio == 0.0


def test_detect_voiding_interval_returns_not_detected_when_roi_is_invalid() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0]
    flow = [0.0, 1.5, 1.4, 0.0]
    roi = [False, False, False, False]

    result = detect_voiding_interval(
        timestamps_s=timestamps,
        flow_ml_s=flow,
        roi_valid=roi,
        audio_rms_dbfs=None,
    )

    assert result.detected is False
    assert result.confidence == 0.0


def test_slice_indices_for_interval_returns_inclusive_indices() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0]

    indices = slice_indices_for_interval(timestamps, start_time_s=1.0, end_time_s=3.0)

    assert indices == [1, 2, 3]
