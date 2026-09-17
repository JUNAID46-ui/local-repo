"""Watermark and logo detection using Grounding DINO and SAM 2."""

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch

from app.config import MODELS_DIR, get_device

logger = logging.getLogger(__name__)

_grounding_dino_model = None
_sam2_predictor = None


def _download_if_missing(url: str, dest: Path) -> Path:
    """Download a file if it does not exist locally."""
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading %s to %s", url, dest)
    import urllib.request
    urllib.request.urlretrieve(url, str(dest))
    return dest


def load_grounding_dino(device: Optional[torch.device] = None):
    """Load the Grounding DINO model for text-based object detection."""
    global _grounding_dino_model
    if _grounding_dino_model is not None:
        return _grounding_dino_model

    device = device or get_device()
    try:
        from groundingdino.util.inference import load_model as gd_load
    except ImportError:
        raise RuntimeError(
            "groundingdino is not installed. "
            "Install it with: pip install groundingdino-py"
        )

    config_url = (
        "https://raw.githubusercontent.com/IDEA-Research/GroundingDINO/"
        "main/groundingdino/config/GroundingDINO_SwinT_OGC.py"
    )
    weights_url = (
        "https://github.com/IDEA-Research/GroundingDINO/releases/download/"
        "v0.1.0-alpha/groundingdino_swint_ogc.pth"
    )

    config_path = _download_if_missing(config_url, MODELS_DIR / "groundingdino" / "GroundingDINO_SwinT_OGC.py")
    weights_path = _download_if_missing(weights_url, MODELS_DIR / "groundingdino" / "groundingdino_swint_ogc.pth")

    _grounding_dino_model = gd_load(str(config_path), str(weights_path), device=str(device))
    logger.info("Grounding DINO loaded on %s", device)
    return _grounding_dino_model


def load_sam2(device: Optional[torch.device] = None):
    """Load the SAM 2 image predictor."""
    global _sam2_predictor
    if _sam2_predictor is not None:
        return _sam2_predictor

    device = device or get_device()
    try:
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except ImportError:
        raise RuntimeError(
            "sam2 is not installed. "
            "Install it with: pip install sam-2"
        )

    checkpoint_url = (
        "https://dl.fbaipublicfiles.com/segment_anything_2/"
        "092824/sam2.1_hiera_large.pt"
    )
    checkpoint_path = _download_if_missing(checkpoint_url, MODELS_DIR / "sam2" / "sam2.1_hiera_large.pt")

    model = build_sam2(
        "sam2.1_hiera_l",
        str(checkpoint_path),
        device=str(device),
    )
    _sam2_predictor = SAM2ImagePredictor(model)
    logger.info("SAM 2 image predictor loaded on %s", device)
    return _sam2_predictor


def detect_with_text_prompt(
    image: np.ndarray,
    text_prompt: str,
    box_threshold: float = 0.25,
    text_threshold: float = 0.25,
    device: Optional[torch.device] = None,
) -> list[dict]:
    """
    Detect objects in an image using a text prompt via Grounding DINO.

    Returns a list of detections, each with 'box' (xyxy), 'score', and 'phrase'.
    """
    device = device or get_device()
    model = load_grounding_dino(device)

    from groundingdino.util.inference import predict

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.shape[2] == 3 else image
    from groundingdino.util.utils import get_phrases_from_posmap
    import groundingdino.datasets.transforms as T
    from PIL import Image

    pil_image = Image.fromarray(image_rgb)
    transform = T.Compose([
        T.RandomResize([800], max_size=1333),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    transformed, _ = transform(pil_image, None)

    boxes, logits, phrases = predict(
        model,
        transformed,
        text_prompt,
        box_threshold,
        text_threshold,
        device=str(device),
    )

    h, w = image.shape[:2]
    detections = []
    for box, score, phrase in zip(boxes, logits, phrases):
        cx, cy, bw, bh = box.tolist()
        x1 = int((cx - bw / 2) * w)
        y1 = int((cy - bh / 2) * h)
        x2 = int((cx + bw / 2) * w)
        y2 = int((cy + bh / 2) * h)
        detections.append({
            "box": [x1, y1, x2, y2],
            "score": float(score),
            "phrase": phrase,
        })
    return detections


def detect_with_box(
    image: np.ndarray,
    box: list[int],
    device: Optional[torch.device] = None,
) -> np.ndarray:
    """
    Given a user-drawn bounding box [x1, y1, x2, y2], produce a
    pixel-accurate mask using SAM 2.
    """
    device = device or get_device()
    predictor = load_sam2(device)

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    predictor.set_image(image_rgb)

    input_box = np.array(box).reshape(1, 4)
    masks, scores, _ = predictor.predict(
        box=input_box,
        multimask_output=False,
    )
    return masks[0].astype(np.uint8) * 255


def detect_with_point(
    image: np.ndarray,
    point: tuple[int, int],
    device: Optional[torch.device] = None,
) -> np.ndarray:
    """
    Given a user click point (x, y), produce a pixel-accurate mask using SAM 2.
    """
    device = device or get_device()
    predictor = load_sam2(device)

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    predictor.set_image(image_rgb)

    input_point = np.array([[point[0], point[1]]])
    input_label = np.array([1])
    masks, scores, _ = predictor.predict(
        point_coords=input_point,
        point_labels=input_label,
        multimask_output=False,
    )
    return masks[0].astype(np.uint8) * 255


def detect_watermark(
    image: np.ndarray,
    method: str = "text",
    text_prompt: str = "watermark",
    box: Optional[list[int]] = None,
    point: Optional[tuple[int, int]] = None,
    device: Optional[torch.device] = None,
) -> np.ndarray:
    """
    Main detection entry point.

    method: "text" uses Grounding DINO + SAM 2,
            "box" uses SAM 2 with a user-drawn box,
            "point" uses SAM 2 with a user click.

    Returns a binary mask (0 or 255) at the same resolution as the input image.
    """
    device = device or get_device()

    if method == "text":
        detections = detect_with_text_prompt(image, text_prompt, device=device)
        if not detections:
            logger.warning("No detections found for prompt '%s'", text_prompt)
            return np.zeros(image.shape[:2], dtype=np.uint8)

        best = max(detections, key=lambda d: d["score"])
        mask = detect_with_box(image, best["box"], device=device)
        return mask

    elif method == "box":
        if box is None:
            raise ValueError("box is required when method='box'")
        return detect_with_box(image, box, device=device)

    elif method == "point":
        if point is None:
            raise ValueError("point is required when method='point'")
        return detect_with_point(image, point, device=device)

    else:
        raise ValueError(f"Unknown detection method: {method}")
