from __future__ import annotations

from uroflow_mobile.capture_contract import capture_to_level_payload, validate_capture_payload


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": "ios_capture_v1",
        "session": {
            "session_id": "session-001",
            "sync_id": "sync-001",
            "started_at": "2026-02-23T20:10:00Z",
            "mode": "water_impact",
            "calibration": {
                "ml_per_mm": 8.0,
            },
        },
        "samples": [
            {
                "t_s": 0.0,
                "depth_level_mm": 0.0,
                "rgb_level_mm": 0.0,
                "depth_confidence": 0.95,
                "roi_valid": True,
            },
            {
                "t_s": 0.5,
                "depth_level_mm": 1.8,
                "rgb_level_mm": 1.7,
                "depth_confidence": 0.88,
                "roi_valid": True,
            },
            {
                "t_s": 1.0,
                "depth_level_mm": None,
                "rgb_level_mm": 3.4,
                "depth_confidence": 0.2,
                "roi_valid": True,
            },
        ],
    }


def _valid_feature_manifest(sample_count: int = 3) -> dict[str, object]:
    return {
        "version": "mobile_feature_manifest_v0.1",
        "source": "runtime-audio-imu",
        "derivatives_only": True,
        "sample_count": sample_count,
        "feature_keys": [
            "audio_rms_dbfs",
            "depth_confidence",
            "depth_level_mm",
            "motion_norm",
            "rgb_level_mm",
            "roi_valid",
            "runtime_quality.high_motion_ratio",
            "t_s",
        ],
        "raw_media": {
            "store_raw_video": False,
            "store_raw_audio": False,
            "upload_raw_video": False,
            "upload_raw_audio": False,
        },
        "privacy": {
            "roi_only": True,
            "media_scope": "roi_derivatives_only",
        },
    }


def test_validate_capture_payload_accepts_valid_shape() -> None:
    report = validate_capture_payload(_valid_payload())

    assert report.valid is True
    assert report.errors == []
    assert report.sample_count == 3


def test_validate_capture_payload_rejects_non_monotonic_timestamps() -> None:
    payload = _valid_payload()
    samples = payload["samples"]
    assert isinstance(samples, list)
    samples[2]["t_s"] = 0.4

    report = validate_capture_payload(payload)

    assert report.valid is False
    assert any("strictly increasing" in error for error in report.errors)


def test_capture_to_level_payload_preserves_optional_null_depth() -> None:
    level_payload = capture_to_level_payload(_valid_payload())

    assert level_payload["timestamps_s"] == [0.0, 0.5, 1.0]
    assert level_payload["depth_level_mm"] == [0.0, 1.8, None]
    assert level_payload["rgb_level_mm"] == [0.0, 1.7, 3.4]
    assert level_payload["depth_confidence"] == [0.95, 0.88, 0.2]

    meta = level_payload["meta"]
    assert isinstance(meta, dict)
    assert meta["session_id"] == "session-001"
    assert meta["sync_id"] == "sync-001"
    assert meta["ml_per_mm"] == 8.0


def test_validate_capture_payload_rejects_empty_sync_id_when_present() -> None:
    payload = _valid_payload()
    payload["session"]["sync_id"] = " "  # type: ignore[index]

    report = validate_capture_payload(payload)

    assert report.valid is False
    assert any("session.sync_id" in error for error in report.errors)


def test_validate_capture_payload_allows_optional_analysis_block() -> None:
    payload = _valid_payload()
    payload["analysis"] = {
        "runtime_flow_series": [
            {"t_s": 0.0, "flow_ml_s": 0.0},
            {"t_s": 0.5, "flow_ml_s": 12.1},
        ],
        "runtime_quality": {
            "quality_score": 86.5,
            "quality_status": "valid",
            "roi_valid_ratio": 0.94,
            "low_confidence_ratio": 0.08,
        },
        "runtime_timeline": {
            "clock_source": "elapsed_wall_clock_ms",
            "sample_count": 3,
            "duration_s": 1.0,
            "median_sample_step_s": 0.5,
            "max_sample_gap_s": 0.5,
            "max_sample_gap_ratio": 1.0,
            "monotonic": True,
            "gap_warning": False,
        },
    }

    report = validate_capture_payload(payload)

    assert report.valid is True
    assert report.errors == []


def test_validate_capture_payload_rejects_invalid_runtime_timeline() -> None:
    payload = _valid_payload()
    payload["analysis"] = {
        "runtime_timeline": {
            "clock_source": "device_wall_clock",
            "sample_count": 99,
            "duration_s": -1,
            "median_sample_step_s": "0.5",
            "max_sample_gap_s": -0.1,
            "max_sample_gap_ratio": None,
            "monotonic": "yes",
            "gap_warning": "no",
        },
    }

    report = validate_capture_payload(payload)

    assert report.valid is False
    assert (
        "analysis.runtime_timeline.clock_source must be 'elapsed_wall_clock_ms'"
        in report.errors
    )
    assert "analysis.runtime_timeline.sample_count must match samples length" in report.errors
    assert (
        "analysis.runtime_timeline.duration_s must be a non-negative finite number"
        in report.errors
    )
    assert (
        "analysis.runtime_timeline.median_sample_step_s must be null "
        "or a non-negative finite number"
        in report.errors
    )
    assert (
        "analysis.runtime_timeline.max_sample_gap_s must be null or a non-negative finite number"
        in report.errors
    )
    assert "analysis.runtime_timeline.monotonic must be boolean" in report.errors
    assert "analysis.runtime_timeline.gap_warning must be boolean" in report.errors


def test_validate_capture_payload_allows_derivatives_only_feature_manifest() -> None:
    payload = _valid_payload()
    payload["feature_manifest"] = _valid_feature_manifest()

    report = validate_capture_payload(payload)

    assert report.valid is True
    assert report.errors == []


def test_validate_capture_payload_rejects_feature_manifest_raw_media_upload() -> None:
    payload = _valid_payload()
    manifest = _valid_feature_manifest(sample_count=2)
    manifest["derivatives_only"] = False
    manifest["raw_media"]["upload_raw_audio"] = True  # type: ignore[index]
    payload["feature_manifest"] = manifest

    report = validate_capture_payload(payload)

    assert report.valid is False
    assert "feature_manifest.derivatives_only must be true" in report.errors
    assert "feature_manifest.sample_count must match samples length" in report.errors
    assert "feature_manifest.raw_media.upload_raw_audio must be false" in report.errors
