from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

SUPPORTED_CAPTURE_MODES = {"water_impact", "jet_in_air", "porcelain_wall"}
SCHEMA_VERSION = "ios_capture_v1"


@dataclass(frozen=True)
class CaptureValidationReport:
    """Validation outcome for iOS capture payload."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    sample_count: int
    roi_valid_ratio: float
    low_depth_confidence_ratio: float


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_finite_number(value: Any) -> bool:
    return _is_number(value) and math.isfinite(float(value))


def _parse_started_at(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False

    candidate = value
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def validate_capture_payload(payload: dict[str, Any]) -> CaptureValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be '{SCHEMA_VERSION}'")

    session = payload.get("session")
    if not isinstance(session, dict):
        errors.append("session object is required")
        session = {}

    session_id = session.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        errors.append("session.session_id must be a non-empty string")

    if not _parse_started_at(session.get("started_at")):
        errors.append("session.started_at must be ISO-8601 timestamp")

    mode = session.get("mode")
    if mode not in SUPPORTED_CAPTURE_MODES:
        errors.append(
            "session.mode must be one of: "
            + ", ".join(sorted(SUPPORTED_CAPTURE_MODES))
        )

    calibration = session.get("calibration")
    if not isinstance(calibration, dict):
        errors.append("session.calibration object is required")
        calibration = {}

    ml_per_mm = calibration.get("ml_per_mm")
    if not _is_finite_number(ml_per_mm) or float(ml_per_mm) <= 0:
        errors.append("session.calibration.ml_per_mm must be a positive number")

    samples = payload.get("samples")
    if not isinstance(samples, list):
        errors.append("samples must be an array")
        samples = []

    if len(samples) < 2:
        errors.append("at least two samples are required")

    previous_t = None
    roi_valid_count = 0
    low_confidence_count = 0

    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            errors.append(f"samples[{index}] must be an object")
            continue

        t_s = sample.get("t_s")
        if not _is_finite_number(t_s):
            errors.append(f"samples[{index}].t_s must be a finite number")
            continue

        t_value = float(t_s)
        if previous_t is not None and t_value <= previous_t:
            errors.append(f"samples[{index}].t_s must be strictly increasing")
        previous_t = t_value

        depth_confidence = sample.get("depth_confidence")
        if not _is_finite_number(depth_confidence):
            errors.append(f"samples[{index}].depth_confidence must be in [0,1]")
            continue

        confidence_value = float(depth_confidence)
        if confidence_value < 0.0 or confidence_value > 1.0:
            errors.append(f"samples[{index}].depth_confidence must be in [0,1]")
        if confidence_value < 0.6:
            low_confidence_count += 1

        roi_valid = sample.get("roi_valid")
        if not isinstance(roi_valid, bool):
            errors.append(f"samples[{index}].roi_valid must be boolean")
        elif roi_valid:
            roi_valid_count += 1

        depth_level = sample.get("depth_level_mm")
        rgb_level = sample.get("rgb_level_mm")

        depth_ok = depth_level is None or _is_finite_number(depth_level)
        rgb_ok = rgb_level is None or _is_finite_number(rgb_level)

        if not depth_ok:
            errors.append(f"samples[{index}].depth_level_mm must be number or null")
        if not rgb_ok:
            errors.append(f"samples[{index}].rgb_level_mm must be number or null")

        if depth_level is None and rgb_level is None:
            errors.append(f"samples[{index}] must include depth_level_mm or rgb_level_mm")

        motion_norm = sample.get("motion_norm")
        if motion_norm is not None and (
            not _is_finite_number(motion_norm) or float(motion_norm) < 0
        ):
            errors.append(f"samples[{index}].motion_norm must be >= 0 when provided")

        audio_rms_dbfs = sample.get("audio_rms_dbfs")
        if audio_rms_dbfs is not None and not _is_finite_number(audio_rms_dbfs):
            errors.append(f"samples[{index}].audio_rms_dbfs must be numeric when provided")

    sample_count = len(samples)
    roi_ratio = roi_valid_count / sample_count if sample_count else 0.0
    low_conf_ratio = low_confidence_count / sample_count if sample_count else 0.0

    if sample_count and roi_ratio < 0.85:
        warnings.append("ROI valid ratio < 0.85; likely repeat measurement")
    if sample_count and low_conf_ratio > 0.25:
        warnings.append("Low depth confidence ratio > 0.25; fallback reliance expected")

    return CaptureValidationReport(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        sample_count=sample_count,
        roi_valid_ratio=roi_ratio,
        low_depth_confidence_ratio=low_conf_ratio,
    )


def capture_to_level_payload(payload: dict[str, Any]) -> dict[str, object]:
    report = validate_capture_payload(payload)
    if not report.valid:
        raise ValueError("invalid capture payload: " + "; ".join(report.errors))

    samples = payload["samples"]
    timestamps_s: list[float] = []
    depth_level_mm: list[float | None] = []
    rgb_level_mm: list[float | None] = []
    depth_confidence: list[float] = []

    for sample in samples:
        timestamps_s.append(float(sample["t_s"]))

        depth_value = sample.get("depth_level_mm")
        depth_level_mm.append(None if depth_value is None else float(depth_value))

        rgb_value = sample.get("rgb_level_mm")
        rgb_level_mm.append(None if rgb_value is None else float(rgb_value))

        depth_confidence.append(float(sample["depth_confidence"]))

    has_any_rgb = any(value is not None for value in rgb_level_mm)

    level_payload: dict[str, object] = {
        "timestamps_s": timestamps_s,
        "depth_level_mm": depth_level_mm,
        "depth_confidence": depth_confidence,
        "meta": {
            "session_id": payload["session"]["session_id"],
            "ml_per_mm": float(payload["session"]["calibration"]["ml_per_mm"]),
        },
    }

    if has_any_rgb:
        level_payload["rgb_level_mm"] = rgb_level_mm

    return level_payload
