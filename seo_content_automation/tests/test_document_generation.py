import pytest
from pathlib import Path
from app.models.article import FinalArticle, ImageConcept, InternalLink, ExternalSource
from app.models.business import BusinessProfile
from app.models.qa import QAResult, SEOReport, AEOReport, GEOReport, FactCheckReport, StyleReport
from app.services.document_generation import DocumentGenerator


def _make_article(index: int = 1) -> FinalArticle:
    return FinalArticle(
        title=f"Test Article {index}: Refrigerator Repair Guide",
        primary_keyword="refrigerator repair",
        secondary_keywords=["fridge repair", "appliance service"],
        search_intent="commercial",
        service_category="Refrigerator Repair",
        body_text=(
            "## Why Refrigerators Break Down\n\n"
            "Refrigerators are essential home appliances. When they stop working, "
            "you need professional refrigerator repair service fast.\n\n"
            "## Common Problems\n\n"
            "The most common refrigerator issues include compressor failure, "
            "thermostat problems, and sealed system leaks.\n\n"
            "## When to Call a Professional\n\n"
            "If your refrigerator is making unusual noises or not cooling properly, "
            "contact a qualified technician.\n"
        ),
        meta_description="Professional refrigerator repair in Tucson. Fast, reliable service for all major brands.",
        url_slug="refrigerator-repair-tucson-guide",
        word_count=80,
        keyword_count=3,
        keyword_density=1.8,
        images=[
            ImageConcept(
                image_number=1,
                purpose="featured",
                concept="Technician inspecting refrigerator",
                scene_description="A technician examining a refrigerator compressor in a kitchen",
                subject="Refrigerator repair technician",
                location_context="Tucson residential kitchen",
                photography_style="Professional, well-lit",
                filename="refrigerator-repair-tucson-technician.jpg",
                alt_text="Appliance technician inspecting a refrigerator in a Tucson home",
                suggested_placement="Top of article",
            ),
        ],
        internal_links=[
            InternalLink(
                anchor_text="appliance repair services",
                target_url="https://example.com/services",
                reason="Links to main services page",
            ),
        ],
        external_sources=[
            ExternalSource(
                source_title="Energy Star Refrigerator Guide",
                source_url="https://www.energystar.gov/refrigerators",
                source_type="government",
                claim_supported="Energy efficiency ratings",
            ),
        ],
        aeo_elements=["Direct answer to 'why refrigerator not cooling'"],
        geo_elements=["Tucson climate context for appliance wear"],
        qa_passed=True,
    )


def _make_business() -> BusinessProfile:
    return BusinessProfile(
        business_id="test",
        business_name="Example Appliance Repair",
        website="https://example.com",
        location="Tucson, Arizona",
        industry="Appliance Repair",
        services=["Refrigerator Repair", "Oven Repair"],
        service_areas=["Tucson", "Marana"],
        target_audience="Homeowners",
    )


def _make_qa_result() -> QAResult:
    return QAResult(
        seo=SEOReport(passed=True, keyword_density=1.8, primary_keyword_present=True),
        aeo=AEOReport(passed=True),
        geo=GEOReport(passed=True),
        fact_check=FactCheckReport(passed=True),
        style=StyleReport(passed=True),
        overall_passed=True,
    )


class TestDocumentGenerator:
    def test_generate_docx(self, tmp_path: Path):
        generator = DocumentGenerator()
        articles = [_make_article(1), _make_article(2)]
        business = _make_business()
        qa_results = [_make_qa_result(), _make_qa_result()]

        output_path = tmp_path / "test_output.docx"
        generator.generate(articles, business, qa_results, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_generate_single_article(self, tmp_path: Path):
        generator = DocumentGenerator()
        articles = [_make_article(1)]
        business = _make_business()
        qa_results = [_make_qa_result()]

        output_path = tmp_path / "single.docx"
        generator.generate(articles, business, qa_results, output_path)
        assert output_path.exists()

    def test_output_directory_creation(self, tmp_path: Path):
        generator = DocumentGenerator()
        articles = [_make_article(1)]
        business = _make_business()
        qa_results = [_make_qa_result()]

        output_path = tmp_path / "new_dir" / "sub_dir" / "test.docx"
        generator.generate(articles, business, qa_results, output_path)
        assert output_path.exists()
