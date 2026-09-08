from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.config import settings, PROJECT_ROOT
from app.integrations.google_sheets import (
    GoogleSheetsClient,
    MockSheetClient,
    load_active_businesses,
)
from app.models.business import BusinessProfile
from app.services.pipeline import ContentPipeline
from app.utils.logging import setup_logging

logger = setup_logging()


def get_mock_businesses() -> list[BusinessProfile]:
    sample_path = PROJECT_ROOT / "data" / "sample" / "mock_businesses.json"
    if sample_path.exists():
        import json
        with open(sample_path) as f:
            data = json.load(f)
        return [BusinessProfile(**b) for b in data]

    return [BusinessProfile(
        business_id="example_appliance_repair",
        business_name="Example Appliance Repair",
        website="https://example.com",
        location="Tucson, Arizona",
        country="United States",
        industry="Appliance Repair",
        services=[
            "Refrigerator Repair",
            "Oven Repair",
            "Dishwasher Repair",
            "Dryer Repair",
            "Washer Repair",
        ],
        primary_service="Refrigerator Repair",
        target_audience="Homeowners in Tucson needing appliance repair",
        business_description=(
            "Example Appliance Repair provides professional home appliance "
            "repair services in Tucson, Arizona and surrounding areas."
        ),
        business_facts=[
            "Serves Tucson and surrounding areas",
            "Repairs all major home appliance brands",
            "Provides in-home repair service",
        ],
        brand_voice="professional, helpful, knowledgeable, friendly",
        primary_keywords=[
            "appliance repair Tucson",
            "refrigerator repair Tucson",
            "oven repair Tucson",
        ],
        commercial_keywords=[
            "appliance repair service",
            "appliance technician",
            "home appliance repair",
        ],
        service_areas=["Tucson", "Marana", "Oro Valley", "Sahuarita", "Vail"],
        existing_content_urls=[],
        internal_link_base="https://example.com",
        output_folder="Example_Appliance_Repair",
        active=True,
    )]


def run_pipeline(
    businesses: list[BusinessProfile] | None = None,
    business_id: str | None = None,
    dry_run: bool = False,
    use_mock: bool = False,
) -> None:
    if businesses is None:
        if use_mock:
            businesses = get_mock_businesses()
        else:
            try:
                client = GoogleSheetsClient()
                businesses = load_active_businesses(client)
            except Exception as e:
                logger.error(f"Failed to load businesses from Google Sheets: {e}")
                logger.info("Falling back to mock businesses for testing")
                businesses = get_mock_businesses()

    if business_id:
        businesses = [b for b in businesses if b.business_id == business_id]
        if not businesses:
            logger.error(f"Business not found: {business_id}")
            return

    if not businesses:
        logger.warning("No active businesses to process")
        return

    logger.info(f"Processing {len(businesses)} business(es), dry_run={dry_run}")

    if use_mock or not settings.anthropic_api_key:
        from app.agents.base import MockAgent
        from app.agents.topic_selector import TopicSelector
        from app.agents.keyword_researcher import KeywordResearcher
        from app.agents.research_agent import ResearchAgent
        from app.agents.content_writer import ContentWriter
        from app.agents.seo_editor import SEOEditor
        from app.agents.fact_checker import FactChecker
        from tests.test_pipeline_mock import (
            MOCK_TOPIC_RESPONSE,
            MOCK_KEYWORD_RESPONSE,
            MOCK_RESEARCH_RESPONSE,
            MOCK_ARTICLE_RESPONSE,
            MOCK_EDITOR_RESPONSE,
            MOCK_FACT_CHECK_RESPONSE,
        )
        pipeline = ContentPipeline(
            topic_selector=TopicSelector(agent=MockAgent("topic_selector", MOCK_TOPIC_RESPONSE)),
            keyword_researcher=KeywordResearcher(agent=MockAgent("keyword_researcher", MOCK_KEYWORD_RESPONSE)),
            research_agent=ResearchAgent(agent=MockAgent("research_agent", MOCK_RESEARCH_RESPONSE)),
            content_writer=ContentWriter(agent=MockAgent("writer", MOCK_ARTICLE_RESPONSE)),
            seo_editor=SEOEditor(agent=MockAgent("seo_editor", MOCK_EDITOR_RESPONSE)),
            fact_checker=FactChecker(agent=MockAgent("fact_checker", MOCK_FACT_CHECK_RESPONSE)),
            use_mock_web=True,
        )
    else:
        pipeline = ContentPipeline(use_mock_web=dry_run)

    result = pipeline.run(businesses, dry_run=dry_run)

    logger.info("=" * 60)
    logger.info(f"Run ID: {result.run_id}")
    logger.info(f"Total articles: {result.total_articles}")
    logger.info(f"Successful: {result.successful_articles}")
    logger.info(f"Failed: {result.failed_articles}")
    for biz in result.businesses:
        logger.info(f"  {biz.business_name}: {biz.status}")
        if biz.docx_path:
            logger.info(f"    DOCX: {biz.docx_path}")
        for art in biz.articles:
            status_str = art.status
            if art.article:
                status_str += f" ({art.article.word_count} words, {art.article.keyword_density}% density)"
            logger.info(f"    - {art.topic.title}: {status_str}")
    logger.info("=" * 60)


def start_scheduler() -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler()
    trigger = CronTrigger(
        hour=settings.schedule.hour,
        minute=settings.schedule.minute,
        timezone=settings.schedule.timezone,
    )
    scheduler.add_job(run_pipeline, trigger, id="daily_content_pipeline")
    logger.info(
        f"Scheduler started. Next run at "
        f"{settings.schedule.hour:02d}:{settings.schedule.minute:02d} "
        f"{settings.schedule.timezone}"
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Content Automation Pipeline")
    parser.add_argument("--run-now", action="store_true", help="Run pipeline immediately")
    parser.add_argument("--business", type=str, help="Process single business by ID")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (topic selection only)")
    parser.add_argument("--schedule", action="store_true", help="Start the daily scheduler")
    parser.add_argument("--mock", action="store_true", help="Use mock data and agents")

    args = parser.parse_args()

    if args.schedule:
        start_scheduler()
    elif args.run_now or args.business or args.dry_run:
        run_pipeline(
            business_id=args.business,
            dry_run=args.dry_run,
            use_mock=args.mock,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
