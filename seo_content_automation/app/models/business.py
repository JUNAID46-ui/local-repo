from __future__ import annotations

from pydantic import BaseModel, Field


class BusinessProfile(BaseModel):
    business_id: str
    business_name: str
    website: str = ""
    location: str = ""
    country: str = ""
    industry: str = ""
    services: list[str] = Field(default_factory=list)
    primary_service: str = ""
    target_audience: str = ""
    business_description: str = ""
    business_facts: list[str] = Field(default_factory=list)
    brand_voice: str = "professional, helpful, knowledgeable"
    primary_keywords: list[str] = Field(default_factory=list)
    commercial_keywords: list[str] = Field(default_factory=list)
    service_areas: list[str] = Field(default_factory=list)
    existing_content_urls: list[str] = Field(default_factory=list)
    internal_link_base: str = ""
    output_folder: str = ""
    active: bool = True


class BusinessState(BaseModel):
    business_id: str
    generated_topics: list[str] = Field(default_factory=list)
    generated_primary_keywords: list[str] = Field(default_factory=list)
    last_run: str = ""
    total_articles_generated: int = 0
