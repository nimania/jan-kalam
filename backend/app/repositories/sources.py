from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.source import Source


def list_all(db: Session, *, enabled_only: bool = False) -> list[Source]:
    stmt = select(Source).order_by(Source.name)
    if enabled_only:
        stmt = stmt.where(Source.enabled.is_(True))
    return list(db.execute(stmt).scalars().all())


def get(db: Session, source_id: str) -> Source | None:
    return db.get(Source, source_id)


def get_by_name(db: Session, name: str) -> Source | None:
    return db.execute(
        select(Source).where(Source.name == name)
    ).scalars().one_or_none()


def create(db: Session, source: Source) -> Source:
    db.add(source)
    db.commit()
    db.refresh(source)
    return source
