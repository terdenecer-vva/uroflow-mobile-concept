"""Core package for mobile uroflowmetry concept."""

from .metrics import UroflowSummary, calculate_uroflow_summary

__all__ = ["UroflowSummary", "calculate_uroflow_summary"]

try:
    from .flow_from_video import VideoFlowConfig, estimate_flow_curve_from_video
    from .pipeline import PipelineArtifacts, UroflowVideoPipeline
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
