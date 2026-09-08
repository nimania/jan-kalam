"""Enumerations used across models. Stored as VARCHAR (native_enum=False) so the
same definitions work on SQLite (tests) and Postgres (prod)."""
from __future__ import annotations

import enum


class Category(str, enum.Enum):
    iran = "iran"
    world = "world"
    politics = "politics"
    economy = "economy"
    technology = "technology"
    ai = "ai"
    culture = "culture"


class FeedType(str, enum.Enum):
    rss = "rss"
    atom = "atom"
    json = "json"
    api = "api"


class StoryStatus(str, enum.Enum):
    draft = "draft"          # clustered, not yet AI-processed
    processing = "processing"
    published = "published"
    flagged = "flagged"      # flagged by admin for QC


class StatementKind(str, enum.Enum):
    """The four-layer separation, materialized as rows."""
    fact = "fact"
    uncertainty = "uncertainty"
    agreement = "agreement"
    disagreement = "disagreement"


class EntityType(str, enum.Enum):
    person = "person"
    organization = "organization"
    location = "location"
    event = "event"
    other = "other"


class IranRelevance(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"
    none = "none"  # -> «ارتباط مستقیمی با ایران ندارد.»
