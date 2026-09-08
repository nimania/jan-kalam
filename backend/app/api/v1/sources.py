from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import sources as repo
from app.schemas.source import SourceOut

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(
    enabled_only: bool = False, db: Session = Depends(get_db)
) -> list[SourceOut]:
    return [SourceOut.model_validate(s) for s in repo.list_all(db, enabled_only=enabled_only)]
