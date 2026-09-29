from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class FigureAsset(UUIDPrimaryKeyMixin, Base):
    """Cached profile picture for a figure's channel (جان‌کلام چهره‌ها).

    Downloaded once (and refreshed weekly) during the build, which runs OUTSIDE
    Iran and can reach Telegram; the bytes are then written into the static site
    so they load for everyone, including inside Iran where t.me is filtered.

    Stored in the (cached) build DB so it isn't re-downloaded every 15 minutes.
    """

    __tablename__ = "figure_assets"

    handle: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    ext: Mapped[str] = mapped_column(String(8), default="jpg")
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
