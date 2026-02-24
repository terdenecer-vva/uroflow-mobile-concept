from __future__ import annotations

import pytest

from uroflow_mobile.session import CaptureSessionConfig, analyze_capture_session


def _base_payload() -> dict[str, object]:
    return {
        "schema_version": "ios_capture_v1",
        "session": {
            "session_id": "session-qa-001",
            "started_at": "2026-02-24T10:00:00Z",
            "mode": "water_impact",
            "calibration": {
                "ml_per_mm": 8.0,
                "min_depth_confidence": 0.6,
            },
        },
        "samples": [
            {
                "t_s": 0.0,
                "depth_level_mm": 0.0,
                "rgb_level_mm": 0.0,
                "depth_confidence": 0.95,
                "motion_norm": 0.02,
                "audio_rms_dbfs": -50.0,
                "roi_valid": True,
            },
            {
                "t_s": 1.0,
                "depth_level_mm": 0.0,
                "rgb_level_mm": 0.0,
                "depth_confidence": 0.95,
                "motion_norm": 0.02,
                "audio_rms_dbfs": -49.0,
                "roi_valid": True,
            },
            {
                "t_s": 2.0,
                "depth_level_mm": 0.0,
                "rgb_level_mm": 0.0,
                "depth_confidence": 0.95,
                "motion_norm": 0.02,
                "audio_rms_dbfs": -35.0,
                "roi_valid": True,
            },
            {
                "t_s": 3.0,
                "depth_level_mm": 5.0,
                "rgb_level_mm": 5.1,
                "depth_confidence": 0.94,
                "motion_norm": 0.03,
                "audio_rms_dbfs": -31.0,
                "roi_valid": True,
            },
            {
                "t_s": 4.0,
                "depth_level_mm": 10.0,
                "rgb_level_mm": 10.2,
                "depth_confidence": 0.92,
                "motion_norm": 0.03,
                "audio_rms_dbfs": -30.0,
                "roi_valid": True,
            },
            {
                "t_s": 5.0,
                "depth_level_mm": 15.0,
                "rgb_level_mm": 15.0,
                "depth_confidence": 0.9,
                "motion_norm": 0.03,
                "audio_rms_dbfs": -30.0,
                "roi_valid": True,
            },
            {
                "t_s": 6.0,
                "depth_level_mm": 20.0,
                "rgb_level_mm": 20.1,
                "depth_confidence": 0.91,
                "motion_norm": 0.03,
                "audio_rms_dbfs": -31.0,
                "roi_valid": True,
            },
            {
                "t_s": 7.0,
                "depth_level_mm": 20.0,
                "rgb_level_mm": 20.1,
                "depth_confidence": 0.91,
                "motion_norm": 0.03,
                "audio_rms_dbfs": -47.0,
                "roi_valid": True,
            },
            {
                "t_s": 8.0,
                "depth_level_mm": 20.0,
                "rgb_level_mm": 20.0,
                "depth_confidence": 0.91,
                "motion_norm": 0.03,
                "audio_rms_dbfs": -48.0,
                "roi_valid": True,
            },
        ],
    }


def test_analyze_capture_session_returns_valid_status_for_clean_signal() -> None:
    analysis = analyze_capture_session(
        _base_payload(),
        config=CaptureSessionConfig(
            ml_per_mm_override=10.0,
            max_level_noise_mm=4.0,
            event_min_audio_delta_db=8.0,
        ),
    )

    assert analysis.session_id == "session-qa-001"
    assert analysis.ml_per_mm == 10.0
    assert analysis.event_detection.detected is True
    assert analysis.event_detection.start_time_s >= 1.0
    assert analysis.event_detection.end_time_s <= 8.0
    assert analysis.summary.voided_volume_ml >= 150.0
    assert analysis.quality.status == "valid"
    assert analysis.quality.score >= 75.0


def test_analyze_capture_session_marks_repeat_for_motion_and_roi_issues() -> None:
    payload = _base_payload()
    samples = payload["samples"]
    assert isinstance(samples, list)

    for index, sample in enumerate(samples):
        sample["motion_norm"] = 0.6
        if index < 5:
            sample["roi_valid"] = False

    analysis = analyze_capture_session(payload)

    assert analysis.quality.status in {"repeat", "reject"}
    assert analysis.quality.high_motion_ratio > 0.9
    assert analysis.quality.roi_valid_ratio < 0.5
    assert any("high_motion_ratio_above_threshold" in reason for reason in analysis.quality.reasons)


def test_analyze_capture_session_raises_for_invalid_payload() -> None:
    payload = _base_payload()
    samples = payload["samples"]
    assert isinstance(samples, list)
    samples[2]["t_s"] = 1.0

    with pytest.raises(ValueError, match="invalid capture payload"):
        analyze_capture_session(payload)
