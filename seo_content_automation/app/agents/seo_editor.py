from __future__ import annotations

import json
import logging

from app.agents.base import BaseAgent
from app.config import settings
from app.models.article import ArticleDraft, ExternalSource, ImageConcept, InternalLink
from app.models.business import BusinessProfile
from app.models.research import TopicResearch
from app.utils.text import calculate_keyword_density, strip_dashes

logger = logging.getLogger("seo_automation")


class SEOEditor:
    def __init__(self, agent: BaseAgent | None = None):
        self.agent = agent or BaseAgent("seo_editor", model=settings.models.primary)

    def edit_article(
        self,
        draft: ArticleDraft,
        research: TopicResearch,
        business: BusinessProfile,
        revision_feedback: str = "",
    ) -> ArticleDraft:
        prompt = self._build_prompt(draft, research, business, revision_feedback)
        result = self.agent.call_json(prompt, max_tokens=8192)

        body_text = result.get("body_text", draft.body_text)
        body_text = strip_dashes(body_text)

        kw_count, word_count, density = calculate_keyword_density(
            body_text, draft.primary_keyword
        )

        images = []
        for img in result.get("images", []):
            images.append(ImageConcept(
                image_number=img.get("image_number", 0),
                purpose=img.get("purpose", "supporting"),
                concept=img.get("concept", ""),
                scene_description=img.get("scene_description", ""),
                subject=img.get("subject", ""),
                location_context=img.get("location_context", ""),
                photography_style=img.get("photography_style", ""),
                filename=img.get("filename", ""),
                alt_text=img.get("alt_text", ""),
                suggested_placement=img.get("suggested_placement", ""),
            ))

        internal_links = []
        for link in result.get("internal_links", []):
            internal_links.append(InternalLink(
                anchor_text=link.get("anchor_text", ""),
                target_url=link.get("target_url", ""),
                reason=link.get("reason", ""),
            ))

        external_sources = []
        for src in result.get("external_sources", []):
            external_sources.append(ExternalSource(
                source_title=src.get("source_title", ""),
                source_url=src.get("source_url", ""),
                source_type=src.get("source_type", ""),
                claim_supported=src.get("claim_supported", ""),
            ))

        meta_desc = result.get("meta_description", draft.meta_description)

        draft.body_text = body_text
        draft.word_count = word_count
        draft.keyword_count = kw_count
        draft.keyword_density = density
        draft.images = images
        draft.internal_links = internal_links
        draft.external_sources = external_sources
        if meta_desc:
            draft.meta_description = meta_desc

        return draft

    def _build_prompt(
        self,
        draft: ArticleDraft,
        research: TopicResearch,
        business: BusinessProfile,
        revision_feedback: str,
    ) -> str:
        revision_section = ""
        if revision_feedback:
            revision_section = f"\n\nREVISION FEEDBACK:\n{revision_feedback}\n"

        kw = research.keyword_research
        img_settings = settings.images

        return f"""Edit and optimize this article for SEO, AEO, and GEO.

TITLE: {draft.title}
PRIMARY KEYWORD: {draft.primary_keyword}
TARGET KEYWORD DENSITY: approximately {settings.content.target_keyword_density}%
CURRENT KEYWORD DENSITY: {draft.keyword_density}%
CURRENT WORD COUNT: {draft.word_count}

SECONDARY KEYWORDS: {', '.join(kw.secondary_keywords)}
SEMANTIC KEYWORDS: {', '.join(kw.semantic_keywords)}
COMMERCIAL KEYWORDS: {', '.join(kw.commercial_keywords)}
LOCAL KEYWORDS: {', '.join(kw.local_keywords)}

BUSINESS:
Name: {business.business_name}
Location: {business.location}
Website: {business.website}
Internal Link Base: {business.internal_link_base}
Services: {', '.join(business.services)}

CURRENT ARTICLE:
{draft.body_text}

CURRENT META DESCRIPTION: {draft.meta_description}
{revision_section}
TASKS:
1. Refine keyword integration (target ~{settings.content.target_keyword_density}% density, never keyword-stuff).
2. Improve heading structure.
3. Refine meta description ({settings.content.meta_description_min_length}-{settings.content.meta_description_max_length} chars).
4. Generate {img_settings.featured_count} featured image + {img_settings.supporting_min}-{img_settings.supporting_max} supporting image concepts.
5. Suggest internal links from {business.website} (only verified URLs).
6. Suggest relevant external sources.
7. REMOVE any em dashes or en dashes. Use hyphens, commas, or periods.
8. Do NOT add generic AI phrases.

Return valid JSON with: body_text, meta_description, images (array), internal_links (array), external_sources (array).
Each image: image_number, purpose, concept, scene_description, subject, location_context, photography_style, filename, alt_text, suggested_placement.
Each internal_link: anchor_text, target_url, reason.
Each external_source: source_title, source_url, source_type, claim_supported."""
