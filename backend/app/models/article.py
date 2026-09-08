from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Category


class Article(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single normalized item from a source feed. We store metadata, an
    excerpt/description, and a link — never a full copyrighted article unless the
    source's policy explicitly permits it."""

    __tablename__ = "articles"

    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalized for fast feed rendering / attribution.
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))

    article_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)  # excerpt only
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    author: Mapped[str | None] = mapped_column(String(300))
    language: Mapped[str] = mapped_column(String(8), default="en")
    category: Mapped[Category | None] = mapped_column(
        Enum(Category, native_enum=False, length=16)
    )

    # Populated only when Source.allow_full_content / allow_image is true.
    raw_content_if_permitted: Mapped[str | None] = mapped_column(Text)
    image_url_if_permitted: Mapped[str | None] = mapped_column(String(1000))

    # Content hash for deduplication (Phase 2). Unique to reject exact dupes.
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    source: Mapped["Source"] = relationship(back_populates="articles")  # noqa: F821
    story_links: Mapped[list["StoryArticle"]] = relationship(  # noqa: F821
        back_populates="article", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_articles_source_published", "source_id", "published_at"),
    )
