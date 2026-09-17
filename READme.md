# Watermark Remover

**Watermark and logo removal tool** for images and videos that you own or have written permission to edit. Built with Python, it combines state-of-the-art detection, segmentation, tracking, and inpainting models to cleanly remove watermarks while preserving the original surface texture, grain, and lighting.

This tool is designed strictly for use on your own content. You must confirm file ownership or editing rights before processing any file, both in the web interface and via the command line.

## What It Handles

- Static watermarks in a fixed position (corner badges, editing app logos)
- Watermarks that move, fade, or change size across a video
- Logos printed on 3D objects that rotate through a full 360 degrees, changing angle, perspective, and lighting
- Single images with semi-transparent or solid watermarks

## How It Works

1. **Detection** - Grounding DINO finds the watermark from a text prompt ("watermark", "logo"), or SAM 2 refines a user-drawn box or click into a pixel-accurate mask.
2. **Tracking** - SAM 2 video prediction propagates the mask through every frame. For rotating objects, OpenCV ORB feature matching estimates per-frame perspective to refine mask shape.
3. **Static shortcut** - If the mask barely moves, the tool measures per-pixel overlay opacity across frames and mathematically removes the semi-transparent parts. Only fully opaque areas go to inpainting.
4. **Inpainting** - ProPainter fills masked video regions using optical flow so real texture from other frames gets pulled in. LaMa handles single images and any remaining gaps.
5. **Surface matching** - Histogram matching, synthetic grain injection, and temporal smoothing with optical flow keep the filled area looking like the surrounding surface.
6. **Output** - FFmpeg rebuilds the video at original resolution, frame rate, and audio. Images save in their original format and size.

## Requirements

- Python 3.10 or newer
- FFmpeg installed system-wide (`apt install ffmpeg` or `brew install ffmpeg`)
- An NVIDIA GPU with CUDA is strongly recommended for reasonable processing times
- Apple Silicon (MPS) works but is slower
- CPU processing is supported but will be very slow on video

## Installation

```bash
# Clone the repository
git clone <this-repo-url>
cd watermark-remover

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install PyTorch with CUDA (adjust for your CUDA version)
# See https://pytorch.org/get-started/locally/
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install dependencies
pip install -r requirements.txt

# Install Grounding DINO
pip install groundingdino-py

# Install SAM 2
pip install sam-2

# Install ProPainter (optional, for video inpainting)
pip install git+https://github.com/sczhou/ProPainter.git
```

Model weights download automatically on first run and are cached in the `models/` directory.

## Usage

### Web Interface

```bash
python run.py serve --port 8000
```

Open `http://localhost:8000` in your browser. Upload a file, confirm you have the rights to edit it, choose a detection method, and click Process.

### Command Line

**Remove a watermark from an image:**
```bash
python run.py image photo.jpg -o clean_photo.jpg -t "watermark" --confirm-rights
```

**Remove a logo from a video:**
```bash
python run.py video clip.mp4 -o clean_clip.mp4 -t "logo" --confirm-rights
```

**Use a bounding box instead of text detection:**
```bash
python run.py image photo.jpg -o clean.jpg --method box --box 10 20 200 80 --confirm-rights
```

**Batch process a folder:**
```bash
python run.py batch ./input_folder -o ./output_folder --confirm-rights
```

**Check model licences:**
```bash
python run.py licences
```

### CLI Options

| Option | Default | Description |
|---|---|---|
| `--method` | `text` | Detection method: `text`, `box`, or `point` |
| `-t, --text-prompt` | `watermark` | Text prompt for auto-detection |
| `--box X1 Y1 X2 Y2` | - | Bounding box coordinates |
| `--point X Y` | - | Click point coordinates |
| `--dilate` | `6` | Mask dilation in pixels (covers soft edges) |
| `--feather` | `3` | Edge feather in pixels for blending |
| `--crf` | `17` | Video quality, lower is better (0-51) |
| `--export-mask` | off | Save the detected mask separately |
| `--confirm-rights` | required | Confirm file ownership or permission |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web interface |
| `GET` | `/api/health` | Health check and device info |
| `GET` | `/api/licences` | List all model licences |
| `POST` | `/api/process` | Upload and process a file |
| `GET` | `/api/jobs/{id}` | Check job progress |
| `GET` | `/api/jobs/{id}/download` | Download processed file |
| `GET` | `/api/jobs/{id}/mask` | Download detected mask |
| `POST` | `/api/batch` | Batch process multiple files |
| `POST` | `/api/colour-match` | Match colours between video time ranges |

Full API docs are available at `/docs` when the server is running.

## Project Structure

```
watermark-remover/
├── app/
│   ├── __init__.py
│   ├── api.py               # FastAPI backend
│   ├── config.py             # Device detection and settings
│   ├── detection.py          # Grounding DINO + SAM 2 detection
│   ├── tracking.py           # SAM 2 video tracking + perspective
│   ├── static_overlay.py     # Static watermark opacity estimation
│   ├── inpainting.py         # ProPainter + LaMa inpainting
│   ├── surface_matching.py   # Texture, grain, and temporal smoothing
│   ├── video_io.py           # FFmpeg video read/write
│   ├── colour_match.py       # Colour grading between time ranges
│   ├── quality.py            # Edge quality checks
│   └── pipeline.py           # Main processing orchestration
├── frontend/
│   └── index.html            # Web interface
├── models/                   # Auto-downloaded model weights
├── run.py                    # CLI entry point
├── requirements.txt
└── README.md
```

## Model Licences

| Model | Licence | Commercial Use |
|---|---|---|
| Grounding DINO | Apache-2.0 | Yes |
| SAM 2 | Apache-2.0 | Yes |
| ProPainter | S-Lab License 1.0 | **No** |
| LaMa | Apache-2.0 | Yes |
| RAFT | BSD-3-Clause | Yes |

ProPainter is not licensed for commercial use. If you need commercial use, the tool falls back to LaMa for frame-by-frame video inpainting, which is fully commercially licensed. Run `python run.py licences` to see the full licence report.

## Quality Checks

After processing, the tool compares the edges of filled areas with their surroundings and reports any frame where the difference exceeds a threshold. For videos, you get timestamps for each problem frame so you can inspect them. The web interface shows these as quality warnings in the result panel.

## Resumable Processing

Video processing saves progress to disk. If a job is interrupted, re-running it with the same job ID picks up where it left off rather than starting over. Frame extraction, mask propagation, and inpainting progress are all checkpointed.
