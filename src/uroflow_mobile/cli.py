from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path

from .capture_contract import (
    CaptureValidationReport,
    capture_to_level_payload,
    validate_capture_payload,
)
from .events import EventDetectionResult
from .fusion import (
    FusionEstimationResult,
    FusionLevelConfig,
    FusionQualityFlags,
    estimate_from_level_series,
)
from .gate_metrics import (
    build_gate_metrics,
    load_csv_rows,
    load_mapping_profile,
    select_mapping_profile,
)
from .gate_profile import build_profile_template, load_csv_headers
from .gates import evaluate_release_gates, gate_summary_to_dict
from .metrics import UroflowSummary, calculate_uroflow_summary
from .session import (
    CaptureSessionAnalysis,
    CaptureSessionConfig,
    CaptureSessionQuality,
    analyze_capture_session,
)
from .synthetic import (
    SUPPORTED_PROFILES,
    SyntheticBenchConfig,
    available_scenarios,
    generate_synthetic_bench_series,
    series_to_level_payload,
)


def _parse_roi(value: str | None) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    parts = [item.strip() for item in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("ROI must be in format x,y,w,h")
    try:
        x, y, w, h = (int(part) for part in parts)
    except ValueError as error:
        raise argparse.ArgumentTypeError("ROI values must be integers") from error
    return x, y, w, h


def _coerce_level_values(values: list[object], field_name: str) -> list[float]:
    coerced: list[float] = []
    for index, value in enumerate(values):
        if value is None:
            coerced.append(math.nan)
            continue
        try:
            coerced.append(float(value))
        except (TypeError, ValueError) as error:
            raise ValueError(f"{field_name}[{index}] must be numeric or null") from error
    return coerced


def _summary_to_dict(summary: UroflowSummary) -> dict[str, float | int]:
    return {
        "start_time_s": summary.start_time_s,
        "end_time_s": summary.end_time_s,
        "voiding_time_s": summary.voiding_time_s,
        "flow_time_s": summary.flow_time_s,
        "voided_volume_ml": summary.voided_volume_ml,
        "q_max_ml_s": summary.q_max_ml_s,
        "q_avg_ml_s": summary.q_avg_ml_s,
        "time_to_qmax_s": summary.time_to_qmax_s,
        "interruptions_count": summary.interruptions_count,
    }


def _quality_to_dict(quality: FusionQualityFlags) -> dict[str, float | bool | str]:
    return {
        "low_depth_confidence": quality.low_depth_confidence,
        "insufficient_volume": quality.insufficient_volume,
        "noisy_level_signal": quality.noisy_level_signal,
        "missing_rgb_fallback": quality.missing_rgb_fallback,
        "fallback_to_rgb_used": quality.fallback_to_rgb_used,
        "depth_confidence_ratio": quality.depth_confidence_ratio,
        "fallback_ratio": quality.fallback_ratio,
        "level_noise_mm": quality.level_noise_mm,
        "status": quality.status,
    }


def _validation_to_dict(report: CaptureValidationReport) -> dict[str, object]:
    return {
        "valid": report.valid,
        "errors": report.errors,
        "warnings": report.warnings,
        "sample_count": report.sample_count,
        "roi_valid_ratio": report.roi_valid_ratio,
        "low_depth_confidence_ratio": report.low_depth_confidence_ratio,
    }


def _session_quality_to_dict(quality: CaptureSessionQuality) -> dict[str, object]:
    return {
        "score": quality.score,
        "status": quality.status,
        "reasons": list(quality.reasons),
        "roi_valid_ratio": quality.roi_valid_ratio,
        "low_depth_confidence_ratio": quality.low_depth_confidence_ratio,
        "high_motion_ratio": quality.high_motion_ratio,
        "motion_coverage_ratio": quality.motion_coverage_ratio,
        "audio_clipping_ratio": quality.audio_clipping_ratio,
        "audio_coverage_ratio": quality.audio_coverage_ratio,
    }


def _event_to_dict(event: EventDetectionResult) -> dict[str, object]:
    return {
        "detected": event.detected,
        "start_time_s": event.start_time_s,
        "end_time_s": event.end_time_s,
        "duration_s": event.duration_s,
        "method": event.method,
        "confidence": event.confidence,
        "active_ratio": event.active_ratio,
        "flow_active_ratio": event.flow_active_ratio,
        "roi_valid_ratio": event.roi_valid_ratio,
        "audio_coverage_ratio": event.audio_coverage_ratio,
        "audio_active_ratio": event.audio_active_ratio,
        "audio_threshold_dbfs": event.audio_threshold_dbfs,
    }


def _session_analysis_to_json(
    analysis: CaptureSessionAnalysis,
    input_json: Path,
    config: CaptureSessionConfig,
) -> dict[str, object]:
    return {
        "input_json": str(input_json),
        "session": {
            "session_id": analysis.session_id,
            "sync_id": analysis.sync_id,
            "mode": analysis.mode,
            "ml_per_mm": analysis.ml_per_mm,
        },
        "config": {
            "ml_per_mm_override": config.ml_per_mm_override,
            "level_sigma_mm": config.level_sigma_mm,
            "flow_smoothing_window": config.flow_smoothing_window,
            "min_depth_confidence": config.min_depth_confidence,
            "min_depth_confidence_ratio": config.min_depth_confidence_ratio,
            "min_voided_volume_ml": config.min_voided_volume_ml,
            "max_level_noise_mm": config.max_level_noise_mm,
            "flow_threshold_ml_s": config.flow_threshold_ml_s,
            "min_pause_s": config.min_pause_s,
            "event_flow_threshold_ml_s": config.event_flow_threshold_ml_s,
            "event_min_audio_delta_db": config.event_min_audio_delta_db,
            "event_audio_noise_percentile": config.event_audio_noise_percentile,
            "event_min_active_duration_s": config.event_min_active_duration_s,
            "event_max_gap_s": config.event_max_gap_s,
            "event_padding_s": config.event_padding_s,
            "event_min_duration_s": config.event_min_duration_s,
            "min_roi_valid_ratio": config.min_roi_valid_ratio,
            "max_low_depth_confidence_ratio": config.max_low_depth_confidence_ratio,
            "high_motion_threshold": config.high_motion_threshold,
            "max_high_motion_ratio": config.max_high_motion_ratio,
            "audio_clip_dbfs": config.audio_clip_dbfs,
            "max_audio_clipping_ratio": config.max_audio_clipping_ratio,
            "min_representative_volume_ml": config.min_representative_volume_ml,
            "min_event_confidence": config.min_event_confidence,
            "valid_quality_score": config.valid_quality_score,
            "reject_quality_score": config.reject_quality_score,
        },
        "validation": _validation_to_dict(analysis.validation),
        "event_detection": _event_to_dict(analysis.event_detection),
        "fusion_quality": _quality_to_dict(analysis.fusion.quality),
        "signal_quality": _session_quality_to_dict(analysis.quality),
        "summary": _summary_to_dict(analysis.summary),
        "series_stats": {
            "samples": len(analysis.fusion.timestamps_s),
            "final_volume_ml": analysis.fusion.volume_ml[-1],
            "final_volume_uncertainty_ml": analysis.fusion.volume_uncertainty_ml[-1],
            "mean_level_uncertainty_mm": sum(analysis.fusion.level_uncertainty_mm)
            / len(analysis.fusion.level_uncertainty_mm),
            "mean_volume_uncertainty_ml": sum(analysis.fusion.volume_uncertainty_ml)
            / len(analysis.fusion.volume_uncertainty_ml),
            "mean_flow_uncertainty_ml_s": sum(analysis.fusion.flow_uncertainty_ml_s)
            / len(analysis.fusion.flow_uncertainty_ml_s),
            "used_rgb_fallback_samples": sum(
                1 for used in analysis.fusion.used_rgb_fallback if used
            ),
        },
    }


def _write_curve_csv(path: Path, timestamps_s: list[float], flow_ml_s: list[float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp_s", "flow_ml_s"])
        for timestamp, flow in zip(timestamps_s, flow_ml_s, strict=True):
            writer.writerow([f"{timestamp:.6f}", f"{flow:.6f}"])


def _maybe_write_sha256_manifest(
    output_file: Path,
    sha256_file_arg: str | None,
) -> Path | None:
    if sha256_file_arg is None:
        return None
    manifest_path = Path(sha256_file_arg)
    digest = hashlib.sha256(output_file.read_bytes()).hexdigest()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(f"{digest}  {output_file.name}\n", encoding="utf-8")
    return manifest_path


def _load_api_key_policy_map(
    policy_path: str | None,
) -> dict[str, dict[str, str | None]] | None:
    if policy_path is None:
        return None
    payload = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("API key policy file must contain a JSON object")

    normalized: dict[str, dict[str, str | None]] = {}
    for api_key, raw_policy in payload.items():
        if not isinstance(api_key, str):
            raise ValueError("API key policy keys must be strings")
        if not isinstance(raw_policy, dict):
            raise ValueError("Each API key policy entry must be a JSON object")

        role = raw_policy.get("role")
        site_id = raw_policy.get("site_id")
        operator_id = raw_policy.get("operator_id")
        for field_name, field_value in (
            ("role", role),
            ("site_id", site_id),
            ("operator_id", operator_id),
        ):
            if field_value is not None and not isinstance(field_value, str):
                raise ValueError(f"API key policy field '{field_name}' must be a string or null")
        normalized[api_key] = {
            "role": role,
            "site_id": site_id,
            "operator_id": operator_id,
        }
    return normalized


def _write_fusion_csv(path: Path, estimation: FusionEstimationResult) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "timestamp_s",
                "fused_level_mm",
                "depth_level_mm",
                "rgb_level_mm",
                "depth_confidence",
                "used_rgb_fallback",
                "volume_ml",
                "level_uncertainty_mm",
                "volume_uncertainty_ml",
                "flow_ml_s",
                "flow_uncertainty_ml_s",
            ]
        )
        rgb_series = estimation.rgb_level_mm
        for index, (
            timestamp,
            fused_level,
            depth_level,
            confidence,
            used_fallback,
            volume,
            level_sigma,
            volume_sigma,
            flow,
            sigma_q,
        ) in enumerate(
            zip(
                estimation.timestamps_s,
                estimation.level_mm,
                estimation.depth_level_mm,
                estimation.depth_confidence,
                estimation.used_rgb_fallback,
                estimation.volume_ml,
                estimation.level_uncertainty_mm,
                estimation.volume_uncertainty_ml,
                estimation.flow_ml_s,
                estimation.flow_uncertainty_ml_s,
                strict=True,
            )
        ):
            rgb_value = ""
            if rgb_series is not None:
                rgb_value = f"{rgb_series[index]:.6f}"
            writer.writerow(
                [
                    f"{timestamp:.6f}",
                    f"{fused_level:.6f}",
                    f"{depth_level:.6f}",
                    rgb_value,
                    f"{confidence:.6f}",
                    str(used_fallback).lower(),
                    f"{volume:.6f}",
                    f"{level_sigma:.6f}",
                    f"{volume_sigma:.6f}",
                    f"{flow:.6f}",
                    f"{sigma_q:.6f}",
                ]
            )


def _write_synthetic_csv(
    path: Path,
    timestamps_s: list[float],
    true_flow_ml_s: list[float],
    true_volume_ml: list[float],
    true_level_mm: list[float],
    depth_level_mm: list[float],
    rgb_level_mm: list[float],
    depth_confidence: list[float],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "timestamp_s",
                "true_flow_ml_s",
                "true_volume_ml",
                "true_level_mm",
                "depth_level_mm",
                "rgb_level_mm",
                "depth_confidence",
            ]
        )
        for (
            timestamp,
            true_flow,
            true_volume,
            true_level,
            depth_level,
            rgb_level,
            confidence,
        ) in zip(
            timestamps_s,
            true_flow_ml_s,
            true_volume_ml,
            true_level_mm,
            depth_level_mm,
            rgb_level_mm,
            depth_confidence,
            strict=True,
        ):
            writer.writerow(
                [
                    f"{timestamp:.6f}",
                    f"{true_flow:.6f}",
                    f"{true_volume:.6f}",
                    f"{true_level:.6f}",
                    "" if not math.isfinite(depth_level) else f"{depth_level:.6f}",
                    f"{rgb_level:.6f}",
                    f"{confidence:.6f}",
                ]
            )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uroflow-mobile", description="Concept CLI for smartphone-video uroflow estimation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_video = subparsers.add_parser(
        "analyze-video",
        help="Estimate flow curve Q(t) and uroflow metrics from video.",
    )
    analyze_video.add_argument("video_path", help="Path to smartphone recording.")
    analyze_video.add_argument(
        "--output-csv",
        help="Path for output flow curve CSV. Default: <video_stem>_flow_curve.csv",
    )
    analyze_video.add_argument(
        "--output-json",
        help="Path for output metrics JSON. Default: <video_stem>_summary.json",
    )
    analyze_video.add_argument("--motion-threshold", type=int, default=25)
    analyze_video.add_argument("--min-active-pixels", type=int, default=30)
    analyze_video.add_argument("--smoothing-window-frames", type=int, default=5)
    analyze_video.add_argument("--resize-width", type=int, default=480)
    analyze_video.add_argument("--ml-per-active-pixel-frame", type=float, default=0.002)
    analyze_video.add_argument("--flow-threshold-ml-s", type=float, default=0.2)
    analyze_video.add_argument("--min-pause-s", type=float, default=0.5)
    analyze_video.add_argument("--known-volume-ml", type=float, default=None)
    analyze_video.add_argument("--roi", type=str, default=None, help="ROI in format x,y,w,h")

    analyze_level = subparsers.add_parser(
        "analyze-level-series",
        help="Estimate V(t)/Q(t) from synchronized level/depth-confidence series.",
    )
    analyze_level.add_argument(
        "input_json",
        help=(
            "Path to JSON with timestamps_s and either level_mm or depth_level_mm; "
            "optional rgb_level_mm and depth_confidence"
        ),
    )
    analyze_level.add_argument(
        "--output-csv",
        help="Path for output fusion curve CSV. Default: <input_stem>_fusion_curve.csv",
    )
    analyze_level.add_argument(
        "--output-json",
        help="Path for output fusion summary JSON. Default: <input_stem>_fusion_summary.json",
    )
    analyze_level.add_argument("--ml-per-mm", type=float, required=True)
    analyze_level.add_argument("--level-sigma-mm", type=float, default=1.0)
    analyze_level.add_argument("--flow-smoothing-window", type=int, default=5)
    analyze_level.add_argument("--min-depth-confidence", type=float, default=0.6)
    analyze_level.add_argument("--min-depth-confidence-ratio", type=float, default=0.8)
    analyze_level.add_argument("--min-voided-volume-ml", type=float, default=150.0)
    analyze_level.add_argument("--max-level-noise-mm", type=float, default=2.5)
    analyze_level.add_argument("--flow-threshold-ml-s", type=float, default=0.2)
    analyze_level.add_argument("--min-pause-s", type=float, default=0.5)

    synth = subparsers.add_parser(
        "generate-synthetic-bench",
        help="Generate synthetic Q(t)/level/depth/rgb/confidence bench series.",
    )
    synth.add_argument("--profile", choices=SUPPORTED_PROFILES, default="bell")
    synth.add_argument("--scenario", choices=available_scenarios(), default="quiet_lab")
    synth.add_argument("--duration-s", type=float, default=18.0)
    synth.add_argument("--sample-rate-hz", type=float, default=10.0)
    synth.add_argument("--target-volume-ml", type=float, default=320.0)
    synth.add_argument("--ml-per-mm", type=float, default=8.0)
    synth.add_argument("--seed", type=int, default=42)
    synth.add_argument(
        "--output-json",
        help=(
            "Path for output synthetic level-series JSON. "
            "Default: synthetic_<profile>_<scenario>.json"
        ),
    )
    synth.add_argument(
        "--output-csv",
        help="Path for output synthetic bench CSV. Default: synthetic_<profile>_<scenario>.csv",
    )

    validate_capture = subparsers.add_parser(
        "validate-capture-contract",
        help="Validate iOS capture contract JSON and optionally export level-series JSON.",
    )
    validate_capture.add_argument("input_json", help="Path to iOS capture contract JSON")
    validate_capture.add_argument(
        "--output-level-json",
        help="Optional path to export normalized level-series payload for analyze-level-series",
    )

    analyze_capture = subparsers.add_parser(
        "analyze-capture-session",
        help="Validate capture payload and run complete fusion/summary analysis in one step.",
    )
    analyze_capture.add_argument("input_json", help="Path to iOS capture contract JSON")
    analyze_capture.add_argument(
        "--output-csv",
        help="Path for output fusion curve CSV. Default: <input_stem>_session_curve.csv",
    )
    analyze_capture.add_argument(
        "--output-json",
        help="Path for output session summary JSON. Default: <input_stem>_session_summary.json",
    )
    analyze_capture.add_argument("--ml-per-mm", type=float, default=None)
    analyze_capture.add_argument("--level-sigma-mm", type=float, default=1.0)
    analyze_capture.add_argument("--flow-smoothing-window", type=int, default=5)
    analyze_capture.add_argument("--min-depth-confidence", type=float, default=0.6)
    analyze_capture.add_argument("--min-depth-confidence-ratio", type=float, default=0.8)
    analyze_capture.add_argument("--min-voided-volume-ml", type=float, default=150.0)
    analyze_capture.add_argument("--max-level-noise-mm", type=float, default=2.5)
    analyze_capture.add_argument("--flow-threshold-ml-s", type=float, default=0.2)
    analyze_capture.add_argument("--min-pause-s", type=float, default=0.5)
    analyze_capture.add_argument("--event-flow-threshold-ml-s", type=float, default=0.2)
    analyze_capture.add_argument("--event-min-audio-delta-db", type=float, default=6.0)
    analyze_capture.add_argument("--event-audio-noise-percentile", type=float, default=20.0)
    analyze_capture.add_argument("--event-min-active-duration-s", type=float, default=0.4)
    analyze_capture.add_argument("--event-max-gap-s", type=float, default=0.3)
    analyze_capture.add_argument("--event-padding-s", type=float, default=0.2)
    analyze_capture.add_argument("--event-min-duration-s", type=float, default=1.0)
    analyze_capture.add_argument("--min-roi-valid-ratio", type=float, default=0.85)
    analyze_capture.add_argument("--max-low-depth-confidence-ratio", type=float, default=0.25)
    analyze_capture.add_argument("--high-motion-threshold", type=float, default=0.2)
    analyze_capture.add_argument("--max-high-motion-ratio", type=float, default=0.15)
    analyze_capture.add_argument("--audio-clip-dbfs", type=float, default=-3.0)
    analyze_capture.add_argument("--max-audio-clipping-ratio", type=float, default=0.05)
    analyze_capture.add_argument("--min-representative-volume-ml", type=float, default=150.0)
    analyze_capture.add_argument("--min-event-confidence", type=float, default=0.5)
    analyze_capture.add_argument("--valid-quality-score", type=float, default=75.0)
    analyze_capture.add_argument("--reject-quality-score", type=float, default=40.0)

    evaluate_gates = subparsers.add_parser(
        "evaluate-gates",
        help="Evaluate release gates against metrics JSON.",
    )
    evaluate_gates.add_argument(
        "metrics_json",
        help="Path to JSON with metric values (either flat object or {'metrics': {...}})",
    )
    evaluate_gates.add_argument(
        "--config-json",
        help="Optional path to custom gate config JSON. Default uses package defaults.",
    )
    evaluate_gates.add_argument(
        "--gates",
        nargs="+",
        help="Optional list of gate IDs to evaluate (supports comma-separated values).",
    )
    evaluate_gates.add_argument(
        "--output-json",
        help="Path for output gate summary JSON. Default: <metrics_stem>_gate_summary.json",
    )

    build_gate_metrics_cmd = subparsers.add_parser(
        "build-gate-metrics",
        help="Build gate metrics JSON from clinical/bench CSV files.",
    )
    build_gate_metrics_cmd.add_argument(
        "--clinical-csv",
        help=(
            "Path to clinical comparison CSV "
            "(paired app/reference records or metric/value table)."
        ),
    )
    build_gate_metrics_cmd.add_argument(
        "--bench-csv",
        help="Path to bench CSV (row-level scenarios or metric/value table).",
    )
    build_gate_metrics_cmd.add_argument(
        "--overrides-json",
        help="Optional JSON with extra metrics to merge (flat object or {'metrics': {...}}).",
    )
    build_gate_metrics_cmd.add_argument(
        "--qa-summary-json",
        help=(
            "Optional path to pilot-automation qa_summary.json "
            "(used for metric backfill when CSV-derived metrics are missing)."
        ),
    )
    build_gate_metrics_cmd.add_argument(
        "--tfl-summary-json",
        help=(
            "Optional path to pilot-automation tfl_summary.json "
            "(used for metric backfill when CSV-derived metrics are missing)."
        ),
    )
    build_gate_metrics_cmd.add_argument(
        "--drift-summary-json",
        help=(
            "Optional path to pilot-automation drift_summary.json "
            "(used for metric backfill when CSV-derived metrics are missing)."
        ),
    )
    build_gate_metrics_cmd.add_argument(
        "--g1-eval-json",
        help=(
            "Optional path to pilot-automation g1_eval.json "
            "(used for metric backfill when CSV-derived metrics are missing)."
        ),
    )
    build_gate_metrics_cmd.add_argument(
        "--profile-yaml",
        help=(
            "Optional YAML/JSON mapping profile for column/value remapping "
            "(REDCap/OpenClinica exports)."
        ),
    )
    build_gate_metrics_cmd.add_argument(
        "--profile-name",
        help=(
            "Profile key inside `profiles:` map in mapping file. "
            "Required only when file contains multiple profiles."
        ),
    )
    build_gate_metrics_cmd.add_argument(
        "--output-json",
        help="Path for output metrics JSON. Default: gate_metrics.json",
    )

    generate_profile_cmd = subparsers.add_parser(
        "generate-gate-profile-template",
        help="Generate mapping profile template from CSV headers.",
    )
    generate_profile_cmd.add_argument(
        "--clinical-csv",
        help="Path to clinical CSV export to inspect headers.",
    )
    generate_profile_cmd.add_argument(
        "--bench-csv",
        help="Path to bench CSV export to inspect headers.",
    )
    generate_profile_cmd.add_argument(
        "--profile-name",
        default="clinic_export_v1",
        help="Profile name to place under profiles.<name>.",
    )
    generate_profile_cmd.add_argument(
        "--output-yaml",
        default="gate_profile_template.yaml",
        help="Path for output YAML/JSON profile template.",
    )

    serve_hub_cmd = subparsers.add_parser(
        "serve-clinical-hub",
        help="Run API server for paired app vs reference uroflow measurements.",
    )
    serve_hub_cmd.add_argument(
        "--db-path",
        default="data/clinical_hub.db",
        help="SQLite DB path for paired measurements.",
    )
    serve_hub_cmd.add_argument("--host", default="0.0.0.0")
    serve_hub_cmd.add_argument("--port", type=int, default=8000)
    serve_hub_cmd.add_argument(
        "--api-key",
        help="Optional API key for /api/v1 endpoints. Can also use CLINICAL_HUB_API_KEY env.",
    )
    serve_hub_cmd.add_argument(
        "--api-key-map-json",
        help=(
            "Optional JSON file with per-key role/site policy map. "
            "Can also use CLINICAL_HUB_API_KEYS_FILE env."
        ),
    )

    export_paired_cmd = subparsers.add_parser(
        "export-paired-measurements",
        help="Export paired measurements from clinical hub SQLite DB to CSV.",
    )
    export_paired_cmd.add_argument(
        "--db-path",
        default="data/clinical_hub.db",
        help="SQLite DB path for paired measurements.",
    )
    export_paired_cmd.add_argument(
        "--output-csv",
        required=True,
        help="Target CSV path.",
    )
    export_paired_cmd.add_argument(
        "--sha256-file",
        help="Optional output path for SHA-256 manifest of exported CSV.",
    )

    export_audit_cmd = subparsers.add_parser(
        "export-audit-events",
        help="Export API audit events from clinical hub SQLite DB to CSV.",
    )
    export_audit_cmd.add_argument(
        "--db-path",
        default="data/clinical_hub.db",
        help="SQLite DB path for clinical hub data.",
    )
    export_audit_cmd.add_argument(
        "--output-csv",
        required=True,
        help="Target CSV path for audit events.",
    )
    export_audit_cmd.add_argument(
        "--sha256-file",
        help="Optional output path for SHA-256 manifest of exported CSV.",
    )

    export_capture_cmd = subparsers.add_parser(
        "export-capture-packages",
        help="Export capture packages from clinical hub SQLite DB to CSV.",
    )
    export_capture_cmd.add_argument(
        "--db-path",
        default="data/clinical_hub.db",
        help="SQLite DB path for clinical hub data.",
    )
    export_capture_cmd.add_argument(
        "--output-csv",
        required=True,
        help="Target CSV path for capture packages.",
    )
    export_capture_cmd.add_argument(
        "--sha256-file",
        help="Optional output path for SHA-256 manifest of exported CSV.",
    )

    export_pilot_reports_cmd = subparsers.add_parser(
        "export-pilot-automation-reports",
        help="Export pilot automation reports from clinical hub SQLite DB to CSV.",
    )
    export_pilot_reports_cmd.add_argument(
        "--db-path",
        default="data/clinical_hub.db",
        help="SQLite DB path for clinical hub data.",
    )
    export_pilot_reports_cmd.add_argument(
        "--output-csv",
        required=True,
        help="Target CSV path for pilot automation reports.",
    )
    export_pilot_reports_cmd.add_argument(
        "--sha256-file",
        help="Optional output path for SHA-256 manifest of exported CSV.",
    )

    compare_paired_cmd = subparsers.add_parser(
        "summarize-paired-measurements",
        help="Build method-comparison summary for app vs reference measurements.",
    )
    compare_paired_cmd.add_argument(
        "--db-path",
        default="data/clinical_hub.db",
        help="SQLite DB path for paired measurements.",
    )
    compare_paired_cmd.add_argument(
        "--output-json",
        required=True,
        help="Target JSON path for method-comparison summary.",
    )
    compare_paired_cmd.add_argument("--site-id", help="Optional site filter.")
    compare_paired_cmd.add_argument("--subject-id", help="Optional subject filter.")
    compare_paired_cmd.add_argument(
        "--platform",
        choices=["ios", "android"],
        help="Optional platform filter.",
    )
    compare_paired_cmd.add_argument(
        "--capture-mode",
        choices=["water_impact", "jet_in_air_assist", "fallback_non_water"],
        help="Optional capture mode filter.",
    )
    compare_paired_cmd.add_argument(
        "--quality-status",
        choices=["valid", "repeat", "reject", "all"],
        default="valid",
        help="Quality status subset for summary (default: valid).",
    )

    return parser


def _handle_analyze_video(args: argparse.Namespace) -> int:
    from .flow_from_video import VideoFlowConfig, estimate_flow_curve_from_video

    video_path = Path(args.video_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    roi = _parse_roi(args.roi)
    config = VideoFlowConfig(
        motion_threshold=args.motion_threshold,
        min_active_pixels=args.min_active_pixels,
        smoothing_window_frames=args.smoothing_window_frames,
        resize_width=args.resize_width,
        ml_per_active_pixel_per_frame=args.ml_per_active_pixel_frame,
        flow_threshold_ml_s=args.flow_threshold_ml_s,
        min_pause_s=args.min_pause_s,
        roi=roi,
        known_volume_ml=args.known_volume_ml,
    )

    timestamps_s, flow_ml_s, fps = estimate_flow_curve_from_video(video_path, config=config)
    summary = calculate_uroflow_summary(
        timestamps_s=timestamps_s,
        flow_ml_s=flow_ml_s,
        threshold_ml_s=config.flow_threshold_ml_s,
        min_pause_s=config.min_pause_s,
    )

    output_csv = Path(args.output_csv) if args.output_csv else video_path.with_name(
        f"{video_path.stem}_flow_curve.csv"
    )
    output_json = Path(args.output_json) if args.output_json else video_path.with_name(
        f"{video_path.stem}_summary.json"
    )

    _write_curve_csv(output_csv, timestamps_s, flow_ml_s)
    output_json.write_text(
        json.dumps(
            {
                "video_path": str(video_path),
                "fps": fps,
                "config": {
                    "motion_threshold": config.motion_threshold,
                    "min_active_pixels": config.min_active_pixels,
                    "smoothing_window_frames": config.smoothing_window_frames,
                    "resize_width": config.resize_width,
                    "ml_per_active_pixel_per_frame": config.ml_per_active_pixel_per_frame,
                    "flow_threshold_ml_s": config.flow_threshold_ml_s,
                    "min_pause_s": config.min_pause_s,
                    "roi": config.roi,
                    "known_volume_ml": config.known_volume_ml,
                },
                "summary": _summary_to_dict(summary),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Video analyzed: {video_path}")
    print(f"Flow curve CSV: {output_csv}")
    print(f"Summary JSON: {output_json}")
    print(f"Qmax: {summary.q_max_ml_s:.2f} ml/s")
    print(f"Qavg: {summary.q_avg_ml_s:.2f} ml/s")
    print(f"Voided volume: {summary.voided_volume_ml:.2f} ml")
    print(f"Voiding time: {summary.voiding_time_s:.2f} s")
    print(f"Interruptions: {summary.interruptions_count}")
    return 0


def _load_level_series(
    path: Path,
) -> tuple[list[float], list[float], list[float] | None, list[float] | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    timestamps_raw = payload.get("timestamps_s")
    if timestamps_raw is None:
        raise ValueError("input JSON must include timestamps_s")

    depth_levels_raw = payload.get("depth_level_mm")
    if depth_levels_raw is None:
        depth_levels_raw = payload.get("level_mm")
    if depth_levels_raw is None:
        raise ValueError("input JSON must include level_mm or depth_level_mm")

    timestamps_s = [float(value) for value in timestamps_raw]
    depth_level_mm = _coerce_level_values(depth_levels_raw, "depth_level_mm")

    confidence_raw = payload.get("depth_confidence")
    depth_confidence = None
    if confidence_raw is not None:
        depth_confidence = [float(value) for value in confidence_raw]

    rgb_levels_raw = payload.get("rgb_level_mm")
    rgb_level_mm = None
    if rgb_levels_raw is not None:
        rgb_level_mm = _coerce_level_values(rgb_levels_raw, "rgb_level_mm")

    return timestamps_s, depth_level_mm, depth_confidence, rgb_level_mm


def _handle_analyze_level_series(args: argparse.Namespace) -> int:
    input_json = Path(args.input_json)
    if not input_json.exists():
        raise FileNotFoundError(input_json)

    timestamps_s, depth_level_mm, depth_confidence, rgb_level_mm = _load_level_series(input_json)
    config = FusionLevelConfig(
        ml_per_mm=args.ml_per_mm,
        level_sigma_mm=args.level_sigma_mm,
        flow_smoothing_window=args.flow_smoothing_window,
        min_depth_confidence=args.min_depth_confidence,
        min_depth_confidence_ratio=args.min_depth_confidence_ratio,
        min_voided_volume_ml=args.min_voided_volume_ml,
        max_level_noise_mm=args.max_level_noise_mm,
    )

    estimation = estimate_from_level_series(
        timestamps_s=timestamps_s,
        level_mm=depth_level_mm,
        depth_confidence=depth_confidence,
        config=config,
        rgb_level_mm=rgb_level_mm,
    )
    summary = calculate_uroflow_summary(
        timestamps_s=estimation.timestamps_s,
        flow_ml_s=estimation.flow_ml_s,
        threshold_ml_s=args.flow_threshold_ml_s,
        min_pause_s=args.min_pause_s,
    )

    output_csv = Path(args.output_csv) if args.output_csv else input_json.with_name(
        f"{input_json.stem}_fusion_curve.csv"
    )
    output_json = Path(args.output_json) if args.output_json else input_json.with_name(
        f"{input_json.stem}_fusion_summary.json"
    )

    _write_fusion_csv(output_csv, estimation)

    output_json.write_text(
        json.dumps(
            {
                "input_json": str(input_json),
                "config": {
                    "ml_per_mm": config.ml_per_mm,
                    "level_sigma_mm": config.level_sigma_mm,
                    "flow_smoothing_window": config.flow_smoothing_window,
                    "min_depth_confidence": config.min_depth_confidence,
                    "min_depth_confidence_ratio": config.min_depth_confidence_ratio,
                    "min_voided_volume_ml": config.min_voided_volume_ml,
                    "max_level_noise_mm": config.max_level_noise_mm,
                    "flow_threshold_ml_s": args.flow_threshold_ml_s,
                    "min_pause_s": args.min_pause_s,
                },
                "quality": _quality_to_dict(estimation.quality),
                "summary": _summary_to_dict(summary),
                "series_stats": {
                    "samples": len(estimation.timestamps_s),
                    "final_volume_ml": estimation.volume_ml[-1],
                    "final_volume_uncertainty_ml": estimation.volume_uncertainty_ml[-1],
                    "mean_level_uncertainty_mm": sum(estimation.level_uncertainty_mm)
                    / len(estimation.level_uncertainty_mm),
                    "mean_volume_uncertainty_ml": sum(estimation.volume_uncertainty_ml)
                    / len(estimation.volume_uncertainty_ml),
                    "mean_flow_uncertainty_ml_s": sum(estimation.flow_uncertainty_ml_s)
                    / len(estimation.flow_uncertainty_ml_s),
                    "used_rgb_fallback_samples": sum(
                        1 for used in estimation.used_rgb_fallback if used
                    ),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Level series analyzed: {input_json}")
    print(f"Fusion curve CSV: {output_csv}")
    print(f"Summary JSON: {output_json}")
    print(f"Quality status: {estimation.quality.status}")
    print(f"RGB fallback used: {estimation.quality.fallback_to_rgb_used}")
    print(f"Qmax: {summary.q_max_ml_s:.2f} ml/s")
    print(f"Qavg: {summary.q_avg_ml_s:.2f} ml/s")
    print(f"Voided volume: {summary.voided_volume_ml:.2f} ml")
    return 0


def _handle_generate_synthetic_bench(args: argparse.Namespace) -> int:
    config = SyntheticBenchConfig(
        profile=args.profile,
        scenario=args.scenario,
        duration_s=args.duration_s,
        sample_rate_hz=args.sample_rate_hz,
        target_volume_ml=args.target_volume_ml,
        ml_per_mm=args.ml_per_mm,
        seed=args.seed,
    )
    series = generate_synthetic_bench_series(config)
    summary = calculate_uroflow_summary(
        timestamps_s=series.timestamps_s,
        flow_ml_s=series.true_flow_ml_s,
    )

    default_stem = f"synthetic_{args.profile}_{args.scenario}"
    output_json = Path(args.output_json) if args.output_json else Path(f"{default_stem}.json")
    output_csv = Path(args.output_csv) if args.output_csv else Path(f"{default_stem}.csv")

    level_payload = series_to_level_payload(series)
    depth_values = series.depth_level_mm
    level_payload["depth_level_mm"] = [
        None if not math.isfinite(value) else value for value in depth_values
    ]
    level_payload["meta"] = {
        "generator": "generate-synthetic-bench",
        "profile": config.profile,
        "scenario": config.scenario,
        "ml_per_mm": config.ml_per_mm,
        "target_volume_ml": config.target_volume_ml,
        "seed": config.seed,
        "true_summary": _summary_to_dict(summary),
    }
    output_json.write_text(
        json.dumps(level_payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    _write_synthetic_csv(
        path=output_csv,
        timestamps_s=series.timestamps_s,
        true_flow_ml_s=series.true_flow_ml_s,
        true_volume_ml=series.true_volume_ml,
        true_level_mm=series.true_level_mm,
        depth_level_mm=series.depth_level_mm,
        rgb_level_mm=series.rgb_level_mm,
        depth_confidence=series.depth_confidence,
    )

    print(f"Synthetic bench generated: profile={config.profile}, scenario={config.scenario}")
    print(f"Level-series JSON: {output_json}")
    print(f"Bench CSV: {output_csv}")
    print(f"True Qmax: {summary.q_max_ml_s:.2f} ml/s")
    print(f"True volume: {summary.voided_volume_ml:.2f} ml")
    return 0


def _handle_validate_capture_contract(args: argparse.Namespace) -> int:
    input_json = Path(args.input_json)
    if not input_json.exists():
        raise FileNotFoundError(input_json)

    payload = json.loads(input_json.read_text(encoding="utf-8"))
    report = validate_capture_payload(payload)

    if not report.valid:
        print(f"Capture contract INVALID: {input_json}")
        for error in report.errors:
            print(f"ERROR: {error}")
        for warning in report.warnings:
            print(f"WARNING: {warning}")
        return 1

    print(f"Capture contract valid: {input_json}")
    print(f"Samples: {report.sample_count}")
    print(f"ROI valid ratio: {report.roi_valid_ratio:.3f}")
    print(f"Low depth confidence ratio: {report.low_depth_confidence_ratio:.3f}")
    for warning in report.warnings:
        print(f"WARNING: {warning}")

    if args.output_level_json:
        output_level_json = Path(args.output_level_json)
        level_payload = capture_to_level_payload(payload)
        output_level_json.write_text(
            json.dumps(level_payload, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        print(f"Level-series JSON exported: {output_level_json}")

    return 0


def _handle_analyze_capture_session(args: argparse.Namespace) -> int:
    input_json = Path(args.input_json)
    if not input_json.exists():
        raise FileNotFoundError(input_json)

    payload = json.loads(input_json.read_text(encoding="utf-8"))
    session_config = CaptureSessionConfig(
        ml_per_mm_override=args.ml_per_mm,
        level_sigma_mm=args.level_sigma_mm,
        flow_smoothing_window=args.flow_smoothing_window,
        min_depth_confidence=args.min_depth_confidence,
        min_depth_confidence_ratio=args.min_depth_confidence_ratio,
        min_voided_volume_ml=args.min_voided_volume_ml,
        max_level_noise_mm=args.max_level_noise_mm,
        flow_threshold_ml_s=args.flow_threshold_ml_s,
        min_pause_s=args.min_pause_s,
        event_flow_threshold_ml_s=args.event_flow_threshold_ml_s,
        event_min_audio_delta_db=args.event_min_audio_delta_db,
        event_audio_noise_percentile=args.event_audio_noise_percentile,
        event_min_active_duration_s=args.event_min_active_duration_s,
        event_max_gap_s=args.event_max_gap_s,
        event_padding_s=args.event_padding_s,
        event_min_duration_s=args.event_min_duration_s,
        min_roi_valid_ratio=args.min_roi_valid_ratio,
        max_low_depth_confidence_ratio=args.max_low_depth_confidence_ratio,
        high_motion_threshold=args.high_motion_threshold,
        max_high_motion_ratio=args.max_high_motion_ratio,
        audio_clip_dbfs=args.audio_clip_dbfs,
        max_audio_clipping_ratio=args.max_audio_clipping_ratio,
        min_representative_volume_ml=args.min_representative_volume_ml,
        min_event_confidence=args.min_event_confidence,
        valid_quality_score=args.valid_quality_score,
        reject_quality_score=args.reject_quality_score,
    )

    analysis = analyze_capture_session(payload, config=session_config)

    output_csv = Path(args.output_csv) if args.output_csv else input_json.with_name(
        f"{input_json.stem}_session_curve.csv"
    )
    output_json = Path(args.output_json) if args.output_json else input_json.with_name(
        f"{input_json.stem}_session_summary.json"
    )

    _write_fusion_csv(output_csv, analysis.fusion)
    output_json.write_text(
        json.dumps(
            _session_analysis_to_json(analysis, input_json=input_json, config=session_config),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Capture session analyzed: {input_json}")
    print(f"Fusion curve CSV: {output_csv}")
    print(f"Session summary JSON: {output_json}")
    print(f"Session ID: {analysis.session_id}")
    if analysis.sync_id is not None:
        print(f"Sync ID: {analysis.sync_id}")
    print(
        f"Event interval: {analysis.event_detection.start_time_s:.2f}s -> "
        f"{analysis.event_detection.end_time_s:.2f}s"
    )
    print(f"Event confidence: {analysis.event_detection.confidence:.2f}")
    print(f"Quality status: {analysis.quality.status}")
    print(f"Quality score: {analysis.quality.score:.1f}")
    print(f"Qmax: {analysis.summary.q_max_ml_s:.2f} ml/s")
    print(f"Qavg: {analysis.summary.q_avg_ml_s:.2f} ml/s")
    print(f"Voided volume: {analysis.summary.voided_volume_ml:.2f} ml")
    return 0


def _parse_gate_names(raw_values: list[str] | None) -> list[str] | None:
    if raw_values is None:
        return None
    parsed: list[str] = []
    for value in raw_values:
        for gate_name in value.split(","):
            clean_name = gate_name.strip()
            if clean_name:
                parsed.append(clean_name)
    return parsed or None


def _load_metrics_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("metrics JSON must be an object")

    nested = payload.get("metrics")
    if isinstance(nested, dict):
        return nested
    return payload


def _handle_evaluate_gates(args: argparse.Namespace) -> int:
    metrics_path = Path(args.metrics_json)
    if not metrics_path.exists():
        raise FileNotFoundError(metrics_path)

    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = _load_metrics_payload(metrics_payload)

    config: dict[str, object] | None = None
    config_path: Path | None = None
    if args.config_json:
        config_path = Path(args.config_json)
        if not config_path.exists():
            raise FileNotFoundError(config_path)
        loaded_config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(loaded_config, dict):
            raise ValueError("gate config JSON must be an object")
        config = loaded_config

    selected_gates = _parse_gate_names(args.gates)
    summary = evaluate_release_gates(metrics=metrics, config=config, gates=selected_gates)
    payload = gate_summary_to_dict(summary)
    payload["metrics_path"] = str(metrics_path)
    if config_path is not None:
        payload["config_path"] = str(config_path)

    output_json = Path(args.output_json) if args.output_json else metrics_path.with_name(
        f"{metrics_path.stem}_gate_summary.json"
    )
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Release gates evaluated: {metrics_path}")
    print(f"Gate summary JSON: {output_json}")
    print(f"Config version: {summary.config_version}")
    for gate_result in summary.gate_results:
        status = "PASS" if gate_result.passed else "FAIL"
        print(f"{gate_result.gate}: {status}")
        for rule in gate_result.rule_results:
            if not rule.passed:
                print(f"  - {rule.rule_id}: {rule.reason}")
    print(f"Overall status: {'PASS' if summary.passed else 'FAIL'}")
    return 0 if summary.passed else 1


def _handle_build_gate_metrics(args: argparse.Namespace) -> int:
    if (
        not args.clinical_csv
        and not args.bench_csv
        and not args.overrides_json
        and not args.qa_summary_json
        and not args.tfl_summary_json
        and not args.drift_summary_json
        and not args.g1_eval_json
    ):
        raise ValueError(
            "at least one source must be provided: --clinical-csv, --bench-csv, "
            "--overrides-json, --qa-summary-json, --tfl-summary-json, "
            "--drift-summary-json, or --g1-eval-json"
        )

    clinical_rows: list[dict[str, object]] | None = None
    if args.clinical_csv:
        clinical_path = Path(args.clinical_csv)
        if not clinical_path.exists():
            raise FileNotFoundError(clinical_path)
        clinical_rows = load_csv_rows(clinical_path)

    bench_rows: list[dict[str, object]] | None = None
    if args.bench_csv:
        bench_path = Path(args.bench_csv)
        if not bench_path.exists():
            raise FileNotFoundError(bench_path)
        bench_rows = load_csv_rows(bench_path)

    overrides: dict[str, object] | None = None
    if args.overrides_json:
        overrides_path = Path(args.overrides_json)
        if not overrides_path.exists():
            raise FileNotFoundError(overrides_path)
        overrides_payload = json.loads(overrides_path.read_text(encoding="utf-8"))
        overrides = _load_metrics_payload(overrides_payload)

    def _load_json_object(path_value: str | None, label: str) -> dict[str, object] | None:
        if not path_value:
            return None
        path = Path(path_value)
        if not path.exists():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{label} JSON must be an object")
        return payload

    qa_summary = _load_json_object(args.qa_summary_json, "qa_summary")
    tfl_summary = _load_json_object(args.tfl_summary_json, "tfl_summary")
    drift_summary = _load_json_object(args.drift_summary_json, "drift_summary")
    g1_eval = _load_json_object(args.g1_eval_json, "g1_eval")

    mapping_profile: dict[str, object] | None = None
    profile_name_resolved: str | None = None
    if args.profile_name and not args.profile_yaml:
        raise ValueError("--profile-name requires --profile-yaml")
    if args.profile_yaml:
        profile_path = Path(args.profile_yaml)
        profile_document = load_mapping_profile(profile_path)
        profile_name_resolved, mapping_profile = select_mapping_profile(
            profile_document,
            profile_name=args.profile_name,
        )

    metrics = build_gate_metrics(
        clinical_rows=clinical_rows,
        bench_rows=bench_rows,
        mapping_profile=mapping_profile,
        qa_summary=qa_summary,
        tfl_summary=tfl_summary,
        drift_summary=drift_summary,
        g1_eval=g1_eval,
        overrides=overrides,
    )
    if not metrics:
        raise ValueError("no metrics could be derived from the provided sources")

    output_json = Path(args.output_json) if args.output_json else Path("gate_metrics.json")
    payload = {
        "metrics": metrics,
        "sources": {
            "clinical_csv": args.clinical_csv,
            "bench_csv": args.bench_csv,
            "overrides_json": args.overrides_json,
            "profile_yaml": args.profile_yaml,
            "profile_name": profile_name_resolved,
            "qa_summary_json": args.qa_summary_json,
            "tfl_summary_json": args.tfl_summary_json,
            "drift_summary_json": args.drift_summary_json,
            "g1_eval_json": args.g1_eval_json,
        },
    }
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"Gate metrics built: {output_json}")
    print(f"Metric count: {len(metrics)}")
    print(", ".join(sorted(metrics)))
    return 0


def _handle_generate_gate_profile_template(args: argparse.Namespace) -> int:
    if not args.clinical_csv and not args.bench_csv:
        raise ValueError("at least one source is required: --clinical-csv or --bench-csv")

    clinical_headers: list[str] | None = None
    if args.clinical_csv:
        clinical_path = Path(args.clinical_csv)
        if not clinical_path.exists():
            raise FileNotFoundError(clinical_path)
        clinical_headers = load_csv_headers(clinical_path)

    bench_headers: list[str] | None = None
    if args.bench_csv:
        bench_path = Path(args.bench_csv)
        if not bench_path.exists():
            raise FileNotFoundError(bench_path)
        bench_headers = load_csv_headers(bench_path)

    template = build_profile_template(
        profile_name=args.profile_name,
        clinical_headers=clinical_headers,
        bench_headers=bench_headers,
    )

    output_path = Path(args.output_yaml)
    suffix = output_path.suffix.lower()
    if suffix == ".json":
        output_path.write_text(
            json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    else:
        try:
            import yaml
        except ModuleNotFoundError as error:
            raise ModuleNotFoundError(
                "PyYAML is required for YAML output. Install package 'PyYAML'."
            ) from error
        output_path.write_text(
            yaml.safe_dump(template, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    profile = template["profiles"][args.profile_name]
    assert isinstance(profile, dict)
    clinical = profile.get("clinical", {})
    bench = profile.get("bench", {})
    clinical_map = clinical.get("column_map", {})
    bench_map = bench.get("column_map", {})

    print(f"Profile template generated: {output_path}")
    print(f"Profile name: {args.profile_name}")
    print(f"Clinical headers: {len(clinical_headers or [])}")
    print(f"Bench headers: {len(bench_headers or [])}")
    clinical_mapping_count = len(clinical_map) if isinstance(clinical_map, dict) else 0
    bench_mapping_count = len(bench_map) if isinstance(bench_map, dict) else 0
    print(f"Suggested clinical mappings: {clinical_mapping_count}")
    print(f"Suggested bench mappings: {bench_mapping_count}")
    return 0


def _handle_serve_clinical_hub(args: argparse.Namespace) -> int:
    from .clinical_hub import create_clinical_hub_app

    try:
        import uvicorn
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "uvicorn is required to run serve-clinical-hub. "
            "Install with: pip install -e '.[clinical-api]'"
        ) from error

    db_path = Path(args.db_path)
    api_key = args.api_key or os.getenv("CLINICAL_HUB_API_KEY")
    api_key_map_path = args.api_key_map_json or os.getenv("CLINICAL_HUB_API_KEYS_FILE")
    api_key_policy_map = _load_api_key_policy_map(api_key_map_path)
    app = create_clinical_hub_app(
        db_path=db_path,
        api_key=api_key,
        api_key_policy_map=api_key_policy_map,
    )
    if api_key_policy_map and api_key:
        print("Clinical Hub API key protection: enabled (policy map + shared fallback)")
    elif api_key_policy_map:
        print("Clinical Hub API key protection: enabled (policy map)")
    elif api_key:
        print("Clinical Hub API key protection: enabled (shared key)")
    else:
        print("Clinical Hub API key protection: disabled")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _handle_export_paired_measurements(args: argparse.Namespace) -> int:
    from .clinical_hub import export_paired_measurements_to_csv

    db_path = Path(args.db_path)
    output_csv = Path(args.output_csv)
    row_count = export_paired_measurements_to_csv(db_path=db_path, output_csv=output_csv)
    manifest_path = _maybe_write_sha256_manifest(output_csv, args.sha256_file)
    print(f"Paired measurements exported: {output_csv}")
    print(f"Rows exported: {row_count}")
    if manifest_path is not None:
        print(f"SHA-256 manifest: {manifest_path}")
    return 0


def _handle_export_audit_events(args: argparse.Namespace) -> int:
    from .clinical_hub import export_audit_events_to_csv

    db_path = Path(args.db_path)
    output_csv = Path(args.output_csv)
    row_count = export_audit_events_to_csv(db_path=db_path, output_csv=output_csv)
    manifest_path = _maybe_write_sha256_manifest(output_csv, args.sha256_file)
    print(f"Audit events exported: {output_csv}")
    print(f"Rows exported: {row_count}")
    if manifest_path is not None:
        print(f"SHA-256 manifest: {manifest_path}")
    return 0


def _handle_export_capture_packages(args: argparse.Namespace) -> int:
    from .clinical_hub import export_capture_packages_to_csv

    db_path = Path(args.db_path)
    output_csv = Path(args.output_csv)
    row_count = export_capture_packages_to_csv(db_path=db_path, output_csv=output_csv)
    manifest_path = _maybe_write_sha256_manifest(output_csv, args.sha256_file)
    print(f"Capture packages exported: {output_csv}")
    print(f"Rows exported: {row_count}")
    if manifest_path is not None:
        print(f"SHA-256 manifest: {manifest_path}")
    return 0


def _handle_export_pilot_automation_reports(args: argparse.Namespace) -> int:
    from .clinical_hub import export_pilot_automation_reports_to_csv

    db_path = Path(args.db_path)
    output_csv = Path(args.output_csv)
    row_count = export_pilot_automation_reports_to_csv(db_path=db_path, output_csv=output_csv)
    manifest_path = _maybe_write_sha256_manifest(output_csv, args.sha256_file)
    print(f"Pilot automation reports exported: {output_csv}")
    print(f"Rows exported: {row_count}")
    if manifest_path is not None:
        print(f"SHA-256 manifest: {manifest_path}")
    return 0


def _handle_summarize_paired_measurements(args: argparse.Namespace) -> int:
    from .clinical_hub import build_method_comparison_summary

    quality_status = None if args.quality_status == "all" else args.quality_status
    summary = build_method_comparison_summary(
        db_path=Path(args.db_path),
        site_id=args.site_id,
        subject_id=args.subject_id,
        platform=args.platform,
        capture_mode=args.capture_mode,
        quality_status=quality_status,
    )

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Method-comparison summary saved: {output_json}")
    print(f"Records considered: {summary.records_considered}")
    for metric in summary.metrics:
        if metric.paired_samples == 0:
            continue
        mae = metric.mean_absolute_error if metric.mean_absolute_error is not None else float("nan")
        bias = metric.mean_error if metric.mean_error is not None else float("nan")
        print(
            f"{metric.metric}: n={metric.paired_samples}, "
            f"MAE={mae:.3f}, bias={bias:.3f}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze-video":
        return _handle_analyze_video(args)
    if args.command == "analyze-level-series":
        return _handle_analyze_level_series(args)
    if args.command == "generate-synthetic-bench":
        return _handle_generate_synthetic_bench(args)
    if args.command == "validate-capture-contract":
        return _handle_validate_capture_contract(args)
    if args.command == "analyze-capture-session":
        return _handle_analyze_capture_session(args)
    if args.command == "evaluate-gates":
        return _handle_evaluate_gates(args)
    if args.command == "build-gate-metrics":
        return _handle_build_gate_metrics(args)
    if args.command == "generate-gate-profile-template":
        return _handle_generate_gate_profile_template(args)
    if args.command == "serve-clinical-hub":
        return _handle_serve_clinical_hub(args)
    if args.command == "export-paired-measurements":
        return _handle_export_paired_measurements(args)
    if args.command == "export-audit-events":
        return _handle_export_audit_events(args)
    if args.command == "export-capture-packages":
        return _handle_export_capture_packages(args)
    if args.command == "export-pilot-automation-reports":
        return _handle_export_pilot_automation_reports(args)
    if args.command == "summarize-paired-measurements":
        return _handle_summarize_paired_measurements(args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
