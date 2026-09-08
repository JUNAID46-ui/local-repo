import pytest
from app.models.article import ArticleDraft
from app.models.business import BusinessProfile
from app.services.seo_validation import SEOValidator


def _make_article(**overrides) -> ArticleDraft:
    defaults = {
        "title": "Refrigerator Repair in Tucson - Complete Guide",
        "primary_keyword": "refrigerator repair",
        "body_text": " ".join(["refrigerator repair"] + ["word"] * 48) * 4,
        "meta_description": "Professional refrigerator repair in Tucson. Fast service for all brands.",
        "url_slug": "refrigerator-repair-tucson",
    }
    defaults.update(overrides)
    return ArticleDraft(**defaults)


def _make_business() -> BusinessProfile:
    return BusinessProfile(
        business_id="test",
        business_name="Test Repair Co",
        location="Tucson, Arizona",
        services=["Refrigerator Repair"],
    )


class TestSEOValidator:
    def setup_method(self):
        self.validator = SEOValidator()
        self.business = _make_business()

    def test_valid_article_passes(self):
        article = _make_article()
        report = self.validator.validate(article, self.business)
        assert report.primary_keyword_present

    def test_missing_meta_description_fails(self):
        article = _make_article(meta_description="")
        report = self.validator.validate(article, self.business)
        assert not report.passed
        assert any("Missing meta description" in f.description for f in report.findings)

    def test_short_meta_description_warning(self):
        article = _make_article(meta_description="Too short")
        report = self.validator.validate(article, self.business)
        assert any("too short" in f.description for f in report.findings)

    def test_long_meta_description_warning(self):
        article = _make_article(meta_description="x" * 200)
        report = self.validator.validate(article, self.business)
        assert any("too long" in f.description for f in report.findings)

    def test_keyword_not_in_title(self):
        article = _make_article(title="Home Appliance Guide")
        report = self.validator.validate(article, self.business)
        assert not report.title_has_keyword

    def test_missing_url_slug(self):
        article = _make_article(url_slug="")
        report = self.validator.validate(article, self.business)
        assert not report.url_slug_ok
