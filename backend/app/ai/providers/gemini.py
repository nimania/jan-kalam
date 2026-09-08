"""Real provider using the Google Gemini API.

Used when settings.ai_provider == "gemini" and a key is set. Gemini can be told
to return JSON directly (response_mime_type), which makes parsing clean. The key
lives server-side only. Not exercised by the offline test suite.

Two robustness features:
  • Self-healing model selection — Google returns 404 when the configured model
    name isn't valid for this key/version ("Call ListModels…"). So we ask the key
    which models it supports for generateContent and pick the best; if a chosen
    model still 404s we blacklist it and fall through to the next best.
  • Multi-key rotation — AI_API_KEY may hold SEVERAL keys (comma / whitespace /
    newline separated). Each free key has its own quota, so on a 429 (rate/quota)
    we rotate to the next key. This multiplies sustainable throughput on the free
    tier without any paid billing.
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
_key_idx: int = 0


def _keys() -> list[str]:
    """Parse AI_API_KEY into one or more keys (comma / whitespace separated)."""
    raw = settings.ai_api_key or ""
    keys = [k.strip() for k in re.split(r"[,\s]+", raw) if k.strip()]
    return keys or [""]


def _current_key(keys: list[str]) -> str:
    return keys[_key_idx % len(keys)]


def _rotate_key(keys: list[str]) -> None:
    global _key_idx
    _key_idx = (_key_idx + 1) % len(keys)


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
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }

        body = self._call(payload)

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

    def _call(self, payload: dict) -> dict:
        """Resolve a model and POST generateContent, with self-healing:
          • 404  → blacklist the model and try the next best,
          • 429  → rotate to the next API key (or back off if only one key),
          • 200  → done. Correct URL includes '/models/'."""
        keys = _keys()
        n_keys = len(keys)
        attempts = max(6, n_keys + 3)
        resp = None
        for i in range(attempts):
            key = _current_key(keys)
            model = _resolve_model(self._preferred, key, self.timeout)
            self.model = model
            url = f"{_BASE}/models/{model}:generateContent"
            headers = {"x-goog-api-key": key, "content-type": "application/json"}
            resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
            code = resp.status_code
            if code == 200:
                return resp.json()
            if code == 404:
                logger.warning("model '%s' returned 404; blacklisting", model)
                _mark_bad(model)
                continue
            if code == 429:
                if n_keys > 1:
                    logger.info("key #%d rate-limited; rotating key", _key_idx + 1)
                    _rotate_key(keys)
                else:
                    wait = min(2 * (i + 1), 12)
                    logger.info("rate limited; backing off %ss", wait)
                    time.sleep(wait)
                continue
            resp.raise_for_status()  # other errors: surface immediately
        if resp is not None:
            resp.raise_for_status()
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
