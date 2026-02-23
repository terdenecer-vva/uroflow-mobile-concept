from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .flow_from_video import VideoFlowConfig, estimate_flow_curve_from_video
from .metrics import UroflowSummary, calculate_uroflow_summary
from .models import PipelineConfig


@dataclass
class PipelineArtifacts:
    """Artifacts produced by each stage of processing."""

    video_path: Path
    preprocessed_video_path: Path | None = None
    flow_curve_path: Path | None = None
    report_path: Path | None = None
    summary: UroflowSummary | None = None


class UroflowVideoPipeline:
    """Conceptual pipeline: smartphone video -> Q(t) -> uroflow report."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()

    def run(
        self,
        video_path: str | Path,
        output_dir: str | Path | None = None,
        known_volume_ml: float | None = None,
    ) -> PipelineArtifacts:
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(path)

        target_dir = Path(output_dir) if output_dir else path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        flow_curve_path = target_dir / f"{path.stem}_flow_curve.csv"
        report_path = target_dir / f"{path.stem}_summary.json"

        flow_config = VideoFlowConfig(
            flow_threshold_ml_s=self.config.min_flow_threshold_ml_s,
            min_pause_s=self.config.min_pause_duration_s,
            known_volume_ml=known_volume_ml,
        )
        timestamps_s, flow_ml_s, fps = estimate_flow_curve_from_video(path, config=flow_config)
        summary = calculate_uroflow_summary(
            timestamps_s=timestamps_s,
            flow_ml_s=flow_ml_s,
            threshold_ml_s=self.config.min_flow_threshold_ml_s,
            min_pause_s=self.config.min_pause_duration_s,
        )

        with flow_curve_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["timestamp_s", "flow_ml_s"])
            for timestamp, flow in zip(timestamps_s, flow_ml_s, strict=True):
                writer.writerow([f"{timestamp:.6f}", f"{flow:.6f}"])

        report_payload = {
            "video_path": str(path),
            "fps": fps,
            "summary": {
                "start_time_s": summary.start_time_s,
                "end_time_s": summary.end_time_s,
                "voiding_time_s": summary.voiding_time_s,
                "flow_time_s": summary.flow_time_s,
                "voided_volume_ml": summary.voided_volume_ml,
                "q_max_ml_s": summary.q_max_ml_s,
                "q_avg_ml_s": summary.q_avg_ml_s,
                "time_to_qmax_s": summary.time_to_qmax_s,
                "interruptions_count": summary.interruptions_count,
            },
        }
        report_path.write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return PipelineArtifacts(
            video_path=path,
            flow_curve_path=flow_curve_path,
            report_path=report_path,
            summary=summary,
        )
