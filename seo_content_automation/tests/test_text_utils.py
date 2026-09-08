import pytest
from app.utils.text import (
    calculate_keyword_density,
    contains_dashes,
    detect_ai_phrases,
    detect_repetitive_patterns,
    generate_url_slug,
    sanitize_filename,
    strip_dashes,
    count_words,
)


class TestSanitizeFilename:
    def test_basic(self):
        assert sanitize_filename("Hello World") == "Hello_World"

    def test_special_chars(self):
        assert sanitize_filename('Test: File "Name"') == "Test_File_Name"

    def test_slashes(self):
        assert sanitize_filename("path/to/file") == "pathtofile"

    def test_max_length(self):
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_empty(self):
        assert sanitize_filename("") == ""

    def test_dots_underscores(self):
        result = sanitize_filename("...test...")
        assert not result.startswith(".")
        assert not result.endswith(".")


class TestKeywordDensity:
    def test_basic_density(self):
        text = "appliance repair is great. We do appliance repair daily."
        count, words, density = calculate_keyword_density(text, "appliance repair")
        assert count == 2
        assert words == 9
        assert round(density, 2) == 22.22

    def test_zero_density(self):
        text = "This is a test sentence."
        count, words, density = calculate_keyword_density(text, "appliance repair")
        assert count == 0
        assert density == 0.0

    def test_case_insensitive(self):
        text = "Appliance Repair is our specialty. We offer appliance repair services."
        count, _, _ = calculate_keyword_density(text, "appliance repair")
        assert count == 2

    def test_empty_text(self):
        count, words, density = calculate_keyword_density("", "keyword")
        assert count == 0
        assert words == 0
        assert density == 0.0

    def test_target_two_percent(self):
        words_list = ["word"] * 98 + ["appliance repair"]
        text = " ".join(words_list)
        count, words, density = calculate_keyword_density(text, "appliance repair")
        assert count == 1
        assert density > 0


class TestDashDetection:
    def test_em_dash(self):
        text = "This is a test — with an em dash."
        em, en = contains_dashes(text)
        assert em == 1
        assert en == 0

    def test_en_dash(self):
        text = "Pages 10–20 have the info."
        em, en = contains_dashes(text)
        assert em == 0
        assert en == 1

    def test_both_dashes(self):
        text = "This — has both – and — dashes."
        em, en = contains_dashes(text)
        assert em == 2
        assert en == 1

    def test_no_dashes(self):
        text = "This is a clean sentence with a regular hyphen - like this."
        em, en = contains_dashes(text)
        assert em == 0
        assert en == 0

    def test_strip_dashes(self):
        text = "Hello — world – test"
        result = strip_dashes(text)
        assert "—" not in result
        assert "–" not in result


class TestUrlSlug:
    def test_basic(self):
        slug = generate_url_slug("How to Repair a Refrigerator in Tucson")
        assert slug == "how-to-repair-a-refrigerator-in-tucson"

    def test_special_chars(self):
        slug = generate_url_slug("What's the Cost? (2024 Guide)")
        assert "?" not in slug
        assert "(" not in slug
        assert "'" not in slug

    def test_max_length(self):
        long_title = "word " * 50
        slug = generate_url_slug(long_title)
        assert len(slug) <= 80


class TestAIPhraseDetection:
    def test_detect_phrases(self):
        text = "In today's digital world, it is important to note that we leverage cutting-edge technology."
        blocklist = [
            "in today's digital world",
            "it is important to note",
            "leverage",
            "cutting-edge",
        ]
        found = detect_ai_phrases(text, blocklist)
        assert len(found) == 4

    def test_no_phrases(self):
        text = "Refrigerator compressors fail for several reasons."
        blocklist = ["in today's digital world", "leverage"]
        found = detect_ai_phrases(text, blocklist)
        assert len(found) == 0

    def test_wildcard_pattern(self):
        text = "Take your business to the next level."
        blocklist = ["take your * to the next level"]
        found = detect_ai_phrases(text, blocklist)
        assert len(found) == 1


class TestRepetitivePatterns:
    def test_detect_repetition(self):
        text = (
            "It is important to check. It is important to test. "
            "It is important to verify. Something else entirely."
        )
        patterns = detect_repetitive_patterns(text)
        assert len(patterns) > 0

    def test_no_repetition(self):
        text = (
            "First, check the compressor. Next, inspect the fan. "
            "After that, test the thermostat."
        )
        patterns = detect_repetitive_patterns(text)
        assert len(patterns) == 0


class TestCountWords:
    def test_basic(self):
        assert count_words("hello world test") == 3

    def test_empty(self):
        assert count_words("") == 0
