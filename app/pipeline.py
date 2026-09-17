"""Main processing pipeline that orchestrates all modules."""

import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from app.config import (
    DEFAULT_CRF,
    DEFAULT_FEATHER_PX,
    DEFAULT_MASK_DILATE_PX,
    OUTPUT_DIR,
    PROGRESS_DIR,
    get_device,
)

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    DETECTING = "detecting"
    TRACKING = "tracking"
    STATIC_REMOVAL = "static_removal"
    INPAINTING = "inpainting"
    SURFACE_MATCHING = "surface_matching"
    REBUILDING = "rebuilding"
    QUALITY_CHECK = "quality_check"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobProgress:
    job_id: str
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    total_frames: int = 0
    processed_frames: int = 0
    eta_seconds: float = 0.0
    message: str = ""
    quality_issues: list = field(default_factory=list)
    output_path: str = ""
    mask_path: str = ""
    error: str = ""
    started_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "progress": round(self.progress, 2),
            "total_frames": self.total_frames,
            "processed_frames": self.processed_frames,
            "eta_seconds": round(self.eta_seconds, 1),
            "message": self.message,
            "quality_issues": self.quality_issues,
            "output_path": self.output_path,
            "mask_path": self.mask_path,
            "error": self.error,
        }

    def save(self):
        path = PROGRESS_DIR / f"{self.job_id}.json"
        path.write_text(json.dumps(self.to_dict()))

    @classmethod
    def load(cls, job_id: str) -> Optional["JobProgress"]:
        path = PROGRESS_DIR / f"{job_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        progress = cls(job_id=job_id)
        progress.status = JobStatus(data["status"])
        progress.progress = data["progress"]
        progress.total_frames = data["total_frames"]
        progress.processed_frames = data["processed_frames"]
        progress.eta_seconds = data["eta_seconds"]
        progress.message = data["message"]
        progress.quality_issues = data["quality_issues"]
        progress.output_path = data["output_path"]
        progress.mask_path = data["mask_path"]
        progress.error = data["error"]
        return progress


def _update_eta(progress: JobProgress, frames_done: int, total: int):
    elapsed = time.time() - progress.started_at
    if frames_done > 0:
        per_frame = elapsed / frames_done
        remaining = total - frames_done
        progress.eta_seconds = per_frame * remaining
    progress.processed_frames = frames_done
    if total > 0:
        progress.progress = frames_done / total


def process_image(
    image_path: str,
    output_path: str,
    detection_method: str = "text",
    text_prompt: str = "watermark",
    box: Optional[list[int]] = None,
    point: Optional[tuple[int, int]] = None,
    dilate_px: int = DEFAULT_MASK_DILATE_PX,
    feather_px: int = DEFAULT_FEATHER_PX,
    export_mask: bool = False,
    job_id: str = "image_job",
    on_progress: Optional[Callable] = None,
) -> dict:
    """Process a single image to remove a watermark or logo."""
    from app.detection import detect_watermark
    from app.inpainting import inpaint_image_lama
    from app.surface_matching import match_histogram_local, estimate_noise_params, add_matching_grain
    from app.quality import check_edge_quality

    device = get_device()
    progress = JobProgress(job_id=job_id, started_at=time.time())

    progress.status = JobStatus.DETECTING
    progress.message = "Detecting watermark"
    progress.save()

    image = cv2.imread(image_path)
    if image is None:
        raise RuntimeError(f"Cannot read image: {image_path}")

    mask = detect_watermark(
        image,
        method=detection_method,
        text_prompt=text_prompt,
        box=box,
        point=point,
        device=device,
    )

    if mask.max() == 0:
        progress.status = JobStatus.DONE
        progress.message = "No watermark detected"
        progress.save()
        return progress.to_dict()

    if dilate_px > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (dilate_px * 2 + 1, dilate_px * 2 + 1),
        )
        mask = cv2.dilate(mask, kernel)

    if export_mask:
        mask_out = str(Path(output_path).with_suffix(".mask.png"))
        cv2.imwrite(mask_out, mask)
        progress.mask_path = mask_out

    progress.status = JobStatus.INPAINTING
    progress.message = "Inpainting"
    progress.save()

    result = inpaint_image_lama(image, mask, device, feather_px=feather_px)

    progress.status = JobStatus.SURFACE_MATCHING
    progress.message = "Matching surface"
    progress.save()

    result = match_histogram_local(result, mask)
    noise_mean, noise_std = estimate_noise_params(result, mask)
    result = add_matching_grain(result, mask, noise_mean, noise_std)

    progress.status = JobStatus.QUALITY_CHECK
    progress.message = "Checking quality"
    progress.save()

    quality = check_edge_quality(image, result, mask)
    if not quality["passed"]:
        progress.quality_issues = [quality]

    ext = Path(image_path).suffix
    if not output_path.endswith(ext):
        output_path = str(Path(output_path).with_suffix(ext))

    cv2.imwrite(output_path, result)

    progress.status = JobStatus.DONE
    progress.progress = 1.0
    progress.output_path = output_path
    progress.message = "Done"
    progress.save()

    return progress.to_dict()


def process_video(
    video_path: str,
    output_path: str,
    detection_method: str = "text",
    text_prompt: str = "watermark",
    box: Optional[list[int]] = None,
    point: Optional[tuple[int, int]] = None,
    dilate_px: int = DEFAULT_MASK_DILATE_PX,
    feather_px: int = DEFAULT_FEATHER_PX,
    crf: int = DEFAULT_CRF,
    export_mask: bool = False,
    job_id: str = "video_job",
    chunk_size: int = 80,
    on_progress: Optional[Callable] = None,
) -> dict:
    """Process a video to remove a watermark or logo."""
    from app.detection import detect_watermark
    from app.tracking import (
        propagate_mask_through_video,
        refine_mask_with_perspective,
        dilate_masks,
        classify_mask_motion,
    )
    from app.static_overlay import process_static_watermark
    from app.inpainting import inpaint_video_propainter, inpaint_image_lama
    from app.surface_matching import process_surface_matching
    from app.video_io import (
        get_video_info,
        extract_frames,
        read_frames,
        write_frames,
        rebuild_video,
        save_mask_video,
    )
    from app.quality import check_video_quality, select_preview_frames

    device = get_device()
    progress = JobProgress(job_id=job_id, started_at=time.time())

    work_dir = PROGRESS_DIR / job_id
    frames_dir = work_dir / "frames"
    output_frames_dir = work_dir / "output_frames"

    existing = JobProgress.load(job_id)
    if existing and existing.status not in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED):
        logger.info("Resuming job %s from %s", job_id, existing.status)
        progress = existing
        progress.started_at = time.time()

    try:
        info = get_video_info(video_path)
        progress.total_frames = info["total_frames"] or int(info["duration"] * info["fps"])

        if not frames_dir.exists():
            progress.status = JobStatus.DETECTING
            progress.message = "Extracting frames"
            progress.save()
            extract_frames(video_path, frames_dir)

        progress.status = JobStatus.DETECTING
        progress.message = "Detecting watermark on first frame"
        progress.save()

        first_frame = cv2.imread(str(sorted(frames_dir.glob("*.jpg"))[0]))
        initial_mask = detect_watermark(
            first_frame,
            method=detection_method,
            text_prompt=text_prompt,
            box=box,
            point=point,
            device=device,
        )

        if initial_mask.max() == 0:
            progress.status = JobStatus.DONE
            progress.message = "No watermark detected"
            progress.save()
            return progress.to_dict()

        progress.status = JobStatus.TRACKING
        progress.message = "Tracking mask through video"
        progress.save()

        masks = propagate_mask_through_video(frames_dir, initial_mask, 0, device)

        frames = read_frames(frames_dir)
        masks = refine_mask_with_perspective(frames, masks)
        masks = dilate_masks(masks, dilate_px)

        if export_mask:
            mask_out = str(Path(output_path).with_suffix(".mask.mp4"))
            save_mask_video(masks, mask_out, info["fps"], (info["height"], info["width"]))
            progress.mask_path = mask_out

        motion_type = classify_mask_motion(masks)
        logger.info("Mask classified as: %s", motion_type)

        if motion_type == "static":
            progress.status = JobStatus.STATIC_REMOVAL
            progress.message = "Removing static overlay"
            progress.save()

            frames, residual_masks = process_static_watermark(frames, initial_mask)
            masks = {i: residual_masks[i] for i in range(len(residual_masks))}

        has_residual = any(m.max() > 0 for m in masks.values())
        if has_residual:
            progress.status = JobStatus.INPAINTING
            progress.message = "Inpainting masked regions"
            progress.save()

            frames = inpaint_video_propainter(frames, masks, device, chunk_size)
            _update_eta(progress, len(frames) // 2, len(frames))
            progress.save()

        progress.status = JobStatus.SURFACE_MATCHING
        progress.message = "Matching surface texture"
        progress.save()

        frames = process_surface_matching(frames, masks)

        progress.status = JobStatus.QUALITY_CHECK
        progress.message = "Checking quality"
        progress.save()

        original_frames = read_frames(frames_dir)
        problems = check_video_quality(original_frames, frames, masks, fps=info["fps"])
        progress.quality_issues = problems

        progress.status = JobStatus.REBUILDING
        progress.message = "Rebuilding video"
        progress.save()

        write_frames(frames, output_frames_dir)
        rebuild_video(output_frames_dir, output_path, video_path, crf)

        progress.status = JobStatus.DONE
        progress.progress = 1.0
        progress.output_path = output_path
        progress.message = f"Done. {len(problems)} quality warnings."
        progress.save()

        shutil.rmtree(work_dir, ignore_errors=True)

        return progress.to_dict()

    except Exception as e:
        progress.status = JobStatus.FAILED
        progress.error = str(e)
        progress.message = f"Failed: {e}"
        progress.save()
        raise


def get_preview_frames(
    video_path: str,
    masks: dict[int, np.ndarray],
    processed_frames: list[np.ndarray],
    count: int = 5,
) -> list[dict]:
    """Generate before/after preview pairs for sample frames."""
    from app.video_io import get_video_info, extract_frames, read_frames
    from app.quality import select_preview_frames

    info = get_video_info(video_path)
    total = info["total_frames"] or len(processed_frames)
    indices = select_preview_frames(total, count, masks)

    work_dir = PROGRESS_DIR / "preview_temp"
    extract_frames(video_path, work_dir, max_frames=max(indices) + 1)
    originals = read_frames(work_dir)

    previews = []
    for idx in indices:
        if idx < len(originals) and idx < len(processed_frames):
            previews.append({
                "frame_index": idx,
                "timestamp": f"{idx / info['fps']:.2f}s",
                "original": originals[idx],
                "processed": processed_frames[idx],
            })

    shutil.rmtree(work_dir, ignore_errors=True)
    return previews
