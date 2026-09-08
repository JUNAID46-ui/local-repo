from __future__ import annotations

import json
import logging

from app.agents.base import BaseAgent
from app.config import settings
from app.models.article import ArticleDraft
from app.models.business import BusinessProfile
from app.models.qa import FactCheckReport, QAFinding
from app.models.research import TopicResearch

logger = logging.getLogger("seo_automation")


class FactChecker:
    def __init__(self, agent: BaseAgent | None = None):
        self.agent = agent or BaseAgent("fact_checker", model=settings.models.validation)

    def check_facts(
        self,
        article: ArticleDraft,
        research: TopicResearch,
        business: BusinessProfile,
    ) -> FactCheckReport:
        prompt = self._build_prompt(article, research, business)
        result = self.agent.call_json(prompt, max_tokens=4096)

        findings = []
        for f in result.get("findings", []):
            findings.append(QAFinding(
                category="fact",
                severity=f.get("severity", "warning"),
                description=f.get("description", ""),
                suggestion=f.get("suggestion", ""),
                auto_fixable=f.get("auto_fixable", False),
            ))

        return FactCheckReport(
            total_claims=result.get("total_claims", 0),
            verified=result.get("verified", 0),
            supported=result.get("supported", 0),
            business_provided=result.get("business_provided", 0),
            common_knowledge=result.get("common_knowledge", 0),
            unverified=result.get("unverified", 0),
            fabricated_found=result.get("fabricated_found", False),
            findings=findings,
            passed=result.get("passed", True),
        )

    def _build_prompt(
        self,
        article: ArticleDraft,
        research: TopicResearch,
        business: BusinessProfile,
    ) -> str:
        research_facts = ""
        for f in research.topic_facts:
            research_facts += f"- {f.claim} [{f.verification_status}] (source: {f.source})\n"

        biz_facts = "\n".join(f"- {f}" for f in business.business_facts) if business.business_facts else "None"

        return f"""Fact-check this article for accuracy.

ARTICLE TITLE: {article.title}
BUSINESS: {business.business_name} ({business.location})

ARTICLE TEXT:
{article.body_text}

RESEARCH EVIDENCE:
{research_facts}

BUSINESS-PROVIDED FACTS:
{biz_facts}

Check every factual claim. Classify each as:
- VERIFIED: confirmed by authoritative external source
- SUPPORTED: consistent with evidence
- BUSINESS-PROVIDED: stated by the business
- COMMON_KNOWLEDGE: widely known
- UNVERIFIED: cannot confirm

Flag: invented statistics, fabricated testimonials, unverified credentials/certifications/awards, unverified pricing, unverified service claims (24/7, same-day, emergency), misleading implications.

Return valid JSON with: total_claims, verified, supported, business_provided, common_knowledge, unverified, fabricated_found, findings (array of {{severity, description, suggestion, auto_fixable}}), passed."""
