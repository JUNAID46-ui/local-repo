from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def today_str() -> str:
    return utc_now().strftime("%Y-%m-%d")


def generate_run_id() -> str:
    return utc_now().strftime("%Y%m%d_%H%M%S")
