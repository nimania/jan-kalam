from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.taxonomy import Topic
from app.models.user import UserFollow


def list_all(db: Session) -> list[Topic]:
    return list(db.execute(select(Topic).order_by(Topic.slug)).scalars().all())


def get(db: Session, topic_id: str) -> Topic | None:
    return db.get(Topic, topic_id)


def get_by_slug(db: Session, slug: str) -> Topic | None:
    return db.execute(
        select(Topic).where(Topic.slug == slug)
    ).scalars().one_or_none()


def get_follow(db: Session, user_id: str, topic_id: str) -> UserFollow | None:
    return db.execute(
        select(UserFollow).where(
            UserFollow.user_id == user_id, UserFollow.topic_id == topic_id
        )
    ).scalars().one_or_none()
