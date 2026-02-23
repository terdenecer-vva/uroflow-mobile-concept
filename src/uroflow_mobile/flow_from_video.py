from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class VideoFlowConfig:
    """Configuration for deriving a flow curve from smartphone video."""

    motion_threshold: int = 25
    min_active_pixels: int = 30
    smoothing_window_frames: int = 5
    resize_width: int | None = 480
    ml_per_active_pixel_per_frame: float = 0.002
    flow_threshold_ml_s: float = 0.2
    min_pause_s: float = 0.5
    roi: tuple[int, int, int, int] | None = None
    known_volume_ml: float | None = None


def trapz_integral(timestamps_s: Sequence[float], values: Sequence[float]) -> float:
    if len(timestamps_s) != len(values):
        raise ValueError("timestamps_s and values must have equal length")
    if len(timestamps_s) < 2:
        return 0.0

    area = 0.0
    for index in range(1, len(timestamps_s)):
        dt = timestamps_s[index] - timestamps_s[index - 1]
        area += 0.5 * (values[index] + values[index - 1]) * dt
    return area


def moving_average(values: Sequence[float], window: int) -> list[float]:
    if window <= 1:
        return list(values)
    if window > len(values):
        window = len(values)

    kernel = np.ones(window, dtype=np.float64) / float(window)
    padded = np.pad(np.asarray(values, dtype=np.float64), (window - 1, 0), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")
    return smoothed.tolist()


def trim_to_active_region(
    timestamps_s: Sequence[float], flow_ml_s: Sequence[float], threshold_ml_s: float
) -> tuple[list[float], list[float]]:
    if len(timestamps_s) != len(flow_ml_s):
        raise ValueError("timestamps_s and flow_ml_s must have equal length")
    if not timestamps_s:
        raise ValueError("empty series")

    active_indices = [i for i, value in enumerate(flow_ml_s) if value >= threshold_ml_s]
    if not active_indices:
        zeroed_timestamps = [value - timestamps_s[0] for value in timestamps_s]
        return zeroed_timestamps, list(flow_ml_s)

    start = max(active_indices[0] - 1, 0)
    end = min(active_indices[-1] + 1, len(flow_ml_s) - 1)

    selected_timestamps = list(timestamps_s[start : end + 1])
    selected_flow = list(flow_ml_s[start : end + 1])
    shift = selected_timestamps[0]
    normalized_timestamps = [value - shift for value in selected_timestamps]
    return normalized_timestamps, selected_flow


def rescale_curve_to_volume(
    timestamps_s: Sequence[float], flow_ml_s: Sequence[float], known_volume_ml: float | None
) -> list[float]:
    if known_volume_ml is None:
        return list(flow_ml_s)
    if known_volume_ml <= 0:
        raise ValueError("known_volume_ml must be positive")

    volume_raw = trapz_integral(timestamps_s, flow_ml_s)
    if volume_raw <= 0:
        return list(flow_ml_s)

    scale = known_volume_ml / volume_raw
    return [value * scale for value in flow_ml_s]


def _parse_roi(gray_frame: np.ndarray, roi: tuple[int, int, int, int] | None) -> np.ndarray:
    if roi is None:
        return gray_frame

    x, y, w, h = roi
    if w <= 0 or h <= 0:
        raise ValueError("ROI width and height must be positive")

    height, width = gray_frame.shape
    if x < 0 or y < 0 or x + w > width or y + h > height:
        raise ValueError("ROI is outside frame bounds")

    return gray_frame[y : y + h, x : x + w]


def estimate_flow_curve_from_video(
    video_path: str | Path, config: VideoFlowConfig | None = None
) -> tuple[list[float], list[float], float]:
    try:
        import cv2
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "opencv-python is required for video analysis. Install with: pip install -e '.[video]'"
        ) from error

    cfg = config or VideoFlowConfig()
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(path)

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"failed to open video: {path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    dt = 1.0 / fps

    frame_index = 0
    previous_gray: np.ndarray | None = None
    timestamps_s: list[float] = []
    raw_flow_ml_s: list[float] = []

    kernel = np.ones((3, 3), dtype=np.uint8)

    while True:
        ok, frame = capture.read()
        if not ok:
            break

        if cfg.resize_width and frame.shape[1] > cfg.resize_width:
            scale = cfg.resize_width / frame.shape[1]
            resized_height = int(frame.shape[0] * scale)
            frame = cv2.resize(
                frame,
                (cfg.resize_width, resized_height),
                interpolation=cv2.INTER_AREA,
            )

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        gray = _parse_roi(gray, cfg.roi)

        if previous_gray is None:
            timestamps_s.append(frame_index * dt)
            raw_flow_ml_s.append(0.0)
            previous_gray = gray
            frame_index += 1
            continue

        diff = cv2.absdiff(gray, previous_gray)
        _, mask = cv2.threshold(diff, cfg.motion_threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        active_pixels = int(np.count_nonzero(mask))
        if active_pixels < cfg.min_active_pixels:
            active_pixels = 0

        flow_ml_s = active_pixels * cfg.ml_per_active_pixel_per_frame * fps
        timestamps_s.append(frame_index * dt)
        raw_flow_ml_s.append(flow_ml_s)

        previous_gray = gray
        frame_index += 1

    capture.release()

    if len(timestamps_s) < 2:
        raise RuntimeError("video is too short to estimate flow")

    smoothed_flow_ml_s = moving_average(raw_flow_ml_s, cfg.smoothing_window_frames)
    trimmed_timestamps_s, trimmed_flow_ml_s = trim_to_active_region(
        timestamps_s, smoothed_flow_ml_s, cfg.flow_threshold_ml_s
    )
    final_flow_ml_s = rescale_curve_to_volume(
        trimmed_timestamps_s, trimmed_flow_ml_s, cfg.known_volume_ml
    )

    return trimmed_timestamps_s, final_flow_ml_s, fps
