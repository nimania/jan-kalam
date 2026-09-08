"""Real provider using the Google Gemini API.

Used when settings.ai_provider == "gemini" and a key is set. Gemini can be told
to return JSON directly (response_mime_type), which makes parsing clean. The key
lives server-side only. Not exercised by the offline test suite.
"""
from __future__ import annotations

import json
import re
import time

import httpx

from app.ai.providers.base import ProviderResult
from app.core.config import settings

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str | None = None, timeout: float = 60.0):
        self.model = model or settings.ai_model_strong or "gemini-2.5-flash"
        self.timeout = timeout

    def generate(self, *, system: str, user: str, context: dict) -> ProviderResult:
        started = time.perf_counter()
        url = f"{_BASE}/{self.model}:generateContent"
        headers = {
            "x-goog-api-key": settings.ai_api_key or "",
            "content-type": "application/json",
        }
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()

        text = self._extract_text(body)
        data = self._parse_json(text)
        usage = body.get("usageMetadata", {})
        latency = int((time.perf_counter() - started) * 1000)
        return ProviderResult(
            data=data,
            model=self.model,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            latency_ms=latency,
            raw=text,
        )

    @staticmethod
    def _extract_text(body: dict) -> str:
        candidates = body.get("candidates", [])
        if not candidates:
            raise ValueError("no candidates in Gemini response")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    @staticmethod
    def _parse_json(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = _JSON_RE.search(text)
            if not match:
                raise ValueError("no JSON object found in Gemini output")
            return json.loads(match.group(0))
