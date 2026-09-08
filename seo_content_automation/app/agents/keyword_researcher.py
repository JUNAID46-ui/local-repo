from __future__ import annotations

import json
import logging

from app.agents.base import BaseAgent
from app.config import settings
from app.models.business import BusinessProfile
from app.models.research import KeywordResearch
from app.models.topic import TopicCandidate

logger = logging.getLogger("seo_automation")


class KeywordResearcher:
    def __init__(self, agent: BaseAgent | None = None):
        self.agent = agent or BaseAgent("keyword_researcher", model=settings.models.research)

    def research_keywords(
        self,
        topic: TopicCandidate,
        business: BusinessProfile,
    ) -> KeywordResearch:
        prompt = self._build_prompt(topic, business)
        result = self.agent.call_json(prompt, max_tokens=4096)

        return KeywordResearch(
            primary_keyword=result.get("primary_keyword", topic.title.lower()),
            secondary_keywords=result.get("secondary_keywords", []),
            semantic_keywords=result.get("semantic_keywords", []),
            related_entities=result.get("related_entities", []),
            commercial_keywords=result.get("commercial_keywords", []),
            local_keywords=result.get("local_keywords", []),
            question_keywords=result.get("question_keywords", []),
            long_tail_keywords=result.get("long_tail_keywords", []),
            search_intent=result.get("search_intent", topic.search_intent),
            keyword_variations=result.get("keyword_variations", []),
        )

    def _build_prompt(self, topic: TopicCandidate, business: BusinessProfile) -> str:
        return f"""Research keywords for this blog article.

TOPIC: {topic.title}
SERVICE CATEGORY: {topic.service_category}
SEARCH INTENT: {topic.search_intent}

BUSINESS:
Name: {business.business_name}
Location: {business.location}
Industry: {business.industry}
Services: {', '.join(business.services)}
Service Areas: {', '.join(business.service_areas)}
Existing Primary Keywords: {', '.join(business.primary_keywords)}
Existing Commercial Keywords: {', '.join(business.commercial_keywords)}

Return valid JSON with:
- primary_keyword (the main target keyword)
- secondary_keywords (5-8)
- semantic_keywords (5-10)
- related_entities
- commercial_keywords (natural commercial phrases fitting this business)
- local_keywords (location-specific variations)
- question_keywords (question-format searches)
- long_tail_keywords (3-5)
- search_intent
- keyword_variations

Do NOT fabricate search volume or difficulty metrics. Only include keywords people would realistically search."""
