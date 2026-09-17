"""Static watermark removal by estimating overlay opacity and colour."""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def estimate_overlay_alpha(
    frames: list[np.ndarray],
    mask: np.ndarray,
    border_px: int = 20,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Estimate per-pixel alpha and colour of a static watermark overlay
    by analysing temporal variation inside vs. outside the mask.

    Returns (alpha_map, logo_colour) where both are float32 arrays
    at the mask resolution.
    """
    h, w = mask.shape[:2]
    mask_bool = mask > 127

    dilated = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_px * 2, border_px * 2)))
    border_region = (dilated > 127) & ~mask_bool

    stack = np.stack([f.astype(np.float32) for f in frames], axis=0)

    temporal_std_inside = np.std(stack[:, :, :, :], axis=0)
    temporal_mean = np.mean(stack, axis=0)

    std_per_pixel = np.mean(temporal_std_inside, axis=2)
    border_std = np.median(std_per_pixel[border_region]) if border_region.any() else 1.0
    inside_std = std_per_pixel.copy()

    if border_std < 0.1:
        border_std = 0.1

    raw_alpha = 1.0 - np.clip(inside_std / border_std, 0, 1)
    raw_alpha[~mask_bool] = 0.0

    alpha_map = cv2.GaussianBlur(raw_alpha.astype(np.float32), (5, 5), 1.0)
    alpha_map = np.clip(alpha_map, 0, 1)

    alpha_3ch = np.stack([alpha_map] * 3, axis=2)
    logo_colour = np.zeros_like(temporal_mean)
    high_alpha = alpha_3ch > 0.1
    if high_alpha.any():
        logo_colour[high_alpha] = (
            (temporal_mean[high_alpha] - (1.0 - alpha_3ch[high_alpha]) * temporal_mean[high_alpha])
            / alpha_3ch[high_alpha]
        )
    logo_colour = np.clip(logo_colour, 0, 255)

    return alpha_map, logo_colour


def remove_semitransparent_overlay(
    frame: np.ndarray,
    alpha_map: np.ndarray,
    logo_colour: np.ndarray,
    alpha_threshold: float = 0.6,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Mathematically remove semi-transparent parts of a watermark.

    original = (observed - alpha * logo_colour) / (1 - alpha)

    Returns (recovered_frame, residual_mask) where residual_mask marks
    pixels that were too opaque (alpha > threshold) and need inpainting.
    """
    frame_f = frame.astype(np.float32)
    alpha_3ch = np.stack([alpha_map] * 3, axis=2)
    logo_f = logo_colour.astype(np.float32)

    semi_transparent = (alpha_map > 0.05) & (alpha_map <= alpha_threshold)
    fully_opaque = alpha_map > alpha_threshold

    recovered = frame_f.copy()

    st_3ch = np.stack([semi_transparent] * 3, axis=2)
    denominator = np.clip(1.0 - alpha_3ch, 0.01, 1.0)

    where_semi = st_3ch
    recovered[where_semi] = (
        (frame_f[where_semi] - alpha_3ch[where_semi] * logo_f[where_semi])
        / denominator[where_semi]
    )

    recovered = np.clip(recovered, 0, 255).astype(np.uint8)

    residual_mask = (fully_opaque.astype(np.uint8) * 255)

    return recovered, residual_mask


def process_static_watermark(
    frames: list[np.ndarray],
    mask: np.ndarray,
    alpha_threshold: float = 0.6,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """
    Full static watermark processing pipeline.

    Returns (processed_frames, residual_masks) where residual_masks
    indicate areas that still need inpainting.
    """
    alpha_map, logo_colour = estimate_overlay_alpha(frames, mask)

    processed = []
    residuals = []
    for frame in frames:
        recovered, residual = remove_semitransparent_overlay(
            frame, alpha_map, logo_colour, alpha_threshold
        )
        processed.append(recovered)
        residuals.append(residual)

    return processed, residuals
