from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app
import app.models  # noqa: F401  (register tables)
from app.models.article import Article
from app.models.enums import Category, IranRelevance, StatementKind, StoryStatus
from app.models.source import Source
from app.models.story import SourceView, Statement, Story, StoryArticle
from app.models.taxonomy import Topic


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory connection
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def SessionFactory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db(SessionFactory):
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(SessionFactory):
    def _override():
        s = SessionFactory()
        try:
            yield s
        finally:
            s.close()

    fastapi_app.dependency_overrides[get_db] = _override
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# --- Seed helpers ---------------------------------------------------------
def make_source(db, name="Reuters", reliability=0.9) -> Source:
    s = Source(
        name=name,
        homepage_url="https://example.test",
        feed_url=f"https://example.test/{name.lower()}.rss",
        region="global",
        reliability_score=reliability,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def make_published_story(db, importance=0.7, headline="خبر آزمایشی") -> Story:
    src = make_source(db, name=f"Reuters-{importance}")
    story = Story(
        headline_fa=headline,
        summary_fa="خلاصهٔ فارسی برای آزمون.",
        what_happened_fa="چه شد.",
        why_it_matters_fa="چرا مهم است.",
        category=Category.economy,
        status=StoryStatus.published,
        iran_relevance=IranRelevance.medium,
        importance_score=importance,
        confidence_score=0.6,
        source_count=1,
        published_at=datetime.now(timezone.utc),
    )
    db.add(story)
    db.flush()
    article = Article(
        source_id=src.id,
        source_name=src.name,
        article_url=f"https://example.test/a-{importance}",
        title="Original English headline",
        hash=f"hash-{importance}",
        published_at=datetime.now(timezone.utc),
    )
    db.add(article)
    db.flush()
    db.add(StoryArticle(story_id=story.id, article_id=article.id, is_primary=True))
    db.add(
        SourceView(
            story_id=story.id,
            source_id=src.id,
            source_name=src.name,
            original_headline="Original English headline",
            article_url=article.article_url,
            viewpoint_fa="این منبع بر اصل رویداد تأکید دارد.",
        )
    )
    db.add_all(
        [
            Statement(story_id=story.id, kind=StatementKind.fact, text_fa="این قطعی است."),
            Statement(
                story_id=story.id,
                kind=StatementKind.uncertainty,
                text_fa="این هنوز نامشخص است.",
            ),
        ]
    )
    db.commit()
    db.refresh(story)
    return story


def make_topic(db, slug="iran", name_fa="ایران") -> Topic:
    t = Topic(slug=slug, name_fa=name_fa, name_en="Iran")
    db.add(t)
    db.commit()
    db.refresh(t)
    return t
