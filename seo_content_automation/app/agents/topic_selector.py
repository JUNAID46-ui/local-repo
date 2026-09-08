from __future__ import annotations

import json
import logging

from app.agents.base import BaseAgent
from app.config import settings
from app.models.business import BusinessProfile
from app.models.topic import TopicCandidate, TopicSelection

logger = logging.getLogger("seo_automation")


class TopicSelector:
    def __init__(self, agent: BaseAgent | None = None):
        self.agent = agent or BaseAgent("topic_selector", model=settings.models.primary)

    def select_topics(
        self,
        business: BusinessProfile,
        previous_topics: list[str],
        previous_keywords: list[str],
        existing_content_titles: list[str] | None = None,
    ) -> TopicSelection:
        max_topics = settings.content.max_articles_per_business

        prompt = self._build_prompt(
            business, previous_topics, previous_keywords,
            existing_content_titles or [], max_topics,
        )

        result = self.agent.call_json(prompt, max_tokens=4096)

        selected = []
        for t in result.get("selected_topics", []):
            topic = TopicCandidate(
                title=t.get("title", ""),
                service_category=t.get("service_category", ""),
                search_intent=t.get("search_intent", "informational"),
                target_audience=t.get("target_audience", ""),
                estimated_value=t.get("estimated_value", "medium"),
                aeo_opportunity=t.get("aeo_opportunity", ""),
                geo_opportunity=t.get("geo_opportunity", ""),
                selected=True,
            )
            selected.append(topic)

        rejected = []
        for t in result.get("rejected_topics", []):
            topic = TopicCandidate(
                title=t.get("title", ""),
                service_category=t.get("service_category", ""),
                search_intent=t.get("search_intent", ""),
                rejection_reason=t.get("rejection_reason", ""),
                selected=False,
            )
            rejected.append(topic)

        selected = self._enforce_rules(selected, business.services, previous_topics)

        return TopicSelection(
            business_id=business.business_id,
            selected_topics=selected[:max_topics],
            rejected_topics=rejected,
            selection_reasoning=result.get("selection_reasoning", ""),
        )

    def _enforce_rules(
        self,
        topics: list[TopicCandidate],
        services: list[str],
        previous_topics: list[str],
    ) -> list[TopicCandidate]:
        seen_categories: set[str] = set()
        seen_intents: set[str] = set()
        prev_lower = {t.lower() for t in previous_topics}
        valid = []

        for topic in topics:
            if topic.title.lower() in prev_lower:
                continue
            cat = topic.service_category.lower()
            if cat in seen_categories:
                continue
            intent = topic.search_intent.lower()
            if intent in seen_intents and len(valid) >= 2:
                continue
            seen_categories.add(cat)
            seen_intents.add(intent)
            valid.append(topic)

        return valid

    def _build_prompt(
        self,
        business: BusinessProfile,
        previous_topics: list[str],
        previous_keywords: list[str],
        existing_content: list[str],
        max_topics: int,
    ) -> str:
        return f"""Select {max_topics} blog topics for this business.

BUSINESS PROFILE:
Name: {business.business_name}
Location: {business.location}
Industry: {business.industry}
Services: {', '.join(business.services)}
Primary Service: {business.primary_service}
Target Audience: {business.target_audience}
Description: {business.business_description}
Service Areas: {', '.join(business.service_areas)}

PREVIOUSLY GENERATED TOPICS (avoid duplicates):
{json.dumps(previous_topics) if previous_topics else "None"}

PREVIOUSLY USED PRIMARY KEYWORDS (avoid reuse):
{json.dumps(previous_keywords) if previous_keywords else "None"}

EXISTING WEBSITE CONTENT (avoid cannibalization):
{json.dumps(existing_content) if existing_content else "None"}

RULES:
- Select exactly {max_topics} topics (or fewer if not enough valid options).
- One topic per service category maximum.
- No two topics targeting the same search intent.
- Mix intent types: informational, commercial, local, problem-solving.
- Consider AEO and GEO opportunities.
- Never fabricate services the business does not offer.

Return valid JSON with: selected_topics, rejected_topics, selection_reasoning."""
