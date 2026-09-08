from __future__ import annotations

from app.config import settings
from app.models.article import ArticleDraft
from app.models.business import BusinessProfile
from app.models.qa import QAFinding, SEOReport
from app.utils.text import calculate_keyword_density


class SEOValidator:
    def validate(self, article: ArticleDraft, business: BusinessProfile) -> SEOReport:
        findings: list[QAFinding] = []

        kw_count, word_count, density = calculate_keyword_density(
            article.body_text, article.primary_keyword,
        )

        title_has_kw = article.primary_keyword.lower() in article.title.lower()
        meta_len = len(article.meta_description)
        meta_has_kw = article.primary_keyword.lower() in article.meta_description.lower()

        target = settings.content.target_keyword_density
        tolerance = settings.content.keyword_density_tolerance

        density_ok = abs(density - target) <= tolerance + 0.5

        if density > 3.5:
            findings.append(QAFinding(
                category="seo", severity="critical",
                description=f"Keyword density too high: {density}% (keyword stuffing)",
                suggestion="Reduce primary keyword occurrences naturally",
            ))
        elif density > target + tolerance:
            findings.append(QAFinding(
                category="seo", severity="warning",
                description=f"Keyword density slightly high: {density}%",
                suggestion="Consider reducing a few keyword occurrences",
            ))
        elif density < 1.0:
            findings.append(QAFinding(
                category="seo", severity="warning",
                description=f"Keyword density low: {density}%",
                suggestion="Add more natural uses of the primary keyword",
            ))

        if not title_has_kw:
            findings.append(QAFinding(
                category="seo", severity="warning",
                description="Primary keyword not in title",
                suggestion="Include primary keyword in the title",
            ))

        if meta_len < settings.content.meta_description_min_length:
            findings.append(QAFinding(
                category="seo", severity="warning",
                description=f"Meta description too short: {meta_len} chars",
                suggestion=f"Expand to {settings.content.meta_description_min_length}-{settings.content.meta_description_max_length} chars",
            ))
        elif meta_len > settings.content.meta_description_max_length:
            findings.append(QAFinding(
                category="seo", severity="warning",
                description=f"Meta description too long: {meta_len} chars",
                suggestion=f"Trim to {settings.content.meta_description_max_length} chars or less",
            ))

        if not meta_has_kw:
            findings.append(QAFinding(
                category="seo", severity="warning",
                description="Primary keyword not in meta description",
                suggestion="Include primary keyword in meta description",
            ))

        if not article.meta_description:
            findings.append(QAFinding(
                category="seo", severity="critical",
                description="Missing meta description",
                suggestion="Generate a meta description",
            ))

        headings = sum(1 for line in article.body_text.split("\n") if line.strip().startswith("#"))
        if headings < 3:
            findings.append(QAFinding(
                category="seo", severity="warning",
                description=f"Only {headings} headings found",
                suggestion="Add more structured headings (H2/H3)",
            ))

        if not article.url_slug:
            findings.append(QAFinding(
                category="seo", severity="warning",
                description="Missing URL slug",
                suggestion="Generate a URL-friendly slug",
            ))

        secondary_used = sum(
            1 for kw in article.secondary_keywords
            if kw.lower() in article.body_text.lower()
        )

        commercial_count = 0
        for term in settings.commercial_intent_terms:
            if term.lower() in article.body_text.lower():
                commercial_count += 1

        passed = not any(f.severity == "critical" for f in findings)

        return SEOReport(
            primary_keyword_present=kw_count > 0,
            keyword_density=density,
            keyword_density_ok=density_ok,
            secondary_keywords_used=secondary_used,
            commercial_terms_count=commercial_count,
            title_has_keyword=title_has_kw,
            meta_description_length=meta_len,
            meta_description_has_keyword=meta_has_kw,
            headings_count=headings,
            internal_links_count=len(article.internal_links),
            url_slug_ok=bool(article.url_slug),
            findings=findings,
            passed=passed,
        )
