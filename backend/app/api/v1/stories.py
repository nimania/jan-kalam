from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import Category
from app.repositories import stories as repo
from app.schemas.story import AskAnswer, AskRequest, StoryDetail, StoryFeed
from app.services import ask as ask_service
from app.services import stories as service

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get("", response_model=StoryFeed)
def list_stories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category: Category | None = None,
    db: Session = Depends(get_db),
) -> StoryFeed:
    """Home feed — published stories ranked by importance, not chronology."""
    return service.get_feed(db, limit=limit, offset=offset, category=category)


@router.get("/{story_id}", response_model=StoryDetail)
def get_story(story_id: str, db: Session = Depends(get_db)) -> StoryDetail:
    detail = service.get_detail(db, story_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="story_not_found")
    return detail


@router.post("/{story_id}/ask", response_model=AskAnswer)
def ask_story(
    story_id: str, payload: AskRequest, db: Session = Depends(get_db)
) -> AskAnswer:
    story = repo.get(db, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story_not_found")
    if not payload.question.strip():
        raise HTTPException(status_code=422, detail="empty_question")
    return ask_service.answer(story, payload.question.strip())
