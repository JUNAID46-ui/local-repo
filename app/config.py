"""Device detection and global configuration."""

import os
import torch
from pathlib import Path

MODELS_DIR = Path(os.environ.get("MODELS_DIR", Path(__file__).parent.parent / "models"))
MODELS_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", Path(__file__).parent.parent / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent.parent / "outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROGRESS_DIR = Path(os.environ.get("PROGRESS_DIR", Path(__file__).parent.parent / "progress"))
PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "2048"))

DEFAULT_CRF = 17
DEFAULT_MASK_DILATE_PX = 6
DEFAULT_FEATHER_PX = 3
DEFAULT_CONTEXT_PX = 128

MODEL_LICENCES = {
    "GroundingDINO": {
        "licence": "Apache-2.0",
        "commercial": True,
        "url": "https://github.com/IDEA-Research/GroundingDINO",
    },
    "SAM2": {
        "licence": "Apache-2.0",
        "commercial": True,
        "url": "https://github.com/facebookresearch/sam2",
    },
    "ProPainter": {
        "licence": "S-Lab License 1.0 (non-commercial)",
        "commercial": False,
        "url": "https://github.com/sczhou/ProPainter",
    },
    "LaMa": {
        "licence": "Apache-2.0",
        "commercial": True,
        "url": "https://github.com/advimman/lama",
    },
    "RAFT": {
        "licence": "BSD-3-Clause",
        "commercial": True,
        "url": "https://github.com/princeton-vl/RAFT",
    },
}


def get_device() -> torch.device:
    """Pick the best available compute device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def licence_report() -> list[dict]:
    """Return licence info for every model, flagging non-commercial ones."""
    rows = []
    for name, info in MODEL_LICENCES.items():
        rows.append({
            "model": name,
            "licence": info["licence"],
            "commercial_use_allowed": info["commercial"],
            "url": info["url"],
            "warning": "" if info["commercial"] else f"{name} is NOT licensed for commercial use.",
        })
    return rows
