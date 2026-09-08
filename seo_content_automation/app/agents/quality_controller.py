from __future__ import annotations

import logging

from app.config import settings
from app.models.article import ArticleDraft
from app.models.business import BusinessProfile
from app.models.qa import (
    AEOReport,
    FactCheckReport,
    GEOReport,
    QAFinding,
    QAResult,
    SEOReport,
    StyleReport,
)
from app.services.seo_validation import SEOValidator
from app.services.style_validation import StyleValidator

logger = logging.getLogger("seo_automation")


class QualityController:
    def __init__(self) -> None:
        self.seo_validator = SEOValidator()
        self.style_validator = StyleValidator()

    def run_qa(
        self,
        article: ArticleDraft,
        business: BusinessProfile,
        fact_report: FactCheckReport,
    ) -> QAResult:
        seo = self.seo_validator.validate(article, business)
        style = self.style_validator.validate(article)
        aeo = self._check_aeo(article)
        geo = self._check_geo(article, business)

        critical_failures = []

        if fact_report.fabricated_found:
            critical_failures.append("Fabricated business or factual claims detected")
        if not article.primary_keyword:
            critical_failures.append("Missing primary keyword")
        if article.keyword_density > 3.5:
            critical_failures.append(f"Keyword stuffing: density {article.keyword_density}%")
        if not article.meta_description:
            critical_failures.append("Missing meta description")
        if style.em_dashes_found > 0:
            critical_failures.append(f"Em dash characters found ({style.em_dashes_found})")
        if style.en_dashes_found > 0:
            critical_failures.append(f"En dash characters found ({style.en_dashes_found})")
        if article.word_count < 200:
            critical_failures.append("Article too short (malformed)")

        overall_passed = len(critical_failures) == 0 and fact_report.passed

        revision_instructions = ""
        if not overall_passed:
            parts = ["Fix these critical issues:"]
            parts.extend(f"- {f}" for f in critical_failures)
            if not fact_report.passed:
                for finding in fact_report.findings:
                    if finding.severity == "critical":
                        parts.append(f"- FACT: {finding.description}")
            for finding in seo.findings:
                if finding.severity == "critical":
                    parts.append(f"- SEO: {finding.description}")
            for finding in style.findings:
                if finding.severity == "critical":
                    parts.append(f"- STYLE: {finding.description}")
            revision_instructions = "\n".join(parts)

        return QAResult(
            seo=seo,
            aeo=aeo,
            geo=geo,
            fact_check=fact_report,
            style=style,
            overall_passed=overall_passed,
            critical_failures=critical_failures,
            revision_needed=not overall_passed,
            revision_instructions=revision_instructions,
        )

    def _check_aeo(self, article: ArticleDraft) -> AEOReport:
        findings: list[QAFinding] = []
        text = article.body_text.lower()

        question_headings = sum(
            1 for line in article.body_text.split("\n")
            if line.strip().startswith(("#", "##", "###")) and "?" in line
        )

        faq_present = "faq" in text or "frequently asked" in text or len(article.faq_questions) > 0
        direct_answers = len(article.aeo_elements)

        if question_headings == 0:
            findings.append(QAFinding(
                category="aeo", severity="warning",
                description="No question-based headings found",
                suggestion="Add at least 2 question-based headings for AEO",
            ))

        if not faq_present:
            findings.append(QAFinding(
                category="aeo", severity="info",
                description="No FAQ section found",
                suggestion="Consider adding a FAQ section with 3-5 relevant questions",
            ))

        passed = not any(f.severity == "critical" for f in findings)

        return AEOReport(
            direct_answers_count=direct_answers,
            question_headings_count=question_headings,
            faq_present=faq_present,
            entity_clarity="adequate",
            concise_answer_opportunities=len(article.faq_questions),
            findings=findings,
            passed=passed,
        )

    def _check_geo(self, article: ArticleDraft, business: BusinessProfile) -> GEOReport:
        findings: list[QAFinding] = []
        text = article.body_text.lower()

        location = business.location.lower()
        location_parts = [p.strip() for p in location.replace(",", " ").split() if len(p.strip()) > 2]
        location_mentions = sum(text.count(part) for part in location_parts)

        local_context = len(article.geo_elements) > 0
        service_area = any(area.lower() in text for area in business.service_areas) if business.service_areas else False

        if location_mentions == 0:
            findings.append(QAFinding(
                category="geo", severity="warning",
                description="No location mentions found in article",
                suggestion=f"Add natural references to {business.location}",
            ))

        passed = not any(f.severity == "critical" for f in findings)

        return GEOReport(
            location_mentions=location_mentions,
            local_context_present=local_context,
            local_facts_verified=True,
            service_area_mentioned=service_area,
            findings=findings,
            passed=passed,
        )
