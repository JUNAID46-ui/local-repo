#!/usr/bin/env python3
"""Command line interface for the watermark removal tool."""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("watermark-remover")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Remove watermarks and logos from images and videos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Remove a watermark from an image using text detection
  python run.py image photo.jpg -o clean_photo.jpg -t "watermark"

  # Remove a logo from a video with a bounding box
  python run.py video clip.mp4 -o clean_clip.mp4 --method box --box 10 20 200 80

  # Batch process a folder
  python run.py batch ./input_folder -o ./output_folder

  # Start the web server
  python run.py serve --port 8000

  # Show model licences
  python run.py licences
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    img_parser = subparsers.add_parser("image", help="Process a single image")
    img_parser.add_argument("input", help="Path to the input image")
    img_parser.add_argument("-o", "--output", help="Path for the output image")
    img_parser.add_argument("--method", choices=["text", "box", "point"], default="text")
    img_parser.add_argument("-t", "--text-prompt", default="watermark", help="Text prompt for detection")
    img_parser.add_argument("--box", nargs=4, type=int, metavar=("X1", "Y1", "X2", "Y2"))
    img_parser.add_argument("--point", nargs=2, type=int, metavar=("X", "Y"))
    img_parser.add_argument("--dilate", type=int, default=6, help="Mask dilation in pixels")
    img_parser.add_argument("--feather", type=int, default=3, help="Edge feather in pixels")
    img_parser.add_argument("--export-mask", action="store_true", help="Save the detected mask")
    img_parser.add_argument("--confirm-rights", action="store_true", required=True,
                            help="Confirm you own the file or have permission to edit it")

    vid_parser = subparsers.add_parser("video", help="Process a video")
    vid_parser.add_argument("input", help="Path to the input video")
    vid_parser.add_argument("-o", "--output", help="Path for the output video")
    vid_parser.add_argument("--method", choices=["text", "box", "point"], default="text")
    vid_parser.add_argument("-t", "--text-prompt", default="watermark", help="Text prompt for detection")
    vid_parser.add_argument("--box", nargs=4, type=int, metavar=("X1", "Y1", "X2", "Y2"))
    vid_parser.add_argument("--point", nargs=2, type=int, metavar=("X", "Y"))
    vid_parser.add_argument("--dilate", type=int, default=6, help="Mask dilation in pixels")
    vid_parser.add_argument("--feather", type=int, default=3, help="Edge feather in pixels")
    vid_parser.add_argument("--crf", type=int, default=17, help="Video quality (lower is better, 0-51)")
    vid_parser.add_argument("--export-mask", action="store_true", help="Save the detected mask")
    vid_parser.add_argument("--confirm-rights", action="store_true", required=True,
                            help="Confirm you own the file or have permission to edit it")

    batch_parser = subparsers.add_parser("batch", help="Process a folder of files")
    batch_parser.add_argument("input_dir", help="Input folder")
    batch_parser.add_argument("-o", "--output-dir", required=True, help="Output folder")
    batch_parser.add_argument("--method", choices=["text", "box", "point"], default="text")
    batch_parser.add_argument("-t", "--text-prompt", default="watermark")
    batch_parser.add_argument("--dilate", type=int, default=6)
    batch_parser.add_argument("--export-mask", action="store_true")
    batch_parser.add_argument("--confirm-rights", action="store_true", required=True,
                            help="Confirm you own these files or have permission to edit them")

    serve_parser = subparsers.add_parser("serve", help="Start the web server")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)

    subparsers.add_parser("licences", help="Show model licences")

    return parser.parse_args()


def cmd_image(args):
    from app.pipeline import process_image

    input_path = args.input
    output_path = args.output or str(Path(input_path).stem + "_clean" + Path(input_path).suffix)

    logger.info("Processing image: %s", input_path)
    start = time.time()

    result = process_image(
        image_path=input_path,
        output_path=output_path,
        detection_method=args.method,
        text_prompt=args.text_prompt,
        box=args.box,
        point=tuple(args.point) if args.point else None,
        dilate_px=args.dilate,
        feather_px=args.feather,
        export_mask=args.export_mask,
    )

    elapsed = time.time() - start
    logger.info("Done in %.1fs. Output: %s", elapsed, result.get("output_path", output_path))

    if result.get("quality_issues"):
        logger.warning("Quality warnings: %s", json.dumps(result["quality_issues"], indent=2))

    return 0


def cmd_video(args):
    from app.pipeline import process_video

    input_path = args.input
    output_path = args.output or str(Path(input_path).stem + "_clean" + Path(input_path).suffix)

    logger.info("Processing video: %s", input_path)
    start = time.time()

    result = process_video(
        video_path=input_path,
        output_path=output_path,
        detection_method=args.method,
        text_prompt=args.text_prompt,
        box=args.box,
        point=tuple(args.point) if args.point else None,
        dilate_px=args.dilate,
        feather_px=args.feather,
        crf=args.crf,
        export_mask=args.export_mask,
    )

    elapsed = time.time() - start
    logger.info("Done in %.1fs. Output: %s", elapsed, result.get("output_path", output_path))

    if result.get("quality_issues"):
        logger.warning("Quality warnings:")
        for issue in result["quality_issues"]:
            logger.warning(
                "  Frame %d (%s): mean_diff=%.1f max_diff=%.1f",
                issue["frame"], issue["timestamp"], issue["mean_diff"], issue["max_diff"],
            )

    return 0


def cmd_batch(args):
    from app.pipeline import process_image, process_video

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.iterdir())
    supported = [
        f for f in files
        if f.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    ]

    if not supported:
        logger.error("No supported files found in %s", input_dir)
        return 1

    logger.info("Found %d files to process", len(supported))
    start = time.time()

    for i, filepath in enumerate(supported, 1):
        output_path = str(output_dir / f"cleaned_{filepath.name}")
        logger.info("[%d/%d] Processing %s", i, len(supported), filepath.name)

        try:
            if filepath.suffix.lower() in IMAGE_EXTENSIONS:
                process_image(
                    image_path=str(filepath),
                    output_path=output_path,
                    detection_method=args.method,
                    text_prompt=args.text_prompt,
                    dilate_px=args.dilate,
                    export_mask=args.export_mask,
                    job_id=f"batch_{i}",
                )
            else:
                process_video(
                    video_path=str(filepath),
                    output_path=output_path,
                    detection_method=args.method,
                    text_prompt=args.text_prompt,
                    dilate_px=args.dilate,
                    export_mask=args.export_mask,
                    job_id=f"batch_{i}",
                )
        except Exception as e:
            logger.error("Failed to process %s: %s", filepath.name, e)

    elapsed = time.time() - start
    logger.info("Batch complete. %d files in %.1fs", len(supported), elapsed)
    return 0


def cmd_serve(args):
    import uvicorn
    logger.info("Starting web server on %s:%d", args.host, args.port)
    uvicorn.run("app.api:app", host=args.host, port=args.port, reload=False)
    return 0


def cmd_licences():
    from app.config import licence_report

    report = licence_report()
    print("\nModel Licences:")
    print("-" * 70)
    for row in report:
        status = "OK" if row["commercial_use_allowed"] else "WARNING"
        print(f"  {row['model']:<20} {row['licence']:<30} [{status}]")
        if row["warning"]:
            print(f"    {row['warning']}")
        print(f"    {row['url']}")
    print("-" * 70)
    print()

    non_commercial = [r for r in report if not r["commercial_use_allowed"]]
    if non_commercial:
        print(f"WARNING: {len(non_commercial)} model(s) are NOT licensed for commercial use:")
        for r in non_commercial:
            print(f"  - {r['model']}: {r['licence']}")
    else:
        print("All models are licensed for commercial use.")

    return 0


def main():
    args = parse_args()

    if args.command is None:
        print("No command specified. Use --help for usage.")
        return 1

    if args.command == "image":
        return cmd_image(args)
    elif args.command == "video":
        return cmd_video(args)
    elif args.command == "batch":
        return cmd_batch(args)
    elif args.command == "serve":
        return cmd_serve(args)
    elif args.command == "licences":
        return cmd_licences()
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
