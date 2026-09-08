from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.agents.business_manager import BusinessManager
from app.agents.content_writer import ContentWriter
from app.agents.document_agent import DocumentAgent
from app.agents.fact_checker import FactChecker
from app.agents.keyword_researcher import KeywordResearcher
from app.agents.quality_controller import QualityController
from app.agents.research_agent import ResearchAgent
from app.agents.seo_editor import SEOEditor
from app.agents.topic_selector import TopicSelector
from app.config import settings
from app.integrations.web_research import MockWebResearcher, WebResearcher
from app.models.article import ArticleDraft, FinalArticle
from app.models.business import BusinessProfile
from app.models.qa import QAResult
from app.models.research import TopicResearch
from app.models.topic import TopicCandidate
from app.services.duplicate_detection import is_duplicate_keyword, is_duplicate_topic
from app.utils.dates import generate_run_id, today_str
from app.utils.logging import RunLogger
from app.utils.text import strip_dashes

logger = logging.getLogger("seo_automation")


@dataclass
class ArticleResult:
    topic: TopicCandidate
    article: FinalArticle | None = None
    qa_result: QAResult | None = None
    status: str = "pending"
    error: str = ""


@dataclass
class BusinessResult:
    business_id: str
    business_name: str
    articles: list[ArticleResult] = field(default_factory=list)
    docx_path: Path | None = None
    status: str = "pending"
    error: str = ""


@dataclass
class PipelineResult:
    run_id: str
    businesses: list[BusinessResult] = field(default_factory=list)
    total_articles: int = 0
    successful_articles: int = 0
    failed_articles: int = 0


class ContentPipeline:
    def __init__(
        self,
        topic_selector: TopicSelector | None = None,
        keyword_researcher: KeywordResearcher | None = None,
        research_agent: ResearchAgent | None = None,
        content_writer: ContentWriter | None = None,
        seo_editor: SEOEditor | None = None,
        fact_checker: FactChecker | None = None,
        use_mock_web: bool = False,
    ):
        self.business_manager = BusinessManager()
        self.topic_selector = topic_selector or TopicSelector()
        self.keyword_researcher = keyword_researcher or KeywordResearcher()
        self.research_agent = research_agent or ResearchAgent()
        self.content_writer = content_writer or ContentWriter()
        self.seo_editor = seo_editor or SEOEditor()
        self.fact_checker = fact_checker or FactChecker()
        self.quality_controller = QualityController()
        self.document_agent = DocumentAgent()
        self.web_researcher = MockWebResearcher() if use_mock_web else WebResearcher()

    def run(
        self,
        businesses: list[BusinessProfile],
        dry_run: bool = False,
    ) -> PipelineResult:
        run_id = generate_run_id()
        run_logger = RunLogger(run_id)
        result = PipelineResult(run_id=run_id)

        logger.info(f"Pipeline run {run_id}: processing {len(businesses)} businesses")

        for business in businesses:
            biz_result = self._process_business(business, run_logger, dry_run)
            result.businesses.append(biz_result)
            result.total_articles += len(biz_result.articles)
            result.successful_articles += sum(
                1 for a in biz_result.articles if a.status == "completed"
            )
            result.failed_articles += sum(
                1 for a in biz_result.articles if a.status == "failed"
            )

        run_logger.save()
        logger.info(
            f"Pipeline complete: {result.successful_articles}/{result.total_articles} articles, "
            f"{result.failed_articles} failed"
        )
        return result

    def _process_business(
        self,
        business: BusinessProfile,
        run_logger: RunLogger,
        dry_run: bool,
    ) -> BusinessResult:
        biz_result = BusinessResult(
            business_id=business.business_id,
            business_name=business.business_name,
        )
        run_logger.log_business_start(business.business_id, business.business_name)

        try:
            valid, warnings = self.business_manager.validate_business(business)
            if not valid:
                biz_result.status = "failed"
                biz_result.error = f"Validation failed: {'; '.join(warnings)}"
                run_logger.log_error(business.business_id, biz_result.error, "validation")
                return biz_result
            for w in warnings:
                logger.warning(f"  Business warning: {w}")

            state = self.business_manager.load_state(business.business_id)
            previous_topics = state.generated_topics
            previous_keywords = state.generated_primary_keywords

            topic_selection = self.topic_selector.select_topics(
                business, previous_topics, previous_keywords,
            )

            if not topic_selection.selected_topics:
                biz_result.status = "completed"
                biz_result.error = "No valid topics available"
                run_logger.log_business_complete(business.business_id, 0, "no_topics")
                return biz_result

            if dry_run:
                for topic in topic_selection.selected_topics:
                    art_result = ArticleResult(topic=topic, status="dry_run")
                    biz_result.articles.append(art_result)
                    run_logger.log_topic(business.business_id, topic.title, "dry_run")
                biz_result.status = "dry_run"
                run_logger.log_business_complete(
                    business.business_id, len(topic_selection.selected_topics), "dry_run",
                )
                return biz_result

            final_articles: list[FinalArticle] = []
            qa_results: list[QAResult] = []
            new_topics: list[str] = []
            new_keywords: list[str] = []

            for topic in topic_selection.selected_topics:
                art_result = self._process_article(
                    topic, business, previous_topics, previous_keywords, run_logger,
                )
                biz_result.articles.append(art_result)

                if art_result.status == "completed" and art_result.article and art_result.qa_result:
                    final_articles.append(art_result.article)
                    qa_results.append(art_result.qa_result)
                    new_topics.append(art_result.article.title)
                    new_keywords.append(art_result.article.primary_keyword)

            if final_articles:
                date_str = today_str()
                output_dir = self.business_manager.get_output_dir(business, date_str)
                docx_path = self.document_agent.generate_docx(
                    final_articles, business, qa_results, output_dir, date_str,
                )
                biz_result.docx_path = docx_path

                self.business_manager.update_state_after_run(
                    state, new_topics, new_keywords, date_str,
                )

            biz_result.status = "completed"
            run_logger.log_business_complete(
                business.business_id, len(final_articles), "completed",
            )

        except Exception as e:
            biz_result.status = "failed"
            biz_result.error = str(e)
            run_logger.log_error(business.business_id, str(e), "pipeline")
            logger.exception(f"Business pipeline failed: {business.business_id}")

        return biz_result

    def _process_article(
        self,
        topic: TopicCandidate,
        business: BusinessProfile,
        previous_topics: list[str],
        previous_keywords: list[str],
        run_logger: RunLogger,
    ) -> ArticleResult:
        art_result = ArticleResult(topic=topic)

        try:
            logger.info(f"  Processing topic: {topic.title}")

            is_dup, dup_match = is_duplicate_topic(topic.title, previous_topics)
            if is_dup:
                art_result.status = "failed"
                art_result.error = f"Duplicate of: {dup_match}"
                run_logger.log_topic(business.business_id, topic.title, "duplicate")
                return art_result

            keywords = self.keyword_researcher.research_keywords(topic, business)

            is_kw_dup, kw_match = is_duplicate_keyword(
                keywords.primary_keyword, previous_keywords,
            )
            if is_kw_dup:
                logger.warning(f"  Keyword overlap with: {kw_match}")

            website_content = ""
            if business.website:
                web_data = self.web_researcher.research_url(business.website)
                if web_data:
                    website_content = web_data.get("text", "")

            research = self.research_agent.research_topic(
                topic, keywords, business, website_content,
            )

            max_revisions = settings.content.max_revision_attempts
            draft = None
            qa_result = None
            revision_instructions = ""

            for attempt in range(max_revisions + 1):
                if attempt == 0:
                    draft = self.content_writer.write_article(
                        research, business, revision_instructions,
                    )
                else:
                    draft = self.content_writer.write_article(
                        research, business, revision_instructions,
                    )

                draft = self.seo_editor.edit_article(draft, research, business)
                draft.body_text = strip_dashes(draft.body_text)

                fact_report = self.fact_checker.check_facts(draft, research, business)
                qa_result = self.quality_controller.run_qa(draft, business, fact_report)

                if qa_result.overall_passed:
                    break

                if attempt < max_revisions:
                    revision_instructions = qa_result.revision_instructions
                    logger.info(f"  Revision {attempt + 1}: {'; '.join(qa_result.critical_failures[:3])}")
                else:
                    logger.warning(f"  Max revisions reached for: {topic.title}")

            if draft and qa_result:
                final = FinalArticle(
                    title=draft.title,
                    primary_keyword=draft.primary_keyword,
                    secondary_keywords=draft.secondary_keywords,
                    search_intent=draft.search_intent,
                    service_category=topic.service_category,
                    body_text=draft.body_text,
                    meta_description=draft.meta_description,
                    url_slug=draft.url_slug,
                    word_count=draft.word_count,
                    keyword_count=draft.keyword_count,
                    keyword_density=draft.keyword_density,
                    images=draft.images,
                    internal_links=draft.internal_links,
                    external_sources=draft.external_sources,
                    aeo_elements=draft.aeo_elements,
                    geo_elements=draft.geo_elements,
                    faq_questions=draft.faq_questions,
                    qa_passed=qa_result.overall_passed,
                    revision_count=max_revisions if not qa_result.overall_passed else 0,
                )
                art_result.article = final
                art_result.qa_result = qa_result
                art_result.status = "completed" if qa_result.overall_passed else "failed_qa"
                run_logger.log_topic(
                    business.business_id, topic.title,
                    "completed" if qa_result.overall_passed else "failed_qa",
                )
            else:
                art_result.status = "failed"
                art_result.error = "No draft generated"
                run_logger.log_topic(business.business_id, topic.title, "failed")

        except Exception as e:
            art_result.status = "failed"
            art_result.error = str(e)
            run_logger.log_error(business.business_id, str(e), f"article:{topic.title}")
            logger.exception(f"  Article processing failed: {topic.title}")

        return art_result
