from __future__ import annotations

import json
import logging

from app.agents.base import BaseAgent
from app.config import settings
from app.models.article import ArticleDraft
from app.models.business import BusinessProfile
from app.models.research import TopicResearch
from app.utils.text import (
    calculate_keyword_density,
    count_words,
    generate_url_slug,
    strip_dashes,
)

logger = logging.getLogger("seo_automation")


class ContentWriter:
    def __init__(self, agent: BaseAgent | None = None):
        self.agent = agent or BaseAgent("writer", model=settings.models.primary)

    def write_article(
        self,
        research: TopicResearch,
        business: BusinessProfile,
        revision_instructions: str = "",
    ) -> ArticleDraft:
        prompt = self._build_prompt(research, business, revision_instructions)
        result = self.agent.call_json(prompt, max_tokens=8192)

        body_text = result.get("body_text", "")
        body_text = strip_dashes(body_text)

        primary_kw = result.get("primary_keyword", research.keyword_research.primary_keyword)
        kw_count, word_count, density = calculate_keyword_density(body_text, primary_kw)

        faq_questions = result.get("faq_questions", [])
        if isinstance(faq_questions, list):
            faq_questions = [
                q if isinstance(q, dict) else {"question": str(q), "answer": ""}
                for q in faq_questions
            ]

        return ArticleDraft(
            title=result.get("title", research.topic_title),
            primary_keyword=primary_kw,
            secondary_keywords=research.keyword_research.secondary_keywords,
            search_intent=research.keyword_research.search_intent,
            body_text=body_text,
            meta_description=result.get("meta_description", ""),
            url_slug=result.get("url_slug", generate_url_slug(result.get("title", research.topic_title))),
            word_count=word_count,
            keyword_count=kw_count,
            keyword_density=density,
            aeo_elements=result.get("aeo_elements", []),
            geo_elements=result.get("geo_elements", []),
            faq_questions=faq_questions,
        )

    def _build_prompt(
        self,
        research: TopicResearch,
        business: BusinessProfile,
        revision_instructions: str,
    ) -> str:
        facts_str = ""
        for f in research.topic_facts[:15]:
            facts_str += f"- {f.claim} [{f.verification_status}]\n"

        problems_str = "\n".join(f"- {p}" for p in research.common_problems[:10])
        solutions_str = "\n".join(f"- {s}" for s in research.solutions[:10])
        questions_str = "\n".join(f"- {q}" for q in research.user_questions[:10])
        local_str = "\n".join(f"- {c}" for c in research.local_context[:8])
        aeo_str = "\n".join(f"- {q}" for q in research.aeo_questions[:8])
        geo_str = "\n".join(f"- {g}" for g in research.geo_factors[:8])

        kw = research.keyword_research
        revision_section = ""
        if revision_instructions:
            revision_section = f"\n\nREVISION INSTRUCTIONS (this is a revision):\n{revision_instructions}\n"

        return f"""Write a complete blog article.

TOPIC: {research.topic_title}
PRIMARY KEYWORD: {kw.primary_keyword}
TARGET KEYWORD DENSITY: approximately {settings.content.target_keyword_density}%

SECONDARY KEYWORDS: {', '.join(kw.secondary_keywords)}
SEMANTIC KEYWORDS: {', '.join(kw.semantic_keywords)}
COMMERCIAL KEYWORDS: {', '.join(kw.commercial_keywords)}
LOCAL KEYWORDS: {', '.join(kw.local_keywords)}
QUESTION KEYWORDS: {', '.join(kw.question_keywords)}

BUSINESS:
Name: {business.business_name}
Location: {business.location}
Services: {', '.join(business.services)}
Service Areas: {', '.join(business.service_areas)}
Brand Voice: {business.brand_voice}
Description: {business.business_description}

RESEARCH FINDINGS:
Facts:
{facts_str}

Common Problems:
{problems_str}

Solutions:
{solutions_str}

User Questions:
{questions_str}

Local Context:
{local_str}

AEO Questions:
{aeo_str}

GEO Factors:
{geo_str}
{revision_section}
WRITING RULES:
- Write as an experienced human professional. No generic AI language.
- NEVER use em dashes or en dashes. Use commas, periods, hyphens, or parentheses.
- Never invent statistics, testimonials, credentials, prices, guarantees, or awards.
- Target approximately {settings.content.target_keyword_density}% primary keyword density. Never keyword-stuff.
- Include question-based headings for AEO.
- Include local context naturally for GEO.
- Article should be {settings.content.min_article_word_count}-{settings.content.max_article_word_count} words.
- Include an FAQ section with 3-5 relevant questions if appropriate.
- Vary sentence structure. Be specific and useful.

Return valid JSON with: title, primary_keyword, body_text, meta_description (140-160 chars), url_slug, faq_questions (array of {{question, answer}}), aeo_elements, geo_elements."""
