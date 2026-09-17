"""Colour matching between time ranges of a video."""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def compute_channel_stats(
    frames: list[np.ndarray],
    percentile_low: float = 1.0,
    percentile_high: float = 99.0,
) -> dict:
    """
    Compute per-channel statistics (gain and offset) for a set of frames
    using percentile-based measurements.
    """
    all_pixels = np.concatenate([f.reshape(-1, 3).astype(np.float32) for f in frames], axis=0)

    stats = {}
    for c, name in enumerate(["B", "G", "R"]):
        channel = all_pixels[:, c]
        low = np.percentile(channel, percentile_low)
        high = np.percentile(channel, percentile_high)
        mean = channel.mean()
        stats[name] = {"low": low, "high": high, "mean": mean, "range": high - low}

    return stats


def match_colour_range(
    source_frames: list[np.ndarray],
    target_frames: list[np.ndarray],
    strength: float = 1.0,
    percentile_low: float = 1.0,
    percentile_high: float = 99.0,
) -> list[np.ndarray]:
    """
    Match the colour of source frames to target frames using
    percentile-based gain and offset per RGB channel.

    strength: 0.0 = no change, 1.0 = full match.
    """
    if strength <= 0:
        return source_frames

    strength = min(strength, 1.0)

    src_stats = compute_channel_stats(source_frames, percentile_low, percentile_high)
    tgt_stats = compute_channel_stats(target_frames, percentile_low, percentile_high)

    gains = {}
    offsets = {}
    for name in ["B", "G", "R"]:
        src_range = max(src_stats[name]["range"], 1e-6)
        tgt_range = max(tgt_stats[name]["range"], 1e-6)
        gain = tgt_range / src_range
        offset = tgt_stats[name]["mean"] - gain * src_stats[name]["mean"]

        gains[name] = 1.0 + (gain - 1.0) * strength
        offsets[name] = offset * strength

    result = []
    for frame in source_frames:
        adjusted = frame.astype(np.float32)
        for c, name in enumerate(["B", "G", "R"]):
            adjusted[:, :, c] = adjusted[:, :, c] * gains[name] + offsets[name]
        result.append(np.clip(adjusted, 0, 255).astype(np.uint8))

    return result


def match_video_colour_ranges(
    frames: list[np.ndarray],
    source_start: int,
    source_end: int,
    target_start: int,
    target_end: int,
    strength: float = 1.0,
) -> list[np.ndarray]:
    """
    Match the colour of one time range to another within the same video.
    Only the source range is modified.
    """
    source_slice = frames[source_start:source_end]
    target_slice = frames[target_start:target_end]

    matched = match_colour_range(source_slice, target_slice, strength)

    result = list(frames)
    for i, matched_frame in enumerate(matched):
        result[source_start + i] = matched_frame

    return result
