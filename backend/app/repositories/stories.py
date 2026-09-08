"""Data-access for stories. No business logic here — just queries."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import Category, StoryStatus
from app.models.story import Story


def _detail_options():
    return (
        selectinload(Story.source_views),
        selectinload(Story.statements),
        selectinload(Story.article_links),
        selectinload(Story.topic_links),
    )


def list_published(
    db: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    category: Category | None = None,
) -> tuple[list[Story], int]:
    stmt = select(Story).where(Story.status == StoryStatus.published)
    if category is not None:
        stmt = stmt.where(Story.category == category)

    total = len(db.execute(stmt).scalars().all())
    stmt = (
        stmt.order_by(Story.importance_score.desc(), Story.published_at.desc())
        .limit(limit)
        .offset(offset)
        .options(*_detail_options())
    )
    return list(db.execute(stmt).scalars().unique().all()), total


def get(db: Session, story_id: str) -> Story | None:
    stmt = select(Story).where(Story.id == story_id).options(*_detail_options())
    return db.execute(stmt).scalars().unique().one_or_none()
