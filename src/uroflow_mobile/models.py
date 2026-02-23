from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for video-to-flow pipeline stages."""

    fps: float = 30.0
    min_flow_threshold_ml_s: float = 0.2
    min_pause_duration_s: float = 0.5
    smoothing_window_s: float = 0.3
