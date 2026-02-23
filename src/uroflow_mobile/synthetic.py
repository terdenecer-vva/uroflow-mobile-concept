from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticBenchConfig:
    """Configuration for synthetic uroflow bench generation."""

    profile: str = "bell"
    scenario: str = "quiet_lab"
    duration_s: float = 18.0
    sample_rate_hz: float = 10.0
    target_volume_ml: float = 320.0
    ml_per_mm: float = 8.0
    seed: int = 42


@dataclass(frozen=True)
class BenchScenario:
    """Noise and artifact envelope for synthetic modality simulation."""

    depth_noise_mm: float
    rgb_noise_mm: float
    low_confidence_probability: float
    missing_depth_probability: float
    motion_spike_probability: float
    motion_spike_mm: float


@dataclass(frozen=True)
class SyntheticBenchSeries:
    """Synthetic synchronized series with ground truth and modality channels."""

    timestamps_s: list[float]
    true_flow_ml_s: list[float]
    true_volume_ml: list[float]
    true_level_mm: list[float]
    depth_level_mm: list[float]
    rgb_level_mm: list[float]
    depth_confidence: list[float]


BENCH_SCENARIOS: dict[str, BenchScenario] = {
    "quiet_lab": BenchScenario(
        depth_noise_mm=0.25,
        rgb_noise_mm=0.18,
        low_confidence_probability=0.04,
        missing_depth_probability=0.0,
        motion_spike_probability=0.0,
        motion_spike_mm=0.0,
    ),
    "reflective_bowl": BenchScenario(
        depth_noise_mm=0.55,
        rgb_noise_mm=0.35,
        low_confidence_probability=0.22,
        missing_depth_probability=0.08,
        motion_spike_probability=0.05,
        motion_spike_mm=2.8,
    ),
    "phone_motion": BenchScenario(
        depth_noise_mm=0.45,
        rgb_noise_mm=0.28,
        low_confidence_probability=0.16,
        missing_depth_probability=0.03,
        motion_spike_probability=0.16,
        motion_spike_mm=4.2,
    ),
}

SUPPORTED_PROFILES = ("bell", "plateau", "intermittent", "staccato")


def _trapz_integral(timestamps_s: Sequence[float], values: Sequence[float]) -> float:
    area = 0.0
    for index in range(1, len(timestamps_s)):
        dt = timestamps_s[index] - timestamps_s[index - 1]
        area += 0.5 * (values[index] + values[index - 1]) * dt
    return area


def _cumulative_integral(timestamps_s: Sequence[float], values: Sequence[float]) -> list[float]:
    cumulative = [0.0]
    area = 0.0
    for index in range(1, len(timestamps_s)):
        dt = timestamps_s[index] - timestamps_s[index - 1]
        area += 0.5 * (values[index] + values[index - 1]) * dt
        cumulative.append(area)
    return cumulative


def generate_timestamps(duration_s: float, sample_rate_hz: float) -> list[float]:
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")

    samples = int(round(duration_s * sample_rate_hz)) + 1
    return [index / sample_rate_hz for index in range(samples)]


def _profile_envelope(normalized_t: float, profile: str) -> float:
    if normalized_t < 0.0 or normalized_t > 1.0:
        return 0.0

    if profile == "bell":
        return math.sin(math.pi * normalized_t) ** 1.8

    if profile == "plateau":
        ramp = 0.18
        if normalized_t < ramp:
            return normalized_t / ramp
        if normalized_t > 1.0 - ramp:
            return (1.0 - normalized_t) / ramp
        return 1.0

    if profile == "intermittent":
        base = math.sin(math.pi * normalized_t) ** 1.5
        in_gap_1 = 0.28 <= normalized_t <= 0.37
        in_gap_2 = 0.62 <= normalized_t <= 0.72
        return 0.0 if in_gap_1 or in_gap_2 else base

    if profile == "staccato":
        base = math.sin(math.pi * normalized_t) ** 1.3
        ripple = 0.55 + 0.45 * (0.5 * (1.0 + math.sin(2.0 * math.pi * 8.0 * normalized_t)))
        return base * ripple

    raise ValueError(f"unsupported profile: {profile}")


def generate_flow_profile(
    timestamps_s: Sequence[float],
    profile: str,
    target_volume_ml: float,
) -> list[float]:
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"unsupported profile: {profile}")
    if target_volume_ml <= 0:
        raise ValueError("target_volume_ml must be positive")
    if len(timestamps_s) < 2:
        raise ValueError("at least two timestamps are required")

    duration = timestamps_s[-1] - timestamps_s[0]
    if duration <= 0:
        raise ValueError("timestamps must be strictly increasing")

    normalized = [(timestamp - timestamps_s[0]) / duration for timestamp in timestamps_s]
    raw_flow = [_profile_envelope(value, profile) for value in normalized]

    raw_volume_ml = _trapz_integral(timestamps_s, raw_flow)
    if raw_volume_ml <= 0:
        raise ValueError("generated zero profile volume")
    scale = target_volume_ml / raw_volume_ml

    return [value * scale for value in raw_flow]


def _simulate_modalities(
    true_level_mm: Sequence[float],
    scenario: BenchScenario,
    rng: random.Random,
) -> tuple[list[float], list[float], list[float]]:
    depth_level_mm: list[float] = []
    rgb_level_mm: list[float] = []
    depth_confidence: list[float] = []

    for level in true_level_mm:
        low_confidence = rng.random() < scenario.low_confidence_probability
        if low_confidence:
            confidence = rng.uniform(0.05, 0.45)
            noise_scale = scenario.depth_noise_mm * 3.0
        else:
            confidence = rng.uniform(0.82, 0.99)
            noise_scale = scenario.depth_noise_mm

        depth_value = level + rng.gauss(0.0, noise_scale)
        if rng.random() < scenario.motion_spike_probability:
            spike_direction = -1.0 if rng.random() < 0.5 else 1.0
            depth_value += spike_direction * scenario.motion_spike_mm
            confidence = min(confidence, 0.35)

        if rng.random() < scenario.missing_depth_probability:
            depth_value = math.nan
            confidence = 0.0

        rgb_value = level + rng.gauss(0.0, scenario.rgb_noise_mm)

        depth_level_mm.append(depth_value)
        rgb_level_mm.append(rgb_value)
        depth_confidence.append(confidence)

    return depth_level_mm, rgb_level_mm, depth_confidence


def generate_synthetic_bench_series(config: SyntheticBenchConfig) -> SyntheticBenchSeries:
    if config.profile not in SUPPORTED_PROFILES:
        raise ValueError(f"unsupported profile: {config.profile}")
    if config.scenario not in BENCH_SCENARIOS:
        raise ValueError(f"unsupported scenario: {config.scenario}")
    if config.ml_per_mm <= 0:
        raise ValueError("ml_per_mm must be positive")

    timestamps_s = generate_timestamps(config.duration_s, config.sample_rate_hz)
    true_flow_ml_s = generate_flow_profile(
        timestamps_s=timestamps_s,
        profile=config.profile,
        target_volume_ml=config.target_volume_ml,
    )
    true_volume_ml = _cumulative_integral(timestamps_s, true_flow_ml_s)
    true_level_mm = [volume / config.ml_per_mm for volume in true_volume_ml]

    scenario = BENCH_SCENARIOS[config.scenario]
    rng = random.Random(config.seed)
    depth_level_mm, rgb_level_mm, depth_confidence = _simulate_modalities(
        true_level_mm=true_level_mm,
        scenario=scenario,
        rng=rng,
    )

    return SyntheticBenchSeries(
        timestamps_s=timestamps_s,
        true_flow_ml_s=true_flow_ml_s,
        true_volume_ml=true_volume_ml,
        true_level_mm=true_level_mm,
        depth_level_mm=depth_level_mm,
        rgb_level_mm=rgb_level_mm,
        depth_confidence=depth_confidence,
    )


def series_to_level_payload(series: SyntheticBenchSeries) -> dict[str, object]:
    return {
        "timestamps_s": series.timestamps_s,
        "depth_level_mm": series.depth_level_mm,
        "rgb_level_mm": series.rgb_level_mm,
        "depth_confidence": series.depth_confidence,
    }


def available_scenarios() -> tuple[str, ...]:
    return tuple(sorted(BENCH_SCENARIOS))
