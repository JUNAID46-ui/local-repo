from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings, PROJECT_ROOT

logger = logging.getLogger("seo_automation")


def _load_prompt(prompt_name: str) -> str:
    prompt_path = PROJECT_ROOT / "prompts" / f"{prompt_name}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""


class BaseAgent:
    def __init__(self, prompt_name: str, model: str | None = None):
        self.prompt_name = prompt_name
        self.system_prompt = _load_prompt(prompt_name)
        self.model = model or settings.models.primary
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    def call(self, user_message: str, max_tokens: int = 8192) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    def call_json(self, user_message: str, max_tokens: int = 8192) -> dict[str, Any]:
        raw = self.call(user_message, max_tokens)
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            logger.error(f"Failed to parse JSON from agent response: {text[:200]}")
            return {}


class MockAgent(BaseAgent):
    def __init__(self, prompt_name: str, mock_response: dict[str, Any] | None = None):
        super().__init__(prompt_name)
        self._mock_response = mock_response or {}

    def call(self, user_message: str, max_tokens: int = 8192) -> str:
        logger.info(f"[MockAgent:{self.prompt_name}] Called with {len(user_message)} chars")
        return json.dumps(self._mock_response)

    def call_json(self, user_message: str, max_tokens: int = 8192) -> dict[str, Any]:
        logger.info(f"[MockAgent:{self.prompt_name}] JSON call with {len(user_message)} chars")
        return self._mock_response
