from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class ProviderResult:
    data: dict                      # parsed JSON object (unvalidated)
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    raw: str = field(default="")    # raw text, for debugging failures


class Provider(Protocol):
    name: str

    def generate(self, *, system: str, user: str, context: dict) -> ProviderResult:
        """Return a ProviderResult whose `data` is a JSON object. `context`
        carries the structured articles so offline providers can work without
        an LLM; real providers use the `user` prompt text."""
        ...
