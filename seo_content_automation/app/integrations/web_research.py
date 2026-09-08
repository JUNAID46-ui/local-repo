from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("seo_automation")


class WebResearcher:
    def __init__(self, timeout: int = 15) -> None:
        self._timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_page(self, url: str) -> str | None:
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "SEOContentBot/1.0"})
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    def extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:10000]

    def extract_links(self, html: str, base_url: str) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if href.startswith("/"):
                href = base_url.rstrip("/") + href
            if href.startswith("http") and text:
                links.append({"url": href, "text": text[:200]})
        return links

    def extract_page_metadata(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("title")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        h1_tags = soup.find_all("h1")
        return {
            "title": title_tag.get_text(strip=True) if title_tag else "",
            "meta_description": meta_desc["content"] if meta_desc and meta_desc.get("content") else "",
            "h1": h1_tags[0].get_text(strip=True) if h1_tags else "",
        }

    def research_url(self, url: str) -> dict[str, Any] | None:
        html = self.fetch_page(url)
        if not html:
            return None
        return {
            "url": url,
            "text": self.extract_text(html),
            "links": self.extract_links(html, url),
            "metadata": self.extract_page_metadata(html),
        }


class MockWebResearcher:
    def fetch_page(self, url: str) -> str | None:
        return "<html><body><h1>Mock Page</h1><p>Mock content for testing.</p></body></html>"

    def extract_text(self, html: str) -> str:
        return "Mock page content for testing purposes."

    def extract_links(self, html: str, base_url: str) -> list[dict[str, str]]:
        return [{"url": f"{base_url}/services", "text": "Our Services"}]

    def extract_page_metadata(self, html: str) -> dict[str, str]:
        return {"title": "Mock Business", "meta_description": "Mock business description", "h1": "Mock Page"}

    def research_url(self, url: str) -> dict[str, Any] | None:
        return {
            "url": url,
            "text": "Mock page content for testing purposes.",
            "links": [{"url": f"{url}/services", "text": "Our Services"}],
            "metadata": {"title": "Mock Business", "meta_description": "Mock description", "h1": "Mock"},
        }
