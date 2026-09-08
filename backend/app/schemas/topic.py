from __future__ import annotations

from app.schemas.common import ORMModel


class TopicOut(ORMModel):
    id: str
    slug: str
    name_fa: str
    name_en: str | None = None


class TopicCreate(ORMModel):
    slug: str
    name_fa: str
    name_en: str | None = None


class FollowResult(ORMModel):
    topic_id: str
    following: bool
