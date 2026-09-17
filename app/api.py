"""FastAPI backend for the watermark removal tool."""

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    MAX_UPLOAD_SIZE_MB,
    OUTPUT_DIR,
    UPLOAD_DIR,
    get_device,
    licence_report,
)
from app.pipeline import JobProgress, JobStatus, process_image, process_video

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Watermark Remover",
    description="Remove watermarks and logos from images and videos you own or have permission to edit.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}

_running_jobs: dict[str, JobProgress] = {}


def _is_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in IMAGE_EXTENSIONS


def _is_video(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS


@app.get("/")
async def root():
    """Serve the frontend."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "Watermark Remover API is running. Use /docs for API documentation."}


@app.get("/api/health")
async def health():
    device = get_device()
    return {"status": "ok", "device": str(device)}


@app.get("/api/licences")
async def get_licences():
    """List licences for all models used."""
    return licence_report()


@app.post("/api/process")
async def process_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    rights_confirmed: bool = Form(...),
    detection_method: str = Form("text"),
    text_prompt: str = Form("watermark"),
    box_x1: Optional[int] = Form(None),
    box_y1: Optional[int] = Form(None),
    box_x2: Optional[int] = Form(None),
    box_y2: Optional[int] = Form(None),
    point_x: Optional[int] = Form(None),
    point_y: Optional[int] = Form(None),
    dilate_px: int = Form(6),
    feather_px: int = Form(3),
    crf: int = Form(17),
    export_mask: bool = Form(False),
):
    """
    Upload a file and start watermark removal.

    You must confirm you own or have permission to edit the file.
    """
    if not rights_confirmed:
        raise HTTPException(
            status_code=400,
            detail="You must confirm you own or have permission to edit this file.",
        )

    if file.size and file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_MB} MB.",
        )

    filename = file.filename or "upload"
    if not (_is_image(filename) or _is_video(filename)):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: {IMAGE_EXTENSIONS | VIDEO_EXTENSIONS}",
        )

    job_id = str(uuid.uuid4())[:12]
    upload_path = UPLOAD_DIR / job_id / filename
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    output_filename = f"cleaned_{filename}"
    output_path = str(OUTPUT_DIR / job_id / output_filename)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    box = None
    if all(v is not None for v in [box_x1, box_y1, box_x2, box_y2]):
        box = [box_x1, box_y1, box_x2, box_y2]

    point = None
    if point_x is not None and point_y is not None:
        point = (point_x, point_y)

    if _is_image(filename):
        background_tasks.add_task(
            _run_image_job,
            job_id, str(upload_path), output_path,
            detection_method, text_prompt, box, point,
            dilate_px, feather_px, export_mask,
        )
    else:
        background_tasks.add_task(
            _run_video_job,
            job_id, str(upload_path), output_path,
            detection_method, text_prompt, box, point,
            dilate_px, feather_px, crf, export_mask,
        )

    return {"job_id": job_id, "status": "pending", "message": "Processing started."}


def _run_image_job(
    job_id, upload_path, output_path,
    detection_method, text_prompt, box, point,
    dilate_px, feather_px, export_mask,
):
    try:
        process_image(
            upload_path, output_path,
            detection_method=detection_method,
            text_prompt=text_prompt,
            box=box, point=point,
            dilate_px=dilate_px, feather_px=feather_px,
            export_mask=export_mask, job_id=job_id,
        )
    except Exception as e:
        logger.error("Image job %s failed: %s", job_id, e, exc_info=True)
        progress = JobProgress(job_id=job_id)
        progress.status = JobStatus.FAILED
        progress.error = str(e)
        progress.save()


def _run_video_job(
    job_id, upload_path, output_path,
    detection_method, text_prompt, box, point,
    dilate_px, feather_px, crf, export_mask,
):
    try:
        process_video(
            upload_path, output_path,
            detection_method=detection_method,
            text_prompt=text_prompt,
            box=box, point=point,
            dilate_px=dilate_px, feather_px=feather_px,
            crf=crf, export_mask=export_mask, job_id=job_id,
        )
    except Exception as e:
        logger.error("Video job %s failed: %s", job_id, e, exc_info=True)
        progress = JobProgress(job_id=job_id)
        progress.status = JobStatus.FAILED
        progress.error = str(e)
        progress.save()


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get the current status of a processing job."""
    progress = JobProgress.load(job_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return progress.to_dict()


@app.get("/api/jobs/{job_id}/download")
async def download_result(job_id: str):
    """Download the processed file."""
    progress = JobProgress.load(job_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if progress.status != JobStatus.DONE:
        raise HTTPException(status_code=400, detail="Job is not complete yet")

    if not progress.output_path or not Path(progress.output_path).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(
        progress.output_path,
        filename=Path(progress.output_path).name,
        media_type="application/octet-stream",
    )


@app.get("/api/jobs/{job_id}/mask")
async def download_mask(job_id: str):
    """Download the detected mask."""
    progress = JobProgress.load(job_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if not progress.mask_path or not Path(progress.mask_path).exists():
        raise HTTPException(status_code=404, detail="Mask file not found. Enable export_mask.")

    return FileResponse(
        progress.mask_path,
        filename=Path(progress.mask_path).name,
        media_type="application/octet-stream",
    )


@app.post("/api/batch")
async def batch_process(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    rights_confirmed: bool = Form(...),
    detection_method: str = Form("text"),
    text_prompt: str = Form("watermark"),
    dilate_px: int = Form(6),
    export_mask: bool = Form(False),
):
    """Batch process multiple files."""
    if not rights_confirmed:
        raise HTTPException(
            status_code=400,
            detail="You must confirm you own or have permission to edit these files.",
        )

    jobs = []
    for upload_file in files:
        filename = upload_file.filename or "upload"
        if not (_is_image(filename) or _is_video(filename)):
            continue

        job_id = str(uuid.uuid4())[:12]
        upload_path = UPLOAD_DIR / job_id / filename
        upload_path.parent.mkdir(parents=True, exist_ok=True)

        with open(upload_path, "wb") as f:
            shutil.copyfileobj(upload_file.file, f)

        output_filename = f"cleaned_{filename}"
        output_path = str(OUTPUT_DIR / job_id / output_filename)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if _is_image(filename):
            background_tasks.add_task(
                _run_image_job,
                job_id, str(upload_path), output_path,
                detection_method, text_prompt, None, None,
                dilate_px, 3, export_mask,
            )
        else:
            background_tasks.add_task(
                _run_video_job,
                job_id, str(upload_path), output_path,
                detection_method, text_prompt, None, None,
                dilate_px, 3, 17, export_mask,
            )

        jobs.append({"job_id": job_id, "filename": filename})

    return {"jobs": jobs, "total": len(jobs)}


@app.post("/api/colour-match")
async def colour_match_endpoint(
    file: UploadFile = File(...),
    rights_confirmed: bool = Form(...),
    source_start: int = Form(...),
    source_end: int = Form(...),
    target_start: int = Form(...),
    target_end: int = Form(...),
    strength: float = Form(1.0),
):
    """Match colours between two time ranges of a video."""
    if not rights_confirmed:
        raise HTTPException(status_code=400, detail="Rights confirmation required.")

    from app.colour_match import match_video_colour_ranges
    from app.video_io import extract_frames, read_frames, write_frames, rebuild_video, get_video_info

    job_id = str(uuid.uuid4())[:12]
    filename = file.filename or "video.mp4"
    upload_path = UPLOAD_DIR / job_id / filename
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    frames_dir = UPLOAD_DIR / job_id / "frames"
    extract_frames(str(upload_path), frames_dir)
    frames = read_frames(frames_dir)

    matched = match_video_colour_ranges(
        frames, source_start, source_end, target_start, target_end, strength
    )

    output_frames_dir = UPLOAD_DIR / job_id / "output_frames"
    write_frames(matched, output_frames_dir)

    output_path = str(OUTPUT_DIR / job_id / f"colour_matched_{filename}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    rebuild_video(output_frames_dir, output_path, str(upload_path))

    return FileResponse(output_path, filename=f"colour_matched_{filename}")
