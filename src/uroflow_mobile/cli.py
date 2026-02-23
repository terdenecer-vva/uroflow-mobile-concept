from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .metrics import UroflowSummary, calculate_uroflow_summary


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


def _write_curve_csv(path: Path, timestamps_s: list[float], flow_ml_s: list[float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp_s", "flow_ml_s"])
        for timestamp, flow in zip(timestamps_s, flow_ml_s):
            writer.writerow([f"{timestamp:.6f}", f"{flow:.6f}"])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uroflow-mobile", description="Concept CLI for smartphone-video uroflow estimation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze-video",
        help="Estimate flow curve Q(t) and uroflow metrics from video.",
    )
    analyze.add_argument("video_path", help="Path to smartphone recording.")
    analyze.add_argument(
        "--output-csv",
        help="Path for output flow curve CSV. Default: <video_stem>_flow_curve.csv",
    )
    analyze.add_argument(
        "--output-json",
        help="Path for output metrics JSON. Default: <video_stem>_summary.json",
    )
    analyze.add_argument("--motion-threshold", type=int, default=25)
    analyze.add_argument("--min-active-pixels", type=int, default=30)
    analyze.add_argument("--smoothing-window-frames", type=int, default=5)
    analyze.add_argument("--resize-width", type=int, default=480)
    analyze.add_argument("--ml-per-active-pixel-frame", type=float, default=0.002)
    analyze.add_argument("--flow-threshold-ml-s", type=float, default=0.2)
    analyze.add_argument("--min-pause-s", type=float, default=0.5)
    analyze.add_argument("--known-volume-ml", type=float, default=None)
    analyze.add_argument("--roi", type=str, default=None, help="ROI in format x,y,w,h")

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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze-video":
        return _handle_analyze_video(args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
