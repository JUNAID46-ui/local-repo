from __future__ import annotations

from app.models.research import KeywordResearch
from app.utils.text import calculate_keyword_density


def analyze_keyword_usage(
    text: str,
    keywords: KeywordResearch,
) -> dict[str, any]:
    kw_count, word_count, density = calculate_keyword_density(text, keywords.primary_keyword)

    secondary_usage = {}
    for kw in keywords.secondary_keywords:
        count = text.lower().count(kw.lower())
        secondary_usage[kw] = count

    semantic_usage = {}
    for kw in keywords.semantic_keywords:
        count = text.lower().count(kw.lower())
        semantic_usage[kw] = count

    commercial_usage = {}
    for kw in keywords.commercial_keywords:
        count = text.lower().count(kw.lower())
        commercial_usage[kw] = count

    local_usage = {}
    for kw in keywords.local_keywords:
        count = text.lower().count(kw.lower())
        local_usage[kw] = count

    return {
        "primary_keyword": keywords.primary_keyword,
        "primary_count": kw_count,
        "word_count": word_count,
        "keyword_density": density,
        "secondary_usage": secondary_usage,
        "semantic_usage": semantic_usage,
        "commercial_usage": commercial_usage,
        "local_usage": local_usage,
        "secondary_used_count": sum(1 for v in secondary_usage.values() if v > 0),
        "semantic_used_count": sum(1 for v in semantic_usage.values() if v > 0),
        "commercial_used_count": sum(1 for v in commercial_usage.values() if v > 0),
        "local_used_count": sum(1 for v in local_usage.values() if v > 0),
    }
