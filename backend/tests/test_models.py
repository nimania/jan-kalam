import pytest
from sqlalchemy.exc import IntegrityError

from app.models.article import Article
from app.models.source import Source
from tests.conftest import make_published_story, make_source


def test_source_name_unique(db):
    make_source(db, name="BBC")
    with pytest.raises(IntegrityError):
        db.add(Source(name="BBC", feed_url="https://x.test/f"))
        db.commit()


def test_article_hash_unique(db):
    src = make_source(db, name="AP")
    db.add(
        Article(
            source_id=src.id, source_name=src.name,
            article_url="https://x.test/1", title="t", hash="dup",
        )
    )
    db.commit()
    with pytest.raises(IntegrityError):
        db.add(
            Article(
                source_id=src.id, source_name=src.name,
                article_url="https://x.test/2", title="t2", hash="dup",
            )
        )
        db.commit()


def test_story_cascades_children(db):
    story = make_published_story(db, importance=0.5)
    assert len(story.article_links) == 1
    assert len(story.source_views) == 1
    assert len(story.statements) == 2
    # Deleting the story removes its child rows (cascade).
    from app.models.story import SourceView, Statement, StoryArticle

    db.delete(story)
    db.commit()
    assert db.query(StoryArticle).count() == 0
    assert db.query(SourceView).count() == 0
    assert db.query(Statement).count() == 0
