from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NewsPersonStatement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named person's statement found in a news article.

    This is evidence-backed attribution, not a standalone commentator post.
    The source URL always points to the news article that carried the statement.
    """
    __tablename__ = "news_person_statements"

    story_id: Mapped[str] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    person_name_fa: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    role_fa: Mapped[str | None] = mapped_column(String(300))
    statement_fa: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    article_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    direct_quote: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("story_id", "person_name_fa", "source_name", "statement_fa",
                         name="uq_news_person_statement"),
    )
