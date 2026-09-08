from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_yaml_settings() -> dict[str, Any]:
    settings_path = PROJECT_ROOT / "config" / "settings.yaml"
    if not settings_path.exists():
        settings_path = PROJECT_ROOT / "config" / "settings.example.yaml"
    if settings_path.exists():
        with open(settings_path) as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml = _load_yaml_settings()


class ScheduleSettings(BaseSettings):
    timezone: str = _yaml.get("schedule", {}).get("timezone", "Asia/Karachi")
    hour: int = _yaml.get("schedule", {}).get("hour", 18)
    minute: int = _yaml.get("schedule", {}).get("minute", 0)


class ContentSettings(BaseSettings):
    max_articles_per_business: int = _yaml.get("content", {}).get("max_articles_per_business", 5)
    target_keyword_density: float = _yaml.get("content", {}).get("target_keyword_density", 2.0)
    keyword_density_tolerance: float = _yaml.get("content", {}).get("keyword_density_tolerance", 0.5)
    max_revision_attempts: int = _yaml.get("content", {}).get("max_revision_attempts", 3)
    meta_description_min_length: int = _yaml.get("content", {}).get("meta_description_min_length", 140)
    meta_description_max_length: int = _yaml.get("content", {}).get("meta_description_max_length", 160)
    min_article_word_count: int = _yaml.get("content", {}).get("min_article_word_count", 1200)
    max_article_word_count: int = _yaml.get("content", {}).get("max_article_word_count", 2500)


class ImageSettings(BaseSettings):
    featured_count: int = _yaml.get("images", {}).get("featured_count", 1)
    supporting_min: int = _yaml.get("images", {}).get("supporting_min", 2)
    supporting_max: int = _yaml.get("images", {}).get("supporting_max", 4)


class ModelSettings(BaseSettings):
    primary: str = _yaml.get("models", {}).get("primary", "claude-sonnet-4-20250514")
    research: str = _yaml.get("models", {}).get("research", "claude-sonnet-4-20250514")
    validation: str = _yaml.get("models", {}).get("validation", "claude-haiku-4-5-20251001")


class PathSettings(BaseSettings):
    output_dir: str = _yaml.get("paths", {}).get("output_dir", "output")
    log_dir: str = _yaml.get("paths", {}).get("log_dir", "logs")
    data_dir: str = _yaml.get("paths", {}).get("data_dir", "data")

    @property
    def output_path(self) -> Path:
        return PROJECT_ROOT / self.output_dir

    @property
    def log_path(self) -> Path:
        return PROJECT_ROOT / self.log_dir

    @property
    def data_path(self) -> Path:
        return PROJECT_ROOT / self.data_dir


class GoogleSettings(BaseSettings):
    sheet_id: str = Field(default=os.getenv("GOOGLE_SHEET_ID", ""))
    drive_folder_id: str = Field(default=os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""))
    service_account_file: str = Field(
        default=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
    )


class Settings(BaseSettings):
    anthropic_api_key: str = Field(default=os.getenv("ANTHROPIC_API_KEY", ""))
    schedule: ScheduleSettings = ScheduleSettings()
    content: ContentSettings = ContentSettings()
    images: ImageSettings = ImageSettings()
    models: ModelSettings = ModelSettings()
    paths: PathSettings = PathSettings()
    google: GoogleSettings = GoogleSettings()
    ai_phrase_blocklist: list[str] = Field(
        default_factory=lambda: _yaml.get("ai_phrase_blocklist", [])
    )
    commercial_intent_terms: list[str] = Field(
        default_factory=lambda: _yaml.get("commercial_intent_terms", [])
    )


settings = Settings()
