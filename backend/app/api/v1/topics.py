from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_or_create_user
from app.db.session import get_db
from app.models.user import User, UserFollow
from app.repositories import topics as repo
from app.schemas.topic import FollowResult, TopicOut

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicOut])
def list_topics(db: Session = Depends(get_db)) -> list[TopicOut]:
    return [TopicOut.model_validate(t) for t in repo.list_all(db)]


@router.get("/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: str, db: Session = Depends(get_db)) -> TopicOut:
    topic = repo.get(db, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="topic_not_found")
    return TopicOut.model_validate(topic)


@router.post("/{topic_id}/follow", response_model=FollowResult)
def follow_topic(
    topic_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_user),
) -> FollowResult:
    if repo.get(db, topic_id) is None:
        raise HTTPException(status_code=404, detail="topic_not_found")
    existing = repo.get_follow(db, user.id, topic_id)
    if existing is None:
        db.add(UserFollow(user_id=user.id, topic_id=topic_id))
        db.commit()
    return FollowResult(topic_id=topic_id, following=True)


@router.delete("/{topic_id}/follow", response_model=FollowResult)
def unfollow_topic(
    topic_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_user),
) -> FollowResult:
    existing = repo.get_follow(db, user.id, topic_id)
    if existing is not None:
        db.delete(existing)
        db.commit()
    return FollowResult(topic_id=topic_id, following=False)
