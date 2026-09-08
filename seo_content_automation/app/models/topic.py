from __future__ import annotations

from pydantic import BaseModel, Field


class TopicCandidate(BaseModel):
    title: str
    service_category: str
    search_intent: str  # informational, commercial, local, problem-solving
    target_audience: str = ""
    estimated_value: str = ""  # high, medium, low
    aeo_opportunity: str = ""
    geo_opportunity: str = ""
    rejection_reason: str = ""
    selected: bool = False


class TopicSelection(BaseModel):
    business_id: str
    selected_topics: list[TopicCandidate] = Field(default_factory=list)
    rejected_topics: list[TopicCandidate] = Field(default_factory=list)
    selection_reasoning: str = ""
