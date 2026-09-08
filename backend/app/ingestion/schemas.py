from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class NormalizedItem:
    """A source-agnostic, normalized article ready to persist."""
    title: str
    article_url: str
    description: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    language: str | None = None
    image_url: str | None = None       # only kept if the source permits images
    raw_content: str | None = None     # only kept if the source permits full text
