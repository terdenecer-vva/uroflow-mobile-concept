"""Core package for mobile uroflowmetry concept."""

from .fusion import (
    FusionEstimationResult,
    FusionLevelConfig,
    FusionQualityFlags,
    estimate_flow_curve,
    estimate_flow_uncertainty,
    estimate_from_level_series,
    estimate_volume_curve,
    evaluate_fusion_quality,
)
from .metrics import UroflowSummary, calculate_uroflow_summary

__all__ = [
    "UroflowSummary",
    "calculate_uroflow_summary",
    "FusionLevelConfig",
    "FusionQualityFlags",
    "FusionEstimationResult",
    "estimate_volume_curve",
    "estimate_flow_curve",
    "estimate_flow_uncertainty",
    "evaluate_fusion_quality",
    "estimate_from_level_series",
]

try:
    from .flow_from_video import VideoFlowConfig, estimate_flow_curve_from_video  # noqa: F401
    from .pipeline import PipelineArtifacts, UroflowVideoPipeline  # noqa: F401
except ModuleNotFoundError:
    # Video pipeline dependencies (numpy/opencv) are optional.
    pass
else:
    __all__.extend(
        [
            "VideoFlowConfig",
            "estimate_flow_curve_from_video",
            "PipelineArtifacts",
            "UroflowVideoPipeline",
        ]
    )
