from __future__ import annotations

import json
import logging

from app.agents.base import BaseAgent
from app.config import settings
from app.models.business import BusinessProfile
from app.models.research import (
    KeywordResearch,
    ResearchEvidence,
    ResearchSource,
    TopicResearch,
)
from app.models.topic import TopicCandidate

logger = logging.getLogger("seo_automation")


class ResearchAgent:
    def __init__(self, agent: BaseAgent | None = None):
        self.agent = agent or BaseAgent("research_agent", model=settings.models.research)

    def research_topic(
        self,
        topic: TopicCandidate,
        keywords: KeywordResearch,
        business: BusinessProfile,
        website_content: str = "",
    ) -> TopicResearch:
        prompt = self._build_prompt(topic, keywords, business, website_content)
        result = self.agent.call_json(prompt, max_tokens=8192)

        business_facts = [
            ResearchEvidence(**f) for f in result.get("business_facts", [])
        ]
        topic_facts = [
            ResearchEvidence(**f) for f in result.get("topic_facts", [])
        ]
        sources = [
            ResearchSource(**s) for s in result.get("sources", [])
        ]

        return TopicResearch(
            topic_title=topic.title,
            keyword_research=keywords,
            business_facts=business_facts,
            topic_facts=topic_facts,
            common_problems=result.get("common_problems", []),
            solutions=result.get("solutions", []),
            user_questions=result.get("user_questions", []),
            local_context=result.get("local_context", []),
            industry_terminology=result.get("industry_terminology", []),
            sources=sources,
            aeo_questions=result.get("aeo_questions", []),
            geo_factors=result.get("geo_factors", []),
        )

    def _build_prompt(
        self,
        topic: TopicCandidate,
        keywords: KeywordResearch,
        business: BusinessProfile,
        website_content: str,
    ) -> str:
        biz_facts_str = "\n".join(f"- {f}" for f in business.business_facts) if business.business_facts else "None provided"
        website_section = f"\nWEBSITE CONTENT (excerpt):\n{website_content[:3000]}" if website_content else ""

        return f"""Research this topic thoroughly for a blog article.

TOPIC: {topic.title}
SERVICE CATEGORY: {topic.service_category}
SEARCH INTENT: {topic.search_intent}

PRIMARY KEYWORD: {keywords.primary_keyword}
QUESTION KEYWORDS: {', '.join(keywords.question_keywords)}
LOCAL KEYWORDS: {', '.join(keywords.local_keywords)}

BUSINESS PROFILE:
Name: {business.business_name}
Location: {business.location}
Country: {business.country}
Industry: {business.industry}
Services: {', '.join(business.services)}
Service Areas: {', '.join(business.service_areas)}
Description: {business.business_description}
Business Facts:
{biz_facts_str}
{website_section}

RESEARCH REQUIREMENTS:

1. Business Research - verify business name, location, services. Never invent info.
2. Topic Research - problems, causes, solutions, terminology, facts, statistics (only if verifiable).
3. AEO Research - questions answer engines surface, direct answer opportunities.
4. GEO Research - local climate, housing, regulations, infrastructure, terminology.
5. Source Quality - prefer government, manufacturer, industry org, authoritative publication sources.

FACT CLASSIFICATION:
Each fact must have verification_status: VERIFIED, SUPPORTED, BUSINESS-PROVIDED, COMMON_KNOWLEDGE, or UNVERIFIED.

Return valid JSON with: business_facts, topic_facts, common_problems, solutions, user_questions, local_context, industry_terminology, sources, aeo_questions, geo_factors.

Each fact in business_facts and topic_facts must be an object with: claim, source, source_type, verification_status.
Each source must have: source_title, source_url, source_type, reliability."""
