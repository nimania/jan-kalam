from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FigurePost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One commentator's post (جان‌کلام چهره‌ها), classified once.

    kind:
      analysis    — the figure's own view/analysis → shown as «دیدگاه»
      relay       — relays someone else's news → credited to the original source,
                    never shown as the figure's view
      party_claim — the figure is a PARTY to the matter (own case, own dispute) →
                    shown only as «ادعای یکی از طرفین», never as neutral analysis
      chatter     — jokes, personal attacks, small talk → hidden
      promo       — books, workshops, donation, "watch on YouTube" → hidden
    """

    __tablename__ = "figure_posts"

    article_id: Mapped[str] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    topic_fa: Mapped[str | None] = mapped_column(String(200))
    summary_fa: Mapped[str | None] = mapped_column(Text)   # neutral, attributed, short
    relayed_from: Mapped[str | None] = mapped_column(String(200))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    classified_by: Mapped[str] = mapped_column(String(40), default="rule")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shown: Mapped[bool] = mapped_column(Boolean, default=False)  # analysis/party_claim

    article: Mapped["Article"] = relationship()  # noqa: F821
