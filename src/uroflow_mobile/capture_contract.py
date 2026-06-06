from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

SUPPORTED_CAPTURE_MODES = {"water_impact", "jet_in_air", "porcelain_wall"}
SCHEMA_VERSION = "ios_capture_v1"
FEATURE_MANIFEST_VERSION = "mobile_feature_manifest_v0.1"
RUNTIME_ALIGNMENT_SCHEMA_VERSION = "runtime_stream_alignment_v0.1"


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


def _validate_feature_manifest(
    manifest: Any,
    *,
    sample_count: int,
    errors: list[str],
) -> None:
    if manifest is None:
        return
    if not isinstance(manifest, dict):
        errors.append("feature_manifest must be an object when provided")
        return

    if manifest.get("version") != FEATURE_MANIFEST_VERSION:
        errors.append(f"feature_manifest.version must be '{FEATURE_MANIFEST_VERSION}'")

    source = manifest.get("source")
    if not isinstance(source, str) or not source.strip():
        errors.append("feature_manifest.source must be a non-empty string")

    if manifest.get("derivatives_only") is not True:
        errors.append("feature_manifest.derivatives_only must be true")

    manifest_sample_count = manifest.get("sample_count")
    if not isinstance(manifest_sample_count, int) or isinstance(
        manifest_sample_count, bool
    ):
        errors.append("feature_manifest.sample_count must be an integer")
    elif manifest_sample_count != sample_count:
        errors.append("feature_manifest.sample_count must match samples length")

    feature_keys = manifest.get("feature_keys")
    if not isinstance(feature_keys, list) or not feature_keys:
        errors.append("feature_manifest.feature_keys must be a non-empty array")
    else:
        for index, feature_key in enumerate(feature_keys):
            if not isinstance(feature_key, str) or not feature_key.strip():
                errors.append(
                    f"feature_manifest.feature_keys[{index}] must be a non-empty string"
                )

    raw_media = manifest.get("raw_media")
    if not isinstance(raw_media, dict):
        errors.append("feature_manifest.raw_media must be an object")
    else:
        for flag in (
            "store_raw_video",
            "store_raw_audio",
            "upload_raw_video",
            "upload_raw_audio",
        ):
            if raw_media.get(flag) is not False:
                errors.append(f"feature_manifest.raw_media.{flag} must be false")

    privacy = manifest.get("privacy")
    if not isinstance(privacy, dict):
        errors.append("feature_manifest.privacy must be an object")
    else:
        if privacy.get("roi_only") is not True:
            errors.append("feature_manifest.privacy.roi_only must be true")
        if privacy.get("media_scope") != "roi_derivatives_only":
            errors.append(
                "feature_manifest.privacy.media_scope must be 'roi_derivatives_only'"
            )


def _validate_nullable_non_negative_number(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
) -> None:
    if value is None:
        return
    if not _is_finite_number(value) or float(value) < 0:
        errors.append(f"{field_name} must be null or a non-negative finite number")


def _validate_analysis(
    analysis: Any,
    *,
    sample_count: int,
    errors: list[str],
) -> None:
    if analysis is None:
        return
    if not isinstance(analysis, dict):
        errors.append("analysis must be an object when provided")
        return

    runtime_timeline = analysis.get("runtime_timeline")
    runtime_alignment = analysis.get("runtime_alignment")
    runtime_quality = analysis.get("runtime_quality")
    if (
        isinstance(runtime_quality, dict)
        and "timing_gap_warning" in runtime_quality
        and not isinstance(runtime_quality.get("timing_gap_warning"), bool)
    ):
        errors.append("analysis.runtime_quality.timing_gap_warning must be boolean")
    if (
        isinstance(runtime_quality, dict)
        and "alignment_drift_warning" in runtime_quality
        and not isinstance(runtime_quality.get("alignment_drift_warning"), bool)
    ):
        errors.append("analysis.runtime_quality.alignment_drift_warning must be boolean")

    if runtime_timeline is not None:
        _validate_runtime_timeline(
            runtime_timeline,
            sample_count=sample_count,
            errors=errors,
        )

    if runtime_alignment is not None:
        _validate_runtime_alignment(
            runtime_alignment,
            sample_count=sample_count,
            errors=errors,
        )


def _validate_runtime_timeline(
    runtime_timeline: Any,
    *,
    sample_count: int,
    errors: list[str],
) -> None:
    if not isinstance(runtime_timeline, dict):
        errors.append("analysis.runtime_timeline must be an object when provided")
        return

    if runtime_timeline.get("clock_source") != "elapsed_wall_clock_ms":
        errors.append(
            "analysis.runtime_timeline.clock_source must be 'elapsed_wall_clock_ms'"
        )

    timeline_sample_count = runtime_timeline.get("sample_count")
    if not isinstance(timeline_sample_count, int) or isinstance(
        timeline_sample_count, bool
    ):
        errors.append("analysis.runtime_timeline.sample_count must be an integer")
    elif timeline_sample_count != sample_count:
        errors.append(
            "analysis.runtime_timeline.sample_count must match samples length"
        )

    duration_s = runtime_timeline.get("duration_s")
    if not _is_finite_number(duration_s) or float(duration_s) < 0:
        errors.append(
            "analysis.runtime_timeline.duration_s must be a non-negative finite number"
        )

    _validate_nullable_non_negative_number(
        runtime_timeline.get("median_sample_step_s"),
        field_name="analysis.runtime_timeline.median_sample_step_s",
        errors=errors,
    )
    _validate_nullable_non_negative_number(
        runtime_timeline.get("max_sample_gap_s"),
        field_name="analysis.runtime_timeline.max_sample_gap_s",
        errors=errors,
    )
    _validate_nullable_non_negative_number(
        runtime_timeline.get("max_sample_gap_ratio"),
        field_name="analysis.runtime_timeline.max_sample_gap_ratio",
        errors=errors,
    )

    if not isinstance(runtime_timeline.get("monotonic"), bool):
        errors.append("analysis.runtime_timeline.monotonic must be boolean")
    if not isinstance(runtime_timeline.get("gap_warning"), bool):
        errors.append("analysis.runtime_timeline.gap_warning must be boolean")


def _validate_runtime_alignment(
    runtime_alignment: Any,
    *,
    sample_count: int,
    errors: list[str],
) -> None:
    if not isinstance(runtime_alignment, dict):
        errors.append("analysis.runtime_alignment must be an object when provided")
        return

    if runtime_alignment.get("schema_version") != RUNTIME_ALIGNMENT_SCHEMA_VERSION:
        errors.append(
            "analysis.runtime_alignment.schema_version must be "
            f"'{RUNTIME_ALIGNMENT_SCHEMA_VERSION}'"
        )

    aligned_streams = runtime_alignment.get("aligned_streams")
    if not isinstance(aligned_streams, list) or not aligned_streams:
        errors.append("analysis.runtime_alignment.aligned_streams must be a non-empty array")
    else:
        aligned_stream_names = {
            value.strip() for value in aligned_streams if isinstance(value, str)
        }
        if {"samples", "runtime_flow_series"} - aligned_stream_names:
            errors.append(
                "analysis.runtime_alignment.aligned_streams must include "
                "'samples' and 'runtime_flow_series'"
            )

    alignment_sample_count = runtime_alignment.get("sample_count")
    if not isinstance(alignment_sample_count, int) or isinstance(
        alignment_sample_count, bool
    ):
        errors.append("analysis.runtime_alignment.sample_count must be an integer")
    elif alignment_sample_count != sample_count:
        errors.append(
            "analysis.runtime_alignment.sample_count must match samples length"
        )

    paired_sample_count = runtime_alignment.get("paired_sample_count")
    if not isinstance(paired_sample_count, int) or isinstance(paired_sample_count, bool):
        errors.append("analysis.runtime_alignment.paired_sample_count must be an integer")
        paired_sample_count_value: int | None = None
    elif paired_sample_count < 0:
        errors.append("analysis.runtime_alignment.paired_sample_count must be >= 0")
        paired_sample_count_value = None
    else:
        paired_sample_count_value = paired_sample_count

    max_allowed_drift_ms = runtime_alignment.get("max_allowed_drift_ms")
    if not _is_finite_number(max_allowed_drift_ms) or float(max_allowed_drift_ms) <= 0:
        errors.append(
            "analysis.runtime_alignment.max_allowed_drift_ms must be a positive finite number"
        )
        max_allowed_drift_value: float | None = None
    else:
        max_allowed_drift_value = float(max_allowed_drift_ms)

    max_stream_drift_ms = runtime_alignment.get("max_stream_drift_ms")
    _validate_nullable_non_negative_number(
        max_stream_drift_ms,
        field_name="analysis.runtime_alignment.max_stream_drift_ms",
        errors=errors,
    )
    max_stream_drift_value = (
        float(max_stream_drift_ms) if _is_finite_number(max_stream_drift_ms) else None
    )

    drift_warning = runtime_alignment.get("drift_warning")
    if not isinstance(drift_warning, bool):
        errors.append("analysis.runtime_alignment.drift_warning must be boolean")
        return

    if paired_sample_count_value is None or max_allowed_drift_value is None:
        return

    expected_warning = paired_sample_count_value != sample_count or (
        max_stream_drift_value is not None
        and max_stream_drift_value > max_allowed_drift_value
    )
    if drift_warning != expected_warning:
        errors.append(
            "analysis.runtime_alignment.drift_warning must reflect unpaired streams "
            "or max_stream_drift_ms exceeding max_allowed_drift_ms"
        )


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

    sync_id = session.get("sync_id")
    if sync_id is not None and (not isinstance(sync_id, str) or not sync_id.strip()):
        errors.append("session.sync_id must be a non-empty string when provided")

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

    _validate_feature_manifest(
        payload.get("feature_manifest"),
        sample_count=sample_count,
        errors=errors,
    )
    _validate_analysis(
        payload.get("analysis"),
        sample_count=sample_count,
        errors=errors,
    )

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
    sync_id = payload["session"].get("sync_id")
    if isinstance(sync_id, str) and sync_id.strip():
        level_payload["meta"]["sync_id"] = sync_id

    if has_any_rgb:
        level_payload["rgb_level_mm"] = rgb_level_mm

    return level_payload
