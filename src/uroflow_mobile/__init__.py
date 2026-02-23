"""Core package for mobile uroflowmetry concept."""

from .capture_contract import (
    CaptureValidationReport,
    capture_to_level_payload,
    validate_capture_payload,
)
from .fusion import (
    FusionEstimationResult,
    FusionLevelConfig,
    FusionQualityFlags,
    estimate_flow_curve,
    estimate_flow_uncertainty,
    estimate_flow_uncertainty_from_volume_sigma,
    estimate_from_level_series,
    estimate_level_uncertainty_from_confidence,
    estimate_volume_curve,
    estimate_volume_uncertainty,
    evaluate_fusion_quality,
    fuse_depth_and_rgb_levels,
)
from .metrics import UroflowSummary, calculate_uroflow_summary
from .synthetic import (
    BENCH_SCENARIOS,
    SUPPORTED_PROFILES,
    BenchScenario,
    SyntheticBenchConfig,
    SyntheticBenchSeries,
    available_scenarios,
    generate_flow_profile,
    generate_synthetic_bench_series,
    generate_timestamps,
    series_to_level_payload,
)

__all__ = [
    "UroflowSummary",
    "calculate_uroflow_summary",
    "FusionLevelConfig",
    "FusionQualityFlags",
    "FusionEstimationResult",
    "estimate_volume_curve",
    "estimate_flow_curve",
    "estimate_flow_uncertainty",
    "estimate_level_uncertainty_from_confidence",
    "estimate_volume_uncertainty",
    "estimate_flow_uncertainty_from_volume_sigma",
    "evaluate_fusion_quality",
    "fuse_depth_and_rgb_levels",
    "estimate_from_level_series",
    "CaptureValidationReport",
    "capture_to_level_payload",
    "validate_capture_payload",
    "BenchScenario",
    "SyntheticBenchConfig",
    "SyntheticBenchSeries",
    "SUPPORTED_PROFILES",
    "BENCH_SCENARIOS",
    "generate_timestamps",
    "generate_flow_profile",
    "generate_synthetic_bench_series",
    "series_to_level_payload",
    "available_scenarios",
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
