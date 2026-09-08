"""Recompute importance, Iran relevance, and category for stories, from their
clustered articles. Scores are stored on the story (never recomputed on read)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger
from app.models.enums import IranRelevance, StoryStatus
from app.models.source import Source
from app.models.story import Story, StoryArticle
from app.ranking.importance import (
    count_iran_hits,
    iran_relevance_label,
    score_importance,
)

logger = get_logger("ranking")


def rank_stories(db: Session) -> dict:
    stories = db.execute(
        select(Story)
        .where(Story.status.in_([StoryStatus.draft, StoryStatus.published]))
        .options(selectinload(Story.article_links).selectinload(StoryArticle.article))
    ).scalars().unique().all()

    reliabilities = {
        s.id: s.reliability_score for s in db.execute(select(Source)).scalars().all()
    }
    now = datetime.now(timezone.utc)
    ranked = 0

    for st in stories:
        articles = [l.article for l in st.article_links if l.article]
        if not articles:
            continue
        source_ids = {a.source_id for a in articles}
        rels = [reliabilities.get(a.source_id, 0.5) for a in articles]
        avg_rel = sum(rels) / len(rels) if rels else 0.5
        times = [a.published_at for a in articles if a.published_at]
        latest = max(times) if times else None
        if latest is not None and latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)  # SQLite returns naive
        hours_since = (now - latest).total_seconds() / 3600.0 if latest else None
        iran_hits = count_iran_hits(*[a.title for a in articles],
                                    *[a.description for a in articles])

        breakdown = score_importance(
            distinct_sources=len(source_ids),
            article_count=len(articles),
            avg_reliability=avg_rel,
            hours_since_latest=hours_since,
            iran_hits=iran_hits,
        )
        st.importance_score = breakdown.total
        st.source_count = len(source_ids)
        st.iran_relevance = IranRelevance(iran_relevance_label(iran_hits))

        cats = Counter(a.category for a in articles if a.category)
        if cats:
            st.category = cats.most_common(1)[0][0]
        if latest:
            st.event_time = latest
        ranked += 1

    db.commit()
    logger.info("ranked %d stories", ranked)
    return {"ranked": ranked}
