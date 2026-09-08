import pytest
from app.config import Settings, ScheduleSettings, ContentSettings, ModelSettings


class TestScheduleSettings:
    def test_defaults(self):
        s = ScheduleSettings()
        assert s.timezone == "Asia/Karachi"
        assert s.hour == 18
        assert s.minute == 0


class TestContentSettings:
    def test_defaults(self):
        c = ContentSettings()
        assert c.max_articles_per_business == 5
        assert c.target_keyword_density == 2.0
        assert c.max_revision_attempts == 3
        assert c.meta_description_min_length == 140
        assert c.meta_description_max_length == 160


class TestModelSettings:
    def test_defaults(self):
        m = ModelSettings()
        assert "claude" in m.primary.lower() or "claude" in m.primary
        assert "claude" in m.validation.lower() or "claude" in m.validation
