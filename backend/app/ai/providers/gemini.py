"""Real provider using the Google Gemini API.

Used when settings.ai_provider == "gemini" and a key is set. Gemini can be told
to return JSON directly (response_mime_type), which makes parsing clean. The key
lives server-side only. Not exercised by the offline test suite.

Self-healing model selection: Google returns 404 when the configured model name
is not valid for this API version / key ("Call ListModels to see the list of
available models"). So instead of trusting a hard-coded name, we ask the key
which models it actually supports for generateContent and pick the best one,
preferring the configured model. If a chosen model still 404s on the actual
call, we blacklist it and fall through to the next best — so a stale or
inconsistent model name can never block the whole run. Resolution is cached.
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

# Shared across every GeminiProvider instance for the life of the process.
_resolved_model: str | None = None
_bad_models: set[str] = set()


def _short(name: str) -> str:
    """'models/gemini-2.5-flash' -> 'gemini-2.5-flash' (also strips leading slash)."""
    return name.rsplit("/", 1)[-1]


def _mark_bad(model: str) -> None:
    """Remember a model that 404'd so we never pick it again, and force re-resolve."""
    global _resolved_model
    _bad_models.add(model)
    _resolved_model = None


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
    """Pick a usable model: the configured one if the key supports it (and it
    hasn't 404'd), else the best available. Falls back to the configured name if
    listing fails. Never returns a blacklisted model unless nothing else is left."""
    global _resolved_model
    if _resolved_model:
        return _resolved_model

    pref = _short(preferred)
    try:
        available = [a for a in _list_models(api_key, timeout) if a not in _bad_models]
    except Exception as exc:
        logger.warning("could not list Gemini models (%s); using '%s'", exc, pref)
        _resolved_model = pref
        return _resolved_model

    if pref in available:
        chosen = pref
    elif available:
        chosen = sorted(available, key=_score_model, reverse=True)[0]
    else:
        chosen = pref  # nothing else offered — last resort
    if chosen != pref:
        logger.info("using Gemini model '%s' (configured '%s' not usable)", chosen, pref)
    logger.info("Gemini model resolved to '%s' (%d usable)", chosen, len(available))
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
        headers = {
            "x-goog-api-key": settings.ai_api_key or "",
            "content-type": "application/json",
        }
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }

        body = self._call(headers, payload)

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

    def _call(self, headers: dict, payload: dict) -> dict:
        """Resolve a model and POST generateContent. On 404, blacklist that model
        and try the next best. On 429, back off. Correct URL includes '/models/'."""
        api_key = settings.ai_api_key or ""
        resp = None
        for _model_try in range(5):
            self.model = _resolve_model(self._preferred, api_key, self.timeout)
            url = f"{_BASE}/models/{self.model}:generateContent"
            for wait in (0, 2, 5, 12):  # 429 backoff (free tier is a few req/min)
                if wait:
                    logger.info("rate limited; retrying in %ss", wait)
                    time.sleep(wait)
                resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
                if resp.status_code != 429:
                    break
            if resp.status_code == 404:
                logger.warning("model '%s' returned 404; blacklisting and retrying",
                               self.model)
                _mark_bad(self.model)
                continue
            resp.raise_for_status()
            return resp.json()
        # Exhausted model attempts — surface the last error.
        if resp is not None:
            resp.raise_for_status()
        raise RuntimeError("Gemini request failed: no usable model")

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
