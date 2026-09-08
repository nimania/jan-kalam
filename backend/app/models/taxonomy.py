from __future__ import annotations

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import EntityType


class Topic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A followable subject (Iran, AI, Bitcoin, Russia-Ukraine, ...)."""

    __tablename__ = "topics"

    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(200))

    story_links: Mapped[list["StoryTopic"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    followers: Mapped[list["UserFollow"]] = relationship(  # noqa: F821
        back_populates="topic", cascade="all, delete-orphan"
    )


class StoryTopic(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "story_topics"

    story_id: Mapped[str] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )

    story: Mapped["Story"] = relationship(back_populates="topic_links")  # noqa: F821
    topic: Mapped["Topic"] = relationship(back_populates="story_links")

    __table_args__ = (
        UniqueConstraint("story_id", "topic_id", name="uq_story_topic"),
    )


class Entity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named entity extracted from articles (person, org, location, event)."""

    __tablename__ = "entities"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, native_enum=False, length=16), default=EntityType.other
    )

    __table_args__ = (
        UniqueConstraint("name", "type", name="uq_entity_name_type"),
    )
