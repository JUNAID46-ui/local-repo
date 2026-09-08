import pytest
from app.models.business import BusinessProfile, BusinessState
from app.models.topic import TopicCandidate, TopicSelection
from app.models.research import KeywordResearch, ResearchEvidence, TopicResearch
from app.models.article import ArticleDraft, FinalArticle, ImageConcept
from app.models.qa import QAResult, SEOReport, QAFinding


class TestBusinessProfile:
    def test_create_minimal(self):
        biz = BusinessProfile(business_id="test", business_name="Test")
        assert biz.business_id == "test"
        assert biz.active is True
        assert biz.services == []

    def test_create_full(self):
        biz = BusinessProfile(
            business_id="test",
            business_name="Test Biz",
            website="https://test.com",
            location="City, State",
            services=["A", "B"],
            service_areas=["City"],
        )
        assert len(biz.services) == 2
        assert biz.location == "City, State"


class TestBusinessState:
    def test_default_state(self):
        state = BusinessState(business_id="test")
        assert state.generated_topics == []
        assert state.total_articles_generated == 0

    def test_serialization(self):
        state = BusinessState(
            business_id="test",
            generated_topics=["Topic A"],
            last_run="2026-01-01",
        )
        data = state.model_dump()
        restored = BusinessState(**data)
        assert restored.generated_topics == ["Topic A"]


class TestTopicCandidate:
    def test_create(self):
        topic = TopicCandidate(
            title="Test Topic",
            service_category="Service A",
            search_intent="commercial",
        )
        assert topic.selected is False
        assert topic.rejection_reason == ""


class TestKeywordResearch:
    def test_create(self):
        kw = KeywordResearch(primary_keyword="test keyword")
        assert kw.primary_keyword == "test keyword"
        assert kw.secondary_keywords == []

    def test_full_keyword_set(self):
        kw = KeywordResearch(
            primary_keyword="test",
            secondary_keywords=["a", "b"],
            semantic_keywords=["c"],
            question_keywords=["what is test?"],
        )
        assert len(kw.secondary_keywords) == 2


class TestResearchEvidence:
    def test_default_status(self):
        ev = ResearchEvidence(claim="Some claim")
        assert ev.verification_status == "UNVERIFIED"


class TestArticleDraft:
    def test_create(self):
        article = ArticleDraft(
            title="Test",
            primary_keyword="test",
            body_text="Hello world",
            word_count=2,
        )
        assert article.word_count == 2
        assert article.images == []


class TestQAResult:
    def test_default(self):
        qa = QAResult()
        assert qa.overall_passed is False
        assert qa.critical_failures == []

    def test_finding(self):
        finding = QAFinding(
            category="seo",
            severity="critical",
            description="Missing keyword",
            suggestion="Add keyword",
        )
        assert finding.auto_fixable is False
