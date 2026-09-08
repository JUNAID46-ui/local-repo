from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings, PROJECT_ROOT


def setup_logging(run_id: str | None = None) -> logging.Logger:
    log_dir = PROJECT_ROOT / settings.paths.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("seo_automation")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    console.setFormatter(console_fmt)
    logger.addHandler(console)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = log_dir / f"run_{date_str}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    return logger


class RunLogger:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.start_time = datetime.now(timezone.utc)
        self.entries: list[dict[str, Any]] = []
        self.logger = setup_logging(run_id)

    def log_business_start(self, business_id: str, business_name: str) -> None:
        entry = {
            "event": "business_start",
            "run_id": self.run_id,
            "business_id": business_id,
            "business_name": business_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.entries.append(entry)
        self.logger.info(f"Processing business: {business_name} ({business_id})")

    def log_business_complete(self, business_id: str, topics_count: int, status: str) -> None:
        entry = {
            "event": "business_complete",
            "run_id": self.run_id,
            "business_id": business_id,
            "topics_generated": topics_count,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.entries.append(entry)
        self.logger.info(f"Business {business_id}: {status} ({topics_count} topics)")

    def log_topic(self, business_id: str, topic: str, status: str, details: str = "") -> None:
        entry = {
            "event": "topic_processed",
            "run_id": self.run_id,
            "business_id": business_id,
            "topic": topic,
            "status": status,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.entries.append(entry)
        self.logger.info(f"  Topic '{topic}': {status}")

    def log_error(self, business_id: str, error: str, stage: str = "") -> None:
        entry = {
            "event": "error",
            "run_id": self.run_id,
            "business_id": business_id,
            "stage": stage,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.entries.append(entry)
        self.logger.error(f"Error [{business_id}][{stage}]: {error}")

    def save(self) -> Path:
        log_dir = PROJECT_ROOT / settings.paths.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        end_time = datetime.now(timezone.utc)
        summary = {
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - self.start_time).total_seconds(),
            "entries": self.entries,
        }
        log_file = log_dir / f"run_{self.run_id}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Run log saved: {log_file}")
        return log_file
