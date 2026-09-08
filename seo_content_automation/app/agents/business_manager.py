from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import settings, PROJECT_ROOT
from app.models.business import BusinessProfile, BusinessState

logger = logging.getLogger("seo_automation")


class BusinessManager:
    def __init__(self) -> None:
        self.data_dir = PROJECT_ROOT / settings.paths.data_dir / "businesses"

    def validate_business(self, business: BusinessProfile) -> tuple[bool, list[str]]:
        warnings: list[str] = []
        if not business.business_name:
            warnings.append("Missing business name")
        if not business.services:
            warnings.append("No services listed")
        if not business.location:
            warnings.append("Missing location")
        if not business.business_description:
            warnings.append("Missing business description")
        if not business.website:
            warnings.append("Missing website URL")

        critical = any(w.startswith("Missing business name") or w == "No services listed" for w in warnings)
        return not critical, warnings

    def load_state(self, business_id: str) -> BusinessState:
        state_path = self._state_path(business_id)
        if state_path.exists():
            with open(state_path) as f:
                data = json.load(f)
            return BusinessState(**data)
        return BusinessState(business_id=business_id)

    def save_state(self, state: BusinessState) -> None:
        state_path = self._state_path(state.business_id)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state.model_dump(), f, indent=2)

    def update_state_after_run(
        self,
        state: BusinessState,
        new_topics: list[str],
        new_keywords: list[str],
        run_date: str,
    ) -> BusinessState:
        state.generated_topics.extend(new_topics)
        state.generated_primary_keywords.extend(new_keywords)
        state.last_run = run_date
        state.total_articles_generated += len(new_topics)
        self.save_state(state)
        return state

    def get_output_dir(self, business: BusinessProfile, date_str: str) -> Path:
        from app.utils.text import sanitize_filename
        folder_name = business.output_folder or sanitize_filename(business.business_name)
        output_dir = PROJECT_ROOT / settings.paths.output_dir / folder_name / date_str
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _state_path(self, business_id: str) -> Path:
        from app.utils.text import sanitize_filename
        safe_id = sanitize_filename(business_id)
        return self.data_dir / safe_id / "state.json"

    def load_topic_history(self, business_id: str) -> list[str]:
        state = self.load_state(business_id)
        return state.generated_topics

    def load_keyword_history(self, business_id: str) -> list[str]:
        state = self.load_state(business_id)
        return state.generated_primary_keywords
