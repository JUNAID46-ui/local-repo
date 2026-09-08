import json
import pytest
from pathlib import Path
from app.agents.business_manager import BusinessManager
from app.models.business import BusinessProfile, BusinessState


def _make_business(**overrides) -> BusinessProfile:
    defaults = {
        "business_id": "test_biz",
        "business_name": "Test Business",
        "location": "Test City, TS",
        "services": ["Service A", "Service B"],
        "business_description": "A test business for testing.",
        "website": "https://test.example.com",
    }
    defaults.update(overrides)
    return BusinessProfile(**defaults)


class TestBusinessManager:
    def setup_method(self):
        self.manager = BusinessManager()

    def test_valid_business(self):
        biz = _make_business()
        valid, warnings = self.manager.validate_business(biz)
        assert valid

    def test_missing_name_fails(self):
        biz = _make_business(business_name="")
        valid, warnings = self.manager.validate_business(biz)
        assert not valid

    def test_no_services_fails(self):
        biz = _make_business(services=[])
        valid, warnings = self.manager.validate_business(biz)
        assert not valid

    def test_missing_location_warns(self):
        biz = _make_business(location="")
        valid, warnings = self.manager.validate_business(biz)
        assert valid
        assert any("location" in w.lower() for w in warnings)

    def test_state_save_load(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(self.manager, "data_dir", tmp_path / "businesses")
        state = BusinessState(
            business_id="test",
            generated_topics=["Topic A", "Topic B"],
            generated_primary_keywords=["keyword a"],
            last_run="2026-01-01",
            total_articles_generated=2,
        )
        self.manager.save_state(state)
        loaded = self.manager.load_state("test")
        assert loaded.generated_topics == ["Topic A", "Topic B"]
        assert loaded.total_articles_generated == 2

    def test_load_nonexistent_state(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(self.manager, "data_dir", tmp_path / "businesses")
        state = self.manager.load_state("nonexistent")
        assert state.business_id == "nonexistent"
        assert state.generated_topics == []
