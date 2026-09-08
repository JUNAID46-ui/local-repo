from __future__ import annotations

from app.config import settings
from app.models.article import ArticleDraft
from app.models.qa import QAFinding, StyleReport
from app.utils.text import contains_dashes, detect_ai_phrases, detect_repetitive_patterns


class StyleValidator:
    def validate(self, article: ArticleDraft) -> StyleReport:
        findings: list[QAFinding] = []
        text = article.body_text

        ai_phrases = detect_ai_phrases(text, settings.ai_phrase_blocklist)
        em_count, en_count = contains_dashes(text)
        repetitive = detect_repetitive_patterns(text)

        if em_count > 0:
            findings.append(QAFinding(
                category="style", severity="critical",
                description=f"Em dash characters found: {em_count}",
                suggestion="Replace all em dashes with hyphens, commas, or periods",
                auto_fixable=True,
            ))

        if en_count > 0:
            findings.append(QAFinding(
                category="style", severity="critical",
                description=f"En dash characters found: {en_count}",
                suggestion="Replace all en dashes with hyphens",
                auto_fixable=True,
            ))

        if ai_phrases:
            findings.append(QAFinding(
                category="style", severity="warning",
                description=f"AI phrases detected: {', '.join(ai_phrases[:5])}",
                suggestion="Rewrite these phrases in natural language",
            ))

        if repetitive:
            for pattern in repetitive[:3]:
                findings.append(QAFinding(
                    category="style", severity="warning",
                    description=pattern,
                    suggestion="Vary sentence structure",
                ))

        readability = "good"
        sentences = text.split(".")
        avg_sentence_len = (
            sum(len(s.split()) for s in sentences if s.strip()) / max(len(sentences), 1)
        )
        if avg_sentence_len > 30:
            readability = "difficult"
            findings.append(QAFinding(
                category="style", severity="warning",
                description=f"Average sentence length is {avg_sentence_len:.0f} words",
                suggestion="Break up long sentences for readability",
            ))
        elif avg_sentence_len < 8:
            readability = "choppy"
            findings.append(QAFinding(
                category="style", severity="info",
                description="Sentences are very short on average",
                suggestion="Consider combining some short sentences",
            ))

        passed = not any(f.severity == "critical" for f in findings)

        return StyleReport(
            ai_phrases_found=ai_phrases,
            em_dashes_found=em_count,
            en_dashes_found=en_count,
            repetitive_patterns=repetitive,
            readability_score=readability,
            findings=findings,
            passed=passed,
        )
