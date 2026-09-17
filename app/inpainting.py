"""Inpainting with ProPainter (video) and LaMa (image/fallback)."""

import logging
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch

from app.config import MODELS_DIR, DEFAULT_CONTEXT_PX, DEFAULT_FEATHER_PX, get_device

logger = logging.getLogger(__name__)

_lama_model = None


def _download_if_missing(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading %s to %s", url, dest)
    import urllib.request
    urllib.request.urlretrieve(url, str(dest))
    return dest


def load_lama(device: Optional[torch.device] = None):
    """Load the LaMa big-lama TorchScript model."""
    global _lama_model
    if _lama_model is not None:
        return _lama_model

    device = device or get_device()

    weights_url = (
        "https://github.com/Sanster/models/releases/download/"
        "add_big_lama/big-lama.pt"
    )
    weights_path = _download_if_missing(weights_url, MODELS_DIR / "lama" / "big-lama.pt")

    _lama_model = torch.jit.load(str(weights_path), map_location=device)
    _lama_model.eval()
    logger.info("LaMa loaded on %s", device)
    return _lama_model


def _crop_around_mask(
    image: np.ndarray,
    mask: np.ndarray,
    context_px: int = DEFAULT_CONTEXT_PX,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    """
    Crop a region around the mask with context, aligned to multiples of 8.
    Returns (cropped_image, cropped_mask, (x1, y1, x2, y2)).
    """
    h, w = mask.shape[:2]
    ys, xs = np.where(mask > 127)
    if len(xs) == 0:
        return image, mask, (0, 0, w, h)

    x1 = max(0, int(xs.min()) - context_px)
    y1 = max(0, int(ys.min()) - context_px)
    x2 = min(w, int(xs.max()) + context_px)
    y2 = min(h, int(ys.max()) + context_px)

    x1 = x1 - (x1 % 8)
    y1 = y1 - (y1 % 8)
    x2 = x2 + (8 - x2 % 8) if x2 % 8 != 0 else x2
    y2 = y2 + (8 - y2 % 8) if y2 % 8 != 0 else y2
    x2 = min(w, x2)
    y2 = min(h, y2)

    crop_w = x2 - x1
    crop_h = y2 - y1
    if crop_w % 8 != 0:
        x2 = x1 + (crop_w // 8) * 8
    if crop_h % 8 != 0:
        y2 = y1 + (crop_h // 8) * 8

    return image[y1:y2, x1:x2], mask[y1:y2, x1:x2], (x1, y1, x2, y2)


def _feathered_paste(
    canvas: np.ndarray,
    patch: np.ndarray,
    mask: np.ndarray,
    bbox: tuple[int, int, int, int],
    feather_px: int = DEFAULT_FEATHER_PX,
) -> np.ndarray:
    """Paste inpainted patch back with a feathered edge."""
    x1, y1, x2, y2 = bbox
    result = canvas.copy()

    blend_mask = mask[y1:y2, x1:x2].astype(np.float32) / 255.0
    if feather_px > 0:
        blend_mask = cv2.GaussianBlur(blend_mask, (feather_px * 2 + 1, feather_px * 2 + 1), feather_px)

    blend_3ch = np.stack([blend_mask] * 3, axis=2)

    region = result[y1:y2, x1:x2].astype(np.float32)
    patch_f = patch.astype(np.float32)

    ph, pw = patch_f.shape[:2]
    rh, rw = region.shape[:2]
    mh, mw = min(ph, rh), min(pw, rw)

    blended = region[:mh, :mw] * (1 - blend_3ch[:mh, :mw]) + patch_f[:mh, :mw] * blend_3ch[:mh, :mw]
    result[y1:y1 + mh, x1:x1 + mw] = np.clip(blended, 0, 255).astype(np.uint8)
    return result


def inpaint_image_lama(
    image: np.ndarray,
    mask: np.ndarray,
    device: Optional[torch.device] = None,
    context_px: int = DEFAULT_CONTEXT_PX,
    feather_px: int = DEFAULT_FEATHER_PX,
) -> np.ndarray:
    """Inpaint a single image using LaMa."""
    device = device or get_device()
    model = load_lama(device)

    cropped_img, cropped_mask, bbox = _crop_around_mask(image, mask, context_px)

    if cropped_mask.max() == 0:
        return image

    img_t = torch.from_numpy(cropped_img).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    mask_t = torch.from_numpy(cropped_mask).unsqueeze(0).unsqueeze(0).float() / 255.0

    img_t = img_t.to(device)
    mask_t = mask_t.to(device)

    with torch.no_grad():
        result_t = model(img_t, mask_t)

    result_np = (result_t[0].permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)

    return _feathered_paste(image, result_np, mask, bbox, feather_px)


def inpaint_video_propainter(
    frames: list[np.ndarray],
    masks: dict[int, np.ndarray],
    device: Optional[torch.device] = None,
    chunk_size: int = 80,
) -> list[np.ndarray]:
    """
    Inpaint video frames using ProPainter for flow-guided temporal consistency.

    Falls back to LaMa frame-by-frame if ProPainter is unavailable.
    """
    device = device or get_device()

    try:
        from propainter.inference import inpaint_video as pp_inpaint
    except ImportError:
        logger.warning("ProPainter not available, falling back to LaMa frame-by-frame")
        return _fallback_lama_video(frames, masks, device)

    global_bbox = _get_global_bbox(frames[0].shape[:2], masks)

    result_frames = list(frames)

    for chunk_start in range(0, len(frames), chunk_size):
        chunk_end = min(chunk_start + chunk_size, len(frames))
        chunk_frames = frames[chunk_start:chunk_end]
        chunk_masks = []
        for i in range(chunk_start, chunk_end):
            if i in masks:
                chunk_masks.append(masks[i])
            else:
                chunk_masks.append(np.zeros(frames[0].shape[:2], dtype=np.uint8))

        try:
            inpainted = pp_inpaint(
                frames=chunk_frames,
                masks=chunk_masks,
                device=device,
            )
            for j, frame in enumerate(inpainted):
                result_frames[chunk_start + j] = frame
        except Exception as e:
            logger.error("ProPainter chunk failed: %s, falling back to LaMa", e)
            for j in range(len(chunk_frames)):
                idx = chunk_start + j
                if idx in masks and masks[idx].max() > 0:
                    result_frames[idx] = inpaint_image_lama(
                        chunk_frames[j], masks[idx], device
                    )

    return result_frames


def _fallback_lama_video(
    frames: list[np.ndarray],
    masks: dict[int, np.ndarray],
    device: Optional[torch.device] = None,
) -> list[np.ndarray]:
    """Frame-by-frame LaMa inpainting as fallback."""
    result = []
    for i, frame in enumerate(frames):
        if i in masks and masks[i].max() > 0:
            result.append(inpaint_image_lama(frame, masks[i], device))
        else:
            result.append(frame)
    return result


def _get_global_bbox(
    frame_shape: tuple[int, int],
    masks: dict[int, np.ndarray],
) -> tuple[int, int, int, int]:
    """Compute bounding box that covers all masks across all frames."""
    h, w = frame_shape
    min_x, min_y = w, h
    max_x, max_y = 0, 0

    for mask in masks.values():
        ys, xs = np.where(mask > 127)
        if len(xs) == 0:
            continue
        min_x = min(min_x, int(xs.min()))
        min_y = min(min_y, int(ys.min()))
        max_x = max(max_x, int(xs.max()))
        max_y = max(max_y, int(ys.max()))

    return (
        max(0, min_x - DEFAULT_CONTEXT_PX),
        max(0, min_y - DEFAULT_CONTEXT_PX),
        min(w, max_x + DEFAULT_CONTEXT_PX),
        min(h, max_y + DEFAULT_CONTEXT_PX),
    )
