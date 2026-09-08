from __future__ import annotations

from app.models.enums import Category, FeedType
from app.schemas.common import ORMModel


class SourceOut(ORMModel):
    id: str
    name: str
    homepage_url: str | None = None
    feed_type: FeedType
    default_category: Category | None = None
    language: str
    region: str | None = None
    enabled: bool
    reliability_score: float
    allow_full_content: bool
    allow_image: bool
    attribution_required: bool


class SourceCreate(ORMModel):
    name: str
    feed_url: str
    homepage_url: str | None = None
    feed_type: FeedType = FeedType.rss
    default_category: Category | None = None
    language: str = "en"
    region: str | None = None
    enabled: bool = True
    reliability_score: float = 0.5
    allow_full_content: bool = False
    allow_image: bool = False
    attribution_required: bool = True
    usage_notes: str | None = None


class SourceUpdate(ORMModel):
    enabled: bool | None = None
    reliability_score: float | None = None
    default_category: Category | None = None
    allow_full_content: bool | None = None
    allow_image: bool | None = None
    usage_notes: str | None = None
