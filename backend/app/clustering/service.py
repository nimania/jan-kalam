"""Cluster articles into stories: one event → one story with many sources.

Greedy incremental clustering. Each still-unclustered article joins the most
similar existing draft story if similarity clears the threshold, otherwise it
seeds a new story. Re-running only processes newly unclustered articles, so it
is safe to call on a schedule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.clustering.similarity import score, tokenize
from app.core.logging import get_logger
from app.models.article import Article
from app.models.enums import StoryStatus
from app.models.story import Story, StoryArticle

logger = get_logger("clustering")


@dataclass
class _Cluster:
    story: Story
    tokens: set[str]
    latest_time: datetime | None
    source_ids: set[str] = field(default_factory=set)


def _load_open_clusters(db: Session) -> list[_Cluster]:
    stories = db.execute(
        select(Story)
        .where(Story.status == StoryStatus.draft)
        .options(selectinload(Story.article_links).selectinload(StoryArticle.article))
    ).scalars().unique().all()
    clusters: list[_Cluster] = []
    for st in stories:
        tokens: set[str] = set()
        latest: datetime | None = None
        sources: set[str] = set()
        for link in st.article_links:
            a = link.article
            if not a:
                continue
            tokens |= tokenize(a.title, a.description)
            sources.add(a.source_id)
            if a.published_at and (latest is None or a.published_at > latest):
                latest = a.published_at
        clusters.append(_Cluster(story=st, tokens=tokens, latest_time=latest, source_ids=sources))
    return clusters


def cluster_articles(
    db: Session, *, threshold: float = 0.30, window_hours: float = 72.0
) -> dict:
    """Assign every unclustered article to a story. Returns a summary."""
    clustered_ids = {row[0] for row in db.execute(select(StoryArticle.article_id)).all()}
    articles = db.execute(
        select(Article).order_by(Article.published_at.asc().nullslast())
    ).scalars().all()
    pending = [a for a in articles if a.id not in clustered_ids]

    clusters = _load_open_clusters(db)
    new_stories = 0
    attached = 0

    for art in pending:
        a_tokens = tokenize(art.title, art.description)
        best: _Cluster | None = None
        best_score = 0.0
        for c in clusters:
            s = score(a_tokens, c.tokens, art.published_at, c.latest_time, window_hours=window_hours)
            if s > best_score:
                best, best_score = c, s

        if best is not None and best_score >= threshold:
            db.add(StoryArticle(story_id=best.story.id, article_id=art.id))
            best.tokens |= a_tokens
            best.source_ids.add(art.source_id)
            if art.published_at and (best.latest_time is None or art.published_at > best.latest_time):
                best.latest_time = art.published_at
            best.story.source_count = len(best.source_ids)
            attached += 1
        else:
            story = Story(
                status=StoryStatus.draft,
                category=art.category,
                event_time=art.published_at,
                source_count=1,
            )
            db.add(story)
            db.flush()
            db.add(StoryArticle(story_id=story.id, article_id=art.id, is_primary=True))
            clusters.append(
                _Cluster(story=story, tokens=set(a_tokens),
                         latest_time=art.published_at, source_ids={art.source_id})
            )
            new_stories += 1

    db.commit()
    summary = {
        "pending": len(pending),
        "new_stories": new_stories,
        "attached_to_existing": attached,
        "open_clusters": len(clusters),
    }
    logger.info("clustering: %s", summary)
    return summary
