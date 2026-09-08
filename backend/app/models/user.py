from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    # Auth is Phase 4+; kept nullable so anonymous/device users work for MVP.
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    follows: Mapped[list["UserFollow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserFollow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_follows"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user: Mapped["User"] = relationship(back_populates="follows")
    topic: Mapped["Topic"] = relationship(back_populates="followers")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_user_topic"),
    )
