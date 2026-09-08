from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Category, IranRelevance, StatementKind, StoryStatus


class Story(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A clustered news event with cached AI output. The four layers
    (fact / source view / synthesis / uncertainty) are materialized on the story
    and its child rows and computed ONCE, then served from the DB."""

    __tablename__ = "stories"

    # --- Persian synthesis (the "Jan Kalam") ---
    headline_fa: Mapped[str | None] = mapped_column(String(500))
    summary_fa: Mapped[str | None] = mapped_column(Text)        # 80–150 words
    what_happened_fa: Mapped[str | None] = mapped_column(Text)
    why_it_matters_fa: Mapped[str | None] = mapped_column(Text)

    category: Mapped[Category | None] = mapped_column(
        Enum(Category, native_enum=False, length=16), index=True
    )
    status: Mapped[StoryStatus] = mapped_column(
        Enum(StoryStatus, native_enum=False, length=16),
        default=StoryStatus.draft,
        index=True,
    )
    iran_relevance: Mapped[IranRelevance] = mapped_column(
        Enum(IranRelevance, native_enum=False, length=8), default=IranRelevance.none
    )

    # Explainable scores (see ranking module). Stored, not recomputed on read.
    importance_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)

    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Children
    article_links: Mapped[list["StoryArticle"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    source_views: Mapped[list["SourceView"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    statements: Mapped[list["Statement"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    topic_links: Mapped[list["StoryTopic"]] = relationship(  # noqa: F821
        back_populates="story", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_stories_feed_order", "status", "importance_score"),
    )


class StoryArticle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """M:N link: which articles form a story, with a clustering relevance weight."""

    __tablename__ = "story_articles"

    story_id: Mapped[str] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id: Mapped[str] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relevance: Mapped[float] = mapped_column(Float, default=1.0)
    is_primary: Mapped[bool] = mapped_column(default=False)

    story: Mapped["Story"] = relationship(back_populates="article_links")
    article: Mapped["Article"] = relationship(back_populates="story_links")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("story_id", "article_id", name="uq_story_article"),
    )


class SourceView(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """What one publication says about the story — kept separate from FACT."""

    __tablename__ = "source_views"

    story_id: Mapped[str] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    original_headline: Mapped[str | None] = mapped_column(String(1000))
    article_url: Mapped[str | None] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    viewpoint_fa: Mapped[str | None] = mapped_column(Text)

    story: Mapped["Story"] = relationship(back_populates="source_views")


class Statement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single fact / uncertainty / agreement / disagreement line for a story.
    `kind` enforces the four-layer separation at the data level."""

    __tablename__ = "statements"

    story_id: Mapped[str] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[StatementKind] = mapped_column(
        Enum(StatementKind, native_enum=False, length=16), nullable=False, index=True
    )
    text_fa: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    story: Mapped["Story"] = relationship(back_populates="statements")
