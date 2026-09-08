"""Real provider using the Google Gemini API.

Used when settings.ai_provider == "gemini" and a key is set. Gemini can be told
to return JSON directly (response_mime_type), which makes parsing clean. The key
lives server-side only. Not exercised by the offline test suite.

Self-healing model selection: Google returns 404 when the configured model name
is not valid for this API version / key ("Call ListModels to see the list of
available models"). So instead of trusting a hard-coded name, we ask the key
which models it actually supports for generateContent and pick the best one,
preferring the configured model. The result is cached for the process.
"""
from __future__ import annotations

import json
import re
import time

import httpx

from app.ai.providers.base import ProviderResult
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("ai.gemini")

_BASE = "https://generativelanguage.googleapis.com/v1beta"
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

# Resolved once per process, shared by every GeminiProvider instance.
_resolved_model: str | None = None


def _short(name: str) -> str:
    """'models/gemini-2.5-flash' -> 'gemini-2.5-flash' (also strips leading slash)."""
    return name.rsplit("/", 1)[-1]


def _score_model(name: str) -> int:
    """Rank candidate models: prefer a stable, non-vision 'flash' text model."""
    n = name.lower()
    s = 0
    if "flash" in n:
        s += 100          # flash = fast + cheap, ideal for this workload
    if "2.5" in n:
        s += 30
    elif "2.0" in n:
        s += 20
    if "lite" in n:
        s += 5            # flash-lite is fine and has higher free limits
    if "preview" in n or "exp" in n:
        s -= 40           # avoid preview/experimental — they churn and rate-limit
    if any(x in n for x in ("vision", "image", "tts", "embedding", "aqa", "gemma")):
        s -= 200          # not general text-generation models
    if "1.5" in n or "1.0" in n or "pro-vision" in n:
        s -= 10           # older families, last resort
    return s


def _list_models(api_key: str, timeout: float) -> list[str]:
    """Model names the key can call generateContent on (e.g. 'gemini-2.5-flash')."""
    resp = httpx.get(
        f"{_BASE}/models",
        headers={"x-goog-api-key": api_key},
        timeout=timeout,
    )
    resp.raise_for_status()
    out: list[str] = []
    for m in resp.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            out.append(_short(m.get("name", "")))
    return [n for n in out if n]


def _resolve_model(preferred: str, api_key: str, timeout: float) -> str:
    """Pick a usable model: the configured one if the key supports it, else the
    best available. Falls back to the configured name if listing fails."""
    global _resolved_model
    if _resolved_model:
        return _resolved_model
    try:
        available = _list_models(api_key, timeout)
    except Exception as exc:
        logger.warning("could not list Gemini models (%s); using '%s'", exc, preferred)
        _resolved_model = preferred
        return _resolved_model

    pref = _short(preferred)
    if pref in available:
        chosen = pref
    elif available:
        chosen = sorted(available, key=_score_model, reverse=True)[0]
    else:
        chosen = pref
    if chosen != pref:
        logger.info("configured model '%s' unavailable; using '%s'", pref, chosen)
    logger.info("Gemini model resolved to '%s' (%d available)", chosen, len(available))
    _resolved_model = chosen
    return _resolved_model


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str | None = None, timeout: float = 60.0):
        self._preferred = model or settings.ai_model_strong or "gemini-2.5-flash"
        self.model = self._preferred
        self.timeout = timeout

    def generate(self, *, system: str, user: str, context: dict) -> ProviderResult:
        started = time.perf_counter()
        api_key = settings.ai_api_key or ""
        # Discover a working model (cached across calls).
        self.model = _resolve_model(self._preferred, api_key, self.timeout)

        headers = {"x-goog-api-key": api_key, "content-type": "application/json"}
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }

        body = self._post_with_retry(headers, payload)

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

    def _post_with_retry(self, headers: dict, payload: dict) -> dict:
        """POST generateContent, backing off on 429 (free-tier rate limit)."""
        global _resolved_model
        url = f"{_BASE}/{self.model}:generateContent"
        delays = [2, 5, 12]  # seconds; free tier is a few requests/minute
        last_exc: Exception | None = None
        for attempt in range(len(delays) + 1):
            resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
            if resp.status_code == 429 and attempt < len(delays):
                wait = delays[attempt]
                logger.info("rate limited; retrying in %ss", wait)
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                # Cached model went stale (shouldn't happen after resolve) — clear
                # the cache so the next call re-discovers, then fail this one.
                _resolved_model = None
            try:
                resp.raise_for_status()
            except Exception as exc:
                last_exc = exc
                raise
            return resp.json()
        if last_exc:
            raise last_exc
        raise RuntimeError("Gemini request failed after retries")

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
