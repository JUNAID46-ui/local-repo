"""Video I/O operations using FFmpeg and OpenCV."""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.config import DEFAULT_CRF

logger = logging.getLogger(__name__)


def get_video_info(video_path: str) -> dict:
    """Extract video metadata using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    probe = json.loads(result.stdout)

    video_stream = None
    audio_stream = None
    for stream in probe.get("streams", []):
        if stream["codec_type"] == "video" and video_stream is None:
            video_stream = stream
        elif stream["codec_type"] == "audio" and audio_stream is None:
            audio_stream = stream

    if video_stream is None:
        raise RuntimeError("No video stream found")

    fps_parts = video_stream.get("r_frame_rate", "30/1").split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0

    return {
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
        "fps": fps,
        "duration": float(probe.get("format", {}).get("duration", 0)),
        "total_frames": int(video_stream.get("nb_frames", 0)),
        "codec": video_stream.get("codec_name", "unknown"),
        "has_audio": audio_stream is not None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
    }


def extract_frames(
    video_path: str,
    output_dir: Path,
    start_frame: int = 0,
    max_frames: Optional[int] = None,
) -> int:
    """
    Extract frames from a video as numbered JPEG files.
    Returns the number of frames extracted.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    count = 0
    while True:
        if max_frames is not None and count >= max_frames:
            break

        ret, frame = cap.read()
        if not ret:
            break

        filename = output_dir / f"{count:06d}.jpg"
        cv2.imwrite(str(filename), frame, [cv2.IMWRITE_JPEG_QUALITY, 100])
        count += 1

    cap.release()
    logger.info("Extracted %d frames to %s", count, output_dir)
    return count


def read_frames(frames_dir: Path, max_frames: Optional[int] = None) -> list[np.ndarray]:
    """Read extracted frames from a directory into a list of numpy arrays."""
    frame_files = sorted(frames_dir.glob("*.jpg"))
    if max_frames is not None:
        frame_files = frame_files[:max_frames]

    frames = []
    for f in frame_files:
        img = cv2.imread(str(f))
        if img is not None:
            frames.append(img)

    return frames


def write_frames(frames: list[np.ndarray], output_dir: Path):
    """Write frames as numbered JPEG files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        cv2.imwrite(str(output_dir / f"{i:06d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 100])


def rebuild_video(
    frames_dir: Path,
    output_path: str,
    original_video: str,
    crf: int = DEFAULT_CRF,
    codec: str = "libx264",
) -> str:
    """
    Rebuild a video from frames using FFmpeg.
    Preserves original resolution, frame rate, and audio.
    """
    info = get_video_info(original_video)
    fps = info["fps"]

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "%06d.jpg"),
    ]

    if info["has_audio"]:
        cmd.extend(["-i", original_video, "-map", "0:v", "-map", "1:a", "-c:a", "copy"])

    cmd.extend([
        "-c:v", codec,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg rebuild failed: {result.stderr}")

    logger.info("Video rebuilt at %s", output_path)
    return output_path


def extract_audio(video_path: str, output_path: str) -> Optional[str]:
    """Extract audio track from video. Returns None if no audio."""
    info = get_video_info(video_path)
    if not info["has_audio"]:
        return None

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn", "-acodec", "copy",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("Audio extraction failed: %s", result.stderr)
        return None

    return output_path


def save_mask_video(
    masks: dict[int, np.ndarray],
    output_path: str,
    fps: float,
    frame_shape: tuple[int, int],
):
    """Export detected masks as a video for review."""
    h, w = frame_shape
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h), isColor=False)

    max_frame = max(masks.keys()) if masks else 0
    for i in range(max_frame + 1):
        if i in masks:
            writer.write(masks[i])
        else:
            writer.write(np.zeros((h, w), dtype=np.uint8))

    writer.release()
    logger.info("Mask video saved to %s", output_path)


def save_mask_image(mask: np.ndarray, output_path: str):
    """Export a detected mask as an image."""
    cv2.imwrite(output_path, mask)
