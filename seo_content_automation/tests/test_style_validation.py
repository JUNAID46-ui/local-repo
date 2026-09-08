import pytest
from app.models.article import ArticleDraft
from app.services.style_validation import StyleValidator


def _make_article(body_text: str = "") -> ArticleDraft:
    return ArticleDraft(
        title="Test Article",
        primary_keyword="test",
        body_text=body_text or "This is a normal clean article about testing. " * 20,
    )


class TestStyleValidator:
    def setup_method(self):
        self.validator = StyleValidator()

    def test_clean_article_passes(self):
        article = _make_article()
        report = self.validator.validate(article)
        assert report.passed
        assert report.em_dashes_found == 0
        assert report.en_dashes_found == 0

    def test_em_dash_fails(self):
        article = _make_article("This has an em dash — in it. " * 5)
        report = self.validator.validate(article)
        assert not report.passed
        assert report.em_dashes_found > 0

    def test_en_dash_fails(self):
        article = _make_article("Pages 10–20 have the content. " * 5)
        report = self.validator.validate(article)
        assert not report.passed
        assert report.en_dashes_found > 0

    def test_ai_phrases_detected(self):
        article = _make_article(
            "In today's digital world, we leverage cutting-edge technology. " * 10
        )
        report = self.validator.validate(article)
        assert len(report.ai_phrases_found) > 0

    def test_no_ai_phrases(self):
        article = _make_article(
            "Refrigerators need regular maintenance to run efficiently. " * 10
        )
        report = self.validator.validate(article)
        assert len(report.ai_phrases_found) == 0
