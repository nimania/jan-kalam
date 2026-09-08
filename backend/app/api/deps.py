"""Shared FastAPI dependencies.

MVP identity model: a lightweight user resolved from an `X-User-Id` header
(a device id, for anonymous following). Real auth arrives in Phase 4; this keeps
the follow endpoints working now without over-building.
"""
from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User

DEFAULT_DEVICE = "anonymous-device"


def get_or_create_user(
    db: Session = Depends(get_db),
    x_user_id: str = Header(default=DEFAULT_DEVICE),
) -> User:
    email = f"{x_user_id}@device.jankalam.local"
    user = db.execute(select(User).where(User.email == email)).scalars().one_or_none()
    if user is None:
        user = User(email=email, display_name=x_user_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
