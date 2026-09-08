from __future__ import annotations

from pydantic import BaseModel, Field


class KeywordResearch(BaseModel):
    primary_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)
    semantic_keywords: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    commercial_keywords: list[str] = Field(default_factory=list)
    local_keywords: list[str] = Field(default_factory=list)
    question_keywords: list[str] = Field(default_factory=list)
    long_tail_keywords: list[str] = Field(default_factory=list)
    search_intent: str = ""
    keyword_variations: list[str] = Field(default_factory=list)


class ResearchSource(BaseModel):
    source_title: str
    source_url: str
    source_type: str  # government, manufacturer, industry_org, publication, local
    claim_supported: str = ""
    reliability: str = "unknown"  # high, medium, low, unknown


class ResearchEvidence(BaseModel):
    claim: str
    source: str = ""
    source_type: str = ""
    verification_status: str = "UNVERIFIED"  # VERIFIED, SUPPORTED, BUSINESS-PROVIDED, COMMON_KNOWLEDGE, UNVERIFIED


class TopicResearch(BaseModel):
    topic_title: str
    keyword_research: KeywordResearch
    business_facts: list[ResearchEvidence] = Field(default_factory=list)
    topic_facts: list[ResearchEvidence] = Field(default_factory=list)
    common_problems: list[str] = Field(default_factory=list)
    solutions: list[str] = Field(default_factory=list)
    user_questions: list[str] = Field(default_factory=list)
    local_context: list[str] = Field(default_factory=list)
    industry_terminology: list[str] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    aeo_questions: list[str] = Field(default_factory=list)
    geo_factors: list[str] = Field(default_factory=list)
