from __future__ import annotations

import logging
from pathlib import Path

from app.models.article import FinalArticle
from app.models.business import BusinessProfile
from app.models.qa import QAResult
from app.services.document_generation import DocumentGenerator

logger = logging.getLogger("seo_automation")


class DocumentAgent:
    def __init__(self) -> None:
        self.generator = DocumentGenerator()

    def generate_docx(
        self,
        articles: list[FinalArticle],
        business: BusinessProfile,
        qa_results: list[QAResult],
        output_dir: Path,
        date_str: str,
    ) -> Path:
        from app.utils.text import sanitize_filename
        filename = f"{sanitize_filename(business.business_name)}_SEO_Content_{date_str}.docx"
        output_path = output_dir / filename
        self.generator.generate(articles, business, qa_results, output_path)
        logger.info(f"Generated DOCX: {output_path}")
        return output_path
