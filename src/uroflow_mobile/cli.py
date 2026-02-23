from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from .capture_contract import capture_to_level_payload, validate_capture_payload
from .fusion import (
    FusionEstimationResult,
    FusionLevelConfig,
    FusionQualityFlags,
    estimate_from_level_series,
)
from .metrics import UroflowSummary, calculate_uroflow_summary
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


def _write_curve_csv(path: Path, timestamps_s: list[float], flow_ml_s: list[float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp_s", "flow_ml_s"])
        for timestamp, flow in zip(timestamps_s, flow_ml_s, strict=True):
            writer.writerow([f"{timestamp:.6f}", f"{flow:.6f}"])


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

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
