import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.agents.base import MockAgent
from app.agents.topic_selector import TopicSelector
from app.agents.keyword_researcher import KeywordResearcher
from app.agents.research_agent import ResearchAgent
from app.agents.content_writer import ContentWriter
from app.agents.seo_editor import SEOEditor
from app.agents.fact_checker import FactChecker
from app.models.business import BusinessProfile
from app.services.pipeline import ContentPipeline


MOCK_TOPIC_RESPONSE = {
    "selected_topics": [
        {
            "title": "Signs Your Refrigerator Compressor Is Failing",
            "service_category": "Refrigerator Repair",
            "search_intent": "informational",
            "estimated_value": "high",
            "aeo_opportunity": "What are signs of refrigerator compressor failure",
            "geo_opportunity": "Tucson heat puts extra strain on compressors",
        },
        {
            "title": "How to Choose the Right Oven for Your Tucson Home",
            "service_category": "Oven Repair",
            "search_intent": "commercial",
            "estimated_value": "medium",
            "aeo_opportunity": "Best oven types for desert climate",
            "geo_opportunity": "Tucson altitude affects baking",
        },
    ],
    "rejected_topics": [],
    "selection_reasoning": "Selected diverse topics across services",
}

MOCK_KEYWORD_RESPONSE = {
    "primary_keyword": "refrigerator compressor failure",
    "secondary_keywords": ["fridge compressor", "compressor repair"],
    "semantic_keywords": ["cooling system", "refrigerant"],
    "related_entities": ["compressor", "refrigerant"],
    "commercial_keywords": ["repair service", "technician"],
    "local_keywords": ["Tucson refrigerator repair"],
    "question_keywords": ["why is my fridge not cooling"],
    "long_tail_keywords": ["refrigerator compressor failure signs Tucson"],
    "search_intent": "informational",
    "keyword_variations": ["fridge compressor issues"],
}

MOCK_RESEARCH_RESPONSE = {
    "business_facts": [
        {"claim": "Serves Tucson area", "source": "business", "source_type": "business", "verification_status": "BUSINESS-PROVIDED"},
    ],
    "topic_facts": [
        {"claim": "Compressors typically last 10-20 years", "source": "industry knowledge", "source_type": "industry", "verification_status": "COMMON_KNOWLEDGE"},
    ],
    "common_problems": ["Compressor overheating", "Refrigerant leaks"],
    "solutions": ["Professional compressor replacement", "Refrigerant recharge"],
    "user_questions": ["How do I know if my compressor is bad?"],
    "local_context": ["Tucson heat increases compressor workload"],
    "industry_terminology": ["hermetic compressor", "refrigerant cycle"],
    "sources": [],
    "aeo_questions": ["What causes refrigerator compressor failure?"],
    "geo_factors": ["Desert climate stress on cooling systems"],
}

MOCK_ARTICLE_RESPONSE = {
    "title": "Signs Your Refrigerator Compressor Is Failing",
    "primary_keyword": "refrigerator compressor failure",
    "body_text": (
        "## What Is a Refrigerator Compressor?\n\n"
        "The compressor is the heart of your refrigerator's cooling system. "
        "When a refrigerator compressor failure occurs, your food is at risk. "
        "Understanding the signs of refrigerator compressor failure can save you "
        "time and money on unnecessary repairs.\n\n"
        "## Common Signs of Compressor Problems\n\n"
        "Your refrigerator may show several warning signs before a complete "
        "refrigerator compressor failure. Listen for clicking or humming sounds "
        "that indicate the compressor is struggling to start. A warm refrigerator "
        "despite correct thermostat settings points to potential compressor issues.\n\n"
        "## How Tucson Heat Affects Your Compressor\n\n"
        "In Tucson, summer temperatures regularly exceed 100 degrees. This extreme "
        "heat forces your refrigerator compressor to work harder, increasing the "
        "risk of refrigerator compressor failure. Proper ventilation around your "
        "refrigerator helps reduce this strain.\n\n"
        "## When to Call a Repair Technician\n\n"
        "If you notice these warning signs, contact a qualified appliance repair "
        "technician. Attempting DIY compressor repair can void warranties and "
        "create safety hazards. A professional can diagnose whether the issue is "
        "a true refrigerator compressor failure or a simpler fix.\n\n"
        "## Frequently Asked Questions\n\n"
        "### How long does a refrigerator compressor last?\n\n"
        "Most refrigerator compressors last between 10 and 20 years with proper "
        "maintenance.\n\n"
        "### Can a refrigerator compressor be repaired?\n\n"
        "In some cases, a technician can repair the compressor. However, full "
        "replacement is often more cost-effective for older units.\n"
    ),
    "meta_description": "Learn the warning signs of refrigerator compressor failure and when to call a Tucson repair technician. Protect your food and save money.",
    "url_slug": "signs-refrigerator-compressor-failing",
    "faq_questions": [
        {"question": "How long does a refrigerator compressor last?", "answer": "10-20 years with proper maintenance."},
        {"question": "Can a refrigerator compressor be repaired?", "answer": "Sometimes, but replacement is often more cost-effective."},
    ],
    "aeo_elements": ["Direct answer to compressor lifespan question"],
    "geo_elements": ["Tucson heat impact on compressors"],
}

MOCK_EDITOR_RESPONSE = {
    "body_text": MOCK_ARTICLE_RESPONSE["body_text"],
    "meta_description": MOCK_ARTICLE_RESPONSE["meta_description"],
    "images": [
        {
            "image_number": 1,
            "purpose": "featured",
            "concept": "Technician inspecting refrigerator compressor",
            "scene_description": "Close-up of technician examining compressor unit",
            "subject": "Refrigerator compressor inspection",
            "location_context": "Tucson residential kitchen",
            "photography_style": "Professional, well-lit",
            "filename": "refrigerator-compressor-repair-tucson.jpg",
            "alt_text": "Technician inspecting a refrigerator compressor in Tucson",
            "suggested_placement": "After introduction",
        },
    ],
    "internal_links": [
        {
            "anchor_text": "refrigerator repair services",
            "target_url": "https://example.com/refrigerator-repair",
            "reason": "Links to relevant service page",
        },
    ],
    "external_sources": [
        {
            "source_title": "Energy Star Refrigerator Maintenance",
            "source_url": "https://www.energystar.gov/refrigerators",
            "source_type": "government",
            "claim_supported": "Compressor lifespan and efficiency",
        },
    ],
}

MOCK_FACT_CHECK_RESPONSE = {
    "total_claims": 8,
    "verified": 2,
    "supported": 3,
    "business_provided": 1,
    "common_knowledge": 2,
    "unverified": 0,
    "fabricated_found": False,
    "findings": [],
    "passed": True,
}


def _make_business() -> BusinessProfile:
    return BusinessProfile(
        business_id="example_appliance_repair",
        business_name="Example Appliance Repair",
        website="https://example.com",
        location="Tucson, Arizona",
        country="United States",
        industry="Appliance Repair",
        services=["Refrigerator Repair", "Oven Repair", "Dishwasher Repair"],
        primary_service="Refrigerator Repair",
        target_audience="Homeowners",
        business_description="Professional appliance repair in Tucson.",
        business_facts=["Serves Tucson area"],
        service_areas=["Tucson", "Marana"],
        output_folder="Example_Appliance_Repair",
    )


class TestPipelineMock:
    def test_dry_run(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "mock-key")

        topic_agent = MockAgent("topic_selector", MOCK_TOPIC_RESPONSE)
        topic_selector = TopicSelector(agent=topic_agent)

        pipeline = ContentPipeline(
            topic_selector=topic_selector,
            use_mock_web=True,
        )
        pipeline.business_manager.data_dir = tmp_path / "businesses"

        business = _make_business()
        result = pipeline.run([business], dry_run=True)

        assert result.total_articles == 2
        assert result.businesses[0].status == "dry_run"
        for art in result.businesses[0].articles:
            assert art.status == "dry_run"

    def test_full_mock_pipeline(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "mock-key")

        from app.config import PROJECT_ROOT
        monkeypatch.setattr("app.services.pipeline.settings.paths.output_dir", str(tmp_path / "output"))

        topic_agent = MockAgent("topic_selector", MOCK_TOPIC_RESPONSE)
        kw_agent = MockAgent("keyword_researcher", MOCK_KEYWORD_RESPONSE)
        research_agent_mock = MockAgent("research_agent", MOCK_RESEARCH_RESPONSE)
        writer_agent = MockAgent("writer", MOCK_ARTICLE_RESPONSE)
        editor_agent = MockAgent("seo_editor", MOCK_EDITOR_RESPONSE)
        fact_agent = MockAgent("fact_checker", MOCK_FACT_CHECK_RESPONSE)

        pipeline = ContentPipeline(
            topic_selector=TopicSelector(agent=topic_agent),
            keyword_researcher=KeywordResearcher(agent=kw_agent),
            research_agent=ResearchAgent(agent=research_agent_mock),
            content_writer=ContentWriter(agent=writer_agent),
            seo_editor=SEOEditor(agent=editor_agent),
            fact_checker=FactChecker(agent=fact_agent),
            use_mock_web=True,
        )
        pipeline.business_manager.data_dir = tmp_path / "businesses"

        business = _make_business()
        result = pipeline.run([business], dry_run=False)

        assert result.total_articles > 0
        assert result.businesses[0].status == "completed"

    def test_business_isolation(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "mock-key")

        topic_agent = MockAgent("topic_selector", MOCK_TOPIC_RESPONSE)
        topic_selector = TopicSelector(agent=topic_agent)

        pipeline = ContentPipeline(
            topic_selector=topic_selector,
            use_mock_web=True,
        )
        pipeline.business_manager.data_dir = tmp_path / "businesses"

        biz1 = _make_business()
        biz1.business_id = "biz_1"
        biz1.business_name = "Business One"

        biz2 = _make_business()
        biz2.business_id = "biz_2"
        biz2.business_name = "Business Two"

        result = pipeline.run([biz1, biz2], dry_run=True)
        assert len(result.businesses) == 2
        assert result.businesses[0].business_id != result.businesses[1].business_id
