"""Real provider using the Anthropic Messages API.

Only used when settings.ai_provider == "anthropic" and a key is set. The key
lives server-side only and is never exposed to clients. Not exercised in the
test suite (which runs offline with the mock provider).
"""
from __future__ import annotations

import json
import re
import time

import httpx

from app.ai.providers.base import ProviderResult
from app.core.config import settings

_API_URL = "https://api.anthropic.com/v1/messages"
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str | None = None, timeout: float = 60.0):
        self.model = model or settings.ai_model_strong or "claude-3-5-sonnet-latest"
        self.timeout = timeout

    def generate(self, *, system: str, user: str, context: dict) -> ProviderResult:
        started = time.perf_counter()
        headers = {
            "x-api-key": settings.ai_api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 1500,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        resp = httpx.post(_API_URL, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()

        text = "".join(
            block.get("text", "") for block in body.get("content", [])
            if block.get("type") == "text"
        )
        data = self._parse_json(text)
        usage = body.get("usage", {})
        latency = int((time.perf_counter() - started) * 1000)
        return ProviderResult(
            data=data,
            model=self.model,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            latency_ms=latency,
            raw=text,
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = _JSON_RE.search(text)
            if not match:
                raise ValueError("no JSON object found in model output")
            return json.loads(match.group(0))
