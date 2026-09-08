import pytest
from app.services.duplicate_detection import (
    is_duplicate_keyword,
    is_duplicate_topic,
    jaccard_similarity,
    normalize_title,
    word_set,
)


class TestNormalizeTitle:
    def test_basic(self):
        assert normalize_title("Hello World!") == "hello world"

    def test_special_chars(self):
        assert normalize_title("What's the Cost? (2024)") == "whats the cost 2024"


class TestJaccardSimilarity:
    def test_identical(self):
        s = {"a", "b", "c"}
        assert jaccard_similarity(s, s) == 1.0

    def test_disjoint(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial(self):
        sim = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert 0.4 < sim < 0.6

    def test_empty(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0


class TestDuplicateTopic:
    def test_exact_duplicate(self):
        is_dup, match = is_duplicate_topic(
            "Refrigerator Repair in Tucson",
            ["Refrigerator Repair in Tucson"],
        )
        assert is_dup
        assert match == "Refrigerator Repair in Tucson"

    def test_similar_duplicate(self):
        is_dup, _ = is_duplicate_topic(
            "Refrigerator Repair Tucson Guide",
            ["Tucson Refrigerator Repair Guide"],
        )
        assert is_dup

    def test_not_duplicate(self):
        is_dup, _ = is_duplicate_topic(
            "Refrigerator Repair in Tucson",
            ["Oven Repair in Phoenix", "Dishwasher Maintenance Tips"],
        )
        assert not is_dup

    def test_empty_existing(self):
        is_dup, _ = is_duplicate_topic("Some Title", [])
        assert not is_dup


class TestDuplicateKeyword:
    def test_exact_match(self):
        is_dup, _ = is_duplicate_keyword(
            "refrigerator repair tucson",
            ["refrigerator repair tucson"],
        )
        assert is_dup

    def test_different_keywords(self):
        is_dup, _ = is_duplicate_keyword(
            "oven repair tucson",
            ["dishwasher repair phoenix"],
        )
        assert not is_dup
