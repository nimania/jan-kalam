from __future__ import annotations

from sqlalchemy import Boolean, Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Category, FeedType


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A configured news source. Sources are DATA, not code — usage rules per
    source live here so extraction behavior can vary without code changes."""

    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    homepage_url: Mapped[str | None] = mapped_column(String(500))
    feed_url: Mapped[str] = mapped_column(String(500), nullable=False)
    feed_type: Mapped[FeedType] = mapped_column(
        Enum(FeedType, native_enum=False, length=16), default=FeedType.rss
    )
    default_category: Mapped[Category | None] = mapped_column(
        Enum(Category, native_enum=False, length=16)
    )
    language: Mapped[str] = mapped_column(String(8), default="en")
    region: Mapped[str | None] = mapped_column(String(64))  # global/us/mena/tech...

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Explainable input to importance ranking; not a political label.
    reliability_score: Mapped[float] = mapped_column(Float, default=0.5)

    # --- Copyright / usage policy (configuration, per source) ---
    allow_full_content: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_image: Mapped[bool] = mapped_column(Boolean, default=False)
    attribution_required: Mapped[bool] = mapped_column(Boolean, default=True)
    usage_notes: Mapped[str | None] = mapped_column(Text)

    articles: Mapped[list["Article"]] = relationship(  # noqa: F821
        back_populates="source", cascade="all, delete-orphan"
    )
