from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UsageLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One record per AI call — tokens, model, cost, latency (§24)."""

    __tablename__ = "usage_logs"

    story_id: Mapped[str | None] = mapped_column(
        ForeignKey("stories.id", ondelete="SET NULL"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32), default="synthesis")
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    model: Mapped[str] = mapped_column(String(120), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="ok")  # ok|validation_error|provider_error
    message: Mapped[str | None] = mapped_column(Text)
