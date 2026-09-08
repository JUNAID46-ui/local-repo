from __future__ import annotations

from pydantic import BaseModel, Field


class ImageConcept(BaseModel):
    image_number: int
    purpose: str  # featured, supporting
    concept: str
    scene_description: str
    subject: str
    location_context: str = ""
    photography_style: str = ""
    filename: str
    alt_text: str
    suggested_placement: str = ""


class InternalLink(BaseModel):
    anchor_text: str
    target_url: str
    reason: str


class ExternalSource(BaseModel):
    source_title: str
    source_url: str
    source_type: str
    claim_supported: str


class ArticleDraft(BaseModel):
    title: str
    primary_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = ""
    body_html: str = ""
    body_text: str = ""
    meta_description: str = ""
    url_slug: str = ""
    word_count: int = 0
    keyword_count: int = 0
    keyword_density: float = 0.0
    images: list[ImageConcept] = Field(default_factory=list)
    internal_links: list[InternalLink] = Field(default_factory=list)
    external_sources: list[ExternalSource] = Field(default_factory=list)
    aeo_elements: list[str] = Field(default_factory=list)
    geo_elements: list[str] = Field(default_factory=list)
    faq_questions: list[dict[str, str]] = Field(default_factory=list)


class FinalArticle(BaseModel):
    title: str
    primary_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = ""
    service_category: str = ""
    body_text: str = ""
    meta_description: str = ""
    url_slug: str = ""
    word_count: int = 0
    keyword_count: int = 0
    keyword_density: float = 0.0
    images: list[ImageConcept] = Field(default_factory=list)
    internal_links: list[InternalLink] = Field(default_factory=list)
    external_sources: list[ExternalSource] = Field(default_factory=list)
    aeo_elements: list[str] = Field(default_factory=list)
    geo_elements: list[str] = Field(default_factory=list)
    faq_questions: list[dict[str, str]] = Field(default_factory=list)
    qa_passed: bool = False
    revision_count: int = 0
