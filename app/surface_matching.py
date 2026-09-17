"""Surface matching for 3D rotating objects and texture reconstruction."""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def match_histogram_local(
    image: np.ndarray,
    mask: np.ndarray,
    border_px: int = 30,
) -> np.ndarray:
    """
    Match colour and brightness of the filled area to the surrounding ring.

    Uses per-channel histogram matching between the mask interior
    and a border ring around it.
    """
    dilated = cv2.dilate(
        mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_px * 2, border_px * 2)),
    )
    ring = (dilated > 127) & (mask <= 127)
    inside = mask > 127

    if not ring.any() or not inside.any():
        return image

    result = image.copy()
    for c in range(3):
        src_vals = image[inside, c].astype(np.float32)
        ref_vals = image[ring, c].astype(np.float32)

        if len(src_vals) == 0 or len(ref_vals) == 0:
            continue

        src_mean, src_std = src_vals.mean(), max(src_vals.std(), 1e-6)
        ref_mean, ref_std = ref_vals.mean(), max(ref_vals.std(), 1e-6)

        adjusted = (src_vals - src_mean) * (ref_std / src_std) + ref_mean
        result[inside, c] = np.clip(adjusted, 0, 255).astype(np.uint8)

    return result


def estimate_noise_params(
    image: np.ndarray,
    mask: np.ndarray,
    border_px: int = 30,
) -> tuple[float, float]:
    """
    Estimate the grain/noise level from the area surrounding the mask.

    Returns (noise_mean, noise_std) of the high-frequency residual.
    """
    dilated = cv2.dilate(
        mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_px * 2, border_px * 2)),
    )
    ring = (dilated > 127) & (mask <= 127)

    if not ring.any():
        return 0.0, 1.0

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)
    noise_residual = gray - blurred

    noise_vals = noise_residual[ring]
    return float(noise_vals.mean()), float(max(noise_vals.std(), 0.5))


def add_matching_grain(
    image: np.ndarray,
    mask: np.ndarray,
    noise_mean: float,
    noise_std: float,
) -> np.ndarray:
    """Add synthetic grain to the filled region matching surrounding noise."""
    inside = mask > 127
    if not inside.any():
        return image

    result = image.copy()
    h, w = mask.shape[:2]

    noise = np.random.normal(noise_mean, noise_std, (h, w)).astype(np.float32)

    for c in range(3):
        channel = result[:, :, c].astype(np.float32)
        channel[inside] += noise[inside]
        result[:, :, c] = np.clip(channel, 0, 255).astype(np.uint8)

    return result


def temporal_smooth_with_flow(
    frames: list[np.ndarray],
    masks: dict[int, np.ndarray],
    window: int = 3,
) -> list[np.ndarray]:
    """
    Apply temporal smoothing using optical flow so filled textures
    move with the object rather than flickering.

    Uses OpenCV Farneback optical flow for motion estimation.
    """
    if len(frames) < 2:
        return frames

    result = list(frames)

    for i in range(len(frames)):
        if i not in masks or masks[i].max() == 0:
            continue

        inside = masks[i] > 127

        start = max(0, i - window)
        end = min(len(frames), i + window + 1)

        gray_cur = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        accum = frames[i].astype(np.float64)
        weight = 1.0

        for j in range(start, end):
            if j == i:
                continue

            gray_j = cv2.cvtColor(frames[j], cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(
                gray_j, gray_cur,
                None, 0.5, 3, 15, 3, 5, 1.2, 0
            )

            h, w = gray_cur.shape
            coords_x, coords_y = np.meshgrid(np.arange(w), np.arange(h))
            map_x = (coords_x + flow[:, :, 0]).astype(np.float32)
            map_y = (coords_y + flow[:, :, 1]).astype(np.float32)

            warped = cv2.remap(frames[j], map_x, map_y, cv2.INTER_LINEAR)

            dist = abs(j - i)
            w_j = 1.0 / (1.0 + dist)
            accum += warped.astype(np.float64) * w_j
            weight += w_j

        blended = (accum / weight).astype(np.uint8)
        out = result[i].copy()
        out[inside] = blended[inside]
        result[i] = out

    return result


def process_surface_matching(
    frames: list[np.ndarray],
    masks: dict[int, np.ndarray],
    apply_grain: bool = True,
    apply_temporal_smooth: bool = True,
    temporal_window: int = 3,
) -> list[np.ndarray]:
    """
    Full surface matching pipeline for rotating 3D objects.

    1. Histogram match each frame's filled region to its surroundings.
    2. Add matching grain/noise.
    3. Apply temporal smoothing with optical flow.
    """
    result = list(frames)

    for i in range(len(result)):
        if i not in masks or masks[i].max() == 0:
            continue

        result[i] = match_histogram_local(result[i], masks[i])

        if apply_grain:
            noise_mean, noise_std = estimate_noise_params(result[i], masks[i])
            result[i] = add_matching_grain(result[i], masks[i], noise_mean, noise_std)

    if apply_temporal_smooth and len(result) > 1:
        result = temporal_smooth_with_flow(result, masks, temporal_window)

    return result
