from __future__ import annotations

import re


def normalize_title(title: str) -> str:
    title = title.lower().strip()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def word_set(text: str) -> set[str]:
    stopwords = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "this", "that", "these",
        "those", "it", "its", "your", "you", "we", "our", "my", "their",
        "from", "into", "about", "how", "what", "when", "where", "why", "which",
    }
    words = set(normalize_title(text).split())
    return words - stopwords


def is_duplicate_topic(
    new_title: str,
    existing_titles: list[str],
    threshold: float = 0.6,
) -> tuple[bool, str]:
    new_words = word_set(new_title)
    for existing in existing_titles:
        existing_words = word_set(existing)
        sim = jaccard_similarity(new_words, existing_words)
        if sim >= threshold:
            return True, existing
    return False, ""


def is_duplicate_keyword(
    new_keyword: str,
    existing_keywords: list[str],
    threshold: float = 0.7,
) -> tuple[bool, str]:
    new_words = word_set(new_keyword)
    for existing in existing_keywords:
        existing_words = word_set(existing)
        sim = jaccard_similarity(new_words, existing_words)
        if sim >= threshold:
            return True, existing
    return False, ""
