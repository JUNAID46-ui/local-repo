"""Quality checks for processed output."""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def check_edge_quality(
    original: np.ndarray,
    processed: np.ndarray,
    mask: np.ndarray,
    threshold: float = 15.0,
    border_px: int = 5,
) -> dict:
    """
    Compare the edge of the filled area with its surroundings.

    Returns a dict with 'passed', 'mean_diff', and 'max_diff'.
    """
    dilated = cv2.dilate(
        mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_px * 2, border_px * 2)),
    )
    eroded = cv2.erode(
        mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_px * 2, border_px * 2)),
    )
    edge_band = (dilated > 127) & (eroded <= 127)

    if not edge_band.any():
        return {"passed": True, "mean_diff": 0.0, "max_diff": 0.0}

    diff = np.abs(
        processed.astype(np.float32) - original.astype(np.float32)
    )
    diff_gray = np.mean(diff, axis=2) if diff.ndim == 3 else diff
    edge_diffs = diff_gray[edge_band]

    mean_diff = float(edge_diffs.mean())
    max_diff = float(edge_diffs.max())

    return {
        "passed": mean_diff < threshold,
        "mean_diff": mean_diff,
        "max_diff": max_diff,
    }


def check_video_quality(
    original_frames: list[np.ndarray],
    processed_frames: list[np.ndarray],
    masks: dict[int, np.ndarray],
    threshold: float = 15.0,
    fps: float = 30.0,
) -> list[dict]:
    """
    Check quality across all video frames.

    Returns a list of problem frames with timestamps.
    """
    problems = []

    for i in range(len(processed_frames)):
        if i not in masks or masks[i].max() == 0:
            continue

        result = check_edge_quality(
            original_frames[i],
            processed_frames[i],
            masks[i],
            threshold,
        )

        if not result["passed"]:
            timestamp = i / fps
            minutes = int(timestamp // 60)
            seconds = timestamp % 60
            problems.append({
                "frame": i,
                "timestamp": f"{minutes:02d}:{seconds:05.2f}",
                "mean_diff": result["mean_diff"],
                "max_diff": result["max_diff"],
            })

    return problems


def select_preview_frames(
    total_frames: int,
    count: int = 5,
    masks: dict[int, np.ndarray] = None,
) -> list[int]:
    """
    Select frames for preview, preferring frames where the mask is present.
    Returns a list of frame indices.
    """
    if masks:
        masked_frames = sorted([i for i, m in masks.items() if m.max() > 0])
        if len(masked_frames) >= count:
            step = len(masked_frames) // count
            return [masked_frames[i * step] for i in range(count)]
        elif masked_frames:
            return masked_frames[:count]

    if total_frames <= count:
        return list(range(total_frames))

    step = total_frames // (count + 1)
    return [step * (i + 1) for i in range(count)]
