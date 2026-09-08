from __future__ import annotations

from pydantic import BaseModel, Field


class QAFinding(BaseModel):
    category: str  # seo, aeo, geo, fact, style
    severity: str  # critical, warning, info
    description: str
    suggestion: str = ""
    auto_fixable: bool = False


class SEOReport(BaseModel):
    primary_keyword_present: bool = False
    keyword_density: float = 0.0
    keyword_density_ok: bool = False
    secondary_keywords_used: int = 0
    commercial_terms_count: int = 0
    title_has_keyword: bool = False
    meta_description_length: int = 0
    meta_description_has_keyword: bool = False
    headings_count: int = 0
    internal_links_count: int = 0
    url_slug_ok: bool = False
    findings: list[QAFinding] = Field(default_factory=list)
    passed: bool = False


class AEOReport(BaseModel):
    direct_answers_count: int = 0
    question_headings_count: int = 0
    faq_present: bool = False
    entity_clarity: str = ""
    concise_answer_opportunities: int = 0
    findings: list[QAFinding] = Field(default_factory=list)
    passed: bool = False


class GEOReport(BaseModel):
    location_mentions: int = 0
    local_context_present: bool = False
    local_facts_verified: bool = False
    service_area_mentioned: bool = False
    findings: list[QAFinding] = Field(default_factory=list)
    passed: bool = False


class FactCheckReport(BaseModel):
    total_claims: int = 0
    verified: int = 0
    supported: int = 0
    business_provided: int = 0
    common_knowledge: int = 0
    unverified: int = 0
    fabricated_found: bool = False
    findings: list[QAFinding] = Field(default_factory=list)
    passed: bool = False


class StyleReport(BaseModel):
    ai_phrases_found: list[str] = Field(default_factory=list)
    em_dashes_found: int = 0
    en_dashes_found: int = 0
    repetitive_patterns: list[str] = Field(default_factory=list)
    readability_score: str = ""
    findings: list[QAFinding] = Field(default_factory=list)
    passed: bool = False


class QAResult(BaseModel):
    seo: SEOReport = Field(default_factory=SEOReport)
    aeo: AEOReport = Field(default_factory=AEOReport)
    geo: GEOReport = Field(default_factory=GEOReport)
    fact_check: FactCheckReport = Field(default_factory=FactCheckReport)
    style: StyleReport = Field(default_factory=StyleReport)
    overall_passed: bool = False
    critical_failures: list[str] = Field(default_factory=list)
    revision_needed: bool = False
    revision_instructions: str = ""
