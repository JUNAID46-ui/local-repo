from __future__ import annotations

import re
import unicodedata


def sanitize_filename(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", "_", name.strip())
    name = re.sub(r"_+", "_", name)
    name = name.strip("_.")
    return name[:200]


def calculate_keyword_density(text: str, keyword: str) -> tuple[int, int, float]:
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    words = text_lower.split()
    word_count = len(words)
    if word_count == 0:
        return 0, 0, 0.0
    pattern = re.compile(re.escape(keyword_lower), re.IGNORECASE)
    matches = pattern.findall(text_lower)
    keyword_count = len(matches)
    density = (keyword_count / word_count) * 100 if word_count > 0 else 0.0
    return keyword_count, word_count, round(density, 2)


def strip_dashes(text: str) -> str:
    text = text.replace("—", " - ")  # em dash
    text = text.replace("–", "-")  # en dash
    return text


def contains_dashes(text: str) -> tuple[int, int]:
    em_count = text.count("—")
    en_count = text.count("–")
    return em_count, en_count


def generate_url_slug(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug[:80]


def count_words(text: str) -> int:
    return len(text.split())


def detect_ai_phrases(text: str, blocklist: list[str]) -> list[str]:
    text_lower = text.lower()
    found = []
    for phrase in blocklist:
        if "*" in phrase:
            pattern = phrase.replace("*", r"\w+")
            if re.search(pattern, text_lower):
                found.append(phrase)
        elif phrase.lower() in text_lower:
            found.append(phrase)
    return found


def detect_repetitive_patterns(text: str) -> list[str]:
    patterns_found = []
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) < 3:
        return patterns_found
    starters: dict[str, int] = {}
    for sent in sentences:
        words = sent.split()
        if len(words) >= 3:
            starter = " ".join(words[:3]).lower()
            starters[starter] = starters.get(starter, 0) + 1

    for starter, count in starters.items():
        if count >= 3:
            patterns_found.append(f"Repeated sentence starter ({count}x): '{starter}...'")

    return patterns_found
