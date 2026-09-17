"""Mask propagation and tracking through video frames using SAM 2."""

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch

from app.config import MODELS_DIR, DEFAULT_MASK_DILATE_PX, get_device

logger = logging.getLogger(__name__)

_sam2_video_predictor = None


def load_sam2_video(device: Optional[torch.device] = None):
    """Load the SAM 2 video predictor."""
    global _sam2_video_predictor
    if _sam2_video_predictor is not None:
        return _sam2_video_predictor

    device = device or get_device()
    try:
        from sam2.build_sam import build_sam2_video_predictor
    except ImportError:
        raise RuntimeError("sam2 is not installed. Install with: pip install sam-2")

    checkpoint_path = MODELS_DIR / "sam2" / "sam2.1_hiera_large.pt"
    if not checkpoint_path.exists():
        raise RuntimeError(f"SAM 2 weights not found at {checkpoint_path}. Run detection first.")

    _sam2_video_predictor = build_sam2_video_predictor(
        "sam2.1_hiera_l",
        str(checkpoint_path),
        device=str(device),
    )
    logger.info("SAM 2 video predictor loaded on %s", device)
    return _sam2_video_predictor


def propagate_mask_through_video(
    frames_dir: Path,
    initial_mask: np.ndarray,
    initial_frame_idx: int = 0,
    device: Optional[torch.device] = None,
) -> dict[int, np.ndarray]:
    """
    Propagate a mask from one frame through the entire video using SAM 2.

    frames_dir: directory containing frames as 000000.jpg, 000001.jpg, etc.
    initial_mask: binary mask (H, W) for the initial frame.
    initial_frame_idx: which frame the mask belongs to.

    Returns {frame_index: mask_array} for every frame.
    """
    device = device or get_device()
    predictor = load_sam2_video(device)

    with torch.inference_mode(), torch.autocast(str(device), dtype=torch.bfloat16):
        state = predictor.init_state(video_path=str(frames_dir))

        mask_tensor = torch.from_numpy(initial_mask > 127).float().unsqueeze(0).unsqueeze(0)
        predictor.add_new_mask(
            inference_state=state,
            frame_idx=initial_frame_idx,
            obj_id=1,
            mask=mask_tensor.to(device),
        )

        masks_per_frame = {}
        for frame_idx, obj_ids, masks in predictor.propagate_in_video(state):
            mask = (masks[0, 0] > 0.5).cpu().numpy().astype(np.uint8) * 255
            masks_per_frame[frame_idx] = mask

    return masks_per_frame


def refine_mask_with_perspective(
    frames: list[np.ndarray],
    masks: dict[int, np.ndarray],
    reference_frame_idx: int = 0,
) -> dict[int, np.ndarray]:
    """
    For logos on rotating 3D objects, refine masks using perspective estimation.

    Uses ORB feature matching and homography between consecutive frames
    to warp and refine mask boundaries.
    """
    if not masks:
        return masks

    orb = cv2.ORB_create(nfeatures=1000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    refined = dict(masks)
    ref_frame = frames[reference_frame_idx]
    ref_gray = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2GRAY)
    ref_kp, ref_desc = orb.detectAndCompute(ref_gray, None)

    if ref_desc is None:
        return refined

    for idx in sorted(masks.keys()):
        if idx == reference_frame_idx:
            continue

        cur_gray = cv2.cvtColor(frames[idx], cv2.COLOR_BGR2GRAY)
        cur_kp, cur_desc = orb.detectAndCompute(cur_gray, None)

        if cur_desc is None or len(cur_kp) < 4:
            continue

        matches = bf.match(ref_desc, cur_desc)
        if len(matches) < 4:
            continue

        matches = sorted(matches, key=lambda m: m.distance)[:50]

        src_pts = np.float32([ref_kp[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([cur_kp[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

        H, status = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if H is None:
            continue

        h, w = ref_frame.shape[:2]
        warped_mask = cv2.warpPerspective(
            masks.get(reference_frame_idx, np.zeros((h, w), dtype=np.uint8)),
            H,
            (w, h),
            flags=cv2.INTER_NEAREST,
        )

        existing = masks.get(idx, np.zeros((h, w), dtype=np.uint8))
        combined = cv2.bitwise_or(existing, warped_mask)
        refined[idx] = combined

    return refined


def dilate_masks(
    masks: dict[int, np.ndarray],
    dilate_px: int = DEFAULT_MASK_DILATE_PX,
) -> dict[int, np.ndarray]:
    """Dilate all masks by the given pixel amount to cover soft edges."""
    if dilate_px <= 0:
        return masks

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (dilate_px * 2 + 1, dilate_px * 2 + 1),
    )
    return {
        idx: cv2.dilate(mask, kernel, iterations=1)
        for idx, mask in masks.items()
    }


def classify_mask_motion(masks: dict[int, np.ndarray], threshold: float = 5.0) -> str:
    """
    Determine whether the mask is roughly static or moving across frames.

    Returns "static" or "moving".
    """
    if len(masks) < 2:
        return "static"

    centroids = []
    for mask in masks.values():
        ys, xs = np.where(mask > 127)
        if len(xs) == 0:
            continue
        centroids.append((xs.mean(), ys.mean()))

    if len(centroids) < 2:
        return "static"

    centroids = np.array(centroids)
    movement = np.std(centroids, axis=0)
    total_movement = np.sqrt(movement[0] ** 2 + movement[1] ** 2)

    return "static" if total_movement < threshold else "moving"
