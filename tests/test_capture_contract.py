from __future__ import annotations

from uroflow_mobile.capture_contract import capture_to_level_payload, validate_capture_payload


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": "ios_capture_v1",
        "session": {
            "session_id": "session-001",
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
    assert meta["ml_per_mm"] == 8.0
