"""Provider factory. Picks the real provider only when a key is configured;
otherwise the deterministic mock keeps the pipeline runnable offline."""
from __future__ import annotations

from app.ai.providers.base import Provider, ProviderResult
from app.ai.providers.mock import MockProvider
from app.core.config import settings


def get_provider() -> Provider:
    if settings.ai_api_key:
        if settings.ai_provider == "anthropic":
            from app.ai.providers.anthropic import AnthropicProvider

            return AnthropicProvider()
        if settings.ai_provider == "gemini":
            from app.ai.providers.gemini import GeminiProvider

            return GeminiProvider()
    # "openai" can be added the same way behind this factory.
    return MockProvider()


__all__ = ["Provider", "ProviderResult", "MockProvider", "get_provider"]
