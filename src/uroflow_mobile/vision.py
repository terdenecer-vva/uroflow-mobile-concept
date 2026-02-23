from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionResult:
    """Placeholder for per-frame urine stream detection outputs."""

    frame_index: int
    confidence: float
    estimated_cross_section_px2: float
    estimated_velocity_px_s: float


class VisionEstimator:
    """CV module contract for extracting flow-related features from video."""

    def detect_stream(self, frame_index: int) -> DetectionResult:
        raise NotImplementedError("Implement CV detection model in later milestones")
