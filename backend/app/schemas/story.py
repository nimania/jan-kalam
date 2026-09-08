from __future__ import annotations

from datetime import datetime

from app.models.enums import Category, IranRelevance, StatementKind, StoryStatus
from app.schemas.common import ORMModel, Page


class SourceRef(ORMModel):
    """A source citation for a story — name, original headline, time, link.
    Never the full article."""
    source_name: str
    original_headline: str | None = None
    article_url: str | None = None
    published_at: datetime | None = None


class SourceViewOut(SourceRef):
    id: str
    viewpoint_fa: str | None = None


class StatementOut(ORMModel):
    kind: StatementKind
    text_fa: str
    confidence: float


class TopicRef(ORMModel):
    id: str
    slug: str
    name_fa: str


class StoryCard(ORMModel):
    """Compact representation for the home feed."""
    id: str
    headline_fa: str | None = None
    summary_fa: str | None = None
    category: Category | None = None
    status: StoryStatus
    iran_relevance: IranRelevance
    importance_score: float
    source_count: int
    published_at: datetime | None = None
    source_names: list[str] = []


class StoryDetail(StoryCard):
    """Full story page — the four layers kept explicitly separate."""
    what_happened_fa: str | None = None
    why_it_matters_fa: str | None = None
    confidence_score: float
    facts: list[str] = []          # known / supported
    uncertainties: list[str] = []  # unknown / disputed
    agreements: list[str] = []
    disagreements: list[str] = []
    source_views: list[SourceViewOut] = []
    sources: list[SourceRef] = []
    topics: list[TopicRef] = []


class StoryFeed(Page):
    items: list[StoryCard]


# --- Ask feature ---
class AskRequest(ORMModel):
    question: str


class AskAnswer(ORMModel):
    story_id: str
    question: str
    answer_fa: str
    # Honest signalling of what powered the answer.
    used_facts: list[str] = []
    inferred: bool = False
    ai_available: bool = False
    note: str | None = None
